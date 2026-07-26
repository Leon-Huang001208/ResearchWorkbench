# Desktop First-Run Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** 让 macOS Apple Silicon 和 Windows x64 的桌面安装包在 PostgreSQL/pgvector 未就绪时进入安全配置模式，并在系统配置页执行真实连接检查。

**Architecture:** 新建无副作用的 PostgreSQL/pgvector 预检服务，供后端启动、launcher 和数据库配置测试共用。仅 desktop 模式将预检失败降级为 setup_required；Web 模式保持 fail-fast。欢迎覆盖层展示安全失败原因与修复指引，复用现有数据库配置模态框。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy/psycopg、Pydantic、ES modules、Tauri sidecar、pytest、GitHub Actions。

---

## 文件结构

- 新建 services/database_readiness.py：临时 engine 预检与安全结果模型。
- 新建 app/api/routes/setup.py：读取当前桌面就绪状态。
- 修改 services/configuration_service.py 和 app/api/configuration_models.py：数据库测试使用预检。
- 修改 app/api/main.py：desktop 降级启动、health 状态和 setup 路由。
- 修改 scripts/desktop/backend_launcher.py：无数据库时不退出、不启动 watchdog。
- 新建 app/web/static/js/setup-wizard.js，修改 app.js、configuration.js、index.html、style.css：首次启动覆盖层。
- 修改 scripts/desktop/check_sidecar_health.py 与 .github/workflows/desktop-verify.yml：验证 ready 与 setup_required。
- 修改 docs/desktop_packaging.md，新增对应单元/API/前端静态测试。

### Task 1: 建立无副作用 PostgreSQL + pgvector 预检

**Files:**
- Create: services/database_readiness.py
- Create: tests/unit/test_database_readiness.py

- [ ] **Step 1: 先写失败测试**

~~~
from services.database_readiness import DatabaseReadinessCode, probe_postgresql

def test_probe_reports_ready_only_after_select_and_vector_extension(monkeypatch):
    calls = []

    class Connection:
        def execute(self, statement):
            calls.append(str(statement))
            return [(True,)] if "pg_extension" in str(statement) else []
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False

    class Engine:
        def connect(self):
            return Connection()
        def dispose(self):
            calls.append("dispose")

    monkeypatch.setattr("services.database_readiness.create_engine", lambda *_a, **_k: Engine())

    result = probe_postgresql("postgresql+psycopg://user:secret@localhost:5432/alphafoundry")

    assert result.ready is True
    assert result.code is DatabaseReadinessCode.READY
    assert any("SELECT 1" in call for call in calls)
    assert any("pg_extension" in call for call in calls)
    assert calls[-1] == "dispose"
~~~

同一文件再覆盖：非 PostgreSQL URL 为 invalid_url；连接异常为 connection_failed；扩展不存在为 pgvector_missing；序列化结果与 message 中不出现 secret、用户名、主机或端口。

- [ ] **Step 2: 运行测试确认它因功能缺失失败**

Run: python -m pytest tests/unit/test_database_readiness.py -q
Expected: FAIL，因为 services.database_readiness 尚不存在。

- [ ] **Step 3: 编写最小实现**

~~~
class DatabaseReadinessCode(str, Enum):
    READY = "ready"
    INVALID_URL = "invalid_url"
    CONNECTION_FAILED = "connection_failed"
    DATABASE_UNAVAILABLE = "database_unavailable"
    PGVECTOR_MISSING = "pgvector_missing"
    UNEXPECTED_ERROR = "unexpected_error"

@dataclass(frozen=True)
class DatabaseReadiness:
    ready: bool
    code: DatabaseReadinessCode
    message: str
    remediation: tuple[str, ...]

def probe_postgresql(database_url: str, timeout_seconds: float = 5.0) -> DatabaseReadiness:
    # 校验 PostgreSQL psycopg scheme；创建临时 engine。
    # 依次执行 SELECT 1 与 SELECT EXISTS (... pg_extension ... vector)。
    # finally 无条件 dispose；只记录 stage/error_type/platform，不记录 URL。
