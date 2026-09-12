"""Research BFF: native events, safe ownership, idempotent admission, no agent loop."""

import asyncio
import base64
import hashlib
import json
import os
import secrets
import shutil
import time
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

from websockets.exceptions import WebSocketException

from core.observability import get_logger

from .asset_workspace import AssetWorkspace
from .automation.channels import DeliveryChannelStore
from .automation.delivery import DeliveryDispatcher
from .automation.service import AutomationService, automation_feature_enabled
from .automation.transport import DeliveryTransport
from .capabilities.catalog import CapabilityCatalog
from .capabilities.models import CapabilityError, Metadata, Step
from .capabilities.packages import MAX_COMPRESSED, import_package
from .capabilities.tools import SELECTABLE
from .client import DSHClient, RuntimeFailure
from .datahub import DataHub
from .delivery import FINAL, Delivery, expected_formats
from .frameworks import FrameworkService
from .local_integrations import LocalIntegrationManager
from .mcp_registry import MCPRegistryService
from .mcp_runtime.authorization import AuthorizationManager
from .mcp_runtime.control import load_control as load_mcp_control
from .mcp_runtime.credentials import RuntimeCredentialStore
from .mcp_runtime.installation_store import (
    INTEGRITY_KEY_SERVICE,
    ConfirmationTokenManager,
    InstallationStore,
)
from .mcp_runtime.oauth import OAuthCoordinator, OAuthDiscovery
from .mcp_runtime.package_installer import PackageInstaller
from .mcp_runtime.package_planner import PackagePlanner
from .mcp_runtime.package_resolver import PackageResolver
from .mcp_runtime.sdk_host import SDKHost
from .mcp_runtime.service import MCPRuntimeService, runtime_feature_enabled
from .projection import project
from .report_studio import ReportStudio
from .report_workflows.manager import ReportWorkflowManager
from .service_manager import WebServiceManager
from .store import Store, StoreError
from .tabbit import TabbitIntegration

log = get_logger(__name__)
SESSION_DELETE_BLOCKED_STATUSES = {
    "running",
    "queued",
    "pending",
    "waiting",
    "waiting_approval",
    "awaiting_approval",
    "waiting_input",
    "busy",
    "cancelling",
}
SESSION_RETENTION_SECONDS = 30 * 24 * 60 * 60
SESSION_PURGE_INTERVAL_SECONDS = 6 * 60 * 60
MCP_CONFIRMATION_KEY_ACCOUNT = "confirmation-signing-v1"
MCP_INTERNAL_URL = "http://127.0.0.1:8088"


def _mcp_internal_url() -> str:
    """Resolve the manager-provided loopback origin for this Web process."""

    return os.environ.get("RESEARCH_WEB_INTERNAL_URL", MCP_INTERNAL_URL).rstrip("/")


def _persistent_mcp_key(account: str, keyring_backend=None) -> bytes:
    """Load one fixed-size Host key without ever persisting it in the data root."""

    try:
        if keyring_backend is None:
            import keyring as keyring_backend  # type: ignore[no-redef]
        encoded = keyring_backend.get_password(INTEGRITY_KEY_SERVICE, account)
        if encoded is None:
            generated = secrets.token_bytes(32)
            encoded = base64.urlsafe_b64encode(generated).rstrip(b"=").decode("ascii")
            keyring_backend.set_password(INTEGRITY_KEY_SERVICE, account, encoded)
            if keyring_backend.get_password(INTEGRITY_KEY_SERVICE, account) != encoded:
                raise RuntimeError("mcp_runtime_key_race")
        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except RuntimeError:
        raise
    except Exception as exc:
        log.error("mcp_runtime_key_load_failed", error_type=type(exc).__name__)
        raise RuntimeError("mcp_runtime_key_unavailable") from exc
    if len(raw) != 32:
        raise RuntimeError("mcp_runtime_key_invalid")
    return raw


class _SessionOwnedMCPRuntime:
    """Enforce Research Store ownership before any session-scoped MCP operation."""

    def __init__(self, runtime, store: Store) -> None:
        self.runtime = runtime
        self.store = store

    def __getattr__(self, name):
        return getattr(self.runtime, name)

    async def start(self):
        return await self.runtime.start()

    async def close(self):
        return await self.runtime.close()

    def _owned(self, session_id: str) -> None:
        if not isinstance(session_id, str):
            raise StoreError("研究会话不存在或不属于当前产品")
        self.store.session(session_id)

    def authorize_session(self, session_id: str, **binding):
        self._owned(session_id)
        return self.runtime.authorize_session(session_id, **binding)

    def register_automation_session(self, session_id: str, locks: list[dict]):
        self._owned(session_id)
        return self.runtime.register_automation_session(session_id, locks)

    async def read_resource(self, session_id: str, installation_id: str, uri: str):
        self._owned(session_id)
        return await self.runtime.read_resource(session_id, installation_id, uri)

    async def get_prompt(
        self,
        session_id: str,
        installation_id: str,
        name: str,
        arguments: dict[str, str] | None,
    ):
        self._owned(session_id)
        return await self.runtime.get_prompt(session_id, installation_id, name, arguments)

    async def call_tool(self, **request):
        self._owned(request.get("session_id"))
        return await self.runtime.call_tool(**request)

    def approvals(self, *, session_id: str | None = None):
        if session_id is not None:
            self._owned(session_id)
        return self.runtime.approvals(session_id=session_id)

    async def decide_approval(self, approval_id: str, *, session_id: str, approve: bool):
        self._owned(session_id)
        return await self.runtime.decide_approval(
            approval_id,
            session_id=session_id,
            approve=approve,
        )


