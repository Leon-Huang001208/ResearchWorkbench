"""Host integration only: native DSH owns all execution and conversation history."""

import hashlib
import json
from uuid import uuid4

from core.observability import get_logger

from ..projection import content_text, project
from ..store import StoreError
from .contracts import Budget, NodeResult, SpecialistError
from .ledger import SpecialistLedger
from .registry import catalog

log = get_logger(__name__)


def ledger(service):
    value = getattr(service, "specialist_ledger", None)
    if value is None:
        value = service.specialist_ledger = SpecialistLedger(service.store)
    return value


def validate_send(service, sid, mode, budget):
    """No mode switch may silently escape an unresolved specialist run."""
    current = ledger(service).read(sid)
    if mode == "specialist":
        if service.store.session(sid)["mode"] != "fingpt":
            raise SpecialistError("专业协作仅用于研究会话")
        if budget is None:
            raise SpecialistError("请明确确认本次协作预算", "specialist_budget_unconfirmed")
        return Budget.model_validate(budget).model_dump()
    if budget is not None:
        raise SpecialistError("普通研究不能附带协作预算")
    if current and not current.get("finalization_ready"):
        raise SpecialistError("协作任务尚未结束，请先核对或明确续跑", "specialist_unresolved", 409)
    return None


def prepare(service, sid, key, budget, contract):
    row = service.store.session(sid)
    skills = {}
    for slug in sorted({skill for role in catalog()["roles"].values() for skill in role["skills"]}):
        selection = service.capabilities.selection(slug)
        service.capabilities.snapshot(selection, service.store.directory(sid))
        record = service.capabilities.row(slug)["versions"][str(selection["version"])]
        manifest = {
            "SKILL.md": record["compiled_sha256"],
            **{entry["path"]: entry["sha256"] for entry in record["files"]},
        }
        skills[slug] = {
            key: selection[key]
            for key in ("id", "version", "kind", "native_name", "sha256", "resource_path")
        }
        skills[slug]["resource_snapshot_sha256"] = hashlib.sha256(
            json.dumps(manifest, sort_keys=True).encode()
        ).hexdigest()
    state = ledger(service).create(
        sid,
        budget,
        contract["as_of"],
        {name: row.get(name) for name in ("model_provider", "model", "model_profile_id")},
        key,
        skills=skills,
    )
    receipt = service.store.receipt(sid, key)
    receipt["specialist_run_id"] = state["id"]
    service.store.save()
    return (
        "\n专业协作执行合同：你是 Orchestrator，DSH 是唯一执行引擎。"
        "先用 specialist_plan 提交动态 DAG，再用 specialist_run 调度已准入节点；"
        "用 specialist_status 核对真实状态。禁止直接 subagent 或 rwb_plugin_agent 绕过节点准入。"
        "计划必须有 industry、quant、review；行业和量化可以并行，独立 review 依赖两者成果。"
        "计划节点使用 id、role、input、depends_on、skills，expected_version 从实际状态读取。"
        "只使用已发布角色；补充研究创建新尝试并明确引用成果，不继续旧子对话。"
        "子节点最终只返回 JSON：conclusion、evidence_ids、as_of_date、limitations、artifact_ids。"
        "Quant 只承诺可复算的描述性分析；预测、策略回测须另行准入。"
        "缺商业授权时仅用已批准公开来源，记录来源变化、覆盖和可比性。"
        "固定研究截止时间，分别记录公开时间和实际获取时间，不借用截止后披露或未选入的跨任务记忆。"
        "预算不足、取消未知或节点失败时保留部分成果，不得宣布正式定稿。"
        "角色、预算及截止以 Host 状态为准："
        + json.dumps(
            {"run_id": state["id"], "as_of": contract["as_of"], "budget": budget},
            ensure_ascii=False,
        )
    )


def cancel_requested(service, sid):
    if ledger(service).read(sid) is not None:
        ledger(service).apply(sid, "cancel", {}, agent_id=sid, call_id=f"host-cancel:{uuid4().hex}")


def _native_end(events):
    ends = [item["event"] for item in events if item.get("event", {}).get("type") == "turn/end"]
    return max(ends, key=lambda item: item["seq"]) if ends else None


