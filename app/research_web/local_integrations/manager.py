"""Truthful host capability projections without launching vendor software."""

import asyncio
import copy
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import re
import stat
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable, Mapping
from uuid import uuid4

from core.observability import get_logger

log = get_logger(__name__)

CATEGORY_LABELS = {
    "local_service": "本机服务",
    "folders": "文件夹同步",
    "office": "Office 与金融插件",
    "browsers": "浏览器扩展",
    "mcp": "本地 MCP",
}
ALLOWED_STATUSES = {
    "可用",
    "待配置",
    "待授权",
    "待验证",
    "未发现",
    "未登录",
    "受限",
    "异常",
    "不适用",
}
DISCOVERY_VALUES = {"已发现", "未发现", "未配置", "未扫描", "异常", "不适用"}
AUTHORIZATION_VALUES = {"无需授权", "已授权", "待授权", "待验证", "未登录", "受限", "异常", "不适用"}
VERIFICATION_VALUES = {"已验证", "待验证", "未通过", "受限", "异常", "不适用"}
SNAPSHOT_FIELDS = {"platform", "service", "summary", "categories", "items", "last_checked_at"}
SERVICE_FIELDS = {"online", "label"}
SUMMARY_FIELDS = {"available", "needs_attention", "total"}
CATEGORY_FIELDS = {"id", "label", "item_ids"}
ITEM_FIELDS = {
    "id",
    "category",
    "label",
    "discovery",
    "authorization",
    "verification",
    "callable",
    "status",
    "message",
    "detail",
    "capabilities",
    "actions",
    "last_checked_at",
    "last_verified_at",
}
ACTION_FIELDS = {"id", "label", "href"}
SAFE_ID = re.compile(r"^[a-z0-9_]+$")
SAFE_DATA_ACTION = re.compile(r"^#/settings/data\?connection=[a-z0-9_]+$")
SENSITIVE_ENVIRONMENT_KEY = re.compile(r"(?:token|secret|password|credential|api.?key)", re.I)
MAX_PROBE_RECORDS = 128
MAX_VERIFICATION_RECORDS = 128
MAX_WIND_ADDIN_FINGERPRINT_ENTRIES = 512
VERIFICATION_TTL_SECONDS = 24 * 60 * 60
WIND_VERIFICATION_TTL_SECONDS = 5 * 60
VERIFICATION_TARGETS = {"excel", "word", "powerpoint", "wind_excel"}
VERIFICATION_ITEMS = {
    "excel": ("excel_app", "excel_automation_bridge"),
    "word": ("word_app",),
    "powerpoint": ("powerpoint_app",),
    "wind_excel": ("wind_terminal", "wind_excel_addin"),
}
VERIFICATION_MESSAGES = {
    "available": ("可用", "已授权", "已验证", "真实打开、操作、保存与重新读取验证已通过。"),
    "authorization_required": ("待授权", "待授权", "待验证", "需要允许 Research Workbench 控制对应的 Office 应用。"),
    "login_required": ("未登录", "未登录", "待验证", "已发现组件，但厂商会话尚未登录或不可用。"),
    "timeout": ("异常", "待验证", "异常", "真实验证超时；验证任务已停止，请确认应用状态后重试。"),
    "formula_error": ("待验证", "待验证", "未通过", "工作簿已运行，但公式或必需单元格验证未通过。"),
    "failed": ("异常", "待验证", "异常", "真实验证失败，请查看本地安全日志后重试。"),
}


class LocalIntegrationError(Exception):
    """Stable, non-secret error returned by the local integration boundary."""

    def __init__(self, message: str, code: str = "local_integration_error", status: int = 500):
        super().__init__(message)
        self.code = code
        self.status = status


def _default_module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def _default_registry_app_exists(executable: str) -> bool:
    if platform.system().lower() != "windows":
        return False
    try:
        import winreg  # type: ignore[import-not-found]

        key_path = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{executable}"
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive, key_path):
                    return True
            except OSError:
                continue
    except (ImportError, AttributeError, OSError):
        return False
    return False


@dataclass(frozen=True)
class DetectionEnvironment:
    """Injectable host facts keep macOS and Windows detection testable and side-effect free."""

    system: str
    home: Path
    application_roots: tuple[Path, ...]
    office_addin_roots: tuple[Path, ...]
    module_available: Callable[[str], bool]
    registry_app_exists: Callable[[str], bool]
    environment_variables: Mapping[str, str]

    @classmethod
    def current(cls) -> "DetectionEnvironment":
        home = Path.home()
        return cls(
            system=platform.system(),
            home=home,
            application_roots=(Path("/Applications"), home / "Applications"),
            office_addin_roots=(
                home
                / "Library/Group Containers/UBF8T346G9.Office/User Content.localized/Add-Ins.localized",
                home / "Library/Group Containers/UBF8T346G9.Office/User Content.localized/Add-ins",
                home / "Library/Group Containers/UBF8T346G9.Office/User Content/Add-Ins",
                home / "Library/Containers/com.microsoft.Excel/Data/Documents/wef",
            ),
            module_available=_default_module_available,
            registry_app_exists=_default_registry_app_exists,
            environment_variables=dict(os.environ),
        )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def _named_entry_exists(roots: tuple[Path, ...], names: tuple[str, ...]) -> bool:
    return any(_exists(root / name) for root in roots for name in names)


def _wind_addin_paths(roots: tuple[Path, ...]) -> tuple[Path, ...]:
    matches: list[Path] = []
    for root in roots:
        try:
            if root.is_dir():
                matches.extend(
                    entry for entry in root.iterdir() if entry.name.lower().startswith("windaddin")
                )
        except OSError:
            continue
    return tuple(sorted(matches, key=lambda path: str(path).casefold()))


