"""
并发安全的账号管理器 - 支持多进程/多模块同时调用

主要功能：
1. 文件锁协调多个进程的账号分配
2. 账号状态持久化到共享文件
3. 账号租借模式（acquire/release）
4. 支持按模块分配不同账号
"""
import json
import logging
import random
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import yaml

# 平台兼容的文件锁
try:
    import fcntl

    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False
    try:
        import msvcrt

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
        self._lock_file = None

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

    def release(self):
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

    def __enter__(self):
        if not self.acquire():
            raise RuntimeError(f"无法获取锁: {self.lock_path}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
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
        """加载配置文件,优先从环境变量 ZQ_ACCOUNTS 读取账号"""
        import os

        # 尝试从环境变量加载账号
        zq_accounts_env = os.environ.get("ZQ_ACCOUNTS")
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

        # 尝试从配置文件加载其他配置（账号轮换、进度追踪等）
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        except Exception:
            config = {}

        # 如果环境变量有账号,优先使用环境变量的;否则用配置文件的
        if accounts:
            config["accounts"] = accounts
        elif "accounts" not in config:
            config["accounts"] = {}

        return config

    def _parse_rotation_config(self) -> RotationConfig:
        """解析轮询配置"""
        cfg = self.config.get("account_rotation", {})
        return RotationConfig(
            enabled=cfg.get("enabled", True),
            max_retries=cfg.get("max_retries", 3),
            retry_delay=cfg.get("retry_delay", 5),
            rotation_strategy=cfg.get("rotation_strategy", "round_robin"),
            lease_timeout=cfg.get("lease_timeout", 300),
            max_consecutive_failures=cfg.get("max_consecutive_failures", 10),
        )

    def _init_state(self):
        """初始化账号状态"""
        if self.state_path.exists():
            try:
                self._load_state()
            except Exception as e:
                logger.warning(f"加载状态文件失败，使用新状态: {e}")
                self._init_new_state()
        else:
            self._init_new_state()

    def _init_new_state(self):
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

    def _save_state(self, state: AccountManagerState):
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

        # 检查永久禁用
        if account.is_disabled:
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

    def get_available_accounts(self) -> List[str]:
        """获取可用账号列表"""
        with FileLock(self.lock_path):
            state = self._load_state()
            state = self._clean_expired_leases(state)

            available = []
            for name, account in state.accounts.items():
                if self._is_account_available(account):
                    available.append(name)

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
            available = [
                name for name, acc in state.accounts.items() if self._is_account_available(acc)
            ]

            if not available:
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

    def release_account(self, account_name: str):
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

    def record_success(self, account_name: str):
        """记录成功"""
        with FileLock(self.lock_path):
            state = self._load_state()

            if account_name in state.accounts:
                account = state.accounts[account_name]
                account.success_count += 1
                account.consecutive_failures = 0
                self._save_state(state)

    def record_failure(self, account_name: str, lock_seconds: int = 300):
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

    def get_account_credentials(self, account_name: str) -> Optional[Dict]:
        """获取指定账号的凭证"""
        accounts = self.config.get("accounts", {})
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

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.account_name:
            self.manager.release_account(self.account_name)