def _reconcile_usage(service, sid, events, actor):
    state = ledger(service).read(sid)
    for item in events:
        event = item.get("event", {})
        if event.get("type") != "assistant/message":
            continue
        data = event.get("data", {})
        usage = data.get("usage") or {}
        counts = (usage.get("inputTokens"), usage.get("outputTokens"))
        if not all(type(value) is int and value >= 0 for value in counts):
            continue
        matches = [
            request
            for request in state["model_requests"].values()
            if request["agent_id"] == actor
            and request.get("turn") == data.get("turn")
            and request.get("step") == data.get("step")
            and request["usage"] is None
        ]
        if len(matches) != 1:
            continue
        ledger(service).apply(
            sid,
            "model_usage",
            {
                "request_id": matches[0]["request_id"],
                "input_tokens": counts[0],
                "output_tokens": counts[1],
            },
            agent_id=actor,
            call_id=f"usage-history:{actor}:{event['seq']}",
        )


def validate_result_references(service, sid, result):
    """Existence is required; evidence correctness remains the original quality gate."""
    parsed = NodeResult.model_validate(result).model_dump()
    files = service.store.files(sid)
    file_ids = {item["id"] for item in files}
    from ..research_evidence import evidence_index
    from ..research_web_sources import stored_sources, upload_evidence_files

    native = list(service.events.get(sid, {}).values())
    sources = evidence_index(
        upload_evidence_files(service.store, sid, files),
        service.datahub.summaries(sid),
        project(native)["activities"],
    )
    sources.extend(stored_sources(service.store, sid))
    source_ids = {
        row["id"]
        for row in sources
        if row.get("state") == "available"
        and row.get("admission", {}).get("report_admitted") is not False
    }
    if not set(parsed["artifact_ids"]) <= file_ids or not set(parsed["evidence_ids"]) <= source_ids:
        raise SpecialistError(
            "节点引用不属于当前研究的真实证据或产物", "specialist_evidence_unbound", 409
        )
    return parsed


async def qualify_terminal(service, sid, payload):
    """Only actual native Skill reads and current evidence bytes qualify results."""
    from .evidence import evidence_snapshot

    state = ledger(service).read(sid)
    attempt = state["attempts"].get(payload["attempt_id"])
    if attempt is None or attempt["child_id"] != payload["child_id"]:
        raise SpecialistError("终态子身份不匹配", "specialist_actor_denied", 403)
    node = next(
        (
            node
            for plan in [state["active_plan"], *state["plan_history"]]
            for node in plan["nodes"]
            if node["id"] == attempt["node_id"] and plan["version"] == attempt["plan_version"]
        ),
        None,
    )
    if node is None:
        raise SpecialistError("节点固定计划缺失")
    slugs = node["skills"] or state["registry"]["roles"][node["role"]]["skills"]
    expected = {state["skills"][slug]["native_name"] for slug in slugs}
    page = await service.client.rpc(
        "subagent.history",
        {
            "parentSessionId": sid,
            "childSessionId": attempt["child_id"],
            "mode": "continuable",
            "maxMessages": 1000,
        },
    )
    if page.get("hasMore"):
        raise SpecialistError("原生方法读取历史不完整", "specialist_skill_unverified", 409)
    activities = project(page["events"])["activities"]
    loaded = {
        row.get("arguments", {}).get("name")
        for row in activities
        if row.get("title") == "skill"
        and row.get("status") == "completed"
        and isinstance(row.get("arguments"), dict)
    }
    if not expected <= loaded:
        raise SpecialistError("专业方法缺少实际读取证据", "specialist_skill_unverified", 409)
    payload["result"] = validate_result_references(service, sid, payload["result"])
    payload["evidence_snapshot"] = evidence_snapshot(service, sid, payload["result"])
    return payload


async def verify_cached(service, sid):
    from .evidence import verify_snapshots

    state = ledger(service).read(sid)
    if state is None:
        return
    for frozen in state.get("skills", {}).values():
        record = service.capabilities.row(frozen["id"])["versions"][str(frozen["version"])]
        manifest = {
            "SKILL.md": record["compiled_sha256"],
            **{entry["path"]: entry["sha256"] for entry in record["files"]},
        }
        if (
            record["compiled_sha256"] != frozen["sha256"]
            or hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
            != frozen["resource_snapshot_sha256"]
        ):
            raise SpecialistError("专业方法版本已改变", "specialist_skill_changed", 409)
        service.capabilities.snapshot(
            {**frozen, "bindings": record["bindings"]}, service.store.directory(sid)
        )
    changed = verify_snapshots(service, sid, state)
    if not changed:
        return
    state = ledger(service).invalidate_evidence(sid, changed)
    for attempt_id in state["operation_result"].get("cancel_attempt_ids", []):
        attempt = state["attempts"][attempt_id]
        await service.client.rpc(
            "subagent.interrupt",
            {"parentSessionId": sid, "childSessionId": attempt["child_id"], "mode": "continuable"},
        )