~~~

使用 core.observability.get_logger(__name__)；固定中文 message 和 remediation 映射，不把异常字符串放入响应。

- [ ] **Step 4: 运行测试确认通过**

Run: python -m pytest tests/unit/test_database_readiness.py -q
Expected: PASS。

- [ ] **Step 5: 提交**

~~~
git add services/database_readiness.py tests/unit/test_database_readiness.py
git commit -m "feat: add PostgreSQL readiness probe"
~~~

### Task 2: 让数据库配置的“测试连接”使用预检

**Files:**
- Modify: services/configuration_service.py:247-275
- Modify: app/api/configuration_models.py:181-184
- Modify: tests/unit/test_configuration_service.py
- Create: tests/unit/app/api/routes/test_configuration_database_probe.py

- [ ] **Step 1: 写失败测试**

~~~
def test_database_test_returns_pgvector_failure_without_persisting(monkeypatch, tmp_path):
    service = ConfigurationService(env_path=tmp_path / ".env", runtime_settings=Settings())
    monkeypatch.setattr(
        "services.configuration_service.probe_postgresql",
        lambda *_: DatabaseReadiness(
            False, DatabaseReadinessCode.PGVECTOR_MISSING,
            "未启用 pgvector 扩展", ("执行 CREATE EXTENSION IF NOT EXISTS vector;",),
        ),
    )

    result = service.test_section(
        "database",
        {"database_url": "postgresql+psycopg://user:secret@localhost:5432/alphafoundry"},
    )

    assert result["success"] is False
    assert result["code"] == "pgvector_missing"
    assert "secret" not in json.dumps(result)
    assert not (tmp_path / ".env").exists()
~~~

再以 TestClient 覆盖 POST /api/config/database/test 的有效 CSRF 请求，断言 API 返回安全 code/remediation，而非底层异常。

- [ ] **Step 2: 确认失败**

Run: python -m pytest tests/unit/test_configuration_service.py tests/unit/app/api/routes/test_configuration_database_probe.py -q
Expected: FAIL，因为现有实现只验证 URL 格式。

- [ ] **Step 3: 最小实现**

将模型改为：

~~~
class ConfigurationTestResponse(StrictModel):
    success: bool
    message: str
    code: str | None = None
    remediation: list[str] = Field(default_factory=list)
~~~

在 ConfigurationService.test_section 的 database 分支调用 probe_postgresql(candidate["DATABASE_URL"], self.connection_timeout)，转为上述响应。不得调用 _write_env_atomic、修改 os.environ 或刷新全局 SQLAlchemy engine。

- [ ] **Step 4: 验证通过**

Run: python -m pytest tests/unit/test_configuration_service.py tests/unit/app/api/routes/test_configuration_database_probe.py -q
Expected: PASS。

- [ ] **Step 5: 提交**

~~~
git add services/configuration_service.py app/api/configuration_models.py tests/unit/test_configuration_service.py tests/unit/app/api/routes/test_configuration_database_probe.py
git commit -m "feat: verify database configuration with pgvector"
~~~

### Task 3: 加入 desktop setup_required 状态与安全读取 API

**Files:**
- Create: app/api/routes/setup.py
- Modify: app/api/main.py:46-112,178-266,323-350
- Modify: tests/unit/app/api/test_health_security.py
- Create: tests/unit/app/api/routes/test_setup_readiness.py

- [ ] **Step 1: 写失败测试**

~~~
from unittest.mock import MagicMock

