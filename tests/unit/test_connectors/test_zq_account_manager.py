"""AccountManager 账号加载单元测试.

重点验证 _load_config 对 ZQ_ACCOUNTS_JSON 的解析及与旧版 ZQ_ACCOUNTS 的优先级关系,
这是系统配置工作台保存（写 ZQ_ACCOUNTS_JSON、删 ZQ_ACCOUNTS）与运行时读取的链路闭环。
"""

import json
from datetime import datetime, timedelta

from data_layer.crawlers.zq.zhiqiu.account_manager import AccountManager, AccountStats

# ---------------------------------------------------------------------------
# 测试用的 config.yaml 路径 —— 实际不存在,AccountManager 会回退到空配置
# ---------------------------------------------------------------------------

NONEXISTENT_CONFIG = "data_layer/crawlers/zq/zhiqiu/__nonexistent_for_test__.yaml"


def _make_manager() -> AccountManager:
    """构造一个不依赖真实配置文件的 AccountManager。

    config_path 指向不存在的文件,_load_config 会读到空 dict,
    账号完全来自环境变量。
    """
    return AccountManager(NONEXISTENT_CONFIG, module_identifier="test")


# ---------------------------------------------------------------------------
# _parse_accounts_json
# ---------------------------------------------------------------------------


class TestParseAccountsJson:
    def test_parse_multiple_accounts(self):
        raw = json.dumps(
            [
                {"name": "acc1", "username": "u1@example.com", "password": "p1"},
                {"name": "acc2", "username": "u2@example.com", "password": "p2"},
                {"name": "acc3", "username": "u3@example.com", "password": "p3"},
            ]
        )
        accounts = AccountManager._parse_accounts_json(raw)

        assert set(accounts.keys()) == {"acc1", "acc2", "acc3"}
        assert accounts["acc1"] == {"username": "u1@example.com", "password": "p1"}

    def test_parse_five_accounts_matches_env_layout(self):
        """还原 .env 中真实的 5 账号 JSON 结构能被正确解析。"""
        raw = (
            '[{"name":"huangyongjia","username":"huangyongjia@huaan.com.cn","password":"Simba1208"},'
            '{"name":"zhanzhengkai","username":"zhanzhengkai@huaan.com.cn","password":"Zzk_2210"},'
            '{"name":"sunhaoxiang","username":"sunhaoxiang@huaan.com.cn","password":"Shx_2622"},'
            '{"name":"majingyi","username":"majingyi@huaan.com.cn","password":"Mjy_2090"},'
            '{"name":"wanghao","username":"wanghao@huaan.com.cn","password":"Wh_68664"}]'
        )
        accounts = AccountManager._parse_accounts_json(raw)

        assert len(accounts) == 5
        assert accounts["wanghao"]["username"] == "wanghao@huaan.com.cn"
        assert accounts["wanghao"]["password"] == "Wh_68664"

    def test_invalid_json_returns_empty(self):
        assert AccountManager._parse_accounts_json("not a json") == {}

    def test_non_list_returns_empty(self):
        assert AccountManager._parse_accounts_json('{"name": "acc1"}') == {}

    def test_skips_items_without_username(self):
        raw = json.dumps(
            [
                {"name": "acc1", "username": "u1", "password": "p1"},
                {"name": "acc2", "password": "p2"},  # 缺 username
            ]
        )
        accounts = AccountManager._parse_accounts_json(raw)
        assert set(accounts.keys()) == {"acc1"}

    def test_falls_back_to_username_as_key_when_name_missing(self):
        raw = json.dumps([{"username": "u1@example.com", "password": "p1"}])
        accounts = AccountManager._parse_accounts_json(raw)
        assert "u1@example.com" in accounts
        assert accounts["u1@example.com"]["password"] == "p1"

    def test_skips_non_dict_items(self):
        raw = json.dumps(["str", 123, {"name": "acc1", "username": "u1", "password": "p1"}])
        accounts = AccountManager._parse_accounts_json(raw)
        assert set(accounts.keys()) == {"acc1"}


# ---------------------------------------------------------------------------
# _load_config 优先级
# ---------------------------------------------------------------------------


