"""系统配置中心的脱敏、持久化与运行时刷新服务。"""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import platform
import re
import stat
import tempfile
import threading
from contextlib import contextmanager
from io import StringIO
from pathlib import Path
from typing import IO, Any, Callable, Iterator, Mapping
from urllib.parse import urlsplit

import yaml
from dotenv.main import resolve_variables
from dotenv.parser import parse_stream

from core.observability import get_logger
from core.settings.config import (
    ProviderProfile,
    Settings,
    TaskRoute,
    resolve_runtime_env_path,
    settings,
)

logger = get_logger(__name__)

SUPPORTED_SECTIONS = {"llm", "zhiqiu", "ifind", "database", "advanced", "web_search"}
SECRET_SUFFIX_LENGTH = 4
ZHIQIU_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "data_layer" / "crawlers" / "zq" / "config.yaml"
)
ConnectionProbe = Callable[[Mapping[str, str], float], bool]


class ConfigurationError(RuntimeError):
    """可安全返回给 API 调用方的配置错误。"""


class ConfigurationPersistenceError(ConfigurationError):
    """配置持久化或运行时刷新失败。"""


class _CrossProcessFileLock:
    """锁定预先存在的单字节，兼容 fcntl 和 Windows msvcrt。"""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle: IO[bytes] | None = None
        self._lock_module: Any = None

    def __enter__(self) -> "_CrossProcessFileLock":
        descriptor = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        handle = os.fdopen(descriptor, "r+b", buffering=0)
        self._handle = handle
        try:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
                os.fsync(handle.fileno())
            handle.seek(0)
            if os.name == "nt":
                self._lock_module = importlib.import_module("msvcrt")
                self._lock_module.locking(handle.fileno(), self._lock_module.LK_LOCK, 1)
            else:
                self._lock_module = importlib.import_module("fcntl")
                self._lock_module.flock(handle.fileno(), self._lock_module.LOCK_EX)
            return self
        except Exception:
            handle.close()
            self._handle = None
            raise

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        if self._handle is None:
            return
        try:
            self._handle.seek(0)
            if os.name == "nt":
                self._lock_module.locking(self._handle.fileno(), self._lock_module.LK_UNLCK, 1)
            else:
                self._lock_module.flock(self._handle.fileno(), self._lock_module.LOCK_UN)
        except Exception as exc:
            logger.warning("配置文件锁释放失败", extra={"error_type": type(exc).__name__})
        finally:
            try:
                self._handle.close()
            except OSError as exc:
                logger.warning("配置锁文件关闭失败", extra={"error_type": type(exc).__name__})
            self._handle = None