async def reconcile(service, sid):
    """Observe owned native child history; never submit or resume a model request."""
    state = ledger(service).read(sid)
    if state is None:
        return None
    from ..client import RuntimeFailure

    try:
        _reconcile_usage(service, sid, list(service.events.get(sid, {}).values()), sid)
        catalog = await service.client.rpc("subagent.list", {"parentSessionId": sid})
        children = {row["id"]: row for row in catalog["entries"]}
        attempts = state.get("attempts", {})
        values = attempts.values() if isinstance(attempts, dict) else attempts
        for attempt in values:
            child = children.get(attempt.get("child_id"))
            if (
                not child
                or child.get("mode") != "continuable"
                or child.get("activity") == "running"
            ):
                continue
            page = await service.client.rpc(
                "subagent.history",
                {
                    "parentSessionId": sid,
                    "childSessionId": child["id"],
                    "mode": "continuable",
                    "maxMessages": 1000,
                },
            )
            if page.get("hasMore"):
                continue
            _reconcile_usage(service, sid, page["events"], child["id"])
            if attempt["status"] not in {
                "reserved",
                "dispatching",
                "accepted",
                "unknown",
                "cancel_requested",
            }:
                continue
            end = _native_end(page["events"])
            if not end:
                continue
            data = end["data"]
            if type(data.get("turn")) is not int or data["turn"] < 0:
                continue
            reason = data.get("stopReason", data.get("reason"))
            if isinstance(reason, dict):
                reason = reason.get("kind")
            if reason not in {"completed", "aborted", "error", "max-tokens", "refusal"}:
                continue
            result = None
            messages = [
                item["event"]
                for item in page["events"]
                if item.get("event", {}).get("type") == "assistant/message"
            ]
            if reason == "completed" and messages:
                message = max(messages, key=lambda item: item["seq"])
                try:
                    result = validate_result_references(
                        service,
                        sid,
                        json.loads(content_text(message["data"]["message"].get("content"))),
                    )
                except (ValueError, TypeError, KeyError, StoreError):
                    reason = "error"
            if reason == "completed" and result is None:
                reason = "invalid_output"
            payload = {
                "attempt_id": attempt["id"],
                "child_id": child["id"],
                "stop_reason": reason,
                "terminal_observation": {
                    "kind": "history",
                    "child_id": child["id"],
                    "end_seq": end["seq"],
                    "turn": data["turn"],
                    "event_sha256": hashlib.sha256(
                        json.dumps(end, sort_keys=True).encode()
                    ).hexdigest(),
                },
            }
            if result is not None:
                payload["result"] = result
                try:
                    payload = await qualify_terminal(service, sid, payload)
                except (ValueError, KeyError, StoreError):
                    payload.pop("result", None)
                    payload["stop_reason"] = "invalid_output"
            ledger(service).apply(
                sid,
                "terminal",
                payload,
                agent_id=child["id"],
                call_id=f"history:{child['id']}:{end['seq']}",
            )
        # A stopped parent is actionable only after the exact accepted prompt's
        # durable marker has an ending turn. A missing/queued/unknown parent is
        # never inferred idle from an absent catalog entry.
        root_rows = (await service.client.rpc("session.list", {})).get("items", [])
        roots = [row for row in root_rows if row.get("sessionId") == sid]
        root_events = [item["event"] for item in service.events.get(sid, {}).values()]
        delivery = service.delivery.current(sid) or {}
        markers = [
            event["seq"]
            for event in root_events
            if event.get("type") == "user/message"
            and delivery.get("marker")
            and delivery["marker"] in content_text(event.get("data", {}).get("content"))
        ]
        ended = markers and any(
            event.get("type") == "turn/end" and event["seq"] > max(markers) for event in root_events
        )
        if (
            len(roots) == 1
            and roots[0].get("running") is False
            and ended
            and all(
                row.get("activity") == "idle" and row.get("mode") == "continuable"
                for row in children.values()
            )
            and service.connected == {"mux", "host"}
            and not any(
                row.get("ownerSessionId", row.get("sessionId")) == sid
                for row in [*service.approvals.values(), *service.questions.values()]
            )
        ):
            latest = ledger(service).read(sid)
            if latest["id"] != state["id"] or (service.delivery.current(sid) or {}).get(
                "marker"
            ) != delivery.get("marker"):
                return latest
            stopped = max(
                (
                    event
                    for event in root_events
                    if event.get("type") == "turn/end" and event["seq"] > max(markers)
                ),
                key=lambda event: event["seq"],
            )
            turn = stopped.get("data", {}).get("turn")
            reserved = [
                attempt["id"]
                for attempt in latest["attempts"].values()
                if (
                    attempt["status"] == "reserved"
                    or (
                        attempt["status"] == "cancel_requested"
                        and attempt.get("cancelled_from_status") == "reserved"
                        and not attempt.get("dispatch_at")
                    )
                )
                and attempt["child_id"] not in children
            ]
            if reserved and type(turn) is int and turn >= 0:
                ledger(service).confirm_not_submitted(
                    sid,
                    reserved,
                    {
                        "parent_session_id": sid,
                        "parent_idle": True,
                        "parent_terminal": {
                            "end_seq": stopped["seq"],
                            "turn": turn,
                            "event_sha256": hashlib.sha256(
                                json.dumps(stopped, sort_keys=True).encode()
                            ).hexdigest(),
                        },
                        "catalog_complete": True,
                        "child_ids": list(children),
                    },
                )
            ledger(service).apply(
                sid, "recover", {}, agent_id=sid, call_id=f"recover-history:{max(markers)}"
            )
    except (RuntimeFailure, KeyError, ValueError, StoreError) as exc:
        log.warning("research_specialist_reconciliation_unconfirmed", error_type=type(exc).__name__)
    return ledger(service).read(sid)


