"""Truthful host capability projections without launching vendor software."""

import asyncio
import importlib.util
import json
import os
import platform
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
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


def _wind_addin_exists(roots: tuple[Path, ...]) -> bool:
    for root in roots:
        if _exists(root / "WindAddin") or _exists(root / "WindAddin.xlam"):
            return True
        try:
            if root.is_dir() and any(
                entry.name.lower().startswith("windaddin") for entry in root.iterdir()
            ):
                return True
        except OSError:
            continue
    return False


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
    }


class LocalIntegrationManager:
    """Build and persist safe local facts; probes never launch detected software."""

    def __init__(
        self,
        state_root: Path,
        *,
        environment: DetectionEnvironment | None = None,
        detector: Callable[[], dict] | None = None,
    ):
        self.state_root = Path(state_root)
        self.environment = environment or DetectionEnvironment.current()
        self.detector = detector
        self.probes: dict[str, dict] = {}
        self.probe_keys: dict[str, str] = {}
        self.probe_tasks: dict[str, asyncio.Task] = {}
        self._latest: dict | None = None

    @property
    def state_path(self) -> Path:
        return self.state_root / "local-integrations.json"

    def snapshot(self) -> dict:
        try:
            value = self.detector() if self.detector is not None else self._detect()
            self._validate_snapshot(value)
            self._latest = value
            self._persist(value)
            return value
        except LocalIntegrationError:
            raise
        except Exception as exc:  # noqa: BLE001 - host inspection is a hard safety boundary.
            log.warning("local_integration_snapshot_failed", error_type=type(exc).__name__)
            raise LocalIntegrationError("本机能力检测失败，请查看本地日志") from exc

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
            addin = bool(appdata) and _named_entry_exists(
                (Path(appdata),), ("Microsoft/AddIns/WindAddin.xlam", "Wind/WindAddin.xlam")
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
            self._application_item(
                "wind_terminal",
                "Wind 金融终端",
                wind,
                checked_at,
                ("terminal",),
                actions=(
                    {
                        "id": "configure",
                        "label": "查看 Wind 数据源",
                        "href": "#/settings/data?connection=wind",
                    },
                ),
            ),
            self._bridge_item(
                "wind_excel_addin",
                "Wind Excel 插件",
                addin,
                excel,
                checked_at,
                "未在 Office 加载项目录发现 WindAddin。",
            ),
            self._ifind_local_item(platform_id, checked_at),
        ]

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

    def _ifind_local_item(self, platform_id: str, checked_at: str) -> dict:
        if platform_id == "macos":
            return _item(
                item_id="ifind_local_sdk",
                category="office",
                label="iFinD 本地 SDK",
                discovery="不适用",
                authorization="不适用",
                verification="不适用",
                callable_value=False,
                status="不适用",
                message="macOS 不使用 iFinD 本地 SDK；请配置 iFinD HTTP API。",
                detail="普通行情客户端不作为 iFinD 数据接口的发现证据。",
                actions=(
                    {
                        "id": "configure",
                        "label": "配置 iFinD HTTP API",
                        "href": "#/settings/data?connection=ifind",
                    },
                ),
                checked_at=checked_at,
            )
        found = platform_id == "windows" and (
            self.environment.module_available("iFinD")
            or self.environment.module_available("iFinDPy")
            or _windows_app_exists(
                self.environment, "iFinD.exe", ("iFinD/iFinD.exe", "同花顺/iFinD/iFinD.exe")
            )
        )
        return self._bridge_item(
            "ifind_local_sdk", "iFinD 本地 SDK", found, True, checked_at, "未发现 iFinD 专业终端或 SDK。"
        )

    def _unsupported_office_items(self, checked_at: str) -> list[dict]:
        labels = (
            ("excel_app", "Microsoft Excel 应用"),
            ("excel_automation_bridge", "Excel 自动化桥"),
            ("word_app", "Microsoft Word 应用"),
            ("powerpoint_app", "Microsoft PowerPoint 应用"),
            ("wind_terminal", "Wind 金融终端"),
            ("wind_excel_addin", "Wind Excel 插件"),
            ("ifind_local_sdk", "iFinD 本地 SDK"),
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
        if not isinstance(value, dict) or not isinstance(value.get("items"), list):
            raise LocalIntegrationError("本机能力检测返回了无效结果")
        for item in value["items"]:
            if not isinstance(item, dict) or item.get("status") not in ALLOWED_STATUSES:
                raise LocalIntegrationError("本机能力检测返回了无效状态")

    def _persist(self, snapshot: dict) -> None:
        try:
            self.state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
            with suppress(OSError):
                self.state_root.chmod(0o700)
            temporary = self.state_path.with_suffix(f".{uuid4().hex}.tmp")
            payload = json.dumps({"snapshot": snapshot}, ensure_ascii=False, sort_keys=True)
            temporary.write_text(payload, encoding="utf-8")
            temporary.chmod(0o600)
            os.replace(temporary, self.state_path)
        except OSError as exc:
            log.warning("local_integration_state_write_failed", error_type=type(exc).__name__)
            raise LocalIntegrationError("本机能力状态无法安全保存") from exc

    def start_probe(self, idempotency_key: str) -> dict:
        existing = self.probe_keys.get(idempotency_key)
        if existing:
            return self._public_probe(self.probes[existing])
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
        try:
            snapshot = await asyncio.to_thread(self.snapshot)
            record.update(status="completed", snapshot=snapshot, completed_at=_utc_now())
            log.info("local_integration_probe_completed")
        except asyncio.CancelledError:
            record.update(status="cancelled", completed_at=_utc_now())
            log.info("local_integration_probe_cancelled")
            raise
        except Exception as exc:  # noqa: BLE001 - normalize all host/IO failures.
            record.update(
                status="failed",
                completed_at=_utc_now(),
                error={"code": "probe_failed", "message": "本机能力检测失败，请查看本地日志"},
            )
            log.warning("local_integration_probe_failed", error_type=type(exc).__name__)
        finally:
            self.probe_tasks.pop(probe_id, None)

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
        tasks = list(self.probe_tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.probe_tasks.clear()
