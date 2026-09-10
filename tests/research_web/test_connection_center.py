"""Unified local DataHub connection configuration, migration, and probe contracts."""

import asyncio
import json
import sys
from types import ModuleType, SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from test_api import NativeFixture

from app.research_web.datahub import DataHub, connections, providers
from app.research_web.datahub.catalog import build_catalog
from app.research_web.datahub.connection_center import platform_summary
from app.research_web.datahub.connections import (
    MYSQL_ACCOUNT,
    MYSQL_SERVICE,
    CredentialStoreError,
    MySQLConfiguration,
    MySQLConnectionStore,
)
from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.probes import probe_source
from app.research_web.main import create_app
from app.research_web.service import ResearchService
from app.research_web.store import Store
from data_layer.adapters.ifind.exceptions import IFinDAuthError, IFinDRateLimitError
from data_layer.adapters.ifind.http_client import IFinDHTTPClient


class MappingKeyring:
    def __init__(self):
        self.values = {}
        self.fail_get = False
        self.fail_set = False
        self.fail_delete = False

    def get_password(self, service, account):
        assert service == MYSQL_SERVICE
        if self.fail_get:
            raise RuntimeError("locked secret value must never escape")
        return self.values.get(account)

    def set_password(self, service, account, value):
        assert service == MYSQL_SERVICE
        if self.fail_set:
            raise RuntimeError("denied secret value must never escape")
        self.values[account] = value

    def delete_password(self, service, account):
        assert service == MYSQL_SERVICE
        if self.fail_delete:
            raise RuntimeError("denied secret value must never escape")
        self.values.pop(account, None)


class MutatingReadbackKeyring(MappingKeyring):
    """Simulate an OS store that mutates successfully before readback fails."""

    def __init__(self):
        super().__init__()
        self.fail_next_readback = False
        self.fail_readback_after_set = False
        self.fail_readback_after_delete = False

    def get_password(self, service, account):
        if self.fail_next_readback:
            self.fail_next_readback = False
            raise RuntimeError("credential store locked after mutation")
        return super().get_password(service, account)

    def set_password(self, service, account, value):
        super().set_password(service, account, value)
        if self.fail_readback_after_set:
            self.fail_readback_after_set = False
            self.fail_next_readback = True

    def delete_password(self, service, account):
        super().delete_password(service, account)
        if self.fail_readback_after_delete:
            self.fail_readback_after_delete = False
            self.fail_next_readback = True


def configured_service(tmp_path, *, env_text=""):
    if env_text:
        (tmp_path / ".env").write_text(env_text, encoding="utf-8")
    service = ResearchService(NativeFixture(), Store(tmp_path))
    keyring = MappingKeyring()
    service.datahub.connections = MySQLConnectionStore(tmp_path, keyring_backend=keyring)
    return service, keyring


def test_windows_profile_replace_skips_unsupported_directory_fsync(tmp_path, monkeypatch):
    opened = []
    real_open = connections.os.open

    def tracked_open(path, *args, **kwargs):
        opened.append(path)
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(connections.os, "open", tracked_open)
    monkeypatch.setattr(connections.os, "name", "nt")

    connections._fsync_directory(tmp_path)

    assert opened == []


def mysql_payload(**overrides):
    payload = {
        "label": "本机只读库",
        "host": "db.example.test",
        "port": 3306,
        "user": "reader",
        "charset": "utf8mb4",
        "tls_mode": "required_no_verify",
        "password": "mysql-secret",
    }
    payload.update(overrides)
    return payload