def project_detail(service, sid, detail):
    state = ledger(service).read(sid)
    if state is None:
        return
    state["revision"] = state["active_plan"]["version"]
    state["nodes"] = [
        {
            **node,
            "status": next(
                (
                    attempt["status"]
                    for attempt in reversed(list(state["attempts"].values()))
                    if attempt["node_id"] == node["id"] and not attempt["invalidated"]
                ),
                "pending",
            ),
        }
        for node in state["active_plan"]["nodes"]
    ]
    requests = list(state["model_requests"].values())
    known = all(request["usage"] is not None for request in requests)
    state["usage"] = {
        "tokens": (
            sum(
                usage["input_tokens"] + usage["output_tokens"]
                for request in requests
                if (usage := request["usage"]) is not None
            )
            if known and requests
            else None
        )
    }
    detail["specialist"] = state
    if not state.get("finalization_ready"):
        detail["research_accepted"] = False


def quality_issues(service, sid):
    state = ledger(service).read(sid)
    if state is not None and not state.get("finalization_ready"):
        return ["specialist_collaboration_incomplete"]
    return []


async def resume(service, sid, confirmed):
    """One explicit new grant; existing delivery ledger still owns prompt admission."""
    if confirmed is not True:
        raise SpecialistError("续跑需要明确确认", "specialist_resume_unconfirmed", 409)
    await reconcile(service, sid)
    await verify_cached(service, sid)
    from ..research_quality_service import latest_receipt

    current = ledger(service).read(sid)
    if current is None:
        raise SpecialistError("没有专业协作研究", "specialist_missing", 404)
    receipt = latest_receipt(service, sid)
    contract = receipt.get("research_contract", {})
    if not contract.get("question"):
        raise SpecialistError("原研究合同缺失，不能续跑", "specialist_contract_missing", 409)
    ledger(service).resume(sid, confirmed=True)
    return await service.send(
        sid,
        contract["question"],
        f"specialist-resume-{current['id']}",
        research_mode="specialist",
        specialist_budget=current["budget"],
        research_as_of=contract["as_of"],
        research_requirements=[row["text"] for row in contract["requirements"]],
    )