class ResearchService:
    def __init__(
        self,
        client: DSHClient,
        store: Store,
        *,
        owned: bool = True,
        expected_cwd: Path | None = None,
        delivery_python: Path | None = None,
        mcp_registry: MCPRegistryService | None = None,
        mcp_runtime=None,
        mcp_keyring_backend=None,
        runtime_manager=None,
        delivery_keyring_backend=None,
    ):
        self.client, self.store, self.owned = client, store, owned
        self.expected_cwd = expected_cwd
        self.delivery = Delivery(store, delivery_python)
        self.capabilities = CapabilityCatalog(store.root)
        self.datahub = DataHub(store)
        self.tabbit = TabbitIntegration(client, store)
        self.local_integrations = LocalIntegrationManager(store.root / "local-integrations")
        self.mcp_registry = mcp_registry or MCPRegistryService(store.root)
        self._runtime_manager = runtime_manager
        if mcp_runtime is None:
            mcp_runtime = self._build_mcp_runtime(mcp_keyring_backend)
        self.mcp_runtime = _SessionOwnedMCPRuntime(mcp_runtime, store)
        self.asset_workspace = AssetWorkspace(self)
        self.frameworks = FrameworkService(self, store.root / "frameworks")
        self.report_studio = ReportStudio(self)
        self.report_workflows = ReportWorkflowManager(self)
        self.delivery_channels = DeliveryChannelStore(
            store, keyring_backend=delivery_keyring_backend
        )
        self.automations = AutomationService(
            store,
            research=self,
            channel_store=self.delivery_channels,
            dispatcher=DeliveryDispatcher(transport=DeliveryTransport(self.delivery_channels)),
        )
        self.connected: set[str] = set()
        self.event_revision = 0
        self.events: dict[str, dict[int, dict]] = {}
        self.loaded: set[str] = set()
        self.approvals: dict[str, dict] = {}
        self.questions: dict[str, dict] = {}
        self.errors: dict[str, str] = {}
        self.running: dict[str, bool] = {}
        self.child_parents: dict[str, str] = {}
        self.child_views: dict[str, tuple[float, dict]] = {}
        self.listeners: set[asyncio.Event] = set()
        self.lock = asyncio.Lock()
        # Product-level query and handoff admission must be serialized separately
        # from native DSH session mutations, which already use ``self.lock``.
        self.workbench_lock = asyncio.Lock()
        self.pump = None
        self.retention_task: asyncio.Task | None = None
        self.last_runtime_success_at: float | None = None
        self.default_model = store.data.get(
            "model", {"provider": "deepseek-official", "model": "deepseek-v4-flash"}
        )

    def _build_mcp_runtime(self, keyring_backend=None):
        """Build the private Host graph only when the runtime feature is enabled."""

        if not runtime_feature_enabled():
            return MCPRuntimeService(enabled=False)

        runtime_root = self.store.root / "mcp-runtime"
        staging_root = runtime_root / "staging"
        installation_root = runtime_root / "packages"
        credentials = RuntimeCredentialStore(keyring_backend)
        signing_key = _persistent_mcp_key(MCP_CONFIRMATION_KEY_ACCOUNT, keyring_backend)
        tokens = ConfirmationTokenManager(signing_key, replay_root=self.store.root)
        manifests = InstallationStore(self.store.root, keyring_backend=keyring_backend)
        staging_root.mkdir(mode=0o700, exist_ok=True)
        resolver = PackageResolver(staging_root)
        planner = PackagePlanner()
        installer = PackageInstaller(
            staging_root,
            installation_root,
            credentials=credentials,
        )
        host = SDKHost(credentials=credentials)
        internal_url = _mcp_internal_url()
        oauth = OAuthCoordinator(
            OAuthDiscovery(),
            credentials,
            redirect_uri=f"{internal_url}/api/research/mcp/oauth/callback",
            client_id="research-workbench",
        )
        control = load_mcp_control(self.store.root, internal_url)
        if self._runtime_manager is None:
            self._runtime_manager = WebServiceManager(data_root=self.store.root)
        return MCPRuntimeService(
            self.store.root,
            enabled=True,
            registry=self.mcp_registry,
            resolver=resolver,
            planner=planner,
            tokens=tokens,
            store=manifests,
            installer=installer,
            host=host,
            authorization=AuthorizationManager(self.store.root),
            idle_gate=self._mcp_idle_gate,
            restart_callback=self._restart_mcp_runtime,
            control=control,
            oauth=oauth,
        )

    async def ensure_owned(self):
        if self.expected_cwd is not None:
            info = await self.client.rpc("host.describe", {})
            self.owned = info.get("cwd") == str(self.expected_cwd.resolve())
        if not self.owned:
            raise RuntimeFailure(
                "该连接不是已确认的 Research Workbench 专属实例，禁止修改", "read_only_runtime"
            )

    async def start(self):
        await self.frameworks.start()
        await self.mcp_registry.start()
        await self.mcp_runtime.start()
        self.pump = asyncio.create_task(self._connect(), name="dsh-events")
        await self.report_workflows.start()
        if automation_feature_enabled():
            await self.automations.start()
        await self.purge_expired_sessions()
        self.retention_task = asyncio.create_task(
            self._retention_loop(), name="research-session-retention"
        )

    async def close(self):
        if self.retention_task:
            self.retention_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.retention_task
            self.retention_task = None
        await self.automations.close()
        await self.report_workflows.close()
        await self.asset_workspace.close()
        await self.local_integrations.close()
        await self.frameworks.close()
        await self.mcp_runtime.close()
        await self.mcp_registry.close()
        await self.datahub.close()
        if self.pump:
            self.pump.cancel()
            with suppress(asyncio.CancelledError):
                await self.pump
        await self.client.close()

    async def _retention_loop(self):
        """Retry expired tombstones while the service remains online."""
        while True:
            await asyncio.sleep(SESSION_PURGE_INTERVAL_SECONDS)
            try:
                await self.purge_expired_sessions()
            except asyncio.CancelledError:
                raise
            except (RuntimeFailure, StoreError, OSError) as exc:
                log.warning(
                    "research_session_retention_cycle_failed",
                    error_type=type(exc).__name__,
                )

    def notify(self):
        for listener in self.listeners:
            listener.set()

    async def _connect(self):
        delay = 0.5
        while True:
            tasks = [asyncio.create_task(self._consume(channel)) for channel in ("mux", "host")]
            try:
                done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    task.result()
            except asyncio.CancelledError:
                raise
            except (
                OSError,
                WebSocketException,
                RuntimeFailure,
                StoreError,
                ValueError,
                KeyError,
                TypeError,
            ) as exc:
                log.warning("dsh_events_disconnected", error_type=type(exc).__name__)
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                self.connected.clear()
                self.event_revision += 1
                self.loaded.clear()
                self.approvals.clear()
                self.questions.clear()
                self.child_views.clear()
                self.notify()
            await asyncio.sleep(delay)
            delay = min(delay * 2, 5)

    async def _consume(self, channel):
        async for envelope in self.client.frames(channel):
            self.event_revision += 1
            if envelope.get("type") == "connected":
                self.connected.add(channel)
                self.last_runtime_success_at = time.time()
                self.notify()
                continue
            frame = envelope["payload"]
            sid = frame.get("sessionId")
            kind = frame["type"]
            owner = sid
            if sid not in self.store.data["sessions"]:
                if kind.startswith(("approval/", "question/")):
                    owner = await self._interaction_owner(sid)
                    if owner is None:
                        continue
                elif sid in self.child_parents:
                    self.notify()
                    continue
                else:
                    continue  # Never expose unowned sessions.
            if kind == "session/event":
                event = frame["event"]
                self.events.setdefault(sid, {})[event["seq"]] = {"event": event}
                if event["type"] == "turn/start":
                    self.errors.pop(sid, None)
                    self.running[sid] = True
                if event["type"] == "turn/end":
                    self.running[sid] = False
                    row = self.store.session(sid)
                    row["status"] = project(list(self.events[sid].values()))["status"]
                    row["updated_at"] = time.time()
                    self.store.save()
            elif kind == "host/session-status":
                self.running[sid] = frame["running"]
                # Current DSH publishes list-state invalidations separately
                # from its durable follow stream. Reload the authoritative log
                # on the next detail read, especially after a turn settles.
                self.loaded.discard(sid)
            elif kind == "host/session-activity":
                self.loaded.discard(sid)
            elif kind == "host/agent-error":
                self.errors[sid] = frame["message"]
            elif kind == "approval/requested":
                self.approvals[frame["approvalId"]] = {
                    **frame,
                    "rpc_id": envelope["rpcId"],
                    "ownerSessionId": owner,
                }
            elif kind == "approval/resolved":
                self.approvals.pop(frame["approvalId"], None)
            elif kind == "question/requested":
                self.questions[envelope["rpcId"]] = {**frame, "ownerSessionId": owner}
            elif kind == "question/resolved":
                self.questions.pop(frame["questionRpcId"], None)
            self.notify()

    async def _interaction_owner(self, sid):
        if sid in self.child_parents:
            return self.child_parents[sid]
        # Pending interactions may replay before the first detail projection.
        # Resolve only via the native parent-scoped registry, never claimed IDs.
        for row in list(self.store.data["sessions"].values()):
            if not row["created"]:
                continue
            children = await self.client.rpc("subagent.list", {"parentSessionId": row["id"]})
            if any(c.get("kind") == "child" and c.get("id") == sid for c in children["entries"]):
                self.child_parents[sid] = row["id"]
                return row["id"]
        log.warning("research_unowned_interaction_ignored")
        return None

    async def runtime(self):
        try:
            info = await self.client.rpc("host.describe", {})
            self.last_runtime_success_at = time.time()
            if self.expected_cwd is not None:
                self.owned = info.get("cwd") == str(self.expected_cwd.resolve())
            ready = self.connected == {"mux", "host"}
            auth = await self.client.rpc("credentials.describe", {"refs": ["RESEARCH_DSH_API_KEY"]})
            configured = (
                auth.get("credentials", {}).get("RESEARCH_DSH_API_KEY", {}).get("configured", False)
            )
            return {
                "connected": ready,
                "health_check_passed": True,
                "provider": info.get("provider"),
                "model": self.default_model["model"],
                "version": info["version"],
                "owned_runtime": self.owned,
                "credential_configured": configured,
                "last_successful_communication_at": self.last_runtime_success_at,
                "message": (
                    ("DSH 已连接" if configured else "DSH 已连接；请先在下方配置 API Key")
                    if ready
                    else "DSH 事件通道连接中"
                ),
            }
        except RuntimeFailure as exc:
            return {
                "connected": False,
                "health_check_passed": False,
                "provider": "DSH",
                "model": None,
                "version": None,
                "owned_runtime": self.owned,
                "last_successful_communication_at": self.last_runtime_success_at,
                "message": str(exc),
            }

    async def configure_model(self, provider, model, api_key=None):
        await self.ensure_owned()
        async with self.lock:
            selection = {"provider": provider, "model": model}
            native = await self.client.rpc("session.list", {})
            busy = {item["sessionId"] for item in native["items"] if item["running"]}
            if api_key:
                await self.client.rpc(
                    "credentials.set", {"ref": "RESEARCH_DSH_API_KEY", "value": api_key}
                )
            for sid, row in self.store.data["sessions"].items():
                if row["created"] and sid not in busy:
                    await self.client.rpc("session.selectModel", {"sessionId": sid, **selection})
                    row["model"] = model
                    self.store.save()
            # Publish the default only after native selections succeeded. No
            # concurrent create/send can observe a half-written selection.
            self.store.data["model"] = selection
            self.store.save()
            self.default_model = selection
            log.info("research_model_configured", provider=provider, model=model)
            return {"configured": True}

    async def create(
        self,
        mode="fingpt",
        title=None,
        *,
        agent_preset="research-web",
        purpose=None,
        metadata=None,
    ):
        await self.ensure_owned()
        async with self.lock:
            row = self.store.create(mode, title or ("Claw 研究" if mode == "claw" else "新研究"))
            if purpose is not None:
                row["purpose"] = purpose
            if metadata:
                row.update(metadata)
            sid = row["id"]
            shutil.copytree(
                Path(__file__).parent / "resources",
                self.store.directory(sid) / "resources",
                ignore=shutil.ignore_patterns("__pycache__"),
                dirs_exist_ok=True,
            )
            shutil.copytree(
                Path(__file__).parent / "skills",
                self.store.directory(sid) / "resources" / "skills",
                ignore=shutil.ignore_patterns("__pycache__"),
                dirs_exist_ok=True,
            )
            try:
                await self.client.rpc(
                    "session.create",
                    {
                        "sessionId": sid,
                        "cwd": str(self.store.directory(sid)),
                        "agentPreset": agent_preset,
                    },
                )
                row["created"] = True
                row["model"] = self.default_model["model"]
                await self.client.rpc(
                    "session.selectModel", {"sessionId": sid, **self.default_model}
                )
                await self.client.rpc("session.rename", {"sessionId": sid, "title": row["title"]})
                self.store.save()
            except RuntimeFailure:
                row["status"] = "failed"
                self.store.save()
                raise
            return self.summary(row)

    @staticmethod
    def summary(row):
        result = {
            key: row[key]
            for key in ("id", "mode", "title", "workspace_id", "status", "model", "updated_at")
        }
        if isinstance(result["updated_at"], (int, float)):
            result["updated_at"] = datetime.fromtimestamp(result["updated_at"], UTC).isoformat()
        if row.get("deleted_at") is not None:
            deleted_at = row["deleted_at"]
            result["deleted_at"] = (
                datetime.fromtimestamp(deleted_at, UTC).isoformat()
                if isinstance(deleted_at, (int, float))
                else deleted_at
            )
            if isinstance(deleted_at, (int, float)):
                result["purge_at"] = datetime.fromtimestamp(
                    deleted_at + SESSION_RETENTION_SECONDS, UTC
                ).isoformat()
            if row.get("purge_started_at") is not None:
                result["purge_state"] = "pending"
        return result

    async def list_sessions(self, view="active"):
        if view not in {"active", "deleted", "all"}:
            raise StoreError("未知的会话列表视图", "invalid_session_view", 422)
        if view in {"deleted", "all"}:
            await self.purge_expired_sessions()
        rows = sorted(
            self.store.data["sessions"].values(),
            key=lambda row: row.get("deleted_at") or row["updated_at"],
            reverse=True,
        )
        rows = [
            row
            for row in rows
            if view == "all"
            or (view == "deleted" and row.get("deleted_at") is not None)
            or (view == "active" and row.get("deleted_at") is None)
        ]
        active_rows = [row for row in rows if row.get("deleted_at") is None]
        native = await self.client.rpc("session.list", {}) if active_rows else {"items": []}
        running = {item["sessionId"]: item["running"] for item in native["items"]}
        results = []
        for row in rows:
            result = self.summary(row)
            if row.get("deleted_at") is not None:
                results.append(result)
                continue
            children = (
                await self.client.rpc("subagent.list", {"parentSessionId": row["id"]})
                if row["created"]
                else {"entries": []}
            )
            child_running = any(child.get("activity") == "running" for child in children["entries"])
            if running.get(row["id"]) or child_running:
                result["status"] = "running"
            elif result["status"] == "running":
                # Recover completion during BFF downtime from the authoritative log.
                self.loaded.discard(row["id"])
                detail = await self.detail(row["id"])
                result["status"] = detail["status"]
            results.append(result)
        return results

    async def soft_delete_session(self, sid: str):
        await self.ensure_owned()
        async with self.lock:
            row = self.store.session(sid, include_deleted=True)
            if row.get("deleted_at") is not None:
                return self.summary(row)
            native = await self.client.rpc("session.list", {})
            native_running = any(
                item.get("sessionId") == sid and item.get("running") is True
                for item in native.get("items", [])
            )
            current_status = row.get("status", "idle")
            if current_status in SESSION_DELETE_BLOCKED_STATUSES and not native_running:
                entries = await self.client.history(sid) if row.get("created") else []
                current_status = project(entries)["status"]
                if current_status == "running":
                    current_status = "interrupted"
            children = (
                await self.client.rpc("subagent.list", {"parentSessionId": sid})
                if row.get("created")
                else {"entries": []}
            )
            child_running = any(
                child.get("activity") == "running" for child in children.get("entries", [])
            )
            waiting = any(
                value.get("ownerSessionId", value.get("sessionId")) == sid
                for value in [*self.approvals.values(), *self.questions.values()]
            )
            if (
                current_status in SESSION_DELETE_BLOCKED_STATUSES
                or native_running
                or child_running
                or waiting
            ):
                raise StoreError(
                    "会话仍在运行或等待处理，结束当前任务后才能删除",
                    "session_busy",
                    409,
                )
            row["status"] = current_status
            row["updated_at"] = time.time()
            self.store.save()
            return self.summary(self.store.soft_delete(sid))

    async def restore_session(self, sid: str):
        await self.ensure_owned()
        async with self.lock:
            row = self.store.session(sid, include_deleted=True)
            deleted_at = row.get("deleted_at")
            if isinstance(deleted_at, (int, float)) and deleted_at <= (
                time.time() - SESSION_RETENTION_SECONDS
            ):
                raise StoreError(
                    "会话已超过 30 天恢复期限，等待永久删除",
                    "session_restore_expired",
                    410,
                )
            return self.summary(self.store.restore(row["id"]))

    async def permanent_delete_session(self, sid: str):
        """Delete the DSH transcript first, then all Workbench-owned session data."""
        await self.ensure_owned()
        async with self.lock:
            row = self.store.session(sid, include_deleted=True)
            if row.get("deleted_at") is None:
                raise StoreError("会话必须先移至已删除", "session_not_deleted", 409)
            if row.get("native_deleted_at") is None:
                try:
                    native = await self.client.rpc("session.delete", {"sessionId": sid})
                except RuntimeFailure as exc:
                    if exc.code != "session/not-found":
                        raise
                    # A prior delete may have committed before Workbench wrote
                    # its tombstone acknowledgement. Authoritative absence is
                    # sufficient to finish the retained local purge safely.
                    native = {"deletedSessionIds": [sid]}
                    log.info("research_native_session_already_absent", session_id=sid)
                deleted_ids = native.get("deletedSessionIds")
                if not isinstance(deleted_ids, list) or sid not in deleted_ids:
                    raise RuntimeFailure(
                        "DSH 未确认原生日志已经删除，Workbench 数据保持不变",
                        "native_session_delete_unconfirmed",
                    )
                self.store.mark_native_deleted(sid)
            self.store.purge(sid)
            self.events.pop(sid, None)
            self.loaded.discard(sid)
            self.approvals = {
                key: value
                for key, value in self.approvals.items()
                if value.get("ownerSessionId", value.get("sessionId")) != sid
            }
            self.questions = {
                key: value
                for key, value in self.questions.items()
                if value.get("ownerSessionId", value.get("sessionId")) != sid
            }
            self.running.pop(sid, None)
            self.notify()
            return {"id": sid, "purged": True}

    async def purge_expired_sessions(self, now: float | None = None) -> int:
        """Best-effort purge of sessions whose recoverable window has elapsed."""
        cutoff = (time.time() if now is None else now) - SESSION_RETENTION_SECONDS
        expired = [
            row["id"]
            for row in self.store.data["sessions"].values()
            if isinstance(row.get("deleted_at"), (int, float)) and row["deleted_at"] <= cutoff
        ]
        purged = 0
        for sid in expired:
            try:
                await self.permanent_delete_session(sid)
                purged += 1
            except (RuntimeFailure, StoreError, OSError) as exc:
                log.warning(
                    "research_session_auto_purge_failed",
                    session_id=sid,
                    error_type=type(exc).__name__,
                )
        return purged

    async def detail(self, sid):
        row = self.store.session(sid)
        if not row["created"]:
            raise RuntimeFailure("该会话未成功创建，请新建研究", "session_create_failed")
        observed = self._cancel_observation(sid)
        entries = await self.delivery.reconcile_cancel(
            sid,
            self.client,
            lambda history=None: self.connected == {"mux", "host"}
            and self._cancel_observation(sid) == observed
            and (
                history is None
                or max((e["event"]["seq"] for e in history), default=-1) >= observed[1]
            )
            and not any(
                value.get("ownerSessionId", value["sessionId"]) == sid
                for value in [*self.approvals.values(), *self.questions.values()]
            ),
        )
        if entries is not None:
            self.events.setdefault(sid, {}).update(
                {entry["event"]["seq"]: entry for entry in entries}
            )
            self.running[sid] = False
            self.loaded.add(sid)
        if sid not in self.loaded:
            entries = await self.client.history(sid)
            native = await self.client.rpc("session.list", {})
            self.running[sid] = any(
                item["sessionId"] == sid and item["running"] for item in native["items"]
            )
            cache = self.events.setdefault(sid, {})
            cache.update({entry["event"]["seq"]: entry for entry in entries})
            self.loaded.add(sid)
        result = {**self.summary(row), **project(list(self.events.get(sid, {}).values()))}
        result["purpose"] = row.get("purpose", "research")
        result["creation_kind"] = row.get("creation_kind")
        latest_receipt = self.store.data["receipts"].get(f"{sid}:{row.get('delivery_key', '')}", {})
        result["capability"] = latest_receipt.get("capability")
        result["capability_history"] = [
            receipt["capability"]
            for key, receipt in self.store.data["receipts"].items()
            if key.startswith(sid + ":") and receipt.get("capability")
        ]
        # Native logs retain the execution contract. Only its product-owned
        # suffix is hidden in the human transcript, including after reload.
        markers = {
            receipt["delivery"]["marker"]
            for key, receipt in self.store.data["receipts"].items()
            if key.startswith(sid + ":") and receipt.get("delivery")
        }
        for message in result["messages"]:
            if message["role"] == "user":
                boundary = max(
                    (message["text"].rfind("\n\n" + marker) for marker in markers), default=-1
                )
                if boundary >= 0:
                    message["text"] = message["text"][:boundary]
        if self.running.get(sid):
            result["status"] = "running"
        elif result["status"] == "running":
            result.update(
                status="interrupted", error="原生执行已不在运行，但历史未记录完成；请补充指令继续"
            )
        if sid in self.errors:
            result.update(status="failed", error=self.errors[sid])
        result["files"] = self.store.files(sid)
        result["datasets"] = self.datahub.summaries(sid)
        result["approvals"] = [
            {"id": key, "title": value["toolName"], "detail": value.get("reason", "需要授权")}
            for key, value in self.approvals.items()
            if value.get("ownerSessionId", value["sessionId"]) == sid
        ]
        result["questions"] = [
            {
                "id": key,
                "text": "\n\n".join(question["question"] for question in value["questions"]),
                "items": value["questions"],
            }
            for key, value in self.questions.items()
            if value.get("ownerSessionId", value["sessionId"]) == sid
        ]
        if result["approvals"]:
            result["status"] = "awaiting_approval"
        children = await self.client.rpc("subagent.list", {"parentSessionId": sid})
        result["subagents"] = []
        for child in children["entries"]:
            view = {
                "id": child["id"],
                "name": child.get("label", child["id"]),
                "status": child.get("reason", "unknown"),
            }
            if child["kind"] == "child":
                self.child_parents[child["id"]] = sid
                try:
                    cached = self.child_views.get(child["id"])
                    if cached and time.monotonic() - cached[0] < 1:
                        projection = cached[1]
                    else:
                        page = await self.client.rpc(
                            "subagent.history",
                            {
                                "parentSessionId": sid,
                                "childSessionId": child["id"],
                                "mode": child["mode"],
                                "maxMessages": 100,
                            },
                        )
                        projection = {
                            **project(page["events"]),
                            "history_truncated": page.get("hasMore", False),
                        }
                        self.child_views[child["id"]] = (time.monotonic(), projection)
                    view.update(
                        status=(
                            "running" if child["activity"] == "running" else projection["status"]
                        ),
                        usage=projection["usage"],
                        duration_ms=projection.get("duration_ms"),
                        error=projection.get("error"),
                        history_truncated=projection["history_truncated"],
                    )
                    result["activities"].extend(
                        {
                            **activity,
                            "id": f"{child['id']}:{activity['id']}",
                            "agent_id": child["id"],
                        }
                        for activity in projection["activities"]
                    )
                except RuntimeFailure as exc:
                    view.update(status="unavailable", error=str(exc))
            result["subagents"].append(view)
        child_running = any(child.get("activity") == "running" for child in children["entries"])
        result["can_cancel"] = bool(self.running.get(sid) or child_running)
        if child_running and not result["approvals"]:
            result["status"] = "running"
        if self.connected != {"mux", "host"}:
            result.update(
                status="disconnected", error="DSH 事件连接已断开；未重发请求，也未判定任务完成"
            )
        result["delivery"] = await self.delivery.refresh(
            sid,
            list(self.events.get(sid, {}).values()),
            busy=result["can_cancel"],
            connected=self.connected == {"mux", "host"},
        )
        delivery = result["delivery"]
        result["can_recheck_stop"] = bool(
            delivery
            and delivery["status"] not in FINAL
            and latest_receipt.get("status") == "accepted"
            and not result["can_cancel"]
        )
        if (
            delivery
            and delivery.get("failure_code") == "cancel_terminal_event_missing"
            and not result["can_cancel"]
            and self.connected == {"mux", "host"}
        ):
            result.update(status="failed", error=self.errors.get(sid) or delivery["reasons"][0])
        return result

    def _cancel_observation(self, sid):
        return self.event_revision, max(self.events.get(sid, {}), default=-1), self.running.get(sid)

    async def send(
        self,
        sid,
        text,
        key,
        attachments=(),
        skill_id=None,
        formats=None,
        *,
        capability_id=None,
        capability_version=None,
        tool_ids=(),
        tabbit_tabs=(),
        tabbit_live_confirmed=False,
    ):
        await self.ensure_owned()
        async with self.lock:
            self.capabilities.assert_consistent()
            row = self.store.session(sid)
            if not row["created"]:
                raise StoreError("会话尚未创建")
            existing = self.store.data["receipts"].get(f"{sid}:{key}")
            if (
                existing
                and "capability_catalog" not in existing
                and not capability_id
                and not tool_ids
                and capability_version is None
                and not tabbit_tabs
                and not tabbit_live_confirmed
            ):
                legacy = {
                    "text": text,
                    "attachments": list(attachments),
                    "skill": skill_id,
                    "expected_formats": expected_formats(formats, skill_id),
                }
                legacy_digest = hashlib.sha256(
                    json.dumps(legacy, sort_keys=True).encode()
                ).hexdigest()
                if existing["digest"] == legacy_digest:
                    if existing["status"] == "accepted":
                        return {"accepted": True}
                    raise RuntimeFailure(
                        "此请求受理结果未知；请检查会话历史，不要重复发送", "admission_unknown"
                    )
            if capability_id and skill_id and capability_id != skill_id:
                raise CapabilityError("skill_id 与 capability_id 冲突", "selection_conflict", 409)
            if capability_version is not None and not capability_id:
                raise CapabilityError("版本必须与 capability_id 一起选择")
            if any(tool not in SELECTABLE for tool in tool_ids):
                raise CapabilityError(
                    "只能选择实际研究工具；内部控制工具不可选择", "tool_unavailable"
                )
            selected_id = capability_id or (
                skill_id if skill_id in self.capabilities.data["items"] else None
            )
            previous = self.store.data["receipts"].get(f"{sid}:{key}", {}).get("capability")
            # A replay of the identical request refers to its original accepted
            # immutable version even when management later disables that version.
            if (
                previous
                and selected_id == previous["id"]
                and capability_version in (None, previous["version"])
            ):
                selection = previous
            else:
                selection = (
                    self.capabilities.selection(selected_id, capability_version)
                    if selected_id
                    else None
                )
            defaults = selection["default_formats"] if selection else None
            required = expected_formats(formats if formats is not None else defaults, skill_id)
            payload = {
                "text": text,
                "attachments": list(attachments),
                "skill": skill_id,
                "expected_formats": required,
                "capability": selection,
                "tool_ids": list(tool_ids),
                "tabbit_tabs": list(tabbit_tabs),
                "tabbit_live_confirmed": tabbit_live_confirmed,
            }
            digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            if f"{sid}:{key}" in self.store.data["receipts"]:
                self.store.reserve(sid, key, digest)
                if self.store.receipt(sid, key)["status"] == "accepted":
                    return {"accepted": True}
                raise RuntimeFailure(
                    "此请求受理结果未知；请检查会话历史，不要重复发送", "admission_unknown"
                )
            if self.connected != {"mux", "host"}:
                raise RuntimeFailure("DSH 事件未连接，暂不提交问题")
            current = await self.detail(sid)
            native = await self.client.rpc("session.list", {})
            busy = current["can_cancel"] or any(
                item["sessionId"] == sid and item["running"] for item in native["items"]
            )
            if busy or (current["delivery"] and current["delivery"]["status"] not in FINAL):
                raise RuntimeFailure(
                    "上一任务或子 Agent 尚未结束，或交付/受理结果未确认；请先等待并刷新，不要重复提交",
                    "delivery_pending",
                )
            files = [
                self.store.file_path(sid, fid).relative_to(self.store.directory(sid)).as_posix()
                for fid in attachments
            ]
            images = []
            image_bytes = 0
            media = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
                ".gif": "image/gif",
            }
            for fid, filename in zip(attachments, files, strict=True):
                mime = media.get(Path(filename).suffix.lower())
                if mime:
                    stream, name = self.store.open_file(sid, fid)
                    with stream:
                        raw = stream.read(8 * 1024 * 1024 + 1)
                    image_bytes += len(raw)
                    if len(raw) > 8 * 1024 * 1024 or image_bytes > 16 * 1024 * 1024:
                        raise StoreError("单张图片最多 8 MB，每条消息图片合计最多 16 MB")
                    images.append(
                        {
                            "type": "image",
                            "mediaType": mime,
                            "name": name,
                            "data": base64.b64encode(raw).decode("ascii"),
                        }
                    )
            native_skill = selection["native_name"] if selection else skill_id
            if native_skill:
                skills = await self.skill_catalog(sid)
                if native_skill not in {skill["name"] for skill in skills["skills"]}:
                    raise CapabilityError(
                        "能力未由 DSH 原生发现；请等待目录观察，旧实例需空闲后更新启动配置",
                        "native_discovery_pending",
                        409,
                    )
            if selection:
                self.capabilities.snapshot(selection, self.store.directory(sid))
            capability_snapshots = self.capabilities.snapshot_catalog(self.store.directory(sid))
            tabbit_markers = await self.tabbit.live_markers(
                sid,
                key,
                list(tabbit_tabs),
                confirmed=tabbit_live_confirmed,
            )
            delivery = self.delivery.begin(sid, key, required)
            if not self.store.reserve(sid, key, digest, delivery):
                status = self.store.receipt(sid, key)["status"]
                if status == "accepted":
                    return {"accepted": True}
                raise RuntimeFailure(
                    "此请求受理结果未知；请检查会话历史，不要重复发送", "admission_unknown"
                )
            self.store.receipt(sid, key)["capability_catalog"] = capability_snapshots
            if selection:
                self.store.receipt(sid, key)["capability"] = selection
            self.store.save()
            prompt = text
            if tabbit_markers:
                prompt += "\n\nTabbit 标签页引用：" + " ".join(tabbit_markers)
            prompt += "\n\n" + delivery["marker"]
            if formats is not None:
                prompt += "\n用户显式选择的输出格式优先于 Skill 默认格式。"
                if not required:
                    prompt += "本次无需文件，直接在聊天中回答。"
            if required:
                prompt += (
                    "\n本任务文件交付要求："
                    + "、".join(required)
                    + "。必须在本次执行中新建或更新 outputs/ 下的实际文件；"
                    "聊天正文、inputs 附件和历史未修改文件不算交付。"
                    "Office 文件必须重开并有实际内容；Excel 至少包含表头与数据行。"
                    "仅使用已可用的严格沙箱工具生成，不虚构文件、数据或验证。"
                )
            if files:
                prompt += "\n\n附件（仅本会话 inputs 目录）：\n" + "\n".join(files)
            if selection:
                prompt += "\n\n本次能力与只读资源快照：" + json.dumps(selection, ensure_ascii=False)
            if tool_ids:
                prompt += "\n用户选择的研究工具意图（不改变原生审批、权限和限制）：" + ", ".join(
                    tool_ids
                )
            if row["mode"] == "claw":
                prompt += (
                    "\n\n使用 DSH 原生子 Agent 分工研究；只使用实际可用工具，不虚构执行或产物。"
                )
            prompt += (
                "\n\n语言契约：除非用户在当前请求中明确要求其他语言，"
                "所有可见过程说明、工具调用前后说明、提问、错误解释、总结和最终答复"
                "均使用简体中文。代码、API 名称、专有名词和必要原文引用可保留原语言，"
                "但解释必须使用中文。英文工具、资料或子 Agent 结果必须先翻译或中文归纳，"
                "不得直接以英文回答透传。"
            )
            if native_skill:
                prompt = f"/{native_skill} " + prompt
            try:
                result = await self.client.rpc(
                    "session.prompt",
                    {
                        "sessionId": sid,
                        "mode": "queue",
                        "content": [{"type": "text", "text": prompt}, *images],
                        "clientTimeZone": "Asia/Shanghai",
                    },
                )
                self.store.receipt(sid, key, "accepted")
                row.update(updated_at=time.time(), status="running")
                self.store.save()
                self.running[sid] = True
                self.errors.pop(sid, None)
                self.notify()
                log.info("research_prompt_admitted", session_id=sid)
                return result
            except RuntimeFailure:
                self.store.receipt(sid, key, "unknown")
                raise

    async def skill_catalog(self, sid):
        await self.ensure_owned()
        self.store.session(sid)
        # skill.list addresses only attached native sessions. models invokes
        # DSH's recorded-preset cold resume without submitting another prompt.
        await self.client.rpc("session.models", {"sessionId": sid})
        return await self.client.rpc("skill.list", {"sessionId": sid})

    async def _capability_idle(self):
        """Called under the same lock as send; ambiguous native state fails closed."""
        self.capabilities.assert_consistent()
        await self.ensure_owned()
        if self.connected != {"mux", "host"}:
            raise CapabilityError(
                "原生状态未连接，草稿已保留但不能发布", "runtime_state_uncertain", 409
            )
        native = await self.client.rpc("session.list", {})
        if any(item.get("running") is not False for item in native["items"]):
            raise CapabilityError("存在活动或未确认的原生回合，草稿已保留", "capability_busy", 409)
        for row in self.store.data["sessions"].values():
            if not row["created"]:
                continue
            children = await self.client.rpc("subagent.list", {"parentSessionId": row["id"]})
            if any(
                c.get("kind") != "child" or c.get("activity") != "inactive"
                for c in children["entries"]
            ):
                raise CapabilityError(
                    "存在活动或无法确认的子 Agent，草稿已保留", "capability_busy", 409
                )
            detail = await self.detail(row["id"])
            if (
                detail["can_cancel"]
                or detail["status"]
                in {"running", "disconnected", "interrupted", "awaiting_approval"}
                or (detail["delivery"] and detail["delivery"]["status"] not in FINAL)
            ):
                raise CapabilityError(
                    "会话活动、恢复或交付受理状态尚未确认", "capability_busy", 409
                )
        if any(
            receipt["status"] in {"pending", "unknown"}
            for receipt in self.store.data["receipts"].values()
        ):
            raise CapabilityError("存在尚未确认的受理请求，草稿已保留", "capability_busy", 409)
        return True

    async def _mcp_idle_gate(self):
        """Use the capability admission lock and return the runtime's exact boolean contract."""

        async with self.lock:
            await self._capability_idle()
        return True

    async def _restart_mcp_runtime(self, _bindings):
        """Restart only the owned DSH process; Research Web remains online."""

        if self._runtime_manager is None:
            raise RuntimeError("mcp_runtime_manager_unavailable")
        await asyncio.to_thread(self._runtime_manager.restart_runtime)
        return True

    async def change_capability(self, cid, action, version=None):
        async with self.lock:
            await self._capability_idle()
            if action == "publish":
                result = self.capabilities.publish(cid)
            else:
                result = self.capabilities.transition(cid, action, version)
            self.notify()
            return result

    async def create_capability_session(self, kind, goal):
        session = await self.create("fingpt", "创建 Skill" if kind == "skill" else "创建 Workflow")
        row = self.store.session(session["id"])
        row["purpose"] = "capability_creation"
        row["creation_kind"] = kind
        self.store.save()
        draft = (
            f"请为以下目标设计一个{kind}候选包：{goal}\n"
            "仅使用当前可用工具，将候选 SKILL.md 和 capability.json 写入 outputs。"
            "outputs 已存在；使用 outputs/ 相对路径，不要探测宿主 cwd、扫描宿主或创建宿主目录。\n"
            "不得发布、安装、执行候选包，不得改变权限或依赖。输出文件是待用户审查的草稿。\n"
            "capability.json 直接是元数据对象，不包裹 metadata/kind；不添加未声明字段。"
            "填全 name/slug/description/category/inputs/scenarios/default_formats/required_tools/dependencies。"
            "name/description/category 使用中文，slug 使用 kebab-case；inputs 的每项只有 name/label/type/required，"
            "type 只能为 text/file/date/number，不使用 string、list[number] 等类型；required 为布尔值。"
            "scenarios 是非空字符串数组；default_formats 只列目标需要的格式，不要全选，允许值见 schema。"
            "required_tools 只列需要的真实工具ID；dependencies 只列第三方发行版依赖，"
            "json/csv/pathlib 等 Python 标准库不列入，只有标准库时 dependencies=[]，不得自动安装依赖。\n"
            "capability.json 的完整约束来自当前 Metadata 模型（含必填字段、枚举和 additionalProperties:false）：\n"
            f"```json\n{json.dumps(Metadata.model_json_schema(), ensure_ascii=False)}\n```\n"
            "SKILL.md 使用 YAML frontmatter name=slug、description，后接实际步骤正文。\n"
            "除研究 Python 脚本、文档、图像与模板外不要生成执行文件；依赖不足明确注明。"
        )
        if kind == "workflow":
            draft += (
                '\n另写 outputs/workflow.json，根对象只有 "steps"：非空、有序的步骤对象数组（最多40项）。'
                "每步只含 title/instruction，以及可选 skill_id/tools；skill_id 只引用目录中已启用 Skill 的产品ID。"
                "步骤对象遵循当前 Step 模型，不添加未声明字段：\n"
                f"```json\n{json.dumps(Step.model_json_schema(), ensure_ascii=False)}\n```"
            )
        return {
            **session,
            "purpose": "capability_creation",
            "draft": draft,
            "auto_submitted": False,
            "auto_published": False,
        }

    async def capability_from_artifact(self, sid, fid):
        async with self.lock:
            row = self.store.session(sid)
            if row.get("purpose") != "capability_creation":
                raise CapabilityError(
                    "只能从专用能力创建会话审查实际产物", "creation_session_required", 409
                )
            current = await self.detail(sid)
            if current["can_cancel"] or current["status"] in {
                "disconnected",
                "interrupted",
                "awaiting_approval",
            }:
                raise CapabilityError("候选包仍在生成或状态未确认", "capability_busy", 409)
            inventory = {item["id"]: item for item in self.store.files(sid)}
            relative = row["files"].get(fid, "")
            if (
                fid not in inventory
                or inventory[fid]["kind"] != "outputs"
                or not relative.startswith("outputs/")
            ):
                raise CapabilityError("只能导入本会话实际 outputs 产物", "artifact_not_output", 409)
            stream, name = self.store.open_file(sid, fid)
            with stream:
                raw = stream.read(MAX_COMPRESSED + 1)
            if name == "SKILL.md":
                # Bundle only the actual explicit root-level candidate files; no host path input.
                import io
                import zipfile

                packed = io.BytesIO()
                companions = {
                    row["files"][item["id"]]: item["id"]
                    for item in inventory.values()
                    if item["kind"] == "outputs"
                }
                with zipfile.ZipFile(packed, "w", zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr("SKILL.md", raw)
                    for filename in ("capability.json", "workflow.json"):
                        path = f"outputs/{filename}"
                        file_id = companions.get(path)
                        if file_id is None:
                            # Absent historical entries are not current companions. A
                            # present path excluded by the safe listing must still fail.
                            try:
                                (self.store.directory(sid) / path).lstat()
                            except FileNotFoundError:
                                continue
                            except OSError as exc:
                                log.warning(
                                    "research_capability_companion_unavailable",
                                    session_id=sid,
                                    resource_name=filename,
                                    error_type=type(exc).__name__,
                                )
                                raise StoreError("候选伴随文件无法安全读取") from exc
                            log.warning(
                                "research_capability_companion_unsafe",
                                session_id=sid,
                                resource_name=filename,
                            )
                            raise StoreError("候选伴随文件不是当前安全普通文件")
                        resource, filename = self.store.open_file(sid, file_id)
                        with resource:
                            archive.writestr(filename, resource.read(MAX_COMPRESSED + 1))
                raw, name = packed.getvalue(), "candidate.zip"
            parsed, _ = import_package(name, raw)
            if parsed["kind"] != row.get("creation_kind"):
                raise CapabilityError(
                    "候选包类型与创建会话目标不一致；请修正实际文件后重新审查，不会自动转换类型",
                    "creation_kind_conflict",
                    422,
                )
            return self.capabilities.import_bytes(
                name, raw, source="conversation", origin={"session_id": sid, "file_id": fid}
            )

    async def approve(self, sid, aid, decision):
        await self.ensure_owned()
        self.store.session(sid)
        request = self.approvals.get(aid)
        if not request or request.get("ownerSessionId", request["sessionId"]) != sid:
            raise StoreError("审批已失效或不属于该会话")
        log.info("research_approval_response", decision=decision)
        result = await self.client.respond(
            request["rpc_id"],
            {
                "sessionId": request["sessionId"],
                "approvalId": aid,
                "outcome": "allowed-once" if decision == "approve" else "rejected",
            },
        )
        if result.get("accepted") is True:
            # The native runtime may not emit its separate cancellation frame
            # until after the turn resumes.  Once it has accepted the answer,
            # the interaction is no longer pending in this BFF either.
            self.approvals.pop(aid, None)
            self.event_revision += 1
            self.notify()
        self.store.audit(
            "approval",
            "approved" if decision == "approve" else "denied",
            session_id=sid,
            tool=request.get("toolName"),
        )
        return result

    async def cancel(self, sid):
        await self.ensure_owned()
        async with self.lock:
            return await self._cancel(sid)

    async def _cancel(self, sid):
        self.store.session(sid)
        delivery = self.delivery.current(sid)
        request = None
        if delivery and delivery["status"] not in FINAL:
            request = {
                "key": self.store.session(sid)["delivery_key"],
                "task_id": delivery["task_id"],
                "marker": delivery["marker"],
                "requested_at": time.time(),
                "accepted": False,
            }
            delivery["cancel_request"] = request
            self.store.save()
        await self.datahub.cancel(sid)
        try:
            result = await self.client.rpc("session.cancel", {"sessionId": sid})
            if request is not None and result.get("accepted") is True:
                request["accepted"] = True
                self.store.save()
        except RuntimeFailure as exc:
            if exc.code not in {"session-not-found", "session/not-found"}:
                raise
            log.info("research_cancel_parent_offline", session_id=sid)
            result = {"accepted": True}
        children = await self.client.rpc("subagent.list", {"parentSessionId": sid})
        for child in children["entries"]:
            if child.get("kind") == "child" and child.get("mode") == "continuable":
                await self.client.rpc(
                    "subagent.interrupt",
                    {"parentSessionId": sid, "childSessionId": child["id"], "mode": "continuable"},
                )
        if request is not None:
            try:
                await self.detail(sid)
            except RuntimeFailure as exc:
                log.warning("research_cancel_followup_unavailable", code=exc.code)
        self.notify()
        self.store.audit("research", "cancelled", session_id=sid)
        return result

    async def answer(self, sid, qid, answers):
        await self.ensure_owned()
        self.store.session(sid)
        request = self.questions.get(qid)
        if not request or request.get("ownerSessionId", request["sessionId"]) != sid:
            raise StoreError("提问已失效或不属于该会话")
        expected = {question["id"] for question in request["questions"]}
        if {answer["id"] for answer in answers} != expected or len(answers) != len(expected):
            raise StoreError("请完整回答该组问题")
        questions = {question["id"]: question for question in request["questions"]}
        for answer in answers:
            if (
                questions[answer["id"]].get("multiSelect") is not True
                and len(answer.get("selected", [])) > 1
            ):
                log.warning("research_question_single_selection_rejected")
                raise StoreError("单选问题只能选择一个选项")
        return await self.client.respond(
            qid, {"sessionId": request["sessionId"], "answer": {"answers": answers}}
        )