def test_connections_summary_has_22_safe_catalog_sources_and_platform_sections(tmp_path):
    service, _keyring = configured_service(tmp_path)
    with TestClient(create_app(service)) as client:
        response = client.get("/api/research/data/connections")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"groups", "sources", "platform", "migration"}
    assert len(body["sources"]) == 22
    assert {item["id"] for item in body["sources"]} == {
        item["id"] for item in build_catalog(environ={})["sources"]
    }
    assert body["groups"] == [
        {
            "id": "professional",
            "label": "专业数据源",
            "items": ["wind", "tinysoft", "ifind", "mysql"],
        },
        {
            "id": "api",
            "label": "API 数据源",
            "items": [
                "tushare",
                "tavily",
                "bing",
                "zhiqiu_reports",
                "zhiqiu_wechat",
                "zhiqiu_transcript",
            ],
        },
        {
            "id": "public",
            "label": "公开来源",
            "items": [
                "akshare",
                "baostock",
                "yahoo",
                "chinastock",
                "csindex",
                "szse",
                "cninfo",
                "cls",
                "cnstock_flash",
                "cnstock_news",
                "eastmoney_fund",
            ],
        },
        {"id": "local", "label": "本机集成", "items": ["local_cache"]},
    ]
    required = {
        "id",
        "label",
        "group",
        "auth_kind",
        "configured",
        "secret_configured",
        "probe_status",
        "integration_completed",
        "callable",
        "configuration_supported",
        "actions",
        "restart_required",
        "warnings",
    }
    assert all(set(item) == required for item in body["sources"])
    assert next(item for item in body["sources"] if item["id"] == "local_cache")["label"] == (
        "Excel 与本机工作流"
    )
    assert set(body["platform"]) == {
        "os",
        "excel_automation",
        "wind_excel",
        "ifind_excel",
        "report_workflow",
    }
    assert body["platform"]["report_workflow"]["status"] == "unverified"
    assert '"password"' not in response.text.casefold()
    assert '"token"' not in response.text.casefold()


def test_corrupt_single_source_profile_does_not_break_connection_catalog(tmp_path):
    service, _keyring = configured_service(tmp_path)
    (tmp_path / "connections").mkdir()
    (tmp_path / "connections/ifind.json").write_text("{broken", encoding="utf-8")
    with TestClient(create_app(service)) as client:
        response = client.get("/api/research/data/connections")
    assert response.status_code == 200
    sources = {item["id"]: item for item in response.json()["sources"]}
    assert len(sources) == 22
    assert sources["ifind"]["configured"] is False
    assert "configuration_read_failed" in sources["ifind"]["warnings"]
    assert sources["mysql"]["warnings"] == []


def test_platform_summary_distinguishes_not_applicable_not_installed_and_unverified(
    monkeypatch,
):
    import app.research_web.datahub.connection_center as module

    monkeypatch.setattr(module, "_module_detected", lambda *_names: False)
    linux = platform_summary(system_name="Linux")
    assert {linux[key]["status"] for key in ("excel_automation", "wind_excel", "ifind_excel")} == {
        "not_applicable"
    }
    darwin = platform_summary(system_name="Darwin")
    assert darwin["excel_automation"]["status"] == "not_installed"
    assert darwin["wind_excel"]["status"] == "not_installed"
    assert darwin["ifind_excel"]["status"] == "not_installed"

    monkeypatch.setattr(module, "_module_detected", lambda *_names: True)
    detected = platform_summary(system_name="Windows")
    assert detected["excel_automation"]["status"] == "unverified"
    assert detected["wind_excel"]["status"] == "unverified"
    assert detected["ifind_excel"]["status"] == "unverified"


