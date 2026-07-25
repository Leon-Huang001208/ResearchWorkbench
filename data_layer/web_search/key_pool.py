"""
API key 池——多 key 轮询、失败追踪、月度额度管理、冷却期自愈.

借鉴知丘 AccountManager 的池化模式，适配 API key 场景（无需跨进程文件锁）。

配额模型：
- 每个 key 每月有固定积分额度（默认 1000）
- 每次 API 调用后上报，达到额度自动停用
- 下月 1 号 0 点自动刷新额度
- API 返回 402/429 时也可主动触发配额耗尽
"""

import datetime as dt
import json
import os
import random
import threading
import time
from dataclasses import dataclass
from typing import Optional

from core.observability import get_logger

logger = get_logger(__name__)


# ── 月度重置工具 ──────────────────────────────────────


def _next_month_reset() -> float:
    """返回下月 1 号 00:00 的 UTC timestamp."""
    now = dt.datetime.utcnow()
    if now.month == 12:
        nxt = now.replace(
            year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0
        )
    else:
        nxt = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return nxt.timestamp()


# ── 状态 / 配置 ──────────────────────────────────────


@dataclass
class KeyStats:
    """单个 key 的状态."""

    name: str
    key: str = ""
    use_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    last_used: float = 0.0
    last_failure: float = 0.0
    is_locked: bool = False
    lock_until: float = 0.0
    is_disabled: bool = False
    disabled_at: float = 0.0
    leased_by: Optional[str] = None
    leased_at: float = 0.0

    # ── 月度额度 ──
    quota_total: int = 1000
    quota_used: int = 0
    quota_exhausted: bool = False
    quota_reset_at: float = 0.0  # 下月 1 号的 timestamp


@dataclass
class PoolConfig:
    """池配置."""

    rotation_strategy: str = "round_robin"
    max_consecutive_failures: int = 5
    lock_seconds: int = 60
    disable_cooldown_seconds: float = 3600.0
    lease_timeout_seconds: int = 300
    quota_limit: int = 1000  # 每 key 月度积分上限


DEFAULT_CONFIG = PoolConfig()


# ── 池 ───────────────────────────────────────────────


