"""Dossier scan transactions and opt-in scheduling on the existing Automation."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from core.observability import get_logger

from ..automation.models import AutomationCreate, AutomationSchedule
from ..automation.service import automation_feature_enabled
from ..store import StoreError
from .signals import RULE_VERSION, RULES_SHA256, evaluate_signals

log = get_logger(__name__)
DEFAULT_SCHEDULE = {"kind": "daily", "timezone": "Asia/Shanghai", "hour": 16, "minute": 30}


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


class DossierSignals:
    """No provider execution: current frozen materials remain the sole inputs."""

    def __init__(self, research, *, now=None):
        self.research = research
        self.dossiers = research.dossiers
        self.metadata = self.dossiers.metadata
        self.now = now or (lambda: datetime.now(UTC))

    def _today(self):
        return self.now().astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()

    @staticmethod
    def _table(connection):
        connection.execute(
            "CREATE TABLE IF NOT EXISTS dossier_aux(dossier_id TEXT PRIMARY KEY REFERENCES dossiers(id),payload TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS dossier_signal_index(id TEXT PRIMARY KEY,dossier_id TEXT NOT NULL REFERENCES dossiers(id),payload TEXT NOT NULL,updated_at TEXT NOT NULL)"
        )

    @staticmethod
    def _aux(connection, did):
        if not connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='dossier_aux'"
        ).fetchone():
            return {}
        row = connection.execute(
            "SELECT payload FROM dossier_aux WHERE dossier_id=?", (did,)
        ).fetchone()
        try:
            value = json.loads(row[0]) if row else {}
        except (ValueError, TypeError) as exc:
            raise StoreError("跟踪状态损坏", "dossier_scan_state_invalid", 503) from exc
        if not isinstance(value, dict):
            raise StoreError("跟踪状态损坏", "dossier_scan_state_invalid", 503)
        return value

    @staticmethod
    def _save(connection, did, aux):
        connection.execute("INSERT OR REPLACE INTO dossier_aux VALUES(?,?)", (did, _json(aux)))

    def definition(self, did, version=1):
        if version != 1:
            raise StoreError("扫描规则版本不可用", "dossier_scan_version_invalid", 409)
        detail = self.dossiers.get(did)
        if detail["archived"]:
            raise StoreError("档案已归档", "dossier_archived", 409)
        identity = {"dossier_id": did, "subject": detail["subject"], "rules": RULES_SHA256}
        return {
            "version": 1,
            "sha256": hashlib.sha256(_json(identity).encode()).hexdigest(),
            "formats": [],
        }

    def _evaluate(self, did, cutoff):
        detail = self.dossiers.get(did)
        if detail["archived"]:
            raise StoreError("档案已归档", "dossier_archived", 409)
        materials = {}
        for item in detail["evidence"]:
            if item.get("state") != "available":
                continue
            try:
                value = self.dossiers.read_evidence(did, item["id"], full=True)
                if inspect.isawaitable(value):
                    raise StoreError("异步证据读取未适配", "dossier_evidence_read_invalid", 503)
                if value.get("truncated") or value.get("state") != "available":
                    item.update(state="missing", error_code="evidence_projection_incomplete")
                    continue
                manifest = value.get("manifest")
                content = value.get("content")
                if not isinstance(manifest, dict) or not isinstance(content, str):
                    continue
                materials[item["id"]] = {"manifest": manifest, "rows": json.loads(content)}
            except StoreError as exc:
                item.update(state="unavailable", error_code=exc.code)
            except (ValueError, TypeError):
                item.update(state="unavailable", error_code="structured_data_invalid")
        return detail, evaluate_signals(detail, materials, cutoff)

    async def scan(self, did, request, *, trigger="manual"):
        request = dict(request)
        cutoff = request.get("as_of") or self._today()
        # Persist the chosen cutoff in the response/event. Keep the original
        # request digest stable when a client retries without an explicit day.
        detail, evaluation = await asyncio.to_thread(self._evaluate, did, cutoff)

        def commit(connection, identifier, revision):
            self._table(connection)
            aux = self._aux(connection, identifier)
            previous = {row["id"]: row for row in aux.get("scan", {}).get("items", [])}
            latest = {row["id"]: row for row in detail["records"] if row.get("kind") == "signal"}
            records, notifications = [], []
            for item in evaluation["items"]:
                old = previous.get(item["id"])
                if old and old.get("fingerprint") == item["fingerprint"]:
                    item["state"] = latest.get(item["id"], old).get("state", "open")
                else:
                    records.append(item)
                    notifications.append(
                        {
                            "signal_id": item["id"],
                            "change": "changed" if old else "new",
                            "title": item["title"],
                        }
                    )
            present = {item["id"] for item in evaluation["items"]}
            watched = {
                row["id"]: row
                for row in detail["records"]
                if row.get("kind") in {"risk", "catalyst"}
            }
            for identity, old in previous.items():
                if identity in present or old.get("state") in {"resolved", "dismissed"}:
                    continue
                # Loss of coverage is not proof that a risk has been resolved.
                item = {**old, "stale": True, "missing": ["evidence_not_reconfirmed"]}
                source_record = watched.get(old.get("source_record_id"), {})
                if old.get("rule") == "watch_window" and source_record.get("state") in {
                    "resolved",
                    "dismissed",
                }:
                    item.update(
                        state="resolved", stale=False, reason="关联观察项已由研究者明确关闭"
                    )
                    notifications.append(
                        {"signal_id": identity, "change": "resolved", "title": item["title"]}
                    )
                if item != old:
                    records.append(item)
                evaluation["items"].append(item)
            evaluation.update(
                trigger=trigger,
                checked_at=self.now().isoformat(),
                notifications=notifications,
                revision=revision,
            )
            aux["scan"] = evaluation
            tracking = aux.get("tracking", {"enabled": False})
            if trigger == "manual":
                tracking.update(
                    eligible=evaluation["coverage"]["eligible"] and automation_feature_enabled(),
                    reason=(
                        "automation_disabled"
                        if not automation_feature_enabled()
                        else (
                            None if evaluation["coverage"]["eligible"] else "evidence_not_qualified"
                        )
                    ),
                    manual_checked_at=cutoff,
                    manual_rules_sha256=RULES_SHA256,
                )
            aux["tracking"] = tracking
            for item in evaluation["items"]:
                connection.execute(
                    "INSERT OR REPLACE INTO dossier_signal_index VALUES(?,?,?,?)",
                    (item["id"], identifier, _json(item), evaluation["checked_at"]),
                )
            self._save(connection, identifier, aux)
            return None, {
                "records": records,
                "notifications": notifications,
                "coverage": evaluation["coverage"],
                "missing": evaluation["missing"],
                "trigger": trigger,
            }

        result = await asyncio.to_thread(self.metadata.mutate, did, request, "scan", commit)
        saved = result.get("scan", {})
        log.info(
            "dossier_scan_committed",
            dossier_id=did,
            revision=result["revision"],
            trigger=trigger,
            changes=len(saved.get("notifications", [])),
        )
        return {
            "dossier": result,
            "signals": saved.get("items", []),
            "coverage": saved.get("coverage", {}),
            "missing": saved.get("missing", []),
            "notifications": saved.get("notifications", []),
        }

    def list(self, *, dossier_id=None, state=None, kind=None, cursor=None, limit=100):
        try:
            offset = int(cursor or 0)
        except (ValueError, TypeError) as exc:
            raise StoreError("信号分页参数非法", "dossier_signal_cursor_invalid", 422) from exc
        if offset < 0 or offset > 100000 or not 1 <= limit <= 200:
            raise StoreError("信号分页参数非法", "dossier_signal_cursor_invalid", 422)
        if dossier_id:
            self.dossiers.get(dossier_id)
        with self.metadata.connection() as connection:
            if (
                connection is None
                or not connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='dossier_signal_index'"
                ).fetchone()
            ):
                return {
                    "items": [],
                    "next_cursor": None,
                    "coverage": {"status": "not_scanned"},
                    "missing": [{"code": "manual_scan_required"}],
                }
            rows = connection.execute(
                "SELECT s.payload FROM dossier_signal_index s JOIN dossiers d ON d.id=s.dossier_id WHERE d.archived=0 AND (? IS NULL OR s.dossier_id=?) AND (? IS NULL OR json_extract(s.payload,'$.state')=?) AND (? IS NULL OR COALESCE(json_extract(s.payload,'$.signal_type'),'review')=?) ORDER BY s.updated_at DESC,s.id LIMIT ? OFFSET ?",
                (dossier_id, dossier_id, state, state, kind, kind, limit + 1, offset),
            ).fetchall()
            items = [json.loads(row[0]) for row in rows[:limit]]
            # Re-read each dossier: current permission/missing state must also
            # apply to index projections, not just evidence download routes.
            current = {}
            for item in items:
                if item["dossier_id"] not in current:
                    current[item["dossier_id"]] = self.dossiers.get(item["dossier_id"])
                detail = current[item["dossier_id"]]
                latest = next((row for row in detail["records"] if row["id"] == item["id"]), None)
                if latest:
                    item["state"] = latest["state"]
                available = {
                    row["id"] for row in detail["evidence"] if row.get("state") == "available"
                }
                if not set(item["evidence_ids"]).issubset(available):
                    item.update(stale=True, missing=["evidence_unavailable"])
            items = [
                row
                for row in items
                if (state is None or row["state"] == state)
                and (kind is None or row.get("signal_type", "review") == kind)
            ]
            return {
                "items": items,
                "next_cursor": str(offset + limit) if len(rows) > limit else None,
                "coverage": {"status": "frozen_evidence", "scope": "personal"},
                "missing": [],
            }

    def tracking(self, did, request):
        enabled = request["enabled"]
        if enabled and not automation_feature_enabled():
            raise StoreError("当前运行模式未启用日程服务", "dossier_tracking_unavailable", 409)
        detail = self.dossiers.get(did)
        definition = (
            self.definition(did)
            if enabled
            else {"sha256": detail.get("tracking", {}).get("definition_sha256", "disabled")}
        )
        if enabled:
            tracking = detail.get("tracking", {})
            if (
                not tracking.get("eligible")
                or tracking.get("manual_checked_at") != self._today()
                or tracking.get("manual_rules_sha256") != RULES_SHA256
            ):
                raise StoreError(
                    "请先完成当前日期的合格手动扫描", "dossier_tracking_manual_required", 409
                )
            _, current = self._evaluate(did, self._today())
            if not current["coverage"]["eligible"]:
                raise StoreError(
                    "当前证据已缺失、过期或无权限", "dossier_tracking_evidence_invalid", 409
                )
        schedule = AutomationSchedule.model_validate(request.get("schedule") or DEFAULT_SCHEDULE)
        key = "dossier-tracking-" + did + "-" + definition["sha256"]
        automation_id = "automation-" + hashlib.sha256(key.encode()).hexdigest()
        existing = self.research.store.data.get("automations", {}).get(automation_id)

        def commit(connection, identifier, revision):
            self._table(connection)
            aux = self._aux(connection, identifier)
            value = aux.get("tracking", {})
            value.update(
                enabled=False,
                requested_enabled=enabled,
                request_key=request["idempotency_key"],
                automation_id=automation_id,
                schedule=schedule.model_dump(mode="json"),
                eligible=value.get("eligible", False),
                reason="activation_pending" if enabled else "disabled_by_user",
                rule_version=RULE_VERSION,
                rules_sha256=RULES_SHA256,
                definition_sha256=definition["sha256"],
            )
            aux["tracking"] = value
            self._save(connection, identifier, aux)
            return None, {"tracking": value}

        result = self.metadata.mutate(did, request, "tracking", commit)
        current = self.dossiers.get(did)
        if current["tracking"].get("request_key") != request["idempotency_key"]:
            # Replaying an old authorization must never undo a later disable.
            return {"dossier": result, "tracking": result["tracking"]}
        intent = current["tracking"]
        if enabled and (
            intent.get("definition_sha256") != definition["sha256"]
            or intent.get("rules_sha256") != RULES_SHA256
            or intent.get("automation_id") != automation_id
            or intent.get("schedule") != schedule.model_dump(mode="json")
        ):
            raise StoreError(
                "跟踪授权定义已变化，请重新手动扫描并确认",
                "dossier_tracking_definition_changed",
                409,
            )
        if enabled and current["tracking"].get("enabled"):
            return {"dossier": current, "tracking": current["tracking"]}
        if enabled and current["revision"] != result["revision"]:
            raise StoreError("档案版本已变化，请重新确认跟踪", "dossier_revision_conflict", 409)
        for old in list(self.research.store.data.get("automations", {}).values()):
            target = old.get("target", {})
            if (
                old.get("id") != automation_id
                and target.get("kind") == "dossier_scan"
                and target.get("id") == did
                and old.get("enabled")
            ):
                self.research.automations.disable(old["id"])
        if not enabled and existing:
            self.research.automations.disable(automation_id)
        if enabled:
            if not existing:
                body = AutomationCreate(
                    name="研究档案观察窗口扫描",
                    target_kind="dossier_scan",
                    target_id=did,
                    target_version=1,
                    target_sha256=definition["sha256"],
                    input_template="仅扫描当前档案的冻结证据和观察窗口，不采集、不调用模型。",
                    output_formats=[],
                    schedule=schedule,
                )
                self.research.automations.create(body, creation_key=key)
            elif existing.get("schedule") != schedule.model_dump(mode="json"):
                from ..automation.models import AutomationUpdate

                self.research.automations.update(automation_id, AutomationUpdate(schedule=schedule))
            try:
                self.research.automations.enable(automation_id)

                # An enabled scheduler still refuses execution until this
                # explicit activation event commits. A crash cannot scan with
                # an unconfirmed tracking definition.
                def activate(connection, identifier, revision):
                    self._table(connection)
                    aux = self._aux(connection, identifier)
                    intent = aux.get("tracking", {})
                    if (
                        intent.get("request_key") != request["idempotency_key"]
                        or intent.get("automation_id") != automation_id
                        or intent.get("definition_sha256") != definition["sha256"]
                        or intent.get("rules_sha256") != RULES_SHA256
                    ):
                        raise StoreError(
                            "跟踪授权定义已变化", "dossier_tracking_definition_changed", 409
                        )
                    aux["tracking"].update(enabled=True, requested_enabled=True, reason=None)
                    self._save(connection, identifier, aux)
                    return None, {"tracking": aux["tracking"]}

                activation = {
                    "expected_revision": result["revision"],
                    "idempotency_key": "tracking-activate-"
                    + hashlib.sha256(request["idempotency_key"].encode()).hexdigest(),
                }
                result = self.metadata.mutate(did, activation, "tracking", activate)
            except Exception:
                self.research.automations.disable(automation_id)
                log.error("dossier_tracking_enable_failed", dossier_id=did)
                raise
        log.info("dossier_tracking_changed", dossier_id=did, enabled=enabled)
        return {"dossier": result, "tracking": result["tracking"]}

    async def scheduled(self, did, run_id):
        detail = self.dossiers.get(did)
        if not detail.get("tracking", {}).get("enabled"):
            raise StoreError("档案跟踪未启用", "dossier_tracking_disabled", 409)
        result = await self.scan(
            did,
            {
                "expected_revision": detail["revision"],
                "idempotency_key": "scheduled-" + run_id,
                "as_of": self._today(),
            },
            trigger="schedule",
        )
        return {
            "status": "completed",
            "summary": f"档案扫描完成，{len(result['notifications'])} 项有意义变化。",
            "artifacts": [],
            "suppress_delivery": not bool(result["notifications"]),
        }