def test_source_configuration_api_preserves_pooled_secrets_and_explicit_clear(tmp_path):
    service, keyring = configured_service(tmp_path)
    with TestClient(create_app(service)) as client:
        created = client.put(
            "/api/research/data/sources/ifind/configuration",
            json={
                "backend": "http_api",
                "http_base_url": "https://ifind.example.test/api",
                "accounts": [
                    {"id": "primary", "username": "alice", "password": "first-secret"},
                    {"id": "backup", "username": "bob", "password": "second-secret"},
                ],
            },
        )
        assert created.status_code == 200
        assert created.json()["configured"] is True
        assert [item["secret_configured"] for item in created.json()["accounts"]] == [True, True]
        assert "first-secret" not in created.text and "second-secret" not in created.text

        retained = client.put(
            "/api/research/data/sources/ifind/configuration",
            json={
                "backend": "auto",
                "http_base_url": "https://ifind.example.test/api",
                "accounts": [
                    {"id": "primary", "username": "alice", "password": ""},
                    {"id": "backup", "username": "bob", "password": ""},
                ],
            },
        )
        assert retained.status_code == 200
        assert all(item["secret_configured"] for item in retained.json()["accounts"])

        cleared = client.put(
            "/api/research/data/sources/ifind/configuration",
            json={
                "backend": "auto",
                "http_base_url": "https://ifind.example.test/api",
                "accounts": [
                    {
                        "id": "primary",
                        "username": "alice",
                        "password": "",
                        "clear_password": True,
                    },
                    {"id": "backup", "username": "bob", "password": ""},
                ],
            },
        )
        assert cleared.status_code == 200
        assert [item["secret_configured"] for item in cleared.json()["accounts"]] == [False, True]

        loaded = client.get("/api/research/data/sources/ifind/configuration")
        assert loaded.status_code == 200
        assert loaded.json() == cleared.json()
        assert "password" not in loaded.text.casefold()

    raw = (tmp_path / "connections/ifind.json").read_text(encoding="utf-8")
    assert "secret" not in raw
    assert "alice" in raw and "bob" in raw
    assert keyring.values == {"ifind:backup:password": "second-secret"}


@pytest.mark.parametrize(
    ("source_id", "secret_field"),
    [
        ("tinysoft", "token"),
        ("tushare", "token"),
        ("tavily", "api_key"),
        ("bing", "api_key"),
    ],
)
def test_single_secret_sources_retain_blank_and_support_clear(tmp_path, source_id, secret_field):
    service, keyring = configured_service(tmp_path)
    endpoint = f"/api/research/data/sources/{source_id}/configuration"
    with TestClient(create_app(service)) as client:
        saved = client.put(endpoint, json={secret_field: "single-secret"})
        assert saved.status_code == 200
        assert saved.json()["secret_configured"] is True
        retained = client.put(endpoint, json={secret_field: ""})
        assert retained.json()["secret_configured"] is True
        cleared = client.put(endpoint, json={secret_field: "", "clear_secret": True})
        assert cleared.status_code == 200
        assert cleared.json()["secret_configured"] is False
        assert client.delete(endpoint).json() == {"deleted": True}
    assert "single-secret" not in json.dumps(keyring.values)


def test_wind_saves_adapter_only_and_unsupported_sources_reject_writes(tmp_path):
    service, _keyring = configured_service(tmp_path)
    with TestClient(create_app(service)) as client:
        saved = client.put(
            "/api/research/data/sources/wind/configuration",
            json={"preferred_adapter": "excel"},
        )
        assert saved.status_code == 200
        assert saved.json()["preferred_adapter"] == "excel"
        assert saved.json()["secret_configured"] is False
        rejected_secret = client.put(
            "/api/research/data/sources/wind/configuration",
            json={"preferred_adapter": "client_api", "password": "forbidden"},
        )
        assert rejected_secret.status_code == 422
        unsupported = client.put(
            "/api/research/data/sources/akshare/configuration",
            json={"token": "forbidden"},
        )
        assert unsupported.status_code == 422
        assert unsupported.json()["error"]["code"] == "configuration_not_supported"


def test_zhiqiu_catalog_sources_share_one_account_pool(tmp_path):
    service, _keyring = configured_service(tmp_path)
    with TestClient(create_app(service)) as client:
        saved = client.put(
            "/api/research/data/sources/zhiqiu_reports/configuration",
            json={
                "accounts": [
                    {
                        "id": "team",
                        "username": "reader",
                        "password": "zhiqiu-secret-value",
                    }
                ]
            },
        )
        assert saved.status_code == 200
        for source_id in ("zhiqiu_reports", "zhiqiu_wechat", "zhiqiu_transcript"):
            status = client.get(f"/api/research/data/sources/{source_id}/configuration").json()
            assert status["configured"] is True
            assert status["accounts"][0]["secret_configured"] is True
            assert "zhiqiu-secret-value" not in json.dumps(status)
            assert '"password"' not in json.dumps(status)