def test_desktop_startup_enters_setup_required_without_schema_or_schedulers(monkeypatch):
    monkeypatch.setattr(main, "probe_postgresql", lambda *_: missing_vector_result())
    ensure_schema = MagicMock()
    start_schedulers = MagicMock()
    monkeypatch.setattr(main, "ensure_schema", ensure_schema)
    monkeypatch.setattr(main, "_start_data_acquisition_schedulers", start_schedulers)
    monkeypatch.setattr(main, "RUNTIME_CONTEXT", desktop_context())

    asyncio.run(main.startup())

    assert main.app.state.database_readiness.code.value == "pgvector_missing"
    ensure_schema.assert_not_called()
    start_schedulers.assert_not_called()

def test_web_startup_reraises_database_readiness_failure(monkeypatch):
    monkeypatch.setattr(main, "probe_postgresql", lambda *_: connection_failed_result())
    monkeypatch.setattr(main, "RUNTIME_CONTEXT", web_dev_context())

    with pytest.raises(RuntimeError, match="无法连接 PostgreSQL"):
        asyncio.run(main.startup())
~~~

补充 GET /api/setup/readiness 的 loopback 访问、无秘密字段、setup_required 响应和 /health 的 HTTP 200 + persistence.status == setup_required 测试。

- [ ] **Step 2: 确认失败**

Run: python -m pytest tests/unit/app/api/test_health_security.py tests/unit/app/api/routes/test_setup_readiness.py -q
Expected: FAIL，因为尚无 app.state.database_readiness 和 setup 路由。

- [ ] **Step 3: 最小实现**

在 startup 中替换直接 check_database_connection：

~~~
app.state.database_readiness = probe_postgresql(settings.DATABASE_URL)
if app.state.database_readiness.ready:
    ensure_schema()
    _start_data_acquisition_schedulers()
elif RUNTIME_CONTEXT.mode == "desktop":
    logger.warning("Desktop started in setup-required mode",
                   extra={"code": app.state.database_readiness.code.value})
else:
    raise RuntimeError(app.state.database_readiness.message)
~~~

setup.py 的 GET /api/setup/readiness 使用 require_configuration_origin_only。它重新预检当前 settings.DATABASE_URL，以显示“检查通过，重启生效”，并返回 runtime_status、database、remediation、restart_required；不得返回 URL/异常。/health 用 app.state 状态返回 ready 或 setup_required。

- [ ] **Step 4: 验证通过**

Run: python -m pytest tests/unit/app/api/test_health_security.py tests/unit/app/api/routes/test_setup_readiness.py -q
Expected: PASS。

- [ ] **Step 5: 提交**

~~~
git add app/api/main.py app/api/routes/setup.py tests/unit/app/api/test_health_security.py tests/unit/app/api/routes/test_setup_readiness.py
git commit -m "feat: keep desktop configuration available without database"
~~~

### Task 4: 修正 launcher 的启动前拒绝与 watchdog 行为

**Files:**
- Modify: scripts/desktop/backend_launcher.py:116-166,310-374
- Modify: tests/unit/test_desktop_shell_scaffold.py:770-800

- [ ] **Step 1: 写失败测试**

~~~
from unittest.mock import MagicMock

def test_frozen_backend_launcher_allows_missing_postgres_for_setup(monkeypatch, tmp_path):
    launcher = load_launcher_module()
    monkeypatch.setattr(launcher.sys, "frozen", True, raising=False)
    monkeypatch.setenv("ALPHAFOUNDRY_DESKTOP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://invalid:invalid@127.0.0.1:1/alphafoundry",
    )

    assert launcher.apply_frozen_desktop_defaults() == tmp_path

def test_launcher_skips_watchdogs_when_database_probe_is_not_ready(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "probe_postgresql", lambda *_: connection_failed_result())
    knowledge = MagicMock()
    scheduler = MagicMock()
    monkeypatch.setattr(launcher, "_start_knowledge_worker", knowledge)
    monkeypatch.setattr(launcher, "_start_crawl_scheduler", scheduler)
    monkeypatch.setattr(launcher, "run_backend", lambda *_: (_ for _ in ()).throw(SystemExit()))

    assert launcher.main([]) == 1
    knowledge.assert_not_called()
    scheduler.assert_not_called()
