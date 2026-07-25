"""
并发安全的账号管理器 - 支持多进程/多模块同时调用

主要功能：
1. 文件锁协调多个进程的账号分配
2. 账号状态持久化到共享文件
3. 账号租借模式（acquire/release）
4. 支持按模块分配不同账号
"""

import importlib
import json
import logging
import random
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from types import TracebackType
from typing import IO, Any, Dict, List, Optional, cast

import yaml

# 平台兼容的文件锁
try:
    import fcntl

    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False
    try:
        msvcrt = importlib.import_module("msvcrt")

        HAS_MSVCRT = True
    except ImportError:
        HAS_MSVCRT = False


logger = logging.getLogger(__name__)


@dataclass
class AccountStats:
    """账号统计信息"""

    name: str
    use_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    last_used: Optional[str] = None  # ISO format string
    last_failure: Optional[str] = None  # ISO format string
    is_locked: bool = False
    lock_until: Optional[str] = None  # ISO format string
    is_disabled: bool = False  # 永久禁用（连续失败过多）
    disabled_at: Optional[str] = None  # 永久禁用的时间戳，用于冷却期自动解禁
    leased_by: Optional[str] = None  # 租借者标识（模块名或进程ID）
    leased_at: Optional[str] = None  # 租借时间


@dataclass
class RotationConfig:
    """轮询配置"""

    enabled: bool = True
    max_retries: int = 3
    retry_delay: int = 5
    rotation_strategy: str = "round_robin"  # round_robin|random|least_used
    lease_timeout: int = 300  # 账号租借超时时间（秒）
    max_consecutive_failures: int = 10  # 连续失败 N 次后永久禁用账号
    disable_cooldown_hours: float = 6.0  # 永久禁用 N 小时后自动解禁，给一次重试机会


@dataclass
class AccountManagerState:
    """账号管理器持久化状态"""

    version: str = "1.0"
    current_index: int = 0
    accounts: Dict[str, AccountStats] = field(default_factory=dict)
    last_updated: Optional[str] = None