def test_catalog_uses_connection_status_instead_of_legacy_environment_and_cj_key_is_tinysoft():
    legacy_env = {
        "IFIND_USERNAME": "legacy-user",
        "IFIND_PASSWORD": "legacy-secret",
        "TUSHARE_TOKEN": "legacy-token",
        "TAVILY_API_KEY": "legacy-key",
        "BING_API_KEY": "legacy-key",
        "CJ_KEY": "legacy-key",
    }
    catalog = build_catalog(environ=legacy_env, connection_statuses={})
    sources = {item["id"]: item for item in catalog["sources"]}
    for source_id in ("ifind", "tushare", "tavily", "bing", "tinysoft"):
        assert sources[source_id]["readiness"]["configured"] is False
    assert sources["wind"]["config_keys"] == []
    assert sources["tinysoft"]["config_keys"] == ["CJ_KEY"]


def test_env_migration_preview_never_returns_values_and_apply_clears_only_selected(tmp_path):
    service, keyring = configured_service(
        tmp_path,
        env_text=(
            "IFIND_USERNAME=alice\n"
            "IFIND_PASSWORD=ifind-secret\n"
            "TUSHARE_TOKEN=tushare-secret\n"
            "CJ_KEY=tinysoft-secret\n"
            "DSH_API_KEY=must-remain\n"
        ),
    )
    with TestClient(create_app(service)) as client:
        preview = client.get("/api/research/data/connections/migration-preview")
        assert preview.status_code == 200
        body = preview.json()
        assert body["available"] is True
        assert {item["source_id"] for item in body["targets"]} == {
            "ifind",
            "tushare",
            "tinysoft",
        }
        assert "ifind-secret" not in preview.text
        assert "tushare-secret" not in preview.text
        assert "tinysoft-secret" not in preview.text

        applied = client.post(
            "/api/research/data/connections/migrations",
            json={"source_ids": ["ifind", "tushare"], "confirm": True},
        )
        assert applied.status_code == 200
        assert set(applied.json()["migrated"]) == {"ifind", "tushare"}

    remaining = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "IFIND_USERNAME" not in remaining and "IFIND_PASSWORD" not in remaining
    assert "TUSHARE_TOKEN" not in remaining
    assert "CJ_KEY=tinysoft-secret" in remaining
    assert "DSH_API_KEY=must-remain" in remaining
    assert keyring.values["ifind:legacy:password"] == "ifind-secret"
    assert keyring.values["tushare:default:token"] == "tushare-secret"


def test_env_migration_rolls_back_configuration_and_keyring_when_env_rewrite_fails(
    tmp_path, monkeypatch
):
    _service, keyring = configured_service(tmp_path, env_text="TAVILY_API_KEY=rollback-secret\n")
    store = _service.datahub.connections
    monkeypatch.setattr(
        store,
        "_write_env",
        lambda _lines: (_ for _ in ()).throw(OSError("disk failure with rollback-secret")),
        raising=False,
    )
    with pytest.raises(CredentialStoreError, match="migration_apply_failed"):
        store.apply_migration(["tavily"])
    assert keyring.values == {}
    assert not (tmp_path / "connections/tavily.json").exists()
    assert "TAVILY_API_KEY=rollback-secret" in (tmp_path / ".env").read_text(encoding="utf-8")


def test_mysql_keyring_readback_failure_restores_previous_secret_and_profile(tmp_path):
    keyring = MutatingReadbackKeyring()
    store = MySQLConnectionStore(tmp_path, keyring_backend=keyring)
    old = MySQLConfiguration(
        label="旧连接",
        host="old.example.test",
        port=3306,
        user="reader",
        charset="utf8mb4",
        tls_mode="required_no_verify",
    )
    store.save(old, password="old-secret")
    original = (tmp_path / "connections/mysql.json").read_bytes()
    keyring.fail_readback_after_set = True
    with pytest.raises(CredentialStoreError, match="credential_store_unavailable"):
        store.save(old.model_copy(update={"label": "新连接"}), password="new-secret")
    assert keyring.values[MYSQL_ACCOUNT] == "old-secret"
    assert (tmp_path / "connections/mysql.json").read_bytes() == original

    keyring.fail_readback_after_delete = True
    with pytest.raises(CredentialStoreError, match="credential_store_unavailable"):
        store.delete()
    assert keyring.values[MYSQL_ACCOUNT] == "old-secret"
    assert (tmp_path / "connections/mysql.json").read_bytes() == original