def _wind_addin_exists(roots: tuple[Path, ...]) -> bool:
    return bool(_wind_addin_paths(roots))


def _windows_roots(environment: DetectionEnvironment) -> tuple[Path, ...]:
    values = (
        environment.environment_variables.get("ProgramFiles"),
        environment.environment_variables.get("ProgramFiles(x86)"),
    )
    return tuple(Path(value) for value in values if value)


def _windows_app_exists(
    environment: DetectionEnvironment, executable: str, relative_paths: tuple[str, ...]
) -> bool:
    if environment.registry_app_exists(executable):
        return True
    return any(
        _exists(root / relative)
        for root in _windows_roots(environment)
        for relative in relative_paths
    )


def _item(
    *,
    item_id: str,
    category: str,
    label: str,
    discovery: str,
    authorization: str,
    verification: str,
    callable_value: bool,
    status: str,
    message: str,
    detail: str,
    checked_at: str,
    capabilities: tuple[str, ...] = (),
    actions: tuple[dict[str, str], ...] = (),
    last_verified_at: str | None = None,
) -> dict:
    if status not in ALLOWED_STATUSES:
        raise ValueError("unsupported local integration status")
    return {
        "id": item_id,
        "category": category,
        "label": label,
        "discovery": discovery,
        "authorization": authorization,
        "verification": verification,
        "callable": callable_value,
        "status": status,
        "message": message,
        "detail": detail,
        "capabilities": list(capabilities),
        "actions": [dict(action) for action in actions],
        "last_checked_at": checked_at,
        "last_verified_at": last_verified_at,
    }