class ApiKeyPool:
    """API key 池——多 key 轮询 + 健康追踪 + 月度额度.

    线程安全，支持 acquire/release、失败追踪、额度管理、自动禁用/解禁。
    """

    def __init__(
        self,
        keys: dict[str, str],
        config: PoolConfig | None = None,
    ) -> None:
        self._config = config or DEFAULT_CONFIG
        self._lock = threading.Lock()
        self._keys: dict[str, KeyStats] = {}
        self._key_order: list[str] = []
        self._round_robin_idx = 0

        quota_limit = self._config.quota_limit
        reset_at = _next_month_reset()
        for name, key_value in keys.items():
            self._keys[name] = KeyStats(
                name=name,
                key=key_value,
                quota_total=quota_limit,
                quota_reset_at=reset_at,
            )
            self._key_order.append(name)

        logger.info(
            "api key pool initialized",
            key_count=len(self._keys),
            strategy=self._config.rotation_strategy,
            quota_limit=quota_limit,
        )

    # ── 工厂方法 ──────────────────────────────────────

    @classmethod
    def from_json_value(cls, raw: str, config: PoolConfig | None = None) -> "ApiKeyPool":
        """Build a key pool from a JSON string without reading process environment."""
        if not raw:
            return cls({}, config)

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("failed to parse api keys json", error_type=type(exc).__name__)
            return cls({}, config)

        keys: dict[str, str] = {}
        if isinstance(data, list):
            for idx, item in enumerate(data):
                if isinstance(item, dict):
                    name = str(item.get("name") or f"key_{idx}")
                    keys[name] = str(item.get("key", ""))
                elif isinstance(item, str):
                    keys[f"key_{idx}"] = item
        elif isinstance(data, dict):
            keys = {str(key): str(value) for key, value in data.items()}

        return cls(keys, config)

    @classmethod
    def from_json_env(cls, env_var: str, config: PoolConfig | None = None) -> "ApiKeyPool":
        """从环境变量 JSON 数组构建 key 池."""
        return cls.from_json_value(os.environ.get(env_var, ""), config)

    @classmethod
    def from_single_key(cls, key: str, name: str = "default") -> "ApiKeyPool":
        if not key:
            return cls({})
        return cls({name: key})

    # ── 查询 ──────────────────────────────────────────

    @property
    def key_count(self) -> int:
        with self._lock:
            return len(self._keys)

    def get_key(self, name: str) -> str:
        with self._lock:
            ks = self._keys.get(name)
            return ks.key if ks else ""

    def get_stats(self, name: str) -> KeyStats | None:
        with self._lock:
            return self._keys.get(name)

    def get_all_stats(self) -> dict[str, KeyStats]:
        with self._lock:
            return dict(self._keys)

    def available_keys(self) -> list[str]:
        now = time.monotonic()
        with self._lock:
            return [name for name, ks in self._keys.items() if self._is_available(ks, now)]

    # ── 租借 ──────────────────────────────────────────

    def acquire(self, preferred: str | None = None) -> str | None:
        with self._lock:
            now = time.monotonic()
            self._refresh_states(now)

            if preferred:
                ks = self._keys.get(preferred)
                if ks and self._is_available(ks, now):
                    return self._lease(ks)

            available = [
                name for name in self._key_order if self._is_available(self._keys[name], now)
            ]
            if not available:
                logger.warning("no available api keys")
                return None

            strategy = self._config.rotation_strategy
            if strategy == "random":
                selected = random.choice(available)
            elif strategy == "least_used":
                selected = min(available, key=lambda n: self._keys[n].use_count)
            else:
                selected = self._round_robin_pick(available)

            return self._lease(self._keys[selected])

    def _round_robin_pick(self, available: list[str]) -> str:
        n = len(self._key_order)
        for _ in range(n):
            self._round_robin_idx = (self._round_robin_idx + 1) % n
            name = self._key_order[self._round_robin_idx]
            if name in available:
                return name
        return available[0]

    def release(self, name: str) -> None:
        with self._lock:
            ks = self._keys.get(name)
            if ks:
                ks.leased_by = None
                ks.leased_at = 0.0

    # ── 健康上报 ──────────────────────────────────────

    def report_success(self, name: str) -> None:
        with self._lock:
            ks = self._keys.get(name)
            if ks:
                ks.success_count += 1
                ks.consecutive_failures = 0

    def report_failure(self, name: str) -> None:
        with self._lock:
            ks = self._keys.get(name)
            if not ks:
                return
            ks.failure_count += 1
            ks.consecutive_failures += 1
            ks.last_failure = time.monotonic()

            cfg = self._config
            if ks.consecutive_failures >= cfg.max_consecutive_failures:
                ks.is_disabled = True
                ks.disabled_at = time.monotonic()
                ks.is_locked = False
                ks.lock_until = 0.0
                ks.leased_by = None
                ks.leased_at = 0.0
                logger.error(
                    "api key disabled after consecutive failures",
                    key_name=name,
                    consecutive_failures=ks.consecutive_failures,
                )
            elif cfg.lock_seconds > 0:
                ks.is_locked = True
                ks.lock_until = time.monotonic() + cfg.lock_seconds
                logger.warning(
                    "api key temporarily locked", key_name=name, seconds=cfg.lock_seconds
                )

    # ── 月度额度 ──────────────────────────────────────

    def report_quota_used(self, name: str, count: int = 1) -> None:
        """上报使用了 1 次额度。达到上限时自动标记配额耗尽，下月自动刷新。"""
        with self._lock:
            ks = self._keys.get(name)
            if not ks:
                return
            ks.quota_used += count
            if ks.quota_used >= ks.quota_total:
                ks.quota_exhausted = True
                ks.leased_by = None
                ks.leased_at = 0.0
                logger.warning(
                    "api key quota exhausted",
                    key_name=name,
                    quota_used=ks.quota_used,
                    quota_total=ks.quota_total,
                )

    def report_quota_exhausted(self, name: str) -> None:
        """主动标记配额耗尽（API 返回 402/429 时调用），下月自动刷新。"""
        with self._lock:
            ks = self._keys.get(name)
            if not ks:
                return
            ks.quota_exhausted = True
            ks.quota_used = ks.quota_total  # 标记已满
            ks.leased_by = None
            ks.leased_at = 0.0
            logger.warning("api key quota exhausted (reported by API)", key_name=name)

    # ── 内部 ──────────────────────────────────────────

    def _is_available(self, ks: KeyStats, now_mono: float) -> bool:
        """检查 key 是否可用（锁内调用）."""
        # ── 月度额度刷新 ──
        if ks.quota_exhausted:
            now_ts = time.time()
            if now_ts < ks.quota_reset_at:
                return False
            # 过了重置线 → 刷新额度
            ks.quota_exhausted = False
            ks.quota_used = 0
            ks.quota_reset_at = _next_month_reset()
            logger.info("api key quota refreshed for new month", key_name=ks.name)

        # ── 永久禁用 + 冷却期 ──
        if ks.is_disabled:
            cooldown = self._config.disable_cooldown_seconds
            if cooldown <= 0:
                return False
            if ks.disabled_at > 0 and now_mono < ks.disabled_at + cooldown:
                return False
            ks.is_disabled = False
            ks.disabled_at = 0.0
            ks.consecutive_failures = 0
            logger.info("api key auto-recovered after cooldown", key_name=ks.name)

        # ── 临时锁定 ──
        if ks.is_locked and now_mono < ks.lock_until:
            return False
        if ks.is_locked:
            ks.is_locked = False
            ks.lock_until = 0.0

        # ── 租约超时强制释放 ──
        if ks.leased_by and ks.leased_at > 0:
            if now_mono - ks.leased_at > self._config.lease_timeout_seconds:
                ks.leased_by = None
                ks.leased_at = 0.0
            else:
                return False

        return True

    def _lease(self, ks: KeyStats) -> str:
        import uuid

        ks.leased_by = uuid.uuid4().hex[:8]
        ks.leased_at = time.monotonic()
        ks.last_used = ks.leased_at
        ks.use_count += 1
        return ks.name

    def _refresh_states(self, now_mono: float) -> None:
        for ks in self._keys.values():
            self._is_available(ks, now_mono)