def test_migration_restores_original_env_when_replace_succeeds_then_reports_failure(
    tmp_path, monkeypatch
):
    service, keyring = configured_service(tmp_path, env_text="TAVILY_API_KEY=keep-me\n")
    store = service.datahub.connections
    original_write_env = store._write_env

    def replace_then_fail(lines):
        original_write_env(lines)
        raise OSError("directory sync failed")

    monkeypatch.setattr(store, "_write_env", replace_then_fail)
    with pytest.raises(CredentialStoreError, match="migration_apply_failed"):
        store.apply_migration(["tavily"])
    assert (tmp_path / ".env").read_text(encoding="utf-8") == "TAVILY_API_KEY=keep-me\n"
    assert keyring.values == {}


@pytest.mark.asyncio
async def test_ifind_sdk_probe_skips_missing_account_and_always_logs_out(monkeypatch):
    events = []
    module = ModuleType("iFinD")
    module.THS_iFinDLogin = (
        lambda username, password: events.append(("login", username, password)) or 0
    )
    module.THS_iFinDLogout = lambda: events.append(("logout",)) or 0
    monkeypatch.setattr("app.research_web.datahub.probes._load_module", lambda *_names: module)

    def secret_reader(_source, account_id):
        if account_id == "missing":
            raise CredentialStoreError("credential_missing")
        return "sdk-secret"

    result = await probe_source(
        "ifind",
        {
            "backend": "python_sdk",
            "http_base_url": None,
            "accounts": [
                {"id": "missing", "username": "first"},
                {"id": "ready", "username": "second"},
            ],
        },
        secret_reader,
    )
    assert result == {"health": "healthy", "failure_code": None}
    assert events == [("login", "second", "sdk-secret"), ("logout",)]


@pytest.mark.asyncio
async def test_ifind_http_probe_logs_in_checks_health_and_always_closes():
    events = []

    class Client:
        async def login(self):
            events.append("login")
            return True

        async def is_alive(self):
            events.append("health")
            return True

        async def probe_query(self):
            events.append("query")
            return [{"code": "000001.SZ"}]

        async def logout(self):
            events.append("logout")

    result = await probe_source(
        "ifind",
        {
            "backend": "http_api",
            "http_base_url": "https://ifind.example.test/api",
            "accounts": [{"id": "ready", "username": "researcher"}],
        },
        lambda *_args: "http-secret",
        ifind_http_client_factory=lambda *_args: Client(),
    )

    assert result == {"health": "healthy", "failure_code": None}
    assert events == ["login", "health", "query", "logout"]


@pytest.mark.asyncio
async def test_ifind_http_probe_maps_auth_failure_and_still_closes():
    events = []

    class Client:
        async def login(self):
            events.append("login")
            raise PermissionError("secret must not escape")

        async def logout(self):
            events.append("logout")

    result = await probe_source(
        "ifind",
        {
            "backend": "http_api",
            "http_base_url": "https://ifind.example.test/api",
            "accounts": [{"id": "ready", "username": "researcher"}],
        },
        lambda *_args: "http-secret",
        ifind_http_client_factory=lambda *_args: Client(),
    )

    assert result == {"health": "unavailable", "failure_code": "vendor_permission_denied"}
    assert events == ["login", "logout"]