~~~

- [ ] **Step 2: 确认失败**

Run: python -m pytest tests/unit/test_desktop_shell_scaffold.py -k 'frozen_backend_launcher or launcher_skips_watchdogs' -q
Expected: FAIL，因为 launcher 当前拒绝缺少有效 URL 并无条件启动 watchdog。

- [ ] **Step 3: 最小实现**

删除 apply_frozen_desktop_defaults 中 PostgreSQL scheme 的 RuntimeError，保留 .env、权限和路径处理。main 在启动两个 watchdog 前调用同一 probe_postgresql(os.environ.get("DATABASE_URL", ""))：仅 ready 才启动；未就绪记录安全 code 后直接运行 FastAPI。绝不记录 URL。

- [ ] **Step 4: 验证通过**

Run: python -m pytest tests/unit/test_desktop_shell_scaffold.py -k 'frozen_backend_launcher or launcher_skips_watchdogs' -q
Expected: PASS。

- [ ] **Step 5: 提交**

~~~
git add scripts/desktop/backend_launcher.py tests/unit/test_desktop_shell_scaffold.py
git commit -m "fix: start desktop setup mode without PostgreSQL"
~~~

### Task 5: 实现欢迎覆盖层与真实数据库卡片状态

**Files:**
- Create: app/web/static/js/setup-wizard.js
- Modify: app/web/static/js/app.js:1-30,200-230
- Modify: app/web/static/js/configuration.js:520-570,1020-1100
- Modify: app/web/templates/index.html:1219-1340,2230-2245
- Modify: app/web/static/style.css
- Modify: tests/unit/test_configuration_frontend_static.py
- Create: tests/unit/test_setup_wizard_frontend_static.py

- [ ] **Step 1: 写失败测试**

~~~
def test_setup_wizard_reads_readiness_and_opens_database_configuration():
    source = SETUP_WIZARD_JS.read_text(encoding="utf-8")
    assert "'/api/setup/readiness'" in source
    assert "openConfigModal('database')" in source
    assert "暂时跳过" in source
    assert "remediation" in source

def test_database_summary_uses_runtime_readiness_not_saved_url_only():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    assert "databaseRuntimeReadiness" in source
    assert "已配置连接地址" not in source
~~~

补充 index.html 存在 #setup-wizard、aria-live、打开配置和跳过按钮；Node 对 app.js、configuration.js、setup-wizard.js 均可解析。

- [ ] **Step 2: 确认失败**

Run: python -m pytest tests/unit/test_configuration_frontend_static.py tests/unit/test_setup_wizard_frontend_static.py -q
Expected: FAIL，因为欢迎模块与真实状态变量还不存在。

- [ ] **Step 3: 最小实现**

setup-wizard.js 导出 initSetupWizard()：GET /api/setup/readiness；仅 runtime_status == setup_required 显示覆盖层；用 textContent 渲染 message/remediation。“打开数据库配置”先 initConfigurationPage 再 openConfigModal("database")；“暂时跳过”仅关闭覆盖层。

configuration.js 导出 openConfigModal；数据库保存与测试后刷新 setup readiness。摘要只能显示“数据库已验证”“数据库待重启”或“数据库未就绪”，由 databaseRuntimeReadiness 决定。app.js 在所有数据库依赖初始化前执行 initSetupWizard，setup 模式不自动请求业务数据。HTML/CSS 添加无障碍覆盖层、焦点与窄屏样式；不得 innerHTML 注入 API 文案。

- [ ] **Step 4: 验证通过**

Run: python -m pytest tests/unit/test_configuration_frontend_static.py tests/unit/test_setup_wizard_frontend_static.py -q && node --check app/web/static/js/app.js && node --check app/web/static/js/configuration.js && node --check app/web/static/js/setup-wizard.js
Expected: PASS。

- [ ] **Step 5: 提交**