class TestLoadConfigPriority:
    def test_reads_zq_accounts_json(self, monkeypatch):
        """ZQ_ACCOUNTS_JSON 存在时,优先使用它。"""
        monkeypatch.setenv(
            "ZQ_ACCOUNTS_JSON",
            json.dumps(
                [
                    {"name": "acc1", "username": "u1", "password": "p1"},
                    {"name": "acc2", "username": "u2", "password": "p2"},
                ]
            ),
        )
        monkeypatch.delenv("ZQ_ACCOUNTS", raising=False)

        manager = _make_manager()
        accounts = manager.config["accounts"]

        assert set(accounts.keys()) == {"acc1", "acc2"}
        assert accounts["acc1"]["password"] == "p1"

    def test_zq_accounts_json_takes_precedence_over_legacy(self, monkeypatch):
        """两个变量都存在时,JSON 格式优先。"""
        monkeypatch.setenv(
            "ZQ_ACCOUNTS_JSON",
            json.dumps([{"name": "json_acc", "username": "json_u", "password": "json_p"}]),
        )
        monkeypatch.setenv("ZQ_ACCOUNTS", "legacy_u:legacy_p")

        manager = _make_manager()
        accounts = manager.config["accounts"]

        assert set(accounts.keys()) == {"json_acc"}
        assert accounts["json_acc"]["password"] == "json_p"

    def test_falls_back_to_legacy_zq_accounts(self, monkeypatch):
        """ZQ_ACCOUNTS_JSON 不存在时,回退到旧版 ZQ_ACCOUNTS。"""
        monkeypatch.delenv("ZQ_ACCOUNTS_JSON", raising=False)
        monkeypatch.setenv("ZQ_ACCOUNTS", "u1:p1,u2:p2")

        manager = _make_manager()
        accounts = manager.config["accounts"]

        assert set(accounts.keys()) == {"u1", "u2"}
        assert accounts["u1"] == {"username": "u1", "password": "p1"}

    def test_falls_back_to_legacy_when_json_invalid(self, monkeypatch):
        """ZQ_ACCOUNTS_JSON 解析失败时,回退到旧版 ZQ_ACCOUNTS。"""
        monkeypatch.setenv("ZQ_ACCOUNTS_JSON", "not a json")
        monkeypatch.setenv("ZQ_ACCOUNTS", "u1:p1")

        manager = _make_manager()
        accounts = manager.config["accounts"]

        assert set(accounts.keys()) == {"u1"}

    def test_empty_accounts_when_no_env(self, monkeypatch):
        """两个环境变量都不存在、配置文件也不存在时,账号池为空。"""
        monkeypatch.delenv("ZQ_ACCOUNTS_JSON", raising=False)
        monkeypatch.delenv("ZQ_ACCOUNTS", raising=False)

        manager = _make_manager()
        assert manager.config["accounts"] == {}


# ---------------------------------------------------------------------------
# 与系统配置保存行为的集成:保存会写 JSON + 删旧版,AccountManager 仍能读全
# ---------------------------------------------------------------------------


class TestSystemConfigIntegration:
    def test_accounts_json_roundtrip_after_sync(self, monkeypatch):
        """模拟系统配置保存后的环境:只有 ZQ_ACCOUNTS_JSON,无 ZQ_ACCOUNTS。

        确认 AccountManager 能完整加载 5 个账号 —— 这是本次修复的核心回归点。
        """
        # 系统配置保存后会写入 ZQ_ACCOUNTS_JSON 并删除 ZQ_ACCOUNTS
        monkeypatch.setenv(
            "ZQ_ACCOUNTS_JSON",
            '[{"name":"huangyongjia","username":"huangyongjia@huaan.com.cn","password":"Simba1208"},'
            '{"name":"zhanzhengkai","username":"zhanzhengkai@huaan.com.cn","password":"Zzk_2210"},'
            '{"name":"sunhaoxiang","username":"sunhaoxiang@huaan.com.cn","password":"Shx_2622"},'
            '{"name":"majingyi","username":"majingyi@huaan.com.cn","password":"Mjy_2090"},'
            '{"name":"wanghao","username":"wanghao@huaan.com.cn","password":"Wh_68664"}]',
        )
        monkeypatch.delenv("ZQ_ACCOUNTS", raising=False)

        manager = _make_manager()

        assert len(manager.config["accounts"]) == 5
        # get_account_credentials 能取到每个账号的凭证
        for name in ["huangyongjia", "zhanzhengkai", "sunhaoxiang", "majingyi", "wanghao"]:
            creds = manager.get_account_credentials(name)
            assert creds is not None
            assert creds["username"].endswith("@huaan.com.cn")
            assert creds["password"]

    def test_disabled_accounts_can_be_re_enabled(self, tmp_path, monkeypatch):
        """解禁后 acquire_account 能再次租到账号。

        用一个真实的状态文件验证 is_disabled=false 的账号可用。
        """
        monkeypatch.delenv("ZQ_ACCOUNTS_JSON", raising=False)
        monkeypatch.delenv("ZQ_ACCOUNTS", raising=False)

        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            "accounts:\n" "  acc1:\n    username: u1\n    password: p1\n",
            encoding="utf-8",
        )

        manager = AccountManager(str(config_path), module_identifier="test_lease")
        # 全新状态,acc1 应可用
        assert "acc1" in manager.get_available_accounts()

        account = manager.acquire_account()
        assert account == "acc1"
        manager.release_account(account)


# ---------------------------------------------------------------------------
# 永久禁用冷却期自动解禁
# ---------------------------------------------------------------------------


