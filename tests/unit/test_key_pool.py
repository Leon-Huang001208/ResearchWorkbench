"""ApiKeyPool 单元测试——多 key 池化、轮询、失败追踪、自愈."""

import time
from unittest.mock import patch

from data_layer.web_search.key_pool import ApiKeyPool, PoolConfig


class TestApiKeyPoolInit:
    def test_from_dict(self):
        pool = ApiKeyPool({"k1": "v1", "k2": "v2"})
        assert pool.key_count == 2
        assert pool.get_key("k1") == "v1"

    def test_from_json_env_list_of_strings(self):
        with patch.dict("os.environ", {"TEST_KEYS": '["a", "b", "c"]'}):
            pool = ApiKeyPool.from_json_env("TEST_KEYS")
            assert pool.key_count == 3
            assert pool.get_key("key_0") == "a"
            assert pool.get_key("key_1") == "b"

    def test_from_json_env_list_of_dicts(self):
        with patch.dict(
            "os.environ",
            {"TEST_KEYS": '[{"name": "alice", "key": "k-a"}, {"name": "bob", "key": "k-b"}]'},
        ):
            pool = ApiKeyPool.from_json_env("TEST_KEYS")
            assert pool.key_count == 2
            assert pool.get_key("alice") == "k-a"

    def test_from_json_env_empty(self):
        with patch.dict("os.environ", {"TEST_KEYS": ""}):
            pool = ApiKeyPool.from_json_env("TEST_KEYS")
            assert pool.key_count == 0

    def test_from_single_key(self):
        pool = ApiKeyPool.from_single_key("my-key", name="main")
        assert pool.key_count == 1
        assert pool.get_key("main") == "my-key"

    def test_from_single_empty_key(self):
        pool = ApiKeyPool.from_single_key("")
        assert pool.key_count == 0


class TestAcquireRelease:
    def test_acquire_returns_name(self):
        pool = ApiKeyPool({"a": "ka", "b": "kb"})
        name = pool.acquire()
        assert name in ("a", "b")
        pool.release(name)

    def test_acquire_leases_all_then_none(self):
        pool = ApiKeyPool({"a": "ka", "b": "kb"})
        n1 = pool.acquire()
        n2 = pool.acquire()
        assert n1 is not None
        assert n2 is not None
        # 第三个租不到
        n3 = pool.acquire()
        assert n3 is None
        pool.release(n1)
        pool.release(n2)

    def test_acquire_preferred(self):
        pool = ApiKeyPool({"x": "kx", "y": "ky"})
        name = pool.acquire(preferred="y")
        assert name == "y"
        pool.release(name)

    def test_round_robin_cycles(self):
        pool = ApiKeyPool({"a": "ka", "b": "kb", "c": "kc"})
        seen: set[str] = set()
        for _ in range(6):
            name = pool.acquire()
            assert name is not None
            seen.add(name)
            pool.release(name)
        assert seen == {"a", "b", "c"}

    def test_least_used_strategy(self):
        config = PoolConfig(rotation_strategy="least_used")
        pool = ApiKeyPool({"a": "ka", "b": "kb"}, config=config)
        # 用两次 a
        for _ in range(3):
            name = pool.acquire()
            pool.report_success(name)
            pool.release(name)
        # 最后几次应该偏向 b
        name = pool.acquire()
        assert name == "b"  # b 一次没用过
        pool.release(name)


class TestFailureAndRecovery:
    def test_consecutive_failures_disables_key(self):
        config = PoolConfig(max_consecutive_failures=3, lock_seconds=0)
        pool = ApiKeyPool({"a": "ka", "b": "kb"}, config=config)
        # 让 a 连续失败 3 次
        for _ in range(3):
            pool.report_failure("a")
        stats = pool.get_stats("a")
        assert stats is not None
        assert stats.is_disabled
        assert stats.consecutive_failures == 3
        # b 仍然可用
        assert "b" in pool.available_keys()

    def test_temporary_lock(self):
        config = PoolConfig(lock_seconds=999, max_consecutive_failures=100)
        pool = ApiKeyPool({"a": "ka"}, config=config)
        pool.report_failure("a")
        assert pool.get_stats("a").is_locked  # type: ignore[union-attr]
        assert pool.available_keys() == []

    def test_cooldown_auto_recovery(self):
        config = PoolConfig(
            max_consecutive_failures=1,
            lock_seconds=0,
            disable_cooldown_seconds=0.01,  # 10ms
        )
        pool = ApiKeyPool({"a": "ka"}, config=config)
        pool.report_failure("a")  # 立即永久禁用
        assert pool.get_stats("a").is_disabled  # type: ignore[union-attr]
        # 等冷却期过
        time.sleep(0.02)
        assert pool.available_keys() == ["a"]
        # 已自动解禁、清零连续失败
        assert not pool.get_stats("a").is_disabled  # type: ignore[union-attr]
        assert pool.get_stats("a").consecutive_failures == 0  # type: ignore[union-attr]

    def test_report_success_clears_consecutive(self):
        pool = ApiKeyPool({"a": "ka"})
        pool.report_failure("a")
        pool.report_failure("a")
        assert pool.get_stats("a").consecutive_failures == 2  # type: ignore[union-attr]
        pool.report_success("a")
        assert pool.get_stats("a").consecutive_failures == 0  # type: ignore[union-attr]


class TestQuotaManagement:
    def test_quota_used_exhausts_key(self):
        config = PoolConfig(quota_limit=3)
        pool = ApiKeyPool({"a": "ka"}, config=config)
        for _ in range(3):
            pool.report_quota_used("a")
        stats = pool.get_stats("a")
        assert stats.quota_exhausted
        assert stats.quota_used == 3
        assert pool.available_keys() == []

    def test_quota_exhausted_api_call(self):
        config = PoolConfig(quota_limit=1)
        pool = ApiKeyPool({"a": "ka"}, config=config)
        pool.report_quota_exhausted("a")
        stats = pool.get_stats("a")
        assert stats.quota_exhausted
        assert stats.quota_used == 1  # 标记已满

    def test_quota_refreshes_next_month(self):
        config = PoolConfig(quota_limit=1)
        pool = ApiKeyPool({"a": "ka"}, config=config)
        pool.report_quota_used("a")
        assert pool.get_stats("a").quota_exhausted

        # 模拟过了重置线：把 quota_reset_at 往回拨
        ks = pool.get_stats("a")
        import time as _time

        ks.quota_reset_at = _time.time() - 1  # 已过期
        assert pool.available_keys() == ["a"]
        # 验证已刷新
        assert not pool.get_stats("a").quota_exhausted
        assert pool.get_stats("a").quota_used == 0

    def test_quota_reset_sets_next_month_boundary(self):
        config = PoolConfig(quota_limit=5)
        pool = ApiKeyPool({"a": "ka"}, config=config)
        # 重置线应是下月 1 号
        reset = pool.get_stats("a").quota_reset_at
        import datetime as dt

        now_ts = dt.datetime.utcnow().timestamp()
        assert reset > now_ts
        # 验证不超过 62 天（最多下下月 1 号）
        two_months = now_ts + 62 * 86400
        assert reset < two_months


class TestLeaseTimeout:
    def test_lease_timeout_force_release(self):
        config = PoolConfig(lease_timeout_seconds=0)
        pool = ApiKeyPool({"a": "ka"}, config=config)
        n1 = pool.acquire()
        assert n1 == "a"
        # 租约已超时（lease_timeout=0），下一个 acquire 应强制释放
        n2 = pool.acquire()
        assert n2 == "a"  # 强制释放成功
        pool.release(n2)