~~~
git add app/web/static/js/setup-wizard.js app/web/static/js/app.js app/web/static/js/configuration.js app/web/templates/index.html app/web/static/style.css tests/unit/test_configuration_frontend_static.py tests/unit/test_setup_wizard_frontend_static.py
git commit -m "feat: guide desktop users through database setup"
~~~

### Task 6: 原生 macOS/Windows CI 验证 ready 与 setup_required

**Files:**
- Modify: scripts/desktop/check_sidecar_health.py
- Modify: tests/unit/test_check_sidecar_health.py
- Modify: .github/workflows/desktop-verify.yml
- Modify: tests/unit/test_desktop_shell_scaffold.py
- Modify: docs/desktop_packaging.md

- [ ] **Step 1: 写失败测试**

~~~
def test_health_helper_requires_expected_persistence_status(monkeypatch, tmp_path):
    module = load_helper_module()
    monkeypatch.setattr(
        module,
        "endpoint_health",
        lambda _port: {"status": "ok", "persistence": {"status": "setup_required"}},
    )

    assert module.wait_for_health(
        8765, 1, logger, expected_persistence_status="setup_required"
    ) is True

def test_desktop_verify_smokes_setup_required_on_both_native_runners():
    source = DESKTOP_VERIFY_WORKFLOW.read_text(encoding="utf-8")
    assert "Smoke test setup-required sidecar /health" in source
    assert "--expected-persistence-status setup_required" in source
    assert "app/web/**" in source
    assert "services/database_readiness.py" in source
~~~

- [ ] **Step 2: 确认失败**

Run: python -m pytest tests/unit/test_check_sidecar_health.py tests/unit/test_desktop_shell_scaffold.py -k 'expected_persistence or setup_required_on_both' -q
Expected: FAIL，因为 helper 当前只验证 HTTP 200，workflow 只验证 ready。

- [ ] **Step 3: 最小实现**

将 helper 拆出 endpoint_health()，解析 health JSON；新增可选 --expected-persistence-status。既有 ready smoke 不传该参数，保持原行为。

macOS 和 Windows runner 在已有真实 pgvector sidecar smoke 后，各增加一次“Smoke test setup-required sidecar /health”：独立数据目录、端口 8766、不可连接的 PostgreSQL URL、--expected-persistence-status setup_required，并上传 setup-smoke.log。workflow path filters 增加 app/api/main.py、app/api/routes/setup.py、app/api/configuration_models.py、app/web/**、services/database_readiness.py、docs/desktop_packaging.md。

文档明确：安装包不安装数据库；首次启动可配置；连接 PostgreSQL + pgvector 后重启；CI 测 ready/setup-required；发版仍须真实 Windows x64 安装级冒烟。

- [ ] **Step 4: 完整本地验证**

~~~
python -m pytest tests/unit/test_database_readiness.py tests/unit/test_configuration_service.py tests/unit/app/api/test_health_security.py tests/unit/app/api/routes/test_configuration_database_probe.py tests/unit/app/api/routes/test_setup_readiness.py tests/unit/test_configuration_frontend_static.py tests/unit/test_setup_wizard_frontend_static.py tests/unit/test_check_sidecar_health.py tests/unit/test_desktop_shell_scaffold.py -q
node --check app/web/static/js/app.js
node --check app/web/static/js/configuration.js
node --check app/web/static/js/setup-wizard.js
~~~

Expected: PASS。随后推送 master，确认 GitHub Actions 中 macOS Apple Silicon 与 Windows x64 都通过原生 pgvector、setup-required sidecar、Tauri bundle。

- [ ] **Step 5: 提交**

~~~
git add scripts/desktop/check_sidecar_health.py tests/unit/test_check_sidecar_health.py .github/workflows/desktop-verify.yml tests/unit/test_desktop_shell_scaffold.py docs/desktop_packaging.md
git commit -m "ci: verify desktop database setup mode"
~~~