@pytest.mark.asyncio
async def test_ifind_http_probe_rejects_empty_data_query_and_always_closes():
    events = []

    class Client:
        async def login(self):
            events.append("login")
            return True

        async def is_alive(self):
            events.append("health")
            return True

        async def probe_query(self):
            events.append("query")
            return []

        async def logout(self):
            events.append("logout")

    result = await probe_source(
        "ifind",
        {
            "backend": "http_api",
            "http_base_url": "https://ifind.example.test/api",
            "accounts": [{"id": "ready", "username": "researcher"}],
        },
        lambda *_args: "http-secret",
        ifind_http_client_factory=lambda *_args: Client(),
    )

    assert result == {"health": "unavailable", "failure_code": "vendor_query_empty"}
    assert events == ["login", "health", "query", "logout"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "expected_code"),
    [
        (IFinDAuthError("auth detail must not escape"), "vendor_login_failed"),
        (IFinDRateLimitError("quota detail must not escape"), "vendor_quota_limited"),
    ],
)
async def test_ifind_http_probe_safely_maps_query_failures_and_closes(failure, expected_code):
    events = []

    class Client:
        async def login(self):
            events.append("login")
            return True

        async def is_alive(self):
            events.append("health")
            return True

        async def probe_query(self):
            events.append("query")
            raise failure

        async def logout(self):
            events.append("logout")

    result = await probe_source(
        "ifind",
        {
            "backend": "http_api",
            "http_base_url": "https://ifind.example.test/api",
            "accounts": [{"id": "ready", "username": "researcher"}],
        },
        lambda *_args: "http-secret",
        ifind_http_client_factory=lambda *_args: Client(),
    )

    assert result == {"health": "unavailable", "failure_code": expected_code}
    assert events == ["login", "health", "query", "logout"]


@pytest.mark.asyncio
async def test_ifind_http_probe_uses_existing_client_contract_with_mock_transport():
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path, request.headers.get("authorization")))
        if request.url.path == "/api/login":
            return httpx.Response(200, json={"token": "ephemeral", "expires_in": 7200})
        if request.url.path == "/api/health":
            return httpx.Response(200, json={"status": "ok"})
        if request.url.path == "/api/basic":
            return httpx.Response(200, json={"data": [{"code": "000001.SZ"}]})
        return httpx.Response(404)

    client = IFinDHTTPClient(
        SimpleNamespace(
            IFIND_HTTP_BASE_URL="https://ifind.example.test/api",
            IFIND_USERNAME="researcher",
            IFIND_PASSWORD="http-secret",
        ),
        transport=httpx.MockTransport(handler),
    )
    result = await probe_source(
        "ifind",
        {
            "backend": "http_api",
            "http_base_url": "https://ifind.example.test/api",
            "accounts": [{"id": "ready", "username": "researcher"}],
        },
        lambda *_args: "http-secret",
        ifind_http_client_factory=lambda *_args: client,
    )

    assert result == {"health": "healthy", "failure_code": None}
    assert calls == [
        ("POST", "/api/login", None),
        ("GET", "/api/health", "Bearer ephemeral"),
        ("POST", "/api/basic", "Bearer ephemeral"),
    ]
    assert client.token is None
    assert client._client is None


@pytest.mark.parametrize(
    "base_url",
    (
        "http://ifind.example.test/api",
        "http://192.168.1.10/api",
        "https://user:secret@ifind.example.test/api",
    ),
)
def test_ifind_http_configuration_rejects_insecure_credential_destinations(base_url):
    from app.research_web.datahub.connections import IFindConfiguration

    with pytest.raises(ValueError):
        IFindConfiguration.model_validate(
            {
                "backend": "http_api",
                "http_base_url": base_url,
                "accounts": [{"id": "primary", "username": "researcher"}],
            }
        )


@pytest.mark.parametrize("host", ("localhost", "127.0.0.1", "[::1]"))
def test_ifind_http_client_allows_loopback_cleartext_only(host):
    client = IFinDHTTPClient(
        SimpleNamespace(
            IFIND_HTTP_BASE_URL=f"http://{host}:8080/api",
            IFIND_USERNAME="researcher",
            IFIND_PASSWORD="secret",
        )
    )
    assert client.base_url == f"http://{host}:8080/api"


@pytest.mark.asyncio
async def test_wind_client_probe_reports_current_session_without_starting_it(monkeypatch):
    module = ModuleType("WindPy")

    class WindSession:
        @staticmethod
        def isconnected():
            return True

        @staticmethod
        def start():
            raise AssertionError("探测不得创建或登录 Wind 会话")

    module.w = WindSession()
    monkeypatch.setattr("app.research_web.datahub.probes._load_module", lambda *_names: module)
    result = await probe_source("wind", {"preferred_adapter": "client_api"}, lambda *_args: "")
    assert result == {"health": "healthy", "failure_code": None}