class FileLock:
    """跨平台文件锁 - 用于跨进程同步"""

    def __init__(self, lock_path: Path, timeout: int = 30):
        self.lock_path = Path(lock_path)
        self.timeout = timeout
        self._lock_file: Optional[IO[str]] = None

    def acquire(self) -> bool:
        """获取锁"""
        start_time = time.time()
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)

        while True:
            try:
                self._lock_file = open(self.lock_path, "w")

                if HAS_FCNTL:
                    # Unix/Linux: 使用 fcntl
                    fcntl.flock(self._lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                elif HAS_MSVCRT:
                    # Windows: 使用 msvcrt
                    msvcrt.locking(self._lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    # 无锁模式 - 单机场景下可以工作
                    pass

                self._lock_file.write(f"{datetime.now().isoformat()}\n")
                self._lock_file.flush()
                return True
            except (IOError, OSError):
                if self._lock_file:
                    self._lock_file.close()
                    self._lock_file = None

                elapsed = time.time() - start_time
                if elapsed >= self.timeout:
                    logger.warning(f"获取锁超时: {self.lock_path}")
                    return False

                time.sleep(0.1)

    def release(self) -> None:
        """释放锁"""
        if self._lock_file:
            try:
                if HAS_FCNTL:
                    fcntl.flock(self._lock_file, fcntl.LOCK_UN)
                elif HAS_MSVCRT:
                    msvcrt.locking(self._lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                self._lock_file.close()
            except Exception:
                pass
            self._lock_file = None

    def __enter__(self) -> "FileLock":
        if not self.acquire():
            raise RuntimeError(f"无法获取锁: {self.lock_path}")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.release()


class AccountManager:
    """并发安全的账号管理器"""

    def __init__(self, config_path: str, module_identifier: Optional[str] = None):
        """
        初始化账号管理器

        Args:
            config_path: 配置文件路径
            module_identifier: 模块标识符（如 "report", "news", "meeting" 或进程ID）
        """
        self.config_path = Path(config_path)
        self.module_identifier = module_identifier or f"process_{id(self)}"
        self.config = self._load_config()
        self.rotation_config = self._parse_rotation_config()

        # 状态文件和锁文件路径
        base_dir = self.config_path.parent
        self.state_path = base_dir / f".{self.config_path.stem}_account_state.json"
        self.lock_path = base_dir / f".{self.config_path.stem}_account_lock"

        # 初始化状态
        self._init_state()

    def _load_config(self) -> dict:
        """加载配置文件,按优先级从环境变量读取账号。

        账号来源优先级（与 ConfigurationService._parse_zhiqiu_accounts 对齐）:
        1. ``ZQ_ACCOUNTS_JSON`` —— 结构化 JSON 数组，系统配置工作台保存时写入此格式
        2. ``ZQ_ACCOUNTS`` —— 旧版 ``user:pass,user:pass`` 逗号分隔格式
        3. 配置文件（config.yaml）的 ``accounts`` 字段 —— 最后兜底

        系统配置保存时会写入 ``ZQ_ACCOUNTS_JSON`` 并删除旧版 ``ZQ_ACCOUNTS``，
        因此必须读取 JSON 格式，否则运行时账号池为空。
        """
        accounts = self._load_accounts_from_env()

        # 尝试从配置文件加载其他配置（账号轮换、进度追踪等）
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        except Exception as e:
            # except 块内的 logger 调用需防护，避免 structlog 二次异常
            try:
                logger.warning(f"加载配置文件失败，使用空配置: {e}")
            except Exception:
                pass
            config = {}

        # 如果环境变量有账号,优先使用环境变量的;否则用配置文件的
        if accounts:
            config["accounts"] = accounts
        elif "accounts" not in config:
            config["accounts"] = {}

        return config

    @staticmethod
    def _load_accounts_from_env() -> Dict[str, Dict[str, str]]:
        """从环境变量加载账号，优先 ZQ_ACCOUNTS_JSON，回退 ZQ_ACCOUNTS。

        Returns:
            以账号名为 key 的凭证字典，形如
            ``{"huangyongjia": {"username": "...", "password": "..."}}``。
        """
        import os

        # 优先解析结构化 JSON 格式（系统配置工作台保存时写入）
        zq_accounts_json = os.environ.get("ZQ_ACCOUNTS_JSON", "")
        if zq_accounts_json:
            accounts = AccountManager._parse_accounts_json(zq_accounts_json)
            if accounts:
                try:
                    logger.info(f"从 ZQ_ACCOUNTS_JSON 加载到 {len(accounts)} 个知丘账号")
                except Exception:
                    pass
                return accounts
            # JSON 解析失败或为空时，记录警告并回退到旧版格式
            try:
                logger.warning("ZQ_ACCOUNTS_JSON 解析失败或为空，回退到 ZQ_ACCOUNTS")
            except Exception:
                pass

        # 回退到旧版逗号分隔格式
        zq_accounts_env = os.environ.get("ZQ_ACCOUNTS", "")
        accounts = {}
        if zq_accounts_env:
            # 解析 ZQ_ACCOUNTS: "user1:pass1,user2:pass2" -> {"user1": {"username": "user1", "password": "pass1"}, ...}
            for account_pair in zq_accounts_env.split(","):
                if ":" in account_pair:
                    username, password = account_pair.split(":", 1)
                    # 使用用户名作为账号 key
                    accounts[username.strip()] = {
                        "username": username.strip(),
                        "password": password.strip(),
                    }
            if accounts:
                try:
                    logger.info(f"从 ZQ_ACCOUNTS 加载到 {len(accounts)} 个知丘账号")
                except Exception:
                    pass

        return accounts

    @staticmethod
    def _parse_accounts_json(raw: str) -> Dict[str, Dict[str, str]]:
        """解析 ZQ_ACCOUNTS_JSON 字符串为账号字典。

        格式示例::

            [{"name": "acc1", "username": "u1", "password": "p1"}, ...]

        解析失败时返回空 dict（不抛异常），由调用方决定是否回退。
        """
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as e:
            try:
                logger.warning(f"解析 ZQ_ACCOUNTS_JSON 失败: {e}")
            except Exception:
                pass
            return {}

        if not isinstance(data, list):
            try:
                logger.warning("ZQ_ACCOUNTS_JSON 不是数组，已忽略")
            except Exception:
                pass
            return {}

        accounts: Dict[str, Dict[str, str]] = {}
        for item in data:
            if not isinstance(item, dict):
                continue
            username = str(item.get("username", "")).strip()
            if not username:
                # 没有 username 的条目无法登录，跳过
                continue
            # 优先用 name 作为账号 key（与系统配置一致），否则用 username
            key = str(item.get("name") or username).strip()
            accounts[key] = {
                "username": username,
                "password": str(item.get("password", "")),
            }
        return accounts

    def _parse_rotation_config(self) -> RotationConfig:
        """解析轮询配置"""
        import os

        cfg = self.config.get("account_rotation", {})

        def _env_int(key: str, default: int) -> int:
            raw = os.environ.get(key, "")
            if not raw:
                return default
            try:
                return int(raw)
            except (TypeError, ValueError):
                try:
                    logger.warning(f"环境变量 {key} 值非法: {raw}，使用默认 {default}")
                except Exception:
                    pass
                return default

        def _env_float(key: str, default: float) -> float:
            raw = os.environ.get(key, "")
            if not raw:
                return default
            try:
                return float(raw)
            except (TypeError, ValueError):
                try:
                    logger.warning(f"环境变量 {key} 值非法: {raw}，使用默认 {default}")
                except Exception:
                    pass
                return default

        return RotationConfig(
            enabled=cfg.get("enabled", True),
            max_retries=_env_int("ZQ_MAX_RETRIES", cfg.get("max_retries", 3)),
            retry_delay=_env_int("ZQ_RETRY_DELAY", cfg.get("retry_delay", 5)),
            rotation_strategy=os.environ.get(
                "ZQ_ROTATION_STRATEGY", cfg.get("rotation_strategy", "round_robin")
            ),
            lease_timeout=_env_int("ZQ_LEASE_TIMEOUT", cfg.get("lease_timeout", 300)),
            max_consecutive_failures=_env_int(
                "ZQ_MAX_CONSECUTIVE_FAILURES", cfg.get("max_consecutive_failures", 10)
            ),
            disable_cooldown_hours=_env_float(
                "ZQ_DISABLE_COOLDOWN_HOURS", cfg.get("disable_cooldown_hours", 6.0)
            ),
        )

    def _init_state(self) -> None:
        """初始化账号状态"""
        if self.state_path.exists():
            try:
                self._load_state()
            except Exception as e:
                logger.warning(f"加载状态文件失败，使用新状态: {e}")
                self._init_new_state()
        else:
            self._init_new_state()

    def _init_new_state(self) -> None:
        """初始化新状态"""
        accounts = self.config.get("accounts", {})
        state = AccountManagerState()

        for name in accounts.keys():
            state.accounts[name] = AccountStats(name=name)

        self._save_state(state)

    def _load_state(self) -> AccountManagerState:
        """从文件加载状态"""
        with open(self.state_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        state = AccountManagerState(
            version=data.get("version", "1.0"),
            current_index=data.get("current_index", 0),
            last_updated=data.get("last_updated"),
        )

        for name, account_data in data.get("accounts", {}).items():
            state.accounts[name] = AccountStats(**account_data)

        return state

    def _save_state(self, state: AccountManagerState) -> None:
        """保存状态到文件"""
        state.last_updated = datetime.now().isoformat()

        data = {
            "version": state.version,
            "current_index": state.current_index,
            "last_updated": state.last_updated,
            "accounts": {name: asdict(acc) for name, acc in state.accounts.items()},
        }

        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _clean_expired_leases(self, state: AccountManagerState) -> AccountManagerState:
        """清理过期的账号租借"""
        now = datetime.now()

        for name, account in state.accounts.items():
            if account.leased_by and account.leased_at:
                leased_time = datetime.fromisoformat(account.leased_at)
                elapsed = (now - leased_time).total_seconds()

                if elapsed > self.rotation_config.lease_timeout:
                    logger.warning(f"账号 {name} 的租借已超时，强制释放")
                    account.leased_by = None
                    account.leased_at = None

        return state

    def _is_account_available(self, account: AccountStats) -> bool:
        """检查账号是否可用"""
        now = datetime.now()

        # 检查永久禁用 —— 超过冷却期则自动解禁，给一次重试机会
        if account.is_disabled:
            if self._should_auto_recover(account, now):
                account.is_disabled = False
                account.disabled_at = None
                account.consecutive_failures = 0
                try:
                    logger.info(
                        f"账号 {account.name} 永久禁用已超过冷却期 "
                        f"{self.rotation_config.disable_cooldown_hours} 小时，自动解禁"
                    )
                except Exception:
                    pass
            else:
                return False

        # 检查临时锁定
        if account.is_locked and account.lock_until:
            lock_until = datetime.fromisoformat(account.lock_until)
            if now < lock_until:
                return False
            # 锁定已过期
            account.is_locked = False
            account.lock_until = None

        # 检查是否被其他进程租借
        if account.leased_by and account.leased_by != self.module_identifier:
            return False

        return True

    def _should_auto_recover(self, account: AccountStats, now: datetime) -> bool:
        """判断永久禁用的账号是否已过冷却期、可以自动解禁。

        - ``disabled_at`` 缺失（旧状态文件）视为已达冷却期，给一次重试机会，
          避免历史遗留的永久禁用账号永远卡死。
        - 冷却期 <= 0 时不自动解禁（运维显式关闭自愈）。
        """
        cooldown = self.rotation_config.disable_cooldown_hours
        if cooldown <= 0:
            return False
        if not account.disabled_at:
            return True
        try:
            disabled_at = datetime.fromisoformat(account.disabled_at)
        except (TypeError, ValueError):
            # 时间戳损坏，给一次重试机会
            return True
        return now >= disabled_at + timedelta(hours=cooldown)

    def get_available_accounts(self) -> List[str]:
        """获取可用账号列表"""
        with FileLock(self.lock_path):
            state = self._load_state()
            state = self._clean_expired_leases(state)

            available = []
            changed = False
            for name, account in state.accounts.items():
                before = (account.is_disabled, account.is_locked)
                if self._is_account_available(account):
                    available.append(name)
                if (account.is_disabled, account.is_locked) != before:
                    changed = True

            # _is_account_available 可能自动解禁或清理过期锁,需落盘
            if changed:
                self._save_state(state)

            return available

    def acquire_account(self, preferred_account: Optional[str] = None) -> Optional[str]:
        """
        租借一个账号

        Args:
            preferred_account: 首选账号名

        Returns:
            租到的账号名，失败返回 None
        """
        with FileLock(self.lock_path):
            state = self._load_state()
            state = self._clean_expired_leases(state)

            # 先尝试首选账号
            if preferred_account:
                account = state.accounts.get(preferred_account)
                if account and self._is_account_available(account):
                    return self._lease_account(state, preferred_account)

            # 按策略选择账号
            available = []
            changed = False
            for name, acc in state.accounts.items():
                before = (acc.is_disabled, acc.is_locked)
                if self._is_account_available(acc):
                    available.append(name)
                if (acc.is_disabled, acc.is_locked) != before:
                    changed = True

            if not available:
                # _is_account_available 可能已自动解禁,需落盘以便下次重试
                if changed:
                    self._save_state(state)
                logger.warning("没有可用账号")
                return None

            strategy = self.rotation_config.rotation_strategy

            if strategy == "round_robin":
                selected = self._round_robin_select(state, available)
            elif strategy == "random":
                selected = random.choice(available)
            elif strategy == "least_used":
                available_stats = [state.accounts[name] for name in available]
                available_stats.sort(key=lambda x: x.use_count)
                selected = available_stats[0].name
            else:
                selected = self._round_robin_select(state, available)

            return self._lease_account(state, selected)

    def _lease_account(self, state: AccountManagerState, account_name: str) -> str:
        """租借账号（内部方法，需要在锁内调用）"""
        account = state.accounts[account_name]
        account.leased_by = self.module_identifier
        account.leased_at = datetime.now().isoformat()
        account.last_used = datetime.now().isoformat()
        account.use_count += 1

        # 更新 current_index 用于 round_robin
        account_names = list(state.accounts.keys())
        if account_name in account_names:
            state.current_index = account_names.index(account_name)

        self._save_state(state)

        logger.info(f"模块 {self.module_identifier} 租借账号: {account_name}")
        return account_name

    def release_account(self, account_name: str) -> None:
        """
        释放账号

        Args:
            account_name: 要释放的账号名
        """
        with FileLock(self.lock_path):
            state = self._load_state()

            account = state.accounts.get(account_name)
            if account and account.leased_by == self.module_identifier:
                account.leased_by = None
                account.leased_at = None
                self._save_state(state)
                logger.info(f"模块 {self.module_identifier} 释放账号: {account_name}")

    def _round_robin_select(self, state: AccountManagerState, available: List[str]) -> str:
        """轮询选择"""
        account_names = list(state.accounts.keys())

        while True:
            state.current_index = (state.current_index + 1) % len(account_names)
            candidate = account_names[state.current_index]
            if candidate in available:
                return candidate

    def record_success(self, account_name: str) -> None:
        """记录成功"""
        with FileLock(self.lock_path):
            state = self._load_state()

            if account_name in state.accounts:
                account = state.accounts[account_name]
                account.success_count += 1
                account.consecutive_failures = 0
                self._save_state(state)

    def record_failure(self, account_name: str, lock_seconds: int = 300) -> None:
        """记录失败（临时锁定，连续失败过多则永久禁用）"""
        with FileLock(self.lock_path):
            state = self._load_state()

            if account_name in state.accounts:
                account = state.accounts[account_name]
                account.failure_count += 1
                account.consecutive_failures += 1
                account.last_failure = datetime.now().isoformat()

                # 连续失败超过阈值 → 永久禁用
                if account.consecutive_failures >= self.rotation_config.max_consecutive_failures:
                    account.is_disabled = True
                    account.disabled_at = datetime.now().isoformat()
                    account.is_locked = False
                    account.lock_until = None
                    account.leased_by = None
                    account.leased_at = None
                    logger.error(f"账号 {account_name} 连续失败 {account.consecutive_failures} 次，已永久禁用")
                elif lock_seconds > 0:
                    account.is_locked = True
                    lock_until = datetime.now() + timedelta(seconds=lock_seconds)
                    account.lock_until = lock_until.isoformat()
                    logger.warning(f"账号 {account_name} 已被临时锁定 {lock_seconds} 秒")

                self._save_state(state)

    def get_account_credentials(self, account_name: str) -> Optional[Dict[str, Any]]:
        """获取指定账号的凭证"""
        accounts = cast(Dict[str, Dict[str, Any]], self.config.get("accounts", {}))
        return accounts.get(account_name)

    def get_account_stats(self, account_name: str) -> Optional[AccountStats]:
        """获取账号统计信息"""
        with FileLock(self.lock_path):
            state = self._load_state()
            return state.accounts.get(account_name)

    def get_all_stats(self) -> Dict[str, AccountStats]:
        """获取所有账号统计信息"""
        with FileLock(self.lock_path):
            state = self._load_state()
            return dict(state.accounts)


class AccountLease:
    """
    账号租借上下文管理器

    使用示例:
        with AccountLease(account_manager, "my_module") as account:
            # 使用账号...
            credentials = account_manager.get_account_credentials(account)
    """

    def __init__(self, manager: AccountManager, preferred_account: Optional[str] = None):
        self.manager = manager
        self.preferred_account = preferred_account
        self.account_name: Optional[str] = None

    def __enter__(self) -> Optional[str]:
        self.account_name = self.manager.acquire_account(self.preferred_account)
        return self.account_name

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self.account_name:
            self.manager.release_account(self.account_name)
