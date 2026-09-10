"""Safe Research Web boundary for the project-owned Tabbit DSH adapter."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Literal

from core.observability import get_logger

from .client import RuntimeFailure
from .store import Store

log = get_logger(__name__)
INSTANCE_PATTERN = re.compile(r"^[A-F0-9]{16}$")
MARKER_PATTERN = re.compile(r"^@\[[^\]\r\n]{1,80}\]\(rwb-tabbit:[a-zA-Z0-9-]{1,160}\)$")
MAX_TABS = 8
MAX_CANDIDATES = 50
TABBIT_STATUSES = {
    "ready",
    "disabled",
    "launcher_missing",
    "browser_offline",
    "unsupported_version",
    "instance_selection_required",
    "error",
}


class TabbitError(Exception):
    """Stable, non-sensitive Tabbit product error."""

    def __init__(self, message: str, code: str = "tabbit_error", status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


class TabbitIntegration:
    """Persist non-secret settings and mediate reviewed DSH plugin routes."""

    def __init__(self, client: Any, store: Store):
        self.client = client
        self.store = store
        self.config_path = store.root / ".control" / "tabbit.json"
        self.applied_path = store.root / ".control" / "tabbit-applied.json"
        self._grants: set[str] = set()
        self._restart_required = False

    def config(self) -> dict[str, Any]:
        defaults: dict[str, Any] = {
            "browser_enabled": True,
            "web_fetch_enabled": False,
            "instance_id": None,
        }
        if not self.config_path.exists():
            return defaults
        try:
            value = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            log.warning("tabbit_config_invalid", error_type=type(exc).__name__)
            raise TabbitError("Tabbit 配置文件无效", "tabbit_config_invalid", 500) from exc
        if not isinstance(value, dict):
            raise TabbitError("Tabbit 配置文件无效", "tabbit_config_invalid", 500)
        merged = {**defaults, **value}
        self._validate_config(merged)
        return merged

    @staticmethod
    def _validate_config(value: dict[str, Any]) -> None:
        if not isinstance(value.get("browser_enabled"), bool) or not isinstance(
            value.get("web_fetch_enabled"), bool
        ):
            raise TabbitError("Tabbit 开关格式无效", "tabbit_config_invalid")
        if value["web_fetch_enabled"] and not value["browser_enabled"]:
            raise TabbitError(
                "启用 Tabbit web_fetch 前必须开启浏览器自动化",
                "tabbit_web_fetch_requires_browser",
                409,
            )
        instance = value.get("instance_id")
        if instance is not None and (
            not isinstance(instance, str) or INSTANCE_PATTERN.fullmatch(instance) is None
        ):
            raise TabbitError("Tabbit 实例 ID 格式无效", "tabbit_instance_invalid")

    def configure(
        self,
        *,
        browser_enabled: bool,
        web_fetch_enabled: bool,
        instance_id: str | None,
    ) -> dict[str, Any]:
        value = {
            "browser_enabled": browser_enabled,
            "web_fetch_enabled": web_fetch_enabled,
            "instance_id": instance_id,
        }
        self._validate_config(value)
        self.config_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, name = tempfile.mkstemp(prefix="tabbit-", dir=self.config_path.parent)
        descriptor_open = True
        try:
            if os.name != "nt":
                os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                descriptor_open = False
                json.dump(value, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            if os.name == "nt":
                os.chmod(name, 0o600)
            os.replace(name, self.config_path)
        except Exception:
            if descriptor_open:
                try:
                    os.close(fd)
                except OSError as close_error:
                    log.warning(
                        "tabbit_config_descriptor_close_failed",
                        error_type=type(close_error).__name__,
                    )
            try:
                Path(name).unlink(missing_ok=True)
            except OSError as cleanup_error:
                log.warning(
                    "tabbit_config_cleanup_failed",
                    error_type=type(cleanup_error).__name__,
                )
            raise
        self._restart_required = True
        log.info(
            "tabbit_config_updated",
            browser_enabled=browser_enabled,
            web_fetch_enabled=web_fetch_enabled,
            instance_selected=instance_id is not None,
        )
        return {**value, "restart_required": True}

    async def status(self) -> dict[str, Any]:
        config = self.config()
        applied = None
        try:
            if self.applied_path.exists():
                applied = json.loads(self.applied_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            applied = None
        restart_required = self._restart_required or (
            applied != config and self.config_path.exists()
        )
        if not config["browser_enabled"]:
            return {
                **config,
                "restart_required": restart_required,
                "status": "disabled",
                "plugin_version": "0.3.4",
                "browser_version": None,
                "launcher_present": False,
                "cli_available": False,
                "online_instances": 0,
                "selected_instance": config["instance_id"],
                "instances": [],
            }
        try:
            remote = await self.client.plugin_json("GET", "/research/tabbit/status")
        except RuntimeFailure as exc:
            log.warning("tabbit_status_failed", code=exc.code)
            remote = {"status": "error"}
        raw_status = remote.get("status")
        remote_status = raw_status if raw_status in TABBIT_STATUSES else "error"
        raw_online = remote.get("onlineInstances", 0)
        online_instances = raw_online if isinstance(raw_online, int) and raw_online >= 0 else 0
        raw_instances = remote.get("instances", [])
        instances = raw_instances if isinstance(raw_instances, list) else []
        selected = remote.get("selectedInstance")
        selected_instance = (
            selected
            if isinstance(selected, str) and INSTANCE_PATTERN.fullmatch(selected)
            else config["instance_id"]
        )
        return {
            **config,
            "restart_required": restart_required,
            "status": remote_status,
            "plugin_version": remote.get("pluginVersion", "0.3.4"),
            "browser_version": remote.get("browserVersion"),
            "launcher_present": remote.get("launcherPresent") is True,
            "cli_available": remote.get("launcherPresent") is True,
            "online_instances": online_instances,
            "selected_instance": selected_instance,
            "instances": [
                {
                    "id": item["id"],
                    "name": str(item.get("name") or item["id"])[:120],
                    "online": item.get("online") is True,
                }
                for item in instances
                if isinstance(item, dict)
                and isinstance(item.get("id"), str)
                and INSTANCE_PATTERN.fullmatch(item["id"])
            ],
        }

    async def access(self, sid: str, decision: Literal["approve", "deny"]) -> dict[str, bool]:
        self.store.session(sid)
        if decision == "deny":
            self._grants.discard(sid)
            try:
                await self.client.plugin_json(
                    "POST",
                    "/research/tabbit/access",
                    payload={"sessionId": sid, "decision": "deny"},
                )
            except RuntimeFailure as exc:
                log.warning("tabbit_access_revoke_failed", session_id=sid, code=exc.code)
            return {"accepted": False}
        config = self.config()
        if not config["browser_enabled"]:
            raise TabbitError("Tabbit 浏览器自动化已关闭", "tabbit_disabled", 409)
        try:
            response = await self.client.plugin_json(
                "POST",
                "/research/tabbit/access",
                payload={"sessionId": sid, "decision": "approve"},
            )
        except RuntimeFailure as exc:
            raise TabbitError("Tabbit 页面访问授权失败", exc.code, 503) from exc
        if response.get("accepted") is not True:
            raise TabbitError("Tabbit 页面访问授权未生效", "tabbit_access_rejected", 409)
        self._grants.add(sid)
        log.info("tabbit_access_granted", session_id=sid)
        return {"accepted": True}

    def _require_grant(self, sid: str) -> None:
        self.store.session(sid)
        if sid not in self._grants:
            raise TabbitError(
                "需要先允许当前会话读取 Tabbit 标签页",
                "tabbit_page_access_required",
                403,
            )

    async def tabs(
        self,
        sid: str,
        *,
        query: str = "",
        limit: int = MAX_CANDIDATES,
        _required: set[tuple[int, str]] | None = None,
    ) -> dict:
        self._require_grant(sid)
        config = self.config()
        params = {"session": sid}
        selected_instance = config["instance_id"]
        if selected_instance is None:
            selected_instance = (await self.status()).get("selected_instance")
        if selected_instance:
            params["instance"] = selected_instance
        try:
            payload = await self.client.plugin_json("GET", "/research/tabbit/tabs", params=params)
        except RuntimeFailure as exc:
            raise TabbitError("Tabbit 标签页列表不可用", exc.code, 503) from exc
        selected_instance = payload.get("instanceId") or selected_instance
        normalized_query = query.strip().casefold()
        items = []
        for raw in payload.get("tabs", []) if isinstance(payload.get("tabs"), list) else []:
            if not isinstance(raw, dict) or raw.get("state") != "available":
                continue
            url = raw.get("url")
            title = raw.get("title")
            tab_id = raw.get("tabId")
            if (
                not isinstance(url, str)
                or not url.startswith(("http://", "https://"))
                or not isinstance(title, str)
                or not isinstance(tab_id, int)
                or not isinstance(selected_instance, str)
            ):
                continue
            if normalized_query and normalized_query not in f"{title} {url}".casefold():
                continue
            key = (tab_id, selected_instance)
            if _required is not None and key not in _required:
                continue
            items.append(
                {
                    "tab_id": tab_id,
                    "instance_id": selected_instance,
                    "title": title[:120],
                    "url": url[:2048],
                    "active": raw.get("active") is True,
                }
            )
            if _required is not None and len(items) >= len(_required):
                break
            if _required is None and len(items) >= min(max(limit, 1), MAX_CANDIDATES):
                break
        return {"items": items, "count": len(items)}

    async def live_markers(
        self,
        sid: str,
        request_id: str,
        refs: list[dict[str, Any]],
        *,
        confirmed: bool,
    ) -> list[str]:
        if not refs:
            return []
        self._require_grant(sid)
        if not confirmed:
            raise TabbitError(
                "需要确认临时接管所选标签页",
                "tabbit_claim_confirmation_required",
                409,
            )
        if len(refs) > MAX_TABS:
            raise TabbitError("每条消息最多引用 8 个标签页", "tabbit_too_many_tabs")
        tab_ids = [ref.get("tab_id") for ref in refs]
        if len(set(tab_ids)) != len(tab_ids):
            raise TabbitError("同一标签页不能重复引用", "tabbit_duplicate_tab")
        instance_id = refs[0].get("instance_id")
        if not isinstance(instance_id, str) or any(
            ref.get("instance_id") != instance_id for ref in refs
        ):
            raise TabbitError("一次只能引用同一 Tabbit 实例", "tabbit_instance_mismatch")
        required = {
            (tab_id, instance_id)
            for tab_id in tab_ids
            if isinstance(tab_id, int) and not isinstance(tab_id, bool)
        }
        inventory = await self.tabs(sid, limit=MAX_CANDIDATES, _required=required)
        available = {(item["tab_id"], item["instance_id"]): item for item in inventory["items"]}
        for ref in refs:
            if (ref.get("tab_id"), ref.get("instance_id")) not in available:
                raise TabbitError(
                    "所选标签页已关闭、被占用或属于其他实例",
                    "tabbit_tab_unavailable",
                    409,
                )
        try:
            response = await self.client.plugin_json(
                "POST",
                "/research/tabbit/live-extract",
                payload={
                    "sessionId": sid,
                    "requestId": request_id,
                    "instanceId": instance_id,
                    "tabIds": tab_ids,
                },
            )
        except RuntimeFailure as exc:
            raise TabbitError("Tabbit 实时页面提取失败，消息未发送", exc.code, 503) from exc
        raw_markers = response.get("markers")
        if not isinstance(raw_markers, list) or len(raw_markers) != len(refs):
            raise TabbitError("Tabbit 提取结果不完整", "tabbit_extract_incomplete", 503)
        markers = []
        for expected, marker in zip(tab_ids, raw_markers, strict=True):
            if (
                not isinstance(marker, dict)
                or marker.get("tabId") != expected
                or not isinstance(marker.get("marker"), str)
                or MARKER_PATTERN.fullmatch(marker["marker"]) is None
            ):
                raise TabbitError("Tabbit 提取结果格式无效", "tabbit_extract_invalid", 503)
            markers.append(marker["marker"])
        log.info("tabbit_live_extract_completed", session_id=sid, tab_count=len(markers))
        return markers