@pytest.mark.asyncio
async def test_probe_runtime_failure_completes_with_stable_error(tmp_path):
    async def broken_probe(*_args):
        raise RuntimeError("vendor detail must not escape")

    hub = DataHub(Store(tmp_path), probe_runner=broken_probe)
    hub.connections.save_source("wind", {"preferred_adapter": "client_api"})
    probe = hub.start_probe("wind", "probe-runtime-failure")
    await hub.probe_tasks[probe["id"]]
    assert hub.probe(probe["id"])["status"] == "completed"
    assert hub.probe(probe["id"])["failure_code"] == "probe_failed"
    await hub.close()


@pytest.mark.asyncio
async def test_vendor_probe_timeout_is_bounded_and_completes(tmp_path, monkeypatch):
    import app.research_web.datahub as datahub_module

    async def hanging_probe(*_args):
        await asyncio.sleep(1)

    monkeypatch.setattr(datahub_module, "PROBE_TIMEOUT", 0.01)
    hub = DataHub(Store(tmp_path), probe_runner=hanging_probe)
    hub.connections.save_source("wind", {"preferred_adapter": "client_api"})
    probe = hub.start_probe("wind", "probe-timeout")
    await hub.probe_tasks[probe["id"]]
    assert hub.probe(probe["id"])["failure_code"] == "probe_timeout"
    await hub.close()


@pytest.mark.asyncio
async def test_wind_probe_uses_injected_adapter_but_never_makes_source_callable(tmp_path):
    calls = []

    async def controlled_probe(source_id, configuration, secret_reader):
        calls.append((source_id, configuration["preferred_adapter"]))
        assert secret_reader is not None
        return {"health": "healthy", "failure_code": None}

    store = Store(tmp_path)
    hub = DataHub(store, probe_runner=controlled_probe)
    hub.connections.save_source("wind", {"preferred_adapter": "client_api"})
    probe = hub.start_probe("wind", "probe-wind-controlled")
    await hub.probe_tasks[probe["id"]]
    result = hub.probe(probe["id"])
    assert result["health"] == "healthy"
    assert calls == [("wind", "client_api")]
    assert hub.catalog_source("wind")["readiness"]["callable"] is False
    await hub.close()


def test_mysql_legacy_api_and_keyring_account_remain_compatible(tmp_path):
    service, keyring = configured_service(tmp_path)
    with TestClient(create_app(service)) as client:
        saved = client.put("/api/research/data/sources/mysql/configuration", json=mysql_payload())
        assert saved.status_code == 200
        assert saved.json()["secret_configured"] is True
        assert client.get("/api/research/data/sources/mysql/configuration").json() == saved.json()
    assert keyring.values[MYSQL_ACCOUNT] == "mysql-secret"


@pytest.mark.asyncio
async def test_tinysoft_provider_uses_saved_keyring_token_after_env_migration(
    tmp_path, monkeypatch
):
    store = MySQLConnectionStore(tmp_path, keyring_backend=MappingKeyring())
    store.save_source("tinysoft", {"token": "saved-cj-token"})
    monkeypatch.delenv("CJ_KEY", raising=False)
    package = ModuleType("cjpy")
    base = ModuleType("cjpy.base")

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["token"] == "saved-cj-token"

        def _create_session(self):
            return type("Session", (), {"trust_env": True})()

    base.CjClient = Client
    package.base = base
    package.get_stocks = lambda **_kwargs: [{"证券代码": "SH600000"}]
    monkeypatch.setitem(sys.modules, "cjpy", package)
    monkeypatch.setitem(sys.modules, "cjpy.base", base)
    result = await providers.fetch(
        BusinessQuery(
            capability="search_assets",
            source="tinysoft",
            parameters={"query": "600000"},
        ),
        connections=store,
    )
    assert result.status == "complete"
    assert result.rows == [{"证券代码": "SH600000"}]
    assert "saved-cj-token" not in repr(result)