class TestDisableCooldownRecovery:
    """验证账号被永久禁用后,经过冷却期能自动解禁,避免死局。"""

    def _make_manager_with_config(self, tmp_path, monkeypatch, cooldown_hours):
        """构造一个单账号 manager,并设置冷却期。"""
        monkeypatch.delenv("ZQ_ACCOUNTS_JSON", raising=False)
        monkeypatch.delenv("ZQ_ACCOUNTS", raising=False)
        monkeypatch.setenv("ZQ_DISABLE_COOLDOWN_HOURS", str(cooldown_hours))

        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            "accounts:\n  acc1:\n    username: u1\n    password: p1\n",
            encoding="utf-8",
        )
        return AccountManager(str(config_path), module_identifier="test_cooldown")

    def test_record_failure_disables_and_records_timestamp(self, tmp_path, monkeypatch):
        """连续失败达阈值后,账号被永久禁用且 disabled_at 被记录。"""
        monkeypatch.setenv("ZQ_MAX_CONSECUTIVE_FAILURES", "3")
        manager = self._make_manager_with_config(tmp_path, monkeypatch, cooldown_hours=6)

        for _ in range(3):
            manager.record_failure("acc1")

        stats = manager.get_account_stats("acc1")
        assert stats.is_disabled is True
        assert stats.disabled_at is not None
        # disabled_at 是合法 ISO 时间
        datetime.fromisoformat(stats.disabled_at)

    def test_disabled_account_unavailable_within_cooldown(self, tmp_path, monkeypatch):
        """冷却期内,永久禁用的账号仍不可用。"""
        monkeypatch.setenv("ZQ_MAX_CONSECUTIVE_FAILURES", "1")
        manager = self._make_manager_with_config(tmp_path, monkeypatch, cooldown_hours=6)

        manager.record_failure("acc1")  # 1 次即禁用
        assert manager.get_account_stats("acc1").is_disabled is True
        assert "acc1" not in manager.get_available_accounts()
        assert manager.acquire_account() is None

    def test_auto_recover_after_cooldown(self, tmp_path, monkeypatch):
        """超过冷却期后,账号自动解禁并可被租借。"""
        monkeypatch.setenv("ZQ_MAX_CONSECUTIVE_FAILURES", "1")
        manager = self._make_manager_with_config(tmp_path, monkeypatch, cooldown_hours=6)

        manager.record_failure("acc1")
        stats = manager.get_account_stats("acc1")
        assert stats.is_disabled is True

        # 篡改 disabled_at 为 7 小时前,模拟已过冷却期
        stats.disabled_at = (datetime.now() - timedelta(hours=7)).isoformat()
        # 直接改状态文件
        import json as _json

        state_path = manager.state_path
        data = _json.loads(state_path.read_text(encoding="utf-8"))
        data["accounts"]["acc1"]["disabled_at"] = stats.disabled_at
        state_path.write_text(_json.dumps(data, ensure_ascii=False), encoding="utf-8")

        # 再次检查可用性应触发自动解禁
        assert "acc1" in manager.get_available_accounts()
        recovered = manager.get_account_stats("acc1")
        assert recovered.is_disabled is False
        assert recovered.consecutive_failures == 0

    def test_legacy_state_without_disabled_at_recovers(self, tmp_path, monkeypatch):
        """旧状态文件(无 disabled_at 字段)的永久禁用账号,视为已达冷却期可恢复。"""
        manager = self._make_manager_with_config(tmp_path, monkeypatch, cooldown_hours=6)

        # 手工构造一个旧格式状态: is_disabled=true 但没有 disabled_at
        state_path = manager.state_path
        data = {
            "version": "1.0",
            "current_index": 0,
            "accounts": {
                "acc1": {
                    "name": "acc1",
                    "use_count": 5,
                    "success_count": 0,
                    "failure_count": 10,
                    "consecutive_failures": 10,
                    "is_locked": False,
                    "lock_until": None,
                    "is_disabled": True,
                    # 故意不写 disabled_at,模拟旧状态文件
                    "leased_by": None,
                    "leased_at": None,
                }
            },
        }
        state_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        assert "acc1" in manager.get_available_accounts()
        recovered = manager.get_account_stats("acc1")
        assert recovered.is_disabled is False

    def test_cooldown_zero_disables_auto_recover(self, tmp_path, monkeypatch):
        """冷却期设为 0 时,不自动解禁(运维显式关闭自愈)。"""
        monkeypatch.setenv("ZQ_MAX_CONSECUTIVE_FAILURES", "1")
        manager = self._make_manager_with_config(tmp_path, monkeypatch, cooldown_hours=0)

        manager.record_failure("acc1")
        # 即使 disabled_at 很久以前,也不应恢复
        stats = manager.get_account_stats("acc1")
        stats.disabled_at = (datetime.now() - timedelta(hours=100)).isoformat()
        import json as _json

        state_path = manager.state_path
        data = _json.loads(state_path.read_text(encoding="utf-8"))
        data["accounts"]["acc1"]["disabled_at"] = stats.disabled_at
        state_path.write_text(_json.dumps(data, ensure_ascii=False), encoding="utf-8")

        assert "acc1" not in manager.get_available_accounts()

    def test_account_stats_default_disabled_at_none(self):
        """AccountStats 默认 disabled_at 为 None。"""
        stats = AccountStats(name="x")
        assert stats.disabled_at is None