class LocalIntegrationManager:
    """Build and persist safe local facts; probes never launch detected software."""

    def __init__(
        self,
        state_root: Path,
        *,
        environment: DetectionEnvironment | None = None,
        detector: Callable[[], dict] | None = None,
        verifier: Callable[[str], dict] | None = None,
        context_fingerprint: Callable[[str], str] | None = None,
        wind_session_ready: Callable[[], bool | None] | None = None,
        probe_timeout_seconds: float = 10.0,
        verification_ttl_seconds: float = VERIFICATION_TTL_SECONDS,
    ):
        self.state_root = Path(state_root)
        self.environment = environment or DetectionEnvironment.current()
        self.detector = detector
        self.verifier = verifier
        self.context_fingerprint = context_fingerprint
        self.wind_session_ready = wind_session_ready
        self.probe_timeout_seconds = max(0.01, float(probe_timeout_seconds))
        self.verification_ttl_seconds = max(0.0, float(verification_ttl_seconds))
        self._detector_executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="local-integration-probe"
        )
        self._active_detection: Future | None = None
        self.probes: dict[str, dict] = {}
        self.probe_keys: dict[str, str] = {}
        self.probe_tasks: dict[str, asyncio.Task] = {}
        self.verifications: dict[str, dict] = {}
        self.verification_keys: dict[str, tuple[str, str]] = {}
        self.verification_tasks: dict[str, asyncio.Task] = {}
        self._state_lock = threading.RLock()
        self.verification_results: dict[str, dict] = self._load_verification_results()
        self._latest: dict | None = None

    @property
    def state_path(self) -> Path:
        return self.state_root / "local-integrations.json"

    def _load_verification_results(self) -> dict[str, dict]:
        path = self.state_root / "local-integrations.json"
        try:
            if not path.exists():
                return {}
            metadata = path.lstat()
            if (
                path.is_symlink()
                or not stat.S_ISREG(metadata.st_mode)
                or metadata.st_size > 1024 * 1024
            ):
                raise OSError("unsafe local integration state")
            payload = json.loads(path.read_text(encoding="utf-8"))
            values = payload.get("verifications", {})
            if not isinstance(values, dict):
                return {}
            return {
                target: {
                    "outcome": value["outcome"],
                    "completed_at": value["completed_at"],
                    "context_fingerprint": value["context_fingerprint"],
                }
                for target, value in values.items()
                if target in VERIFICATION_TARGETS
                and isinstance(value, dict)
                and value.get("outcome") in VERIFICATION_MESSAGES
                and isinstance(value.get("completed_at"), str)
                and len(value["completed_at"]) <= 64
                and isinstance(value.get("context_fingerprint"), str)
                and re.fullmatch(r"[0-9a-f]{64}", value["context_fingerprint"])
            }
        except (OSError, ValueError, TypeError, KeyError) as exc:
            log.warning("local_integration_state_read_failed", error_type=type(exc).__name__)
            return {}

    def snapshot(self, *, persist: bool = True) -> dict:
        try:
            detected = self._detect_snapshot()
            return self._publish_snapshot(detected, persist=persist)
        except LocalIntegrationError:
            raise
        except Exception as exc:  # noqa: BLE001 - host inspection is a hard safety boundary.
            log.warning("local_integration_snapshot_failed", error_type=type(exc).__name__)
            raise LocalIntegrationError("本机能力检测失败，请查看本地日志") from exc

    def _detect_snapshot(self) -> dict:
        value = self.detector() if self.detector is not None else self._detect()
        return copy.deepcopy(value)

    def _publish_snapshot(self, detected: dict, *, persist: bool) -> dict:
        with self._state_lock:
            results = copy.deepcopy(self.verification_results)
            value = self._apply_verification_results(copy.deepcopy(detected), results)
            self._validate_snapshot(value)
            if persist:
                self._persist(value, verification_results=results)
                self._latest = copy.deepcopy(value)
            return value

    def _commit_verification(
        self,
        target: str,
        outcome: str,
        completed_at: str,
        detected: dict,
    ) -> dict:
        with self._state_lock:
            staged_results = copy.deepcopy(self.verification_results)
            staged_results[target] = {
                "outcome": outcome,
                "completed_at": completed_at,
                "context_fingerprint": self._verification_context_fingerprint(target),
            }
            snapshot = self._apply_verification_results(copy.deepcopy(detected), staged_results)
            self._validate_snapshot(snapshot)
            self._persist(snapshot, verification_results=staged_results)
            self.verification_results = staged_results
            self._latest = copy.deepcopy(snapshot)
            return snapshot

    def _apply_verification_results(
        self, snapshot: dict, results: dict[str, dict] | None = None
    ) -> dict:
        results = self.verification_results if results is None else results
        if not results:
            return snapshot
        items = {item["id"]: item for item in snapshot.get("items", [])}
        for target, result in results.items():
            if not self._verification_result_is_current(target, result):
                continue
            outcome = result.get("outcome", "failed")
            status, authorization, verification, message = VERIFICATION_MESSAGES.get(
                outcome, VERIFICATION_MESSAGES["failed"]
            )
            checked_at = result.get("completed_at") or snapshot["last_checked_at"]
            for item_id in VERIFICATION_ITEMS[target]:
                item = items.get(item_id)
                if item is None or item.get("discovery") != "已发现":
                    continue
                item.update(
                    status=status,
                    authorization=authorization,
                    verification=verification,
                    callable=outcome == "available",
                    message=message,
                    detail=(
                        "该状态来自最近五分钟内的真实验证；厂商会话变化后需重新验证。"
                        if target == "wind_excel"
                        else "该状态来自显式真实验证，不由软件发现结果推断。"
                    ),
                    last_verified_at=checked_at,
                )
        snapshot["summary"] = {
            "available": sum(item["status"] == "可用" for item in snapshot["items"]),
            "needs_attention": sum(
                item["status"] not in {"可用", "不适用"} for item in snapshot["items"]
            ),
            "total": len(snapshot["items"]),
        }
        return snapshot

    def _verification_result_is_current(self, target: str, result: dict) -> bool:
        try:
            completed_at = datetime.fromisoformat(result["completed_at"].replace("Z", "+00:00"))
            if completed_at.tzinfo is None:
                return False
            age = datetime.now(UTC) - completed_at.astimezone(UTC)
            if age < timedelta(0):
                return False
            ttl_seconds = self.verification_ttl_seconds
            if target == "wind_excel":
                ttl_seconds = min(ttl_seconds, WIND_VERIFICATION_TTL_SECONDS)
                ready = (
                    self.wind_session_ready()
                    if self.wind_session_ready is not None
                    else self._wind_session_is_ready()
                )
                if ready is False:
                    return False
            if age > timedelta(seconds=ttl_seconds):
                return False
            return result.get("context_fingerprint") == self._verification_context_fingerprint(
                target
            )
        except (KeyError, TypeError, ValueError, OSError):
            return False

    @staticmethod
    def _wind_session_is_ready() -> bool | None:
        try:
            import WindPy  # type: ignore[import-not-found]

            session = getattr(WindPy, "w", None)
            is_connected = getattr(session, "isconnected", None)
            return bool(is_connected()) if callable(is_connected) else None
        except ModuleNotFoundError as exc:
            if exc.name == "WindPy":
                return None
            log.warning(
                "local_integration_wind_session_check_failed",
                error_type=type(exc).__name__,
            )
            return False
        except Exception as exc:  # noqa: BLE001 - vendor failures must not break the snapshot.
            log.warning(
                "local_integration_wind_session_check_failed",
                error_type=type(exc).__name__,
            )
            return False

    @staticmethod
    def _path_fingerprint(path: Path) -> dict:
        try:
            metadata = path.stat()
            identity = {
                "name": path.name,
                "type": "directory" if path.is_dir() else "file",
                "size": metadata.st_size,
                "modified": metadata.st_mtime_ns,
            }
            if path.is_file() and metadata.st_size <= 32 * 1024 * 1024:
                digest = hashlib.sha256()
                with path.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                identity["sha256"] = digest.hexdigest()
            return identity
        except OSError:
            return {"name": path.name, "state": "unavailable"}

    @classmethod
    def _wind_addin_fingerprint(cls, path: Path) -> dict:
        identity = cls._path_fingerprint(path)
        if identity.get("type") != "directory":
            return identity

        entries: list[dict] = []
        try:
            for root, directories, filenames in os.walk(path, followlinks=False):
                directories.sort()
                filenames.sort()
                current = Path(root)
                directories[:] = [name for name in directories if not (current / name).is_symlink()]
                for name in filenames:
                    if len(entries) >= MAX_WIND_ADDIN_FINGERPRINT_ENTRIES:
                        identity["entries_truncated"] = True
                        return identity | {"entries": entries}
                    candidate = current / name
                    relative = candidate.relative_to(path).as_posix()
                    if candidate.is_symlink():
                        entries.append({"path": relative, "state": "symlink"})
                    else:
                        entries.append(
                            {"path": relative, "fingerprint": cls._path_fingerprint(candidate)}
                        )
            identity["entries"] = entries
        except (OSError, ValueError):
            identity["entries_state"] = "unavailable"
        return identity

    def _verification_context_fingerprint(self, target: str) -> str:
        if self.context_fingerprint is not None:
            raw = self.context_fingerprint(target)
            if not isinstance(raw, str):
                raise ValueError("invalid verification context fingerprint")
            return hashlib.sha256(raw.encode("utf-8")).hexdigest()

        app_names = {
            "excel": ("Microsoft Excel.app",),
            "word": ("Microsoft Word.app",),
            "powerpoint": ("Microsoft PowerPoint.app",),
            "wind_excel": ("Microsoft Excel.app", "Wind.app", "Wind金融终端.app"),
        }[target]
        facts: dict[str, object] = {
            "target": target,
            "system": self.environment.system.lower(),
            "apps": [
                self._path_fingerprint(root / name / "Contents/Info.plist")
                for root in self.environment.application_roots
                for name in app_names
                if _exists(root / name)
            ],
        }
        if target in {"excel", "wind_excel"}:
            try:
                version = importlib.metadata.version("xlwings")
            except importlib.metadata.PackageNotFoundError:
                version = "missing"
            spec = importlib.util.find_spec("xlwings")
            facts["xlwings"] = {
                "version": version,
                "origin": self._path_fingerprint(Path(spec.origin))
                if spec is not None and spec.origin
                else {"state": "missing"},
            }
        if target == "wind_excel":
            facts["addins"] = [
                self._wind_addin_fingerprint(candidate)
                for candidate in _wind_addin_paths(self.environment.office_addin_roots)
            ]
            try:
                from app.research_web.report_workflows.catalog import ReportWorkflowService

                catalog = ReportWorkflowService(self.state_root.parent)
                row = catalog._row("huaan-etf-weekly")
                version = row.get("current_version")
                if not isinstance(version, int):
                    raise ValueError("workflow_version_unavailable")
                manifest = catalog.manifest("huaan-etf-weekly", version)
                facts["workflow"] = {
                    "version": version,
                    "resources": [
                        self._path_fingerprint(
                            catalog.resource_path("huaan-etf-weekly", version, policy.workbook)
                        )
                        for policy in manifest.workbook_policies
                    ],
                }
            except Exception as exc:  # noqa: BLE001 - unavailable context invalidates evidence.
                facts["workflow"] = {
                    "state": "unavailable",
                    "error_type": type(exc).__name__,
                }

        serialized = json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _detect(self) -> dict:
        checked_at = _utc_now()
        system = self.environment.system.lower()
        platform_id = (
            "macos"
            if system in {"darwin", "macos", "mac"}
            else "windows"
            if system in {"windows", "win32", "win"}
            else "other"
        )
        items = [
            _item(
                item_id="research_web_service",
                category="local_service",
                label="Research Web 本机服务",
                discovery="已发现",
                authorization="无需授权",
                verification="已验证",
                callable_value=True,
                status="可用",
                message="本机网页与 Python 服务正在当前设备的回环地址运行。",
                detail="此结论仅代表 8088 本机服务在线，不代表其他集成可调用。",
                capabilities=("loopback_api",),
                checked_at=checked_at,
            ),
            _item(
                item_id="folder_sync",
                category="folders",
                label="全局资料库文件夹同步",
                discovery="未配置",
                authorization="待授权",
                verification="待验证",
                callable_value=False,
                status="待配置",
                message="文件夹选择、双向同步与冲突处理将在后续阶段提供。",
                detail="v0 不接受任意路径，也不会在后台扫描文件夹。",
                checked_at=checked_at,
            ),
        ]
        items.extend(self._office_items(platform_id, checked_at))
        items.extend(self._browser_items(platform_id, checked_at))
        items.append(
            _item(
                item_id="local_mcp",
                category="mcp",
                label="本地 MCP",
                discovery="未扫描",
                authorization="待授权",
                verification="待验证",
                callable_value=False,
                status="待配置",
                message="MCP 自动发现与逐工具授权将在后续阶段提供。",
                detail="v0 不读取配置内容、不启动服务器，也不向前端返回命令参数或环境变量。",
                checked_at=checked_at,
            )
        )
        categories = [
            {
                "id": category_id,
                "label": label,
                "item_ids": [item["id"] for item in items if item["category"] == category_id],
            }
            for category_id, label in CATEGORY_LABELS.items()
        ]
        return {
            "platform": platform_id,
            "service": {"online": True, "label": "本机服务在线"},
            "summary": {
                "available": sum(item["status"] == "可用" for item in items),
                "needs_attention": sum(item["status"] not in {"可用", "不适用"} for item in items),
                "total": len(items),
            },
            "categories": categories,
            "items": items,
            "last_checked_at": checked_at,
        }

    def _office_items(self, platform_id: str, checked_at: str) -> list[dict]:
        if platform_id == "macos":
            excel = _named_entry_exists(
                self.environment.application_roots, ("Microsoft Excel.app",)
            )
            word = _named_entry_exists(self.environment.application_roots, ("Microsoft Word.app",))
            powerpoint = _named_entry_exists(
                self.environment.application_roots, ("Microsoft PowerPoint.app",)
            )
            wind = _named_entry_exists(
                self.environment.application_roots, ("Wind.app", "Wind金融终端.app")
            )
            addin = _wind_addin_exists(self.environment.office_addin_roots)
        elif platform_id == "windows":
            excel = _windows_app_exists(
                self.environment,
                "EXCEL.EXE",
                ("Microsoft Office/root/Office16/EXCEL.EXE", "Microsoft Office/Office16/EXCEL.EXE"),
            )
            word = _windows_app_exists(
                self.environment,
                "WINWORD.EXE",
                (
                    "Microsoft Office/root/Office16/WINWORD.EXE",
                    "Microsoft Office/Office16/WINWORD.EXE",
                ),
            )
            powerpoint = _windows_app_exists(
                self.environment,
                "POWERPNT.EXE",
                (
                    "Microsoft Office/root/Office16/POWERPNT.EXE",
                    "Microsoft Office/Office16/POWERPNT.EXE",
                ),
            )
            wind = _windows_app_exists(
                self.environment,
                "WFT.exe",
                ("Wind/WFT/WFT.exe", "Wind/Wind.NET.Client/WindNET.exe"),
            )
            appdata = self.environment.environment_variables.get("APPDATA")
            addin = (
                _named_entry_exists(
                    (Path(appdata),),
                    ("Microsoft/AddIns/WindAddin.xlam", "Wind/WindAddin.xlam"),
                )
                if appdata
                else False
            )
        else:
            return self._unsupported_office_items(checked_at)

        xlwings = self.environment.module_available("xlwings")
        return [
            self._application_item(
                "excel_app", "Microsoft Excel 应用", excel, checked_at, ("open", "calculate", "save")
            ),
            self._bridge_item(
                "excel_automation_bridge",
                "Excel 自动化桥",
                xlwings,
                excel,
                checked_at,
                "xlwings 未安装；这不会改变 Excel 应用的发现结果。",
            ),
            self._application_item(
                "word_app", "Microsoft Word 应用", word, checked_at, ("open", "update", "save")
            ),
            self._application_item(
                "powerpoint_app",
                "Microsoft PowerPoint 应用",
                powerpoint,
                checked_at,
                ("open", "update", "save"),
            ),
            self._wind_terminal_item(wind, checked_at),
            self._bridge_item(
                "wind_excel_addin",
                "Wind Excel 插件",
                addin,
                excel,
                checked_at,
                "未在 Office 加载项目录发现 WindAddin。",
            ),
            self._ifind_terminal_item(platform_id, checked_at),
        ]

    def _wind_terminal_item(self, found: bool, checked_at: str) -> dict:
        actions = (
            {
                "id": "configure",
                "label": "查看 Wind 数据源",
                "href": "#/settings/data?connection=wind",
            },
        )
        if not found:
            return _item(
                item_id="wind_terminal",
                category="office",
                label="Wind 金融终端",
                discovery="未发现",
                authorization="不适用",
                verification="不适用",
                callable_value=False,
                status="未发现",
                message="未在系统应用位置发现 Wind 金融终端。",
                detail="WindPy 数据接口在数据源页单独管理；终端缺失不能推断账号或接口状态。",
                actions=actions,
                checked_at=checked_at,
            )
        return _item(
            item_id="wind_terminal",
            category="office",
            label="Wind 金融终端",
            discovery="已发现",
            authorization="待验证",
            verification="待验证",
            callable_value=False,
            status="待验证",
            message="已检测到 Wind 金融终端，登录状态尚未确认。",
            detail="v0 不启动终端或读取会话；完成登录握手和真实数据验证后才能标记可调用。",
            capabilities=("terminal",),
            actions=actions,
            checked_at=checked_at,
        )

    def _application_item(
        self,
        item_id: str,
        label: str,
        found: bool,
        checked_at: str,
        capabilities: tuple[str, ...],
        actions: tuple[dict[str, str], ...] = (),
    ) -> dict:
        return _item(
            item_id=item_id,
            category="office",
            label=label,
            discovery="已发现" if found else "未发现",
            authorization="无需授权" if found else "不适用",
            verification="待验证" if found else "不适用",
            callable_value=False,
            status="待验证" if found else "未发现",
            message=f"已检测到 {label}。" if found else f"未在系统应用位置发现 {label}。",
            detail="应用存在仅是发现事实；v0 尚未执行打开、更新或保存验证。" if found else "仅在当前操作系统的标准应用位置与已知注册信息中检测。",
            capabilities=capabilities if found else (),
            actions=actions,
            checked_at=checked_at,
        )

    def _bridge_item(
        self,
        item_id: str,
        label: str,
        found: bool,
        prerequisite: bool,
        checked_at: str,
        missing_message: str,
    ) -> dict:
        if not found:
            return _item(
                item_id=item_id,
                category="office",
                label=label,
                discovery="未发现",
                authorization="不适用",
                verification="不适用",
                callable_value=False,
                status="待配置" if prerequisite else "未发现",
                message=missing_message,
                detail="缺少自动化桥不会把已发现的目标应用标成未安装。",
                checked_at=checked_at,
            )
        return _item(
            item_id=item_id,
            category="office",
            label=label,
            discovery="已发现",
            authorization="待授权",
            verification="待验证",
            callable_value=False,
            status="待验证",
            message=f"已检测到 {label}，尚未完成真实调用验证。",
            detail="必须通过安全的真实工作簿或厂商会话验证后才能标记可调用。",
            checked_at=checked_at,
        )

    def _ifind_terminal_item(self, platform_id: str, checked_at: str) -> dict:
        actions = (
            {
                "id": "configure",
                "label": "配置 iFinD HTTP API",
                "href": "#/settings/data?connection=ifind",
            },
        )
        if platform_id == "macos":
            return _item(
                item_id="ifind_terminal",
                category="office",
                label="iFinD 专业终端",
                discovery="不适用",
                authorization="不适用",
                verification="不适用",
                callable_value=False,
                status="不适用",
                message="iFinD 专业终端与本地 SDK 不适用于 macOS；请配置 iFinD HTTP API。",
                detail="普通同花顺客户端不是 iFinD 数据接口证据；SDK 与 HTTP API 在数据源页管理。",
                actions=actions,
                checked_at=checked_at,
            )
        found = platform_id == "windows" and _windows_app_exists(
            self.environment, "iFinD.exe", ("iFinD/iFinD.exe", "同花顺/iFinD/iFinD.exe")
        )
        if not found:
            return _item(
                item_id="ifind_terminal",
                category="office",
                label="iFinD 专业终端",
                discovery="未发现",
                authorization="不适用",
                verification="不适用",
                callable_value=False,
                status="未发现",
                message="未发现 iFinD 专业终端。",
                detail="本机终端与 iFinD SDK/HTTP 数据接口分别判断；Python 模块不会冒充终端。",
                actions=actions,
                checked_at=checked_at,
            )
        return _item(
            item_id="ifind_terminal",
            category="office",
            label="iFinD 专业终端",
            discovery="已发现",
            authorization="待验证",
            verification="待验证",
            callable_value=False,
            status="待验证",
            message="已检测到 iFinD 专业终端，登录状态尚未确认。",
            detail="SDK 与 HTTP API 在数据源页管理；完成登录握手和真实数据验证后才能标记可调用。",
            actions=actions,
            checked_at=checked_at,
        )

    def _unsupported_office_items(self, checked_at: str) -> list[dict]:
        labels = (
            ("excel_app", "Microsoft Excel 应用"),
            ("excel_automation_bridge", "Excel 自动化桥"),
            ("word_app", "Microsoft Word 应用"),
            ("powerpoint_app", "Microsoft PowerPoint 应用"),
            ("wind_terminal", "Wind 金融终端"),
            ("wind_excel_addin", "Wind Excel 插件"),
            ("ifind_terminal", "iFinD 专业终端"),
        )
        return [
            _item(
                item_id=item_id,
                category="office",
                label=label,
                discovery="不适用",
                authorization="不适用",
                verification="不适用",
                callable_value=False,
                status="不适用",
                message="当前操作系统不在本机 Office 集成 v0 支持范围内。",
                detail="本轮只提供 macOS 与 Windows 的无副作用检测。",
                checked_at=checked_at,
            )
            for item_id, label in labels
        ]

    def _browser_items(self, platform_id: str, checked_at: str) -> list[dict]:
        if platform_id == "macos":
            chrome = _named_entry_exists(self.environment.application_roots, ("Google Chrome.app",))
            edge = _named_entry_exists(self.environment.application_roots, ("Microsoft Edge.app",))
        elif platform_id == "windows":
            chrome = _windows_app_exists(
                self.environment, "chrome.exe", ("Google/Chrome/Application/chrome.exe",)
            )
            edge = _windows_app_exists(
                self.environment, "msedge.exe", ("Microsoft/Edge/Application/msedge.exe",)
            )
        else:
            chrome = edge = False

        def browser_status(found: bool) -> str:
            return "待验证" if found else ("不适用" if platform_id == "other" else "未发现")

        return [
            _item(
                item_id=item_id,
                category="browsers",
                label=label,
                discovery="已发现" if found else ("不适用" if platform_id == "other" else "未发现"),
                authorization="无需授权" if found else "不适用",
                verification="待验证" if found else "不适用",
                callable_value=False,
                status=browser_status(found),
                message=f"已检测到 {label}。" if found else f"未发现 {label}。",
                detail="浏览器存在不代表扩展已安装或已配对。",
                checked_at=checked_at,
            )
            for item_id, label, found in (
                ("chrome_app", "Google Chrome", chrome),
                ("edge_app", "Microsoft Edge", edge),
            )
        ] + [
            _item(
                item_id="browser_extension",
                category="browsers",
                label="Research Workbench 浏览器扩展",
                discovery="未配置",
                authorization="待授权",
                verification="待验证",
                callable_value=False,
                status="待配置",
                message="扩展开发包与一次性配对将在后续阶段提供。",
                detail="v0 不采集当前页面、选中文本或正文。",
                checked_at=checked_at,
            )
        ]

    def _validate_snapshot(self, value: dict) -> None:
        if not isinstance(value, dict) or set(value) != SNAPSHOT_FIELDS:
            raise LocalIntegrationError("本机能力检测返回了无效结果")
        if value.get("platform") not in {"macos", "windows", "other"}:
            raise LocalIntegrationError("本机能力检测返回了无效平台")
        service = value.get("service")
        summary = value.get("summary")
        categories = value.get("categories")
        items = value.get("items")
        if (
            not isinstance(service, dict)
            or set(service) != SERVICE_FIELDS
            or not isinstance(service.get("online"), bool)
            or not isinstance(service.get("label"), str)
            or not isinstance(summary, dict)
            or set(summary) != SUMMARY_FIELDS
            or not isinstance(categories, list)
            or not isinstance(items, list)
            or not isinstance(value.get("last_checked_at"), str)
        ):
            raise LocalIntegrationError("本机能力检测返回了无效结果")

        item_ids: set[str] = set()
        for item in items:
            if not isinstance(item, dict) or set(item) != ITEM_FIELDS:
                raise LocalIntegrationError("本机能力检测返回了无效项目")
            item_id = item.get("id")
            text_fields = (
                "label",
                "discovery",
                "authorization",
                "verification",
                "message",
                "detail",
            )
            if (
                not isinstance(item_id, str)
                or not SAFE_ID.fullmatch(item_id)
                or item_id in item_ids
                or item.get("category") not in CATEGORY_LABELS
                or item.get("status") not in ALLOWED_STATUSES
                or item.get("discovery") not in DISCOVERY_VALUES
                or item.get("authorization") not in AUTHORIZATION_VALUES
                or item.get("verification") not in VERIFICATION_VALUES
                or not isinstance(item.get("callable"), bool)
                or not all(
                    isinstance(item.get(field), str) and len(item[field]) <= 2048
                    for field in text_fields
                )
                or not isinstance(item.get("last_checked_at"), str)
                or (
                    item.get("last_verified_at") is not None
                    and (
                        not isinstance(item.get("last_verified_at"), str)
                        or len(item["last_verified_at"]) > 64
                    )
                )
                or not isinstance(item.get("capabilities"), list)
                or not all(
                    isinstance(capability, str) and SAFE_ID.fullmatch(capability)
                    for capability in item["capabilities"]
                )
                or not isinstance(item.get("actions"), list)
                or item["callable"] != (item["status"] == "可用")
                or (
                    item["callable"]
                    and (
                        item["discovery"] != "已发现"
                        or item["authorization"] not in {"无需授权", "已授权"}
                        or item["verification"] != "已验证"
                    )
                )
                or (
                    item["status"] == "不适用"
                    and {
                        item["discovery"],
                        item["authorization"],
                        item["verification"],
                    }
                    != {"不适用"}
                )
            ):
                raise LocalIntegrationError("本机能力检测返回了无效项目")
            item_ids.add(item_id)
            for action in item["actions"]:
                if (
                    not isinstance(action, dict)
                    or set(action) != ACTION_FIELDS
                    or not isinstance(action.get("id"), str)
                    or not SAFE_ID.fullmatch(action["id"])
                    or not isinstance(action.get("label"), str)
                    or len(action["label"]) > 120
                    or not isinstance(action.get("href"), str)
                    or not SAFE_DATA_ACTION.fullmatch(action["href"])
                ):
                    raise LocalIntegrationError("本机能力检测返回了无效操作")

        category_ids: list[str] = []
        category_item_ids: list[str] = []
        item_categories: dict[str, str] = {}
        for category in categories:
            if (
                not isinstance(category, dict)
                or set(category) != CATEGORY_FIELDS
                or category.get("id") not in CATEGORY_LABELS
                or category.get("label") != CATEGORY_LABELS[category["id"]]
                or not isinstance(category.get("item_ids"), list)
                or not all(isinstance(item_id, str) for item_id in category["item_ids"])
            ):
                raise LocalIntegrationError("本机能力检测返回了无效分类")
            category_ids.append(category["id"])
            category_item_ids.extend(category["item_ids"])
            item_categories.update({item_id: category["id"] for item_id in category["item_ids"]})
        if (
            category_ids != list(CATEGORY_LABELS)
            or len(category_item_ids) != len(set(category_item_ids))
            or set(category_item_ids) != item_ids
            or any(item_categories[item["id"]] != item["category"] for item in items)
        ):
            raise LocalIntegrationError("本机能力检测分类与项目不一致")

        expected_summary = {
            "available": sum(item["status"] == "可用" for item in items),
            "needs_attention": sum(item["status"] not in {"可用", "不适用"} for item in items),
            "total": len(items),
        }
        if summary != expected_summary:
            raise LocalIntegrationError("本机能力检测汇总与项目不一致")

        serialized = json.dumps(value, ensure_ascii=False)
        sensitive_values = {str(self.environment.home), str(self.state_root)}
        sensitive_values.update(
            str(secret)
            for key, secret in self.environment.environment_variables.items()
            if SENSITIVE_ENVIRONMENT_KEY.search(key) and len(str(secret)) >= 8
        )
        if any(len(secret) > 3 and secret in serialized for secret in sensitive_values):
            raise LocalIntegrationError("本机能力检测包含不可公开的信息")

    def _persist(
        self,
        snapshot: dict,
        *,
        verification_results: dict[str, dict] | None = None,
    ) -> None:
        temporary: Path | None = None
        try:
            self.state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
            with suppress(OSError):
                self.state_root.chmod(0o700)
            temporary = self.state_path.with_suffix(f".{uuid4().hex}.tmp")
            payload = json.dumps(
                {
                    "snapshot": snapshot,
                    "verifications": (
                        self.verification_results
                        if verification_results is None
                        else verification_results
                    ),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            temporary.write_text(payload, encoding="utf-8")
            temporary.chmod(0o600)
            os.replace(temporary, self.state_path)
        except OSError as exc:
            if temporary is not None:
                with suppress(OSError):
                    temporary.unlink()
            log.warning("local_integration_state_write_failed", error_type=type(exc).__name__)
            raise LocalIntegrationError("本机能力状态无法安全保存") from exc

    def start_probe(self, idempotency_key: str) -> dict:
        existing = self.probe_keys.get(idempotency_key)
        if existing:
            return self._public_probe(self.probes[existing])
        self._prune_probes()
        if self.probe_tasks or (
            self._active_detection is not None and not self._active_detection.done()
        ):
            raise LocalIntegrationError("已有本机探测正在进行，请稍后重试", "local_probe_busy", 409)
        if len(self.probes) >= MAX_PROBE_RECORDS:
            raise LocalIntegrationError("本机探测记录已达到上限，请稍后重试", "local_probe_capacity", 429)
        probe_id = str(uuid4())
        record = {
            "id": probe_id,
            "status": "queued",
            "created_at": _utc_now(),
            "completed_at": None,
        }
        self.probes[probe_id] = record
        self.probe_keys[idempotency_key] = probe_id
        self.probe_tasks[probe_id] = asyncio.create_task(
            self._run_probe(probe_id), name="local-integration-probe"
        )
        log.info("local_integration_probe_started")
        return self._public_probe(record)

    async def _run_probe(self, probe_id: str) -> None:
        record = self.probes[probe_id]
        record["status"] = "checking"
        detection = self._detector_executor.submit(
            self.detector if self.detector is not None else self._detect
        )
        self._active_detection = detection

        def clear_detection(completed: Future) -> None:
            if self._active_detection is completed:
                self._active_detection = None

        detection.add_done_callback(clear_detection)
        try:
            detected = await asyncio.wait_for(
                asyncio.shield(asyncio.wrap_future(detection)),
                timeout=self.probe_timeout_seconds,
            )
            snapshot = self._publish_snapshot(copy.deepcopy(detected), persist=True)
            record.update(status="completed", snapshot=snapshot, completed_at=_utc_now())
            log.info("local_integration_probe_completed")
        except asyncio.CancelledError:
            record.update(status="cancelled", completed_at=_utc_now())
            log.info("local_integration_probe_cancelled")
            raise
        except TimeoutError:
            record.update(
                status="failed",
                completed_at=_utc_now(),
                error={"code": "probe_timed_out", "message": "本机能力检测超时，请稍后重试"},
            )
            log.warning("local_integration_probe_timed_out")
        except Exception as exc:  # noqa: BLE001 - normalize all host/IO failures.
            record.update(
                status="failed",
                completed_at=_utc_now(),
                error={"code": "probe_failed", "message": "本机能力检测失败，请查看本地日志"},
            )
            log.warning("local_integration_probe_failed", error_type=type(exc).__name__)
        finally:
            self.probe_tasks.pop(probe_id, None)

    def start_verification(self, target: str, idempotency_key: str) -> dict:
        if target not in VERIFICATION_TARGETS:
            raise LocalIntegrationError("本机验证目标无效", "verification_target_invalid", 422)
        key = f"{target}:{idempotency_key}"
        existing = self.verification_keys.get(key)
        if existing:
            return self._public_verification(self.verifications[existing[1]])
        self._prune_verifications()
        if any(not task.done() for task in self.verification_tasks.values()):
            raise LocalIntegrationError("已有真实验证正在运行，请稍后重试", "verification_busy", 409)
        if len(self.verifications) >= MAX_VERIFICATION_RECORDS:
            raise LocalIntegrationError(
                "本机验证记录已达到上限，请稍后重试",
                "verification_capacity",
                429,
            )
        verification_id = str(uuid4())
        record = {
            "id": verification_id,
            "target": target,
            "status": "queued",
            "created_at": _utc_now(),
            "completed_at": None,
        }
        self.verifications[verification_id] = record
        self.verification_keys[key] = (target, verification_id)
        self.verification_tasks[verification_id] = asyncio.create_task(
            self._run_verification(verification_id), name=f"local-verification-{target}"
        )
        log.info("local_integration_verification_started", target=target)
        return self._public_verification(record)

    async def _run_verification(self, verification_id: str) -> None:
        record = self.verifications[verification_id]
        record["status"] = "checking"
        cancellation_event: threading.Event | None = None
        worker: asyncio.Task | None = None
        try:
            if self.verifier is not None:
                outcome = await asyncio.to_thread(self.verifier, record["target"])
            else:
                from .verifiers import verify_target

                cancellation_event = threading.Event()
                worker = asyncio.create_task(
                    asyncio.to_thread(
                        verify_target,
                        record["target"],
                        self.state_root,
                        cancellation_event=cancellation_event,
                    )
                )
                outcome = await asyncio.shield(worker)
            normalized = outcome.get("outcome") if isinstance(outcome, dict) else None
            if normalized not in VERIFICATION_MESSAGES:
                normalized = "failed"
            completed_at = _utc_now()
            detected = self._detect()
            await asyncio.to_thread(
                self._commit_verification,
                record["target"],
                normalized,
                completed_at,
                detected,
            )
            record.update(status="completed", outcome=normalized, completed_at=completed_at)
            log.info(
                "local_integration_verification_completed",
                target=record["target"],
                outcome=normalized,
            )
        except asyncio.CancelledError:
            if cancellation_event is not None:
                cancellation_event.set()
            if worker is not None:
                with suppress(asyncio.CancelledError, Exception):
                    await asyncio.shield(worker)
            record.update(status="cancelled", completed_at=_utc_now())
            raise
        except Exception as exc:  # noqa: BLE001 - normalize process and IO failures.
            record.update(
                status="failed",
                completed_at=_utc_now(),
                error={"code": "verification_failed", "message": "本机真实验证失败，请查看本地日志"},
            )
            log.warning("local_integration_verification_failed", error_type=type(exc).__name__)
        finally:
            self.verification_tasks.pop(verification_id, None)

    def verification(self, verification_id: str) -> dict:
        record = self.verifications.get(verification_id)
        if record is None:
            raise LocalIntegrationError("未找到本机验证任务", "verification_not_found", 404)
        return self._public_verification(record)

    @staticmethod
    def _public_verification(record: dict) -> dict:
        return {
            key: record[key]
            for key in ("id", "target", "status", "outcome", "created_at", "completed_at", "error")
            if key in record
        }

    def _prune_probes(self) -> None:
        removable = sorted(
            (
                (record.get("created_at", ""), probe_id)
                for probe_id, record in self.probes.items()
                if probe_id not in self.probe_tasks
            )
        )
        while len(self.probes) >= MAX_PROBE_RECORDS and removable:
            _, probe_id = removable.pop(0)
            self.probes.pop(probe_id, None)
            for key, value in list(self.probe_keys.items()):
                if value == probe_id:
                    self.probe_keys.pop(key, None)

    def _prune_verifications(self) -> None:
        removable = sorted(
            (
                (record.get("created_at", ""), verification_id)
                for verification_id, record in self.verifications.items()
                if verification_id not in self.verification_tasks
            )
        )
        while len(self.verifications) >= MAX_VERIFICATION_RECORDS and removable:
            _, verification_id = removable.pop(0)
            self.verifications.pop(verification_id, None)
            for key, value in list(self.verification_keys.items()):
                if value[1] == verification_id:
                    self.verification_keys.pop(key, None)

    def probe(self, probe_id: str) -> dict:
        record = self.probes.get(probe_id)
        if record is None:
            raise LocalIntegrationError("未找到本机探测任务", "local_probe_not_found", 404)
        return self._public_probe(record)

    @staticmethod
    def _public_probe(record: dict) -> dict:
        return {
            key: record[key]
            for key in ("id", "status", "created_at", "completed_at", "snapshot", "error")
            if key in record
        }

    async def close(self) -> None:
        tasks = [*self.probe_tasks.values(), *self.verification_tasks.values()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.probe_tasks.clear()
        self.verification_tasks.clear()
        self._detector_executor.shutdown(wait=False, cancel_futures=True)