class ConfigurationService:
    """管理允许暴露给配置页面的五类运行参数。"""

    _process_locks: dict[Path, threading.RLock] = {}
    _process_locks_guard = threading.Lock()

    def __init__(
        self,
        env_path: Path | str | None = None,
        runtime_settings: Settings | None = None,
        connection_probes: Mapping[str, ConnectionProbe] | None = None,
        connection_timeout: float = 5.0,
    ) -> None:
        self.env_path = Path(env_path) if env_path is not None else resolve_runtime_env_path()
        self.env_path = self.env_path.expanduser().resolve()
        self.lock_path = self.env_path.parent / f".{self.env_path.name}.lock"
        self.runtime_settings = runtime_settings or settings
        self.connection_timeout = connection_timeout
        self.connection_probes: dict[str, ConnectionProbe] = {
            "llm": self._probe_llm,
            "zhiqiu": self._probe_zhiqiu,
            "ifind": self._probe_ifind,
            "web_search": self._probe_web_search,
        }
        if connection_probes:
            self.connection_probes.update(connection_probes)

    def get_effective_values(self) -> dict[str, str]:
        """读取配置文件，并让当前进程环境覆盖同名文件值。"""
        _, values = self._read_env_file_strict()
        for key, value in os.environ.items():
            if self._is_supported_key(key):
                values[key] = value
        return values

    def _read_env_file_strict(self) -> tuple[str, dict[str, str]]:
        """严格解析 dotenv；任何语法错误都阻止读取和后续写入。"""
        try:
            original = self.env_path.read_text(encoding="utf-8") if self.env_path.exists() else ""
            bindings = list(parse_stream(StringIO(original)))
        except (OSError, UnicodeError, ValueError) as exc:
            logger.error("读取运行时配置文件失败", extra={"error_type": type(exc).__name__})
            raise ConfigurationError("配置文件无法读取") from exc
        if any(binding.error for binding in bindings):
            raise ConfigurationError("配置文件格式无效，未执行写入")
        raw_values = [
            (binding.key, binding.value) for binding in bindings if binding.key is not None
        ]
        resolved = resolve_variables(raw_values, override=True)
        return original, {key: value for key, value in resolved.items() if value is not None}

    def get_snapshot(self) -> dict[str, Any]:
        """返回五分区脱敏快照和就绪状态。"""
        values = self.get_effective_values()
        sections = {
            "llm": self._llm_snapshot(values),
            "zhiqiu": self._zhiqiu_snapshot(values),
            "ifind": self._ifind_snapshot(values),
            "database": self._database_snapshot(values),
            "advanced": self._advanced_snapshot(values),
            "web_search": self._web_search_snapshot(values),
        }
        readiness = {name: bool(section.pop("_ready", False)) for name, section in sections.items()}
        return {
            "sections": sections,
            "readiness": readiness,
            "ready_count": sum(readiness.values()),
            "total_count": len(readiness),
        }

    def update_section(self, section: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        """校验并原子保存单一分区，然后刷新可安全热更新的运行状态。"""
        if section not in SUPPORTED_SECTIONS:
            raise ConfigurationError("不支持的配置分区")

        with self._transaction_lock():
            return self._update_section_locked(section, payload)

    def _update_section_locked(self, section: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        """在进程内和跨进程锁均持有时执行完整更新事务。"""

        current = self.get_effective_values()
        updates, removals, changed_fields = self._build_changes(section, payload, current)
        self._write_env_atomic(updates, removals)

        for key in removals:
            os.environ.pop(key, None)
        os.environ.update(updates)

        restart_required = section == "database"
        if not restart_required:
            try:
                self._refresh_runtime(section)
            except (TypeError, ValueError, AttributeError) as exc:
                logger.error(
                    "配置运行时刷新失败",
                    extra={"section": section, "error_type": type(exc).__name__},
                )
                raise ConfigurationPersistenceError("配置已保存，但运行时刷新失败") from exc

        refreshed_section = self.get_snapshot()["sections"][section]
        logger.info(
            "配置分区保存成功",
            extra={
                "section": section,
                "restart_required": restart_required,
                "changed_fields": sorted(changed_fields),
            },
        )
        return {
            "section": refreshed_section,
            "applied": not restart_required,
            "restart_required": restart_required,
            "message": "重启后生效" if restart_required else "配置已生效",
        }

    @contextmanager
    def _transaction_lock(self) -> Iterator[None]:
        """按配置路径串行化线程和进程间的读改写事务。"""
        with self._process_locks_guard:
            process_lock = self._process_locks.setdefault(self.env_path, threading.RLock())
        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        with process_lock:
            with _CrossProcessFileLock(self.lock_path):
                yield

    def test_section(self, section: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        """验证临时配置，不写文件也不改变进程环境。"""
        if section not in {"llm", "zhiqiu", "ifind", "database", "web_search"}:
            raise ConfigurationError("该配置分区不支持连接测试")
        current = self.get_effective_values()
        updates, removals, _ = self._build_changes(section, payload, current)
        candidate = {**current, **updates}
        for key in removals:
            candidate.pop(key, None)

        if section == "llm" and not self._parse_providers(candidate):
            raise ConfigurationError("至少需要一个大模型 Provider")
        if section == "zhiqiu" and not any(
            account["password_value"] for account in self._parse_zhiqiu_accounts(candidate)
        ):
            raise ConfigurationError("至少需要一个知秋账号")
        if section == "ifind" and not candidate.get("IFIND_USERNAME"):
            raise ConfigurationError("iFinD 用户名不能为空")
        if section == "web_search" and not self._parse_web_search_keys(candidate):
            raise ConfigurationError("至少需要一个联网搜索 API key")
        if section == "database":
            self._validate_database_url(candidate.get("DATABASE_URL", ""))
            return {"success": True, "message": "数据库地址格式验证通过"}

        try:
            success = self.connection_probes[section](candidate, self.connection_timeout)
        except Exception as exc:
            logger.warning(
                "配置连接验证失败",
                extra={"section": section, "error_type": type(exc).__name__},
            )
            success = False
        return {
            "success": success,
            "message": "连接验证成功" if success else "连接验证失败",
        }

    def _probe_llm(self, candidate: Mapping[str, str], timeout: float) -> bool:
        """复用模型 Provider 发送最小聊天请求。"""
        from core.model_gateway.providers import AnthropicProvider, OpenAICompatibleProvider

        providers = self._parse_providers(candidate)
        models_by_provider: dict[str, str] = {}
        for key, provider_name in candidate.items():
            match = re.match(r"^TASK_(.+)_PROVIDER$", key)
            if match:
                model = candidate.get(f"TASK_{match.group(1)}_MODEL", "")
                if model:
                    models_by_provider.setdefault(provider_name, model)
        for item in providers:
            if not item["api_key_value"] and item["protocol"] != "local":
                return False
            profile = ProviderProfile(
                name=item["name"],
                protocol=item["protocol"],  # type: ignore[arg-type]
                base_url=item["base_url"],
                api_key=item["api_key_value"],
            )
            provider = (
                AnthropicProvider(profile)
                if item["protocol"] == "anthropic"
                else OpenAICompatibleProvider(profile)
            )
            try:
                client = getattr(provider, "_client", None)
                if client is None:
                    return False
                model = models_by_provider.get(
                    item["name"],
                    "claude-sonnet-4-6" if item["protocol"] == "anthropic" else "gpt-4o-mini",
                )
                if item["protocol"] == "anthropic":
                    client.messages.create(
                        model=model,
                        messages=[{"role": "user", "content": "ping"}],
                        max_tokens=1,
                        timeout=timeout,
                    )
                else:
                    client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": "ping"}],
                        temperature=0.0,
                        max_tokens=1,
                        timeout=timeout,
                    )
            finally:
                http_client = getattr(provider, "_http_client", None)
                if http_client is not None:
                    http_client.close()
        return bool(providers)

    @staticmethod
    def _probe_zhiqiu(candidate: Mapping[str, str], timeout: float) -> bool:
        """复用知秋客户端逐个验证当前可用账号。"""
        from data_layer.crawlers.zq.zhiqiu.client import ZhiQiuClient

        accounts = ConfigurationService._parse_zhiqiu_accounts(candidate)
        usable = [item for item in accounts if item["username"] and item["password_value"]]
        if not usable:
            return False
        all_succeeded = True
        for item in usable:
            client = ZhiQiuClient(
                item["username"],
                item["password_value"],
            )
            try:
                if not client.login():
                    all_succeeded = False
            finally:
                client.close()
        return all_succeeded

    @staticmethod
    def _probe_web_search(candidate: Mapping[str, str], timeout: float) -> bool:
        """验证至少一个 key 能成功完成一次搜索。"""
        from data_layer.web_search import build_web_search_provider

        keys = ConfigurationService._parse_web_search_keys(candidate)
        usable = [item for item in keys if item["key_value"]]
        if not usable:
            return False
        try:
            provider = build_web_search_provider()
            results = provider.search("ping", max_results=1)
            return len(results) > 0
        except Exception:
            return False

    def _probe_ifind(self, candidate: Mapping[str, str], timeout: float) -> bool:
        """复用 iFinD 后端路由器完成登录和健康检查。"""
        from data_layer.adapters.ifind.router import IFIND_SDK_AVAILABLE, BackendRouter

        backend = candidate.get("IFIND_BACKEND", "auto")
        if backend == "auto":
            backend = (
                "python_sdk"
                if platform.system() != "Darwin" and IFIND_SDK_AVAILABLE
                else "http_api"
            )

        temporary_settings = self.runtime_settings.model_copy(
            update={
                "IFIND_USERNAME": candidate.get("IFIND_USERNAME", ""),
                "IFIND_PASSWORD": candidate.get("IFIND_PASSWORD", ""),
                "IFIND_BACKEND": backend,
                "IFIND_HTTP_BASE_URL": candidate.get(
                    "IFIND_HTTP_BASE_URL", "https://quantapi.10jqka.com.cn"
                ),
            }
        )

        async def run_probe() -> bool:
            client = await BackendRouter(temporary_settings).get_client()
            try:
                return await client.is_alive()
            finally:
                await client.logout()

        return asyncio.run(asyncio.wait_for(run_probe(), timeout=timeout))

    def _build_changes(
        self, section: str, payload: Mapping[str, Any], current: Mapping[str, str]
    ) -> tuple[dict[str, str], set[str], set[str]]:
        builders = {
            "llm": self._build_llm_changes,
            "zhiqiu": self._build_zhiqiu_changes,
            "ifind": self._build_ifind_changes,
            "database": self._build_database_changes,
            "advanced": self._build_advanced_changes,
            "web_search": self._build_web_search_changes,
        }
        return builders[section](payload, current)

    def _build_llm_changes(
        self, payload: Mapping[str, Any], current: Mapping[str, str]
    ) -> tuple[dict[str, str], set[str], set[str]]:
        updates: dict[str, str] = {}
        removals: set[str] = set()
        changed: set[str] = set()
        existing = {item["name"]: item for item in self._parse_providers(current)}

        if "providers" in payload:
            removals.update(key for key in current if re.match(r"^LLM_PROVIDER_\d+_", key))
            providers = payload.get("providers")
            if not isinstance(providers, list):
                raise ConfigurationError("providers 必须是列表")
            names: set[str] = set()
            for index, provider in enumerate(providers, start=1):
                if not isinstance(provider, Mapping):
                    raise ConfigurationError("Provider 格式无效")
                name = self._required_string(provider.get("name"), "Provider 名称")
                if name in names:
                    raise ConfigurationError("Provider 名称不能重复")
                names.add(name)
                protocol = str(provider.get("protocol", "openai_compatible"))
                if protocol not in {"openai_compatible", "anthropic", "local"}:
                    raise ConfigurationError("Provider 协议无效")
                prefix = f"LLM_PROVIDER_{index}_"
                updates[f"{prefix}NAME"] = name
                updates[f"{prefix}PROTOCOL"] = protocol
                base_url = str(provider.get("base_url", "")).strip()
                updates[f"{prefix}BASE_URL"] = base_url
                original_name = str(provider.get("original_name") or name)
                original_provider = existing.get(original_name, {})
                old_secret = str(original_provider.get("api_key_value", ""))
                submitted_secret = provider.get("api_key")
                clear_secret = bool(provider.get("clear_api_key", False))
                if (
                    old_secret
                    and base_url != str(original_provider.get("base_url", ""))
                    and not clear_secret
                    and (submitted_secret is None or str(submitted_secret) == "")
                ):
                    raise ConfigurationError("Provider 地址变更后必须重新输入 Token")
                secret = self._merge_secret(
                    submitted_secret,
                    clear_secret,
                    old_secret,
                )
                if secret:
                    updates[f"{prefix}API_KEY"] = secret
                changed.update({"providers", name})

        if "task_routes" in payload:
            removals.update(key for key in current if re.match(r"^TASK_.+_(PROVIDER|MODEL)$", key))
            routes = payload.get("task_routes")
            if not isinstance(routes, list):
                raise ConfigurationError("task_routes 必须是列表")
            tasks: set[str] = set()
            for route in routes:
                if not isinstance(route, Mapping):
                    raise ConfigurationError("任务路由格式无效")
                task = self._required_string(route.get("task"), "任务名称").upper()
                if not re.fullmatch(r"[A-Z0-9_]+", task) or task in tasks:
                    raise ConfigurationError("任务名称无效或重复")
                tasks.add(task)
                updates[f"TASK_{task}_PROVIDER"] = self._required_string(
                    route.get("provider"), "任务 Provider"
                )
                updates[f"TASK_{task}_MODEL"] = self._required_string(route.get("model"), "任务模型")
            changed.add("task_routes")
        return updates, removals - updates.keys(), changed

    def _build_zhiqiu_changes(
        self, payload: Mapping[str, Any], current: Mapping[str, str]
    ) -> tuple[dict[str, str], set[str], set[str]]:
        updates: dict[str, str] = {}
        removals: set[str] = set()
        changed: set[str] = set()
        existing = {item["name"]: item for item in self._parse_zhiqiu_accounts(current)}
        if "accounts" in payload:
            raw_accounts = payload.get("accounts")
            if not isinstance(raw_accounts, list):
                raise ConfigurationError("accounts 必须是列表")
            accounts: list[dict[str, str]] = []
            names: set[str] = set()
            for item in raw_accounts:
                if not isinstance(item, Mapping):
                    raise ConfigurationError("知秋账号格式无效")
                name = self._required_string(item.get("name"), "账号名称")
                username = self._required_string(item.get("username"), "知秋用户名")
                if name in names:
                    raise ConfigurationError("知秋账号名称不能重复")
                names.add(name)
                original_name = str(item.get("original_name") or name)
                old_secret = str(existing.get(original_name, {}).get("password_value", ""))
                password = self._merge_secret(
                    item.get("password"), bool(item.get("clear_password", False)), old_secret
                )
                accounts.append({"name": name, "username": username, "password": password})
            updates["ZQ_ACCOUNTS_JSON"] = json.dumps(
                accounts, ensure_ascii=False, separators=(",", ":")
            )
            removals.add("ZQ_ACCOUNTS")
            changed.add("accounts")

        mapping = {
            "enabled": ("ZQ_ROTATION_ENABLED", self._boolean_string),
            "rotation_strategy": ("ZQ_ROTATION_STRATEGY", self._rotation_strategy),
            "max_retries": ("ZQ_MAX_RETRIES", lambda value: self._bounded_int(value, 0, 20)),
            "retry_delay": ("ZQ_RETRY_DELAY", lambda value: self._bounded_int(value, 0, 3600)),
            "lease_timeout": ("ZQ_LEASE_TIMEOUT", lambda value: self._bounded_int(value, 1, 86400)),
            "max_consecutive_failures": (
                "ZQ_MAX_CONSECUTIVE_FAILURES",
                lambda value: self._bounded_int(value, 1, 1000),
            ),
        }
        for field, (key, converter) in mapping.items():
            if field in payload:
                updates[key] = converter(payload[field])
                changed.add(field)
        return updates, removals, changed

    def _build_web_search_changes(
        self, payload: Mapping[str, Any], current: Mapping[str, str]
    ) -> tuple[dict[str, str], set[str], set[str]]:
        updates: dict[str, str] = {}
        removals: set[str] = set()
        changed: set[str] = set()
        existing = {item["name"]: item for item in self._parse_web_search_keys(current)}
        if "accounts" in payload:
            raw_accounts = payload.get("accounts")
            if not isinstance(raw_accounts, list):
                raise ConfigurationError("accounts 必须是列表")
            accounts: list[dict[str, str]] = []
            names: set[str] = set()
            for item in raw_accounts:
                if not isinstance(item, Mapping):
                    raise ConfigurationError("API key 账号格式无效")
                name = self._required_string(item.get("name"), "账号名称")
                if name in names:
                    raise ConfigurationError("API key 名称不能重复")
                names.add(name)
                original_name = str(item.get("original_name") or name)
                old_key = str(existing.get(original_name, {}).get("key_value", ""))
                key_value = self._merge_secret(
                    item.get("key"), bool(item.get("clear_key", False)), old_key
                )
                accounts.append({"name": name, "key": key_value})
            updates["WEB_SEARCH_API_KEYS"] = json.dumps(
                accounts, ensure_ascii=False, separators=(",", ":")
            )
            changed.add("accounts")

        scalar_mapping = {
            "provider": ("WEB_SEARCH_PROVIDER", str),
            "rotation_strategy": ("WEB_SEARCH_KEY_ROTATION", str),
            "quota_limit": (
                "WEB_SEARCH_KEY_QUOTA_LIMIT",
                lambda v: self._bounded_int(v, 1, 100000),
            ),
            "max_results": (
                "WEB_SEARCH_MAX_RESULTS",
                lambda v: self._bounded_int(v, 1, 20),
            ),
            "timeout": ("WEB_SEARCH_TIMEOUT", lambda v: self._bounded_int(v, 1, 120)),
        }
        for field, (env_key, converter) in scalar_mapping.items():
            if field in payload:
                updates[env_key] = converter(payload[field])
                changed.add(field)
        return updates, removals, changed

    def _build_ifind_changes(
        self, payload: Mapping[str, Any], current: Mapping[str, str]
    ) -> tuple[dict[str, str], set[str], set[str]]:
        updates: dict[str, str] = {}
        removals: set[str] = set()
        changed: set[str] = set()
        if "accounts" in payload:
            existing = {item["name"]: item for item in self._parse_ifind_accounts(current)}
            accounts: list[dict[str, str]] = []
            names: set[str] = set()
            for item in payload["accounts"] or []:
                if not isinstance(item, Mapping):
                    raise ConfigurationError("iFinD 账号格式无效")
                name = self._required_string(item.get("name"), "iFinD 账号名称")
                if name in names:
                    raise ConfigurationError("iFinD 账号名称不能重复")
                names.add(name)
                username = self._required_string(item.get("username"), "iFinD 用户名")
                original_name = str(item.get("original_name") or name)
                old_secret = str(existing.get(original_name, {}).get("password_value", ""))
                password = self._merge_secret(
                    item.get("password"), bool(item.get("clear_password", False)), old_secret
                )
                accounts.append({"name": name, "username": username, "password": password})
            updates["IFIND_ACCOUNTS_JSON"] = json.dumps(
                accounts, ensure_ascii=False, separators=(",", ":")
            )
            if accounts:
                updates["IFIND_USERNAME"] = accounts[0]["username"]
                if accounts[0]["password"]:
                    updates["IFIND_PASSWORD"] = accounts[0]["password"]
                else:
                    removals.add("IFIND_PASSWORD")
            else:
                removals.update({"IFIND_USERNAME", "IFIND_PASSWORD"})
            changed.add("accounts")
        scalar_fields = {
            "username": "IFIND_USERNAME",
            "backend": "IFIND_BACKEND",
            "http_base_url": "IFIND_HTTP_BASE_URL",
        }
        for field, key in scalar_fields.items():
            if field in payload:
                value = str(payload[field]).strip()
                if field == "backend" and value not in {"auto", "python_sdk", "http_api"}:
                    raise ConfigurationError("iFinD 后端类型无效")
                updates[key] = value
                changed.add(field)
        submitted_password = payload.get("password")
        clear_password = bool(payload.get("clear_password", False))
        backend_changed = "backend" in payload and str(payload["backend"]).strip() != current.get(
            "IFIND_BACKEND", "auto"
        )
        base_url_changed = "http_base_url" in payload and str(
            payload["http_base_url"]
        ).strip() != current.get("IFIND_HTTP_BASE_URL", "https://quantapi.10jqka.com.cn")
        if (
            current.get("IFIND_PASSWORD")
            and (backend_changed or base_url_changed)
            and not clear_password
            and (submitted_password is None or str(submitted_password) == "")
        ):
            raise ConfigurationError("iFinD 连接端点变更后必须重新输入密码")
        if payload.get("clear_password") or (
            submitted_password is not None and str(submitted_password) != ""
        ):
            password = self._merge_secret(
                submitted_password,
                clear_password,
                current.get("IFIND_PASSWORD", ""),
            )
            if password:
                updates["IFIND_PASSWORD"] = password
            else:
                removals.add("IFIND_PASSWORD")
            changed.add("password")
        return updates, removals, changed

    def _build_database_changes(
        self, payload: Mapping[str, Any], current: Mapping[str, str]
    ) -> tuple[dict[str, str], set[str], set[str]]:
        if "database_url" not in payload:
            return {}, set(), set()
        database_url = self._required_string(payload.get("database_url"), "数据库地址")
        self._validate_database_url(database_url)
        return {"DATABASE_URL": database_url}, set(), {"database_url"}

    def _build_advanced_changes(
        self, payload: Mapping[str, Any], current: Mapping[str, str]
    ) -> tuple[dict[str, str], set[str], set[str]]:
        updates: dict[str, str] = {}
        converters = {
            "log_level": ("LOG_LEVEL", self._log_level),
            "log_dir": ("LOG_DIR", lambda value: self._required_string(value, "日志目录")),
            "llm_max_workers": (
                "LLM_EXTRACT_MAX_WORKERS",
                lambda value: self._bounded_int(value, 1, 128),
            ),
            "llm_max_retries": (
                "LLM_EXTRACT_MAX_RETRIES",
                lambda value: self._bounded_int(value, 0, 20),
            ),
            "chunk_size": (
                "LLM_EXTRACT_CHUNK_SIZE",
                lambda value: self._bounded_int(value, 256, 100000),
            ),
            "chunk_overlap": (
                "LLM_EXTRACT_CHUNK_OVERLAP",
                lambda value: self._bounded_int(value, 0, 50000),
            ),
            "long_text_threshold": (
                "LLM_EXTRACT_LONG_TEXT_THRESHOLD",
                lambda value: self._bounded_int(value, 1, 100000),
            ),
        }
        changed: set[str] = set()
        for field, (key, converter) in converters.items():
            if field in payload:
                updates[key] = converter(payload[field])
                changed.add(field)
        if int(
            updates.get(
                "LLM_EXTRACT_CHUNK_OVERLAP", current.get("LLM_EXTRACT_CHUNK_OVERLAP", "300")
            )
        ) >= int(
            updates.get("LLM_EXTRACT_CHUNK_SIZE", current.get("LLM_EXTRACT_CHUNK_SIZE", "3500"))
        ):
            raise ConfigurationError("分块重叠必须小于分块大小")
        return updates, set(), changed

    def _write_env_atomic(self, updates: Mapping[str, str], removals: set[str]) -> None:
        """同目录临时写入并原子替换，保留注释和不相关行。"""
        try:
            original, _ = self._read_env_file_strict()
            lines = original.splitlines(keepends=True)
            remaining = dict(updates)
            output: list[str] = []
            seen: set[str] = set()
            assignment = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")
            for line in lines:
                match = assignment.match(line)
                if not match:
                    output.append(line)
                    continue
                key = match.group(1)
                if key in removals:
                    continue
                if key in remaining:
                    if key not in seen:
                        output.append(f"{key}={self._quote_env_value(remaining.pop(key))}\n")
                        seen.add(key)
                    continue
                output.append(line)

            if output and not output[-1].endswith("\n"):
                output[-1] += "\n"
            for key, value in remaining.items():
                output.append(f"{key}={self._quote_env_value(value)}\n")

            self.env_path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temp_name = tempfile.mkstemp(
                prefix=f".{self.env_path.name}.", dir=self.env_path.parent
            )
            try:
                fchmod = getattr(os, "fchmod", None)
                if fchmod is not None:
                    fchmod(descriptor, stat.S_IRUSR | stat.S_IWUSR)
                else:
                    chmod = getattr(os, "chmod", None)
                    if chmod is not None:
                        chmod(temp_name, stat.S_IRUSR | stat.S_IWUSR)
                handle = os.fdopen(descriptor, "w", encoding="utf-8")
                descriptor = -1
                with handle:
                    handle.writelines(output)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_name, self.env_path)
                temp_name = ""
                self._fsync_parent_directory()
            finally:
                if descriptor >= 0:
                    os.close(descriptor)
                if temp_name:
                    try:
                        os.unlink(temp_name)
                    except FileNotFoundError:
                        pass
        except (OSError, UnicodeError) as exc:
            logger.error("配置原子持久化失败", extra={"error_type": type(exc).__name__})
            raise ConfigurationPersistenceError("配置持久化失败") from exc

    def _fsync_parent_directory(self) -> None:
        """尽力同步父目录元数据；replace 后不再抛出业务失败。"""
        descriptor: int | None = None
        try:
            flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            descriptor = os.open(self.env_path.parent, flags)
            os.fsync(descriptor)
        except Exception as exc:
            logger.warning("配置目录同步失败", extra={"error_type": type(exc).__name__})
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass

    def _refresh_runtime(self, section: str) -> None:
        values = self.get_effective_values()
        if section == "llm":
            self.runtime_settings.PROVIDER_PROFILES = {
                item["name"]: ProviderProfile(
                    name=item["name"],
                    protocol=item["protocol"],  # type: ignore[arg-type]
                    base_url=item["base_url"],
                    api_key=item["api_key_value"],
                )
                for item in self._parse_providers(values)
            }
            routes: dict[str, TaskRoute] = {}
            for key, provider in values.items():
                match = re.match(r"^TASK_(.+)_PROVIDER$", key)
                if match:
                    task_name = match.group(1).lower()
                    routes[task_name] = TaskRoute(
                        provider=provider,
                        model=values.get(f"TASK_{match.group(1)}_MODEL", ""),
                    )
            self.runtime_settings.TASK_ROUTES = routes
        elif section == "ifind":
            self.runtime_settings.IFIND_USERNAME = values.get("IFIND_USERNAME", "")
            self.runtime_settings.IFIND_PASSWORD = values.get("IFIND_PASSWORD", "")
            self.runtime_settings.IFIND_BACKEND = values.get("IFIND_BACKEND", "auto")  # type: ignore[assignment]
            self.runtime_settings.IFIND_HTTP_BASE_URL = values.get(
                "IFIND_HTTP_BASE_URL", "https://quantapi.10jqka.com.cn"
            )
        elif section == "advanced":
            mapping = {
                "LOG_LEVEL": ("LOG_LEVEL", str),
                "LOG_DIR": ("LOG_DIR", Path),
                "LLM_EXTRACT_MAX_WORKERS": ("LLM_EXTRACT_MAX_WORKERS", int),
                "LLM_EXTRACT_MAX_RETRIES": ("LLM_EXTRACT_MAX_RETRIES", int),
                "LLM_EXTRACT_CHUNK_SIZE": ("LLM_EXTRACT_CHUNK_SIZE", int),
                "LLM_EXTRACT_CHUNK_OVERLAP": ("LLM_EXTRACT_CHUNK_OVERLAP", int),
                "LLM_EXTRACT_LONG_TEXT_THRESHOLD": ("LLM_EXTRACT_LONG_TEXT_THRESHOLD", int),
            }
            for key, (attribute, converter) in mapping.items():
                if key in values:
                    setattr(self.runtime_settings, attribute, converter(values[key]))
        elif section == "web_search":
            web_mapping = {
                "WEB_SEARCH_PROVIDER": ("WEB_SEARCH_PROVIDER", str),
                "WEB_SEARCH_API_KEYS": ("WEB_SEARCH_API_KEYS", str),
                "WEB_SEARCH_KEY_ROTATION": ("WEB_SEARCH_KEY_ROTATION", str),
                "WEB_SEARCH_KEY_QUOTA_LIMIT": ("WEB_SEARCH_KEY_QUOTA_LIMIT", int),
                "WEB_SEARCH_MAX_RESULTS": ("WEB_SEARCH_MAX_RESULTS", int),
                "WEB_SEARCH_TIMEOUT": ("WEB_SEARCH_TIMEOUT", int),
            }
            for key, (attribute, converter) in web_mapping.items():
                if key in values:
                    setattr(self.runtime_settings, attribute, converter(values[key]))

    def _llm_snapshot(self, values: Mapping[str, str]) -> dict[str, Any]:
        providers = self._parse_providers(values)
        routes: list[dict[str, str]] = []
        for key, provider in sorted(values.items()):
            match = re.match(r"^TASK_(.+)_PROVIDER$", key)
            if match:
                task = match.group(1).lower()
                routes.append(
                    {
                        "task": task,
                        "provider": provider,
                        "model": values.get(f"TASK_{match.group(1)}_MODEL", ""),
                    }
                )
        public_providers = [
            {
                "original_name": item["name"],
                "name": item["name"],
                "protocol": item["protocol"],
                "base_url": item["base_url"],
                "api_key": self._secret_view(item["api_key_value"]),
            }
            for item in providers
        ]
        return {
            "providers": public_providers,
            "task_routes": routes,
            "_ready": any(
                bool(item["api_key_value"]) or item["protocol"] == "local" for item in providers
            ),
        }

    def _zhiqiu_snapshot(self, values: Mapping[str, str]) -> dict[str, Any]:
        accounts = self._parse_zhiqiu_accounts(values)
        public_accounts = [
            {
                "original_name": item["name"],
                "name": item["name"],
                "username": item["username"],
                "password": self._secret_view(item["password_value"]),
            }
            for item in accounts
        ]
        return {
            "accounts": public_accounts,
            "enabled": self._as_bool(values.get("ZQ_ROTATION_ENABLED", "true")),
            "rotation_strategy": values.get("ZQ_ROTATION_STRATEGY", "round_robin"),
            "max_retries": self._as_int(values.get("ZQ_MAX_RETRIES"), 3),
            "retry_delay": self._as_int(values.get("ZQ_RETRY_DELAY"), 5),
            "lease_timeout": self._as_int(values.get("ZQ_LEASE_TIMEOUT"), 300),
            "max_consecutive_failures": self._as_int(values.get("ZQ_MAX_CONSECUTIVE_FAILURES"), 10),
            "_ready": any(bool(item["password_value"]) for item in accounts),
        }

    def _ifind_snapshot(self, values: Mapping[str, str]) -> dict[str, Any]:
        accounts = self._parse_ifind_accounts(values)
        password = self._secret_view(values.get("IFIND_PASSWORD", ""))
        return {
            "accounts": [
                {
                    "original_name": item["name"],
                    "name": item["name"],
                    "username": item["username"],
                    "password": self._secret_view(item["password_value"]),
                }
                for item in accounts
            ],
            "username": values.get("IFIND_USERNAME", ""),
            "password": password,
            "backend": values.get("IFIND_BACKEND", "auto"),
            "http_base_url": values.get("IFIND_HTTP_BASE_URL", "https://quantapi.10jqka.com.cn"),
            "_ready": any(item["username"] and item["password_value"] for item in accounts),
        }

    def _database_snapshot(self, values: Mapping[str, str]) -> dict[str, Any]:
        database_url = values.get("DATABASE_URL", "")
        return {
            "database_url": self._database_secret_view(database_url),
            "restart_required": True,
            "_ready": bool(database_url),
        }

    def _advanced_snapshot(self, values: Mapping[str, str]) -> dict[str, Any]:
        return {
            "log_level": values.get("LOG_LEVEL", "INFO"),
            "log_dir": values.get("LOG_DIR", str(self.runtime_settings.LOG_DIR)),
            "llm_max_workers": self._as_int(values.get("LLM_EXTRACT_MAX_WORKERS"), 8),
            "llm_max_retries": self._as_int(values.get("LLM_EXTRACT_MAX_RETRIES"), 2),
            "chunk_size": self._as_int(values.get("LLM_EXTRACT_CHUNK_SIZE"), 3500),
            "chunk_overlap": self._as_int(values.get("LLM_EXTRACT_CHUNK_OVERLAP"), 300),
            "long_text_threshold": self._as_int(
                values.get("LLM_EXTRACT_LONG_TEXT_THRESHOLD"), 1000
            ),
            "_ready": True,
        }

    def _web_search_snapshot(self, values: Mapping[str, str]) -> dict[str, Any]:
        keys = self._parse_web_search_keys(values)
        public_keys = [
            {
                "original_name": item["name"],
                "name": item["name"],
                "key": self._secret_view(item["key_value"]),
            }
            for item in keys
        ]
        return {
            "accounts": public_keys,
            "provider": values.get("WEB_SEARCH_PROVIDER", "tavily"),
            "rotation_strategy": values.get("WEB_SEARCH_KEY_ROTATION", "round_robin"),
            "quota_limit": self._as_int(values.get("WEB_SEARCH_KEY_QUOTA_LIMIT"), 1000),
            "max_results": self._as_int(values.get("WEB_SEARCH_MAX_RESULTS"), 5),
            "timeout": self._as_int(values.get("WEB_SEARCH_TIMEOUT"), 15),
            "_ready": any(bool(item["key_value"]) for item in keys),
        }

    @staticmethod
    def _parse_providers(values: Mapping[str, str]) -> list[dict[str, str]]:
        groups: dict[int, dict[str, str]] = {}
        for key, value in values.items():
            match = re.match(r"^LLM_PROVIDER_(\d+)_(NAME|PROTOCOL|BASE_URL|API_KEY)$", key)
            if match:
                groups.setdefault(int(match.group(1)), {})[match.group(2)] = value
        return [
            {
                "name": group.get("NAME", f"provider_{index}"),
                "protocol": group.get("PROTOCOL", "openai_compatible"),
                "base_url": group.get("BASE_URL", ""),
                "api_key_value": group.get("API_KEY", ""),
            }
            for index, group in sorted(groups.items())
        ]

    @staticmethod
    def _parse_zhiqiu_accounts(values: Mapping[str, str]) -> list[dict[str, str]]:
        if "ZQ_ACCOUNTS_JSON" in values:
            structured = values.get("ZQ_ACCOUNTS_JSON", "")
            try:
                raw = json.loads(structured)
                if isinstance(raw, list):
                    return [
                        {
                            "name": str(item.get("name") or item.get("username", "")),
                            "username": str(item.get("username", "")),
                            "password_value": str(item.get("password", "")),
                        }
                        for item in raw
                        if isinstance(item, dict)
                    ]
            except (json.JSONDecodeError, TypeError):
                logger.warning("读取知秋结构化账号失败，账号状态保持未配置")
            return []
        legacy = values.get("ZQ_ACCOUNTS", "")
        accounts: list[dict[str, str]] = []
        for pair in legacy.split(",") if legacy else []:
            if ":" in pair:
                username, password = pair.split(":", 1)
                accounts.append(
                    {
                        "name": username.strip(),
                        "username": username.strip(),
                        "password_value": password.strip(),
                    }
                )
        if accounts:
            return accounts
        try:
            raw_config = yaml.safe_load(ZHIQIU_CONFIG_PATH.read_text(encoding="utf-8")) or {}
            configured_accounts = raw_config.get("accounts", {})
        except (OSError, UnicodeError, yaml.YAMLError, AttributeError) as exc:
            logger.warning("读取知秋原有账号池失败", extra={"error_type": type(exc).__name__})
            return []
        if not isinstance(configured_accounts, dict):
            return []
        return [
            {
                "name": str(name),
                "username": str(details.get("username", "")),
                "password_value": str(details.get("password", "")),
            }
            for name, details in configured_accounts.items()
            if isinstance(details, dict) and details.get("username") and details.get("password")
        ]

    @staticmethod
    def _parse_ifind_accounts(values: Mapping[str, str]) -> list[dict[str, str]]:
        structured = values.get("IFIND_ACCOUNTS_JSON", "")
        if structured:
            try:
                raw = json.loads(structured)
                if isinstance(raw, list):
                    return [
                        {
                            "name": str(item.get("name") or item.get("username", "")),
                            "username": str(item.get("username", "")),
                            "password_value": str(item.get("password", "")),
                        }
                        for item in raw
                        if isinstance(item, dict)
                    ]
            except (json.JSONDecodeError, TypeError):
                logger.warning("读取 iFinD 结构化账号失败，账号状态保持未配置")
            return []
        username = values.get("IFIND_USERNAME", "")
        password = values.get("IFIND_PASSWORD", "")
        if not username and not password:
            return []
        return [{"name": username or "primary", "username": username, "password_value": password}]

    @staticmethod
    def _parse_web_search_keys(values: Mapping[str, str]) -> list[dict[str, str]]:
        """解析 WEB_SEARCH_API_KEYS JSON，回退到单 key TAVILY_API_KEY."""
        structured = values.get("WEB_SEARCH_API_KEYS", "")
        if structured:
            try:
                raw = json.loads(structured)
                if isinstance(raw, list):
                    return [
                        {
                            "name": str(item.get("name") or f"key_{idx}"),
                            "key_value": str(item.get("key", "")),
                        }
                        for idx, item in enumerate(raw)
                        if isinstance(item, dict) and item.get("key")
                    ]
            except (json.JSONDecodeError, TypeError):
                logger.warning("解析 WEB_SEARCH_API_KEYS 失败，回退到单 key")
        # 回退到单 key
        single = values.get("TAVILY_API_KEY", "") or values.get("BING_API_KEY", "")
        if single:
            return [{"name": "default", "key_value": single}]
        return []

    @staticmethod
    def _secret_view(value: str) -> dict[str, Any]:
        if not value:
            return {"configured": False, "masked_value": None, "value": None}
        suffix = value[-SECRET_SUFFIX_LENGTH:]
        return {"configured": True, "masked_value": f"********{suffix}", "value": value}

    @staticmethod
    def _database_secret_view(value: str) -> dict[str, Any]:
        if not value:
            return {"configured": False, "masked_value": None, "value": None}
        try:
            parsed = urlsplit(value)
            host = parsed.hostname or "local"
            port = f":{parsed.port}" if parsed.port else ""
            path = parsed.path or ""
            masked = f"{parsed.scheme}://***@{host}{port}{path}" if parsed.scheme else "********"
        except ValueError:
            masked = "********"
        return {"configured": True, "masked_value": masked, "value": value}

    @staticmethod
    def _merge_secret(new_value: Any, clear: bool, existing: str) -> str:
        if clear:
            return ""
        if new_value is None or str(new_value) == "":
            return existing
        return str(new_value)

    @staticmethod
    def _required_string(value: Any, label: str) -> str:
        normalized = str(value).strip() if value is not None else ""
        if not normalized:
            raise ConfigurationError(f"{label}不能为空")
        return normalized

    @staticmethod
    def _bounded_int(value: Any, minimum: int, maximum: int) -> str:
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ConfigurationError("数值配置无效") from exc
        if not minimum <= parsed <= maximum:
            raise ConfigurationError("数值配置超出允许范围")
        return str(parsed)

    @staticmethod
    def _boolean_string(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if str(value).lower() in {"true", "1"}:
            return "true"
        if str(value).lower() in {"false", "0"}:
            return "false"
        raise ConfigurationError("布尔配置无效")

    @staticmethod
    def _rotation_strategy(value: Any) -> str:
        normalized = str(value)
        if normalized not in {"round_robin", "random", "least_used"}:
            raise ConfigurationError("账号轮询策略无效")
        return normalized

    @staticmethod
    def _log_level(value: Any) -> str:
        normalized = str(value).upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ConfigurationError("日志级别无效")
        return normalized

    @staticmethod
    def _validate_database_url(value: str) -> None:
        try:
            parsed = urlsplit(value)
        except ValueError as exc:
            raise ConfigurationError("数据库地址格式无效") from exc
        if parsed.scheme not in {
            "postgresql",
            "postgresql+psycopg2",
            "sqlite",
            "mysql",
            "mysql+pymysql",
        }:
            raise ConfigurationError("数据库地址协议不受支持")
        if parsed.scheme != "sqlite" and not parsed.hostname:
            raise ConfigurationError("数据库地址缺少主机")

    @staticmethod
    def _quote_env_value(value: str) -> str:
        return "'" + value.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n") + "'"

    @staticmethod
    def _as_bool(value: str) -> bool:
        return value.lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _as_int(value: str | None, default: int) -> int:
        try:
            return int(value) if value is not None else default
        except ValueError:
            return default

    @staticmethod
    def _is_supported_key(key: str) -> bool:
        static_keys = {
            "ZQ_ACCOUNTS_JSON",
            "ZQ_ACCOUNTS",
            "ZQ_ROTATION_ENABLED",
            "ZQ_ROTATION_STRATEGY",
            "ZQ_MAX_RETRIES",
            "ZQ_RETRY_DELAY",
            "ZQ_LEASE_TIMEOUT",
            "ZQ_MAX_CONSECUTIVE_FAILURES",
            "IFIND_USERNAME",
            "IFIND_PASSWORD",
            "IFIND_ACCOUNTS_JSON",
            "IFIND_BACKEND",
            "IFIND_HTTP_BASE_URL",
            "DATABASE_URL",
            "LOG_LEVEL",
            "LOG_DIR",
            "LLM_EXTRACT_MAX_WORKERS",
            "LLM_EXTRACT_MAX_RETRIES",
            "LLM_EXTRACT_CHUNK_SIZE",
            "LLM_EXTRACT_CHUNK_OVERLAP",
            "LLM_EXTRACT_LONG_TEXT_THRESHOLD",
            "WEB_SEARCH_PROVIDER",
            "WEB_SEARCH_API_KEYS",
            "TAVILY_API_KEY",
            "BING_API_KEY",
            "WEB_SEARCH_KEY_ROTATION",
            "WEB_SEARCH_KEY_MAX_FAILURES",
            "WEB_SEARCH_KEY_LOCK_SECONDS",
            "WEB_SEARCH_KEY_COOLDOWN_SECONDS",
            "WEB_SEARCH_KEY_QUOTA_LIMIT",
            "WEB_SEARCH_MAX_RESULTS",
            "WEB_SEARCH_FETCH_CONTENT",
            "WEB_SEARCH_MAX_CHARS",
            "WEB_SEARCH_TIMEOUT",
        }
        return key in static_keys or bool(
            re.match(r"^LLM_PROVIDER_\d+_", key) or re.match(r"^TASK_.+_(PROVIDER|MODEL)$", key)
        )
