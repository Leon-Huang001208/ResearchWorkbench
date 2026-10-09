"""Pure projection of native DSH events; no parallel research execution model."""

import json
from itertools import pairwise

from core.observability import get_logger

log = get_logger(__name__)


def _project_plan(entries: list[dict]) -> dict:
    """Fold whole native snapshots; version identifies a write, never an item."""
    rows: dict[int, dict] = {}
    conflicts: set[int] = set()
    incomplete, corrupt = False, False
    for row in entries:
        event = row.get("event") if isinstance(row, dict) else None
        if not isinstance(event, dict):
            incomplete, corrupt = True, True
            continue
        seq = event.get("seq")
        if not isinstance(event.get("type"), str) or (
            not isinstance(event.get("data"), dict) and event.get("type") != "todo/write"
        ):
            incomplete, corrupt = True, True
            continue
        if not isinstance(seq, int) or isinstance(seq, bool) or seq < 0:
            incomplete, corrupt = True, True
            continue
        if seq in rows and rows[seq] != event:
            conflicts.add(seq)
        rows[seq] = event
    keys = sorted(rows)
    incomplete |= bool(keys and (keys[0] > 0 or any(b != a + 1 for a, b in pairwise(keys))))
    turn, plan, error = None, None, False
    previous = None
    for seq in keys:
        if previous is not None and seq != previous + 1:
            turn, plan = None, None  # the missing records may contain a new turn/start
        previous = seq
        event = rows[seq]
        kind, data = event.get("type"), event.get("data")
        if kind == "turn/start":
            turn = data.get("turn") if isinstance(data, dict) else None
            if not isinstance(turn, int) or isinstance(turn, bool) or turn < 0:
                turn = None
            plan, error = None, turn is None
        if seq in conflicts:
            plan, error, incomplete = None, True, True
        if kind != "todo/write":
            continue
        todos = data.get("todos") if isinstance(data, dict) else None
        valid = isinstance(todos, list)
        seen = set()
        if isinstance(todos, list):
            for item in todos:
                if (
                    not isinstance(item, dict)
                    or set(item) != {"content", "status"}
                    or not isinstance(item["content"], str)
                    or not item["content"].strip()
                    or item["content"] != item["content"].strip()
                    or item["content"] in seen
                    or item["status"] not in ("pending", "in_progress", "completed")
                ):
                    valid = False
                    break
                seen.add(item["content"])
        if not valid or seq in conflicts:
            plan, error = None, True
        elif turn is None:
            plan, incomplete = None, True
        elif not error:
            assert isinstance(todos, list)
            plan = {
                "turn": turn,
                "seq": seq,
                "version": f"{turn}:{seq}",
                "todos": [dict(item) for item in todos],
            }
    if corrupt:
        plan, error = None, True
    result = {"plan": plan, "plan_history_incomplete": incomplete}
    if error:
        result["plan_error"] = "原生计划事件无效；当前计划无法确认。"
        log.warning("research_plan_invalid", event_count=len(rows))
    return result


def content_text(content) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(
        str(block.get("text", ""))
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )


def project(entries: list[dict]) -> dict:
    plan_projection = _project_plan(entries)
    messages: dict = {}
    activities: dict = {}
    partials: dict = {}
    tool_started: dict = {}
    turn_started, duration_ms = None, 0
    status, error, tokens = "idle", None, 0
    input_tokens, output_tokens, usage_observed = 0, 0, False
    title = None
    readable = [
        row
        for row in entries
        if isinstance(row, dict)
        and isinstance(row.get("event"), dict)
        and type(row["event"].get("seq")) is int
        and row["event"]["seq"] >= 0
        and isinstance(row["event"].get("type"), str)
        and (isinstance(row["event"].get("data"), dict) or row["event"]["type"] == "todo/write")
    ]
    for entry in sorted(readable, key=lambda row: row["event"]["seq"]):
        event = entry["event"]
        data, kind, seq = event["data"], event["type"], event["seq"]
        if kind == "todo/write":
            continue  # validated by the independent native plan fold above
        timestamp = event.get("time")
        if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool):
            timestamp = None
        if kind == "user/message":
            # Skill/system injected context is not a human message in the UI.
            source = data.get("source")
            if (
                source
                and isinstance(source, dict)
                and source.get("kind") not in {None, "human", "user"}
            ):
                continue
            mid = str(data.get("id", f"user-{seq}"))
            messages[mid] = {
                "id": mid,
                "role": "user",
                "text": content_text(data.get("content")),
                "seq": seq,
            }
        elif kind in {"assistant/chunk", "assistant/message"}:
            mid = f"assistant-{data.get('turn')}-{data.get('step')}"
            if kind == "assistant/message":
                messages[mid] = {
                    "id": mid,
                    "role": "assistant",
                    "text": content_text(data.get("message", {}).get("content")),
                    "seq": seq,
                }
                partials.pop(mid, None)
                usage = data.get("usage") or {}
                if usage:
                    observed_input = usage.get("inputTokens")
                    observed_output = usage.get("outputTokens")
                    observed_total = usage.get("totalTokens")
                    if isinstance(observed_input, (int, float)) and not isinstance(
                        observed_input, bool
                    ):
                        input_tokens += max(0, int(observed_input))
                        usage_observed = True
                    if isinstance(observed_output, (int, float)) and not isinstance(
                        observed_output, bool
                    ):
                        output_tokens += max(0, int(observed_output))
                        usage_observed = True
                    if isinstance(observed_total, (int, float)) and not isinstance(
                        observed_total, bool
                    ):
                        tokens += max(0, int(observed_total))
                        usage_observed = True
                    elif usage_observed:
                        tokens += max(0, int(observed_input or 0)) + max(
                            0, int(observed_output or 0)
                        )
            elif mid not in messages:
                chunk = data["chunk"]
                blocks = partials.setdefault(mid, {"seq": seq, "blocks": {}})["blocks"]
                index = chunk.get("index", 0)
                if chunk["type"] == "text-delta":
                    blocks[index] = blocks.get(index, "") + chunk.get("text", "")
                elif chunk["type"] == "block-end" and chunk.get("block", {}).get("type") == "text":
                    blocks[index] = chunk["block"].get("text", "")
        elif kind == "tool/call":
            aid = data["callId"]
            tool_started[aid] = timestamp
            activities[aid] = {
                "id": aid,
                "type": "tool",
                "title": data["name"],
                "status": "running",
                "detail": data.get("arguments", ""),
            }
        elif kind == "tool/result":
            message = data.get("message", {})
            block: dict = next(
                (b for b in message.get("content", []) if b.get("type") == "tool-result"), {}
            )
            aid = message.get("source", {}).get("callId") or block.get("toolCallId", f"tool-{seq}")
            row = activities.setdefault(
                aid, {"id": aid, "type": "tool", "title": message.get("name", "工具结果")}
            )
            row.update(
                status="failed" if data.get("error") or block.get("isError") else "completed",
                detail=content_text(block.get("content")),
            )
            started = tool_started.get(aid)
            if started is not None and timestamp is not None and timestamp > started:
                row["duration_ms"] = timestamp - started
            if row.get("title") == "research_run_script" and row["status"] == "completed":
                try:
                    script = json.loads(row["detail"])
                    outcome = script.get("status") if isinstance(script, dict) else None
                    if outcome != "completed":
                        row["status"] = "cancelled" if outcome == "cancelled" else "failed"
                except (ValueError, TypeError):
                    row["status"] = "failed"
        elif kind == "turn/start":
            status, error = "running", None
            turn_started = timestamp
        elif kind == "turn/end":
            if turn_started is not None and timestamp is not None and timestamp > turn_started:
                duration_ms += timestamp - turn_started
            turn_started = None
            reason = data.get("reason", {})
            status = {
                "completed": "completed",
                "aborted": "cancelled",
                "interrupted": "interrupted",
                "error": "failed",
                "blocked": "blocked",
                "max-tokens": "incomplete",
            }.get(reason.get("kind"), "interrupted")
            if status == "failed":
                error = reason.get("error", {}).get("message", "DSH 执行失败")
            for activity in activities.values():
                if activity.get("status") == "running":
                    activity["status"] = "interrupted"
        elif kind == "session/title":
            title = data.get("title")
    for mid, partial in partials.items():
        messages[mid] = {
            "id": mid,
            "role": "assistant",
            "text": "\n".join(partial["blocks"][key] for key in sorted(partial["blocks"])),
            "seq": partial["seq"],
        }
    result = {
        **plan_projection,
        "messages": sorted(
            (message for message in messages.values() if message["text"]),
            key=lambda row: row["seq"],
        ),
        "activities": list(activities.values()),
        "status": status,
        "usage": (
            {
                "tokens": tokens,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
            if usage_observed
            else {}
        ),
    }
    if error:
        if "no API key" in error:
            error = "DeepSeek 尚未授权：请在设置中填写 API Key，然后发送下一条消息继续。"
        result["error"] = error
    if title:
        result["title"] = title
    if duration_ms:
        result["duration_ms"] = duration_ms
    return result
