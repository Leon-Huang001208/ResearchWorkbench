# System Configuration Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增可迁移、可脱敏读取、可安全持久化并同步后端运行配置的系统配置页面。

**Architecture:** FastAPI 路由只处理请求分发，`ConfigurationService` 负责配置路径解析、脱敏视图、校验、原子写入和运行时刷新。Web 工作台新增独立 ES module 和页面分区；通用设置写入开发环境 `.env` 或桌面数据目录 `.env`，知秋账号使用 JSON 环境值并兼容旧格式。

**Tech Stack:** Python 3.9、FastAPI、Pydantic、python-dotenv、原生 JavaScript ES modules、HTML/CSS、pytest、Playwright。

---

## 文件职责映射

- `services/configuration_service.py`：配置路径、读取、脱敏、原子持久化、热更新和连接验证的唯一业务入口。
- `app/api/configuration_models.py`：五类配置的请求、响应和秘密三态契约。
- `app/api/routes/configuration.py`：`/api/config` 路由和依赖注入。
- `core/settings/config.py`：统一解析桌面数据目录或项目目录的 `.env`，提供运行时刷新入口。
- `data_layer/crawlers/zq/zhiqiu/account_manager.py`：优先读取 `ZQ_ACCOUNTS_JSON`，兼容旧 `ZQ_ACCOUNTS` 和 YAML。
- `app/web/static/js/configuration.js`：加载、渲染、编辑、保存和验证配置。
- `app/web/templates/index.html`：导航入口和配置页面语义结构。
- `app/web/static/js/app.js`：模块导入和导航生命周期。
- `app/web/static/style.css`：配置中心布局、状态和响应式样式。

### Task 1: 建立任务审计记录

**Files:**
- Create: `.ai/tasks/task_system_configuration_center.json`
- Create: `.ai/progress/progress_system_configuration_center.md`
- Modify: `.ai/progress/progress.md`

- [ ] **Step 1: 创建 doing 状态任务文件**

```json
{
  "tasks": [{
    "id": "system-configuration-center-001",
    "title": "新增系统配置中心",
    "description": "集中管理模型、知秋、iFinD、数据库和高级运行配置，并同步后端。",
    "priority": "high",
    "dependencies": [],
    "success_criteria": [
      "配置页可读取和保存五类配置",
      "敏感字段只返回脱敏状态",
      "可热更新配置立即生效，数据库明确提示重启",
      "测试、浏览器验证和文档同步完成"
    ],
    "verification_commands": [
      "ruff check .",
      "black . --check",
      "isort . --check-only",
      "mypy core/ data_layer/ knowledge_layer/ reasoning/ reporting/ signal_lab/ app/",
      "python -m pytest tests/ -v",
      "python scripts/generate_py_file_index.py",
      "python scripts/check_task_completion.py",
      "python scripts/check_doc_sync.py"
    ],
    "status": "doing",
    "started_at": "2026-07-12"
  }],
  "metadata": {
    "task_set_id": "system-configuration-center",
    "status": "doing",
    "started_at": "2026-07-12"
  }
}
```

- [ ] **Step 2: 添加进度文件和总索引行**

```markdown
# system-configuration-center 进度

- 状态：进行中
- 目标：实现本地优先的系统配置中心。
- 设计：`docs/superpowers/specs/2026-07-12-system-configuration-center-design.md`
- 计划：`docs/superpowers/plans/2026-07-12-system-configuration-center.md`
```

- [ ] **Step 3: 提交任务记录**

```bash
git add .ai/tasks/task_system_configuration_center.json .ai/progress/progress_system_configuration_center.md .ai/progress/progress.md
git commit -m "chore: track system configuration center"
```

### Task 2: 配置路径与知秋 JSON 兼容层

**Files:**
- Modify: `core/settings/config.py`
- Modify: `data_layer/crawlers/zq/zhiqiu/account_manager.py`
- Create: `tests/unit/test_runtime_configuration_compatibility.py`

- [ ] **Step 1: 写失败测试，覆盖桌面配置路径和 JSON 特殊字符账号**

```python
def test_resolve_env_path_prefers_desktop_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("ALPHAFOUNDRY_DESKTOP_DATA_DIR", str(tmp_path))
    assert resolve_runtime_env_path() == tmp_path / ".env"


def test_account_manager_prefers_json_accounts(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("accounts: {}\n", encoding="utf-8")
    monkeypatch.setenv(
        "ZQ_ACCOUNTS_JSON",
        '{"research":{"username":"user@example.com","password":"a:b,c"}}',
    )
    manager = AccountManager(str(config_path), "test")
    assert manager.get_account_credentials("research") == {
        "username": "user@example.com",
        "password": "a:b,c",
    }
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/unit/test_runtime_configuration_compatibility.py -v`

Expected: FAIL，缺少 `resolve_runtime_env_path` 且账号管理器未读取 JSON。

- [ ] **Step 3: 实现统一路径和兼容解析**

```python
def resolve_runtime_env_path() -> Path:
    explicit = os.environ.get("ALPHAFOUNDRY_CONFIG_PATH", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    desktop_dir = os.environ.get("ALPHAFOUNDRY_DESKTOP_DATA_DIR", "").strip()
    if desktop_dir:
        return Path(desktop_dir).expanduser() / ".env"
    return Path(__file__).resolve().parents[2] / ".env"
```

在 `AccountManager._load_config` 中先 `json.loads(os.environ["ZQ_ACCOUNTS_JSON"])` 并校验每项包含非空用户名和密码；无 JSON 时再使用旧 `ZQ_ACCOUNTS`，最后回退 YAML。解析异常记录不含原值的 warning 并安全回退。

- [ ] **Step 4: 运行兼容测试**

Run: `python -m pytest tests/unit/test_runtime_configuration_compatibility.py -v`

Expected: PASS。

- [ ] **Step 5: 提交兼容层**

```bash
git add core/settings/config.py data_layer/crawlers/zq/zhiqiu/account_manager.py tests/unit/test_runtime_configuration_compatibility.py
git commit -m "feat: support portable runtime configuration"
```

### Task 3: 配置服务与秘密安全

**Files:**
- Create: `services/configuration_service.py`
- Create: `tests/unit/test_configuration_service.py`

- [ ] **Step 1: 写失败测试覆盖脱敏、原子更新和运行时生效**

```python
def test_snapshot_never_returns_saved_secrets(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "IFIND_USERNAME=analyst\nIFIND_PASSWORD=secret-pass\n"
        "LLM_PROVIDER_1_NAME=primary\nLLM_PROVIDER_1_API_KEY=secret-token\n",
        encoding="utf-8",
    )
    service = ConfigurationService(env_path=env_path)
    payload = json.dumps(service.snapshot(), ensure_ascii=False)
    assert "secret-pass" not in payload
    assert "secret-token" not in payload
    assert '"configured": true' in payload


def test_update_preserves_comments_and_unrelated_values(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("# keep me\nUNRELATED=value\nLOG_LEVEL=INFO\n", encoding="utf-8")
    ConfigurationService(env_path=env_path).update_advanced({"log_level": "DEBUG"})
    saved = env_path.read_text(encoding="utf-8")
    assert "# keep me" in saved
    assert "UNRELATED=value" in saved
    assert "LOG_LEVEL=DEBUG" in saved
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/unit/test_configuration_service.py -v`

Expected: FAIL，`ConfigurationService` 尚不存在。

- [ ] **Step 3: 实现 EnvFileStore 和 ConfigurationService**

```python
class EnvFileStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def update(self, changes: dict[str, str | None]) -> None:
        lines = self.path.read_text(encoding="utf-8").splitlines() if self.path.exists() else []
        remaining = dict(changes)
        output: list[str] = []
        for line in lines:
            key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else ""
            if key in remaining:
                value = remaining.pop(key)
                if value is not None:
                    output.append(f"{key}={value}")
            else:
                output.append(line)
        output.extend(f"{key}={value}" for key, value in remaining.items() if value is not None)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, delete=False) as handle:
            handle.write("\n".join(output).rstrip() + "\n")
            temp_path = Path(handle.name)
        temp_path.chmod(0o600)
        temp_path.replace(self.path)
```

`ConfigurationService` 分别实现 `snapshot()`、`update_llm()`、`update_zhiqiu()`、`update_ifind()`、`update_database()`、`update_advanced()` 和 `test_section()`；秘密使用 `SecretState(configured, masked_value)`，掩码只保留末四位。所有更新先完整校验，再一次性写入，最后更新 `os.environ` 和 `settings` 的可热更新字段。数据库只写文件并返回 `restart_required=True`。

- [ ] **Step 4: 补充失败路径测试**

```python
def test_database_update_is_persisted_but_requires_restart(tmp_path):
    result = ConfigurationService(env_path=tmp_path / ".env").update_database(
        {"database_url": "sqlite:////tmp/alpha.db"}
    )
    assert result.restart_required is True
    assert result.applied is False


def test_empty_secret_keeps_existing_value(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("IFIND_PASSWORD=old-secret\n", encoding="utf-8")
    ConfigurationService(env_path=env_path).update_ifind({"password": ""})
    assert "IFIND_PASSWORD=old-secret" in env_path.read_text(encoding="utf-8")
```

- [ ] **Step 5: 运行服务测试**

Run: `python -m pytest tests/unit/test_configuration_service.py -v`

Expected: PASS。

- [ ] **Step 6: 提交配置服务**

```bash
git add services/configuration_service.py tests/unit/test_configuration_service.py
git commit -m "feat: add secure configuration service"
```

### Task 4: 配置 API 契约与路由

**Files:**
- Create: `app/api/configuration_models.py`
- Create: `app/api/routes/configuration.py`
- Modify: `app/api/main.py`
- Create: `tests/unit/test_configuration_api.py`

- [ ] **Step 1: 写失败 API 测试**

```python
def test_get_configuration_returns_masked_snapshot(client):
    response = client.get("/api/config")
    assert response.status_code == 200
    body = response.json()
    assert set(body) >= {"readiness", "llm", "zhiqiu", "ifind", "database", "advanced"}
    assert "api_key" not in json.dumps(body)


def test_put_database_reports_restart_required(client):
    response = client.put(
        "/api/config/database",
        json={"database_url": "sqlite:////tmp/alpha.db"},
    )
    assert response.status_code == 200
    assert response.json()["restart_required"] is True
```

- [ ] **Step 2: 运行 API 测试确认失败**

Run: `python -m pytest tests/unit/test_configuration_api.py -v`

Expected: FAIL，路由返回 404。

- [ ] **Step 3: 定义严格请求模型**

```python
class SecretInput(BaseModel):
    value: str = ""
    clear: bool = False


class DatabaseConfigurationUpdate(BaseModel):
    database_url: str = Field(min_length=1, max_length=2048)


class ConfigurationUpdateResponse(BaseModel):
    section: str
    applied: bool
    restart_required: bool
    message: str
    configuration: dict[str, Any]
```

为 LLM Provider/路由、知秋账号/轮询、iFinD 和高级参数定义 `extra="forbid"` 的模型，并为并发数、重试次数、超时和日志级别设置枚举或数值边界。

- [ ] **Step 4: 实现薄路由和依赖注入**

```python
router = APIRouter(prefix="/api/config", tags=["configuration"])


def get_configuration_service() -> ConfigurationService:
    return ConfigurationService()


@router.get("")
def get_configuration(service: ConfigurationService = Depends(get_configuration_service)):
    return service.snapshot()


@router.put("/{section}", response_model=ConfigurationUpdateResponse)
def update_configuration(section: ConfigurationSection, request: dict[str, Any], service=Depends(get_configuration_service)):
    return service.update_section(section.value, request)
```

实际路由按 `section` 将原始 JSON 解析为对应严格模型后调用服务；捕获配置领域异常并返回不含秘密的 400/422，意外错误使用 `logger.exception` 后返回通用 500。

- [ ] **Step 5: 运行 API 契约和错误测试**

Run: `python -m pytest tests/unit/test_configuration_api.py -v`

Expected: PASS。

- [ ] **Step 6: 提交 API**

```bash
git add app/api/configuration_models.py app/api/routes/configuration.py app/api/main.py tests/unit/test_configuration_api.py
git commit -m "feat: expose configuration API"
```

### Task 5: 系统配置页面与交互

**Files:**
- Modify: `app/web/templates/index.html`
- Create: `app/web/static/js/configuration.js`
- Modify: `app/web/static/js/app.js`
- Modify: `app/web/static/style.css`
- Create: `tests/unit/test_configuration_frontend.py`

- [ ] **Step 1: 写失败静态回归测试**

```python
def test_configuration_page_is_wired_into_navigation():
    html = INDEX_HTML.read_text(encoding="utf-8")
    app_source = APP_JS.read_text(encoding="utf-8")
    assert 'data-section="config"' in html
    assert 'id="section-config"' in html
    assert "initConfigurationPage" in app_source


def test_configuration_page_contains_all_sections():
    html = INDEX_HTML.read_text(encoding="utf-8")
    for section in ("llm", "zhiqiu", "ifind", "database", "advanced"):
        assert f'data-config-section="{section}"' in html
```

- [ ] **Step 2: 运行前端静态测试确认失败**

Run: `python -m pytest tests/unit/test_configuration_frontend.py -v`

Expected: FAIL，导航和页面尚不存在。

- [ ] **Step 3: 添加语义化页面骨架**

```html
<button class="activity-btn" data-section="config" title="系统配置">
  <i class="codicon codicon-settings-gear"></i><span>系统配置</span>
</button>

<section id="section-config" class="content-section config-center">
  <header class="config-center-hero">
    <div><span class="eyebrow">SETUP & MIGRATION</span><h2>系统配置</h2></div>
    <div id="config-readiness" class="config-readiness">正在检查配置…</div>
  </header>
  <div id="config-status-grid" class="config-status-grid"></div>
  <div id="config-sections" class="config-sections">
    <article data-config-section="llm"></article>
    <article data-config-section="zhiqiu"></article>
    <article data-config-section="ifind"></article>
    <article data-config-section="database"></article>
    <details data-config-section="advanced"></details>
  </div>
</section>
```

每个 article 包含真实 label、帮助文本、输入控件、状态消息、验证按钮和保存按钮；秘密输入不设置 value 属性，不把掩码写进输入框。

- [ ] **Step 4: 实现配置模块**

```javascript
export async function initConfigurationPage() {
    const root = document.getElementById('section-config');
    if (!root || root.dataset.initialized === 'true') return;
    root.dataset.initialized = 'true';
    bindConfigurationActions(root);
    await loadConfiguration(root);
}

async function saveSection(root, section) {
    setSectionState(root, section, 'saving', '正在保存…');
    try {
        const response = await apiCall('PUT', `/api/config/${section}`, collectSection(root, section));
        renderSection(root, section, response.configuration);
        setSectionState(root, section, response.restart_required ? 'restart' : 'success', response.message);
        await loadConfigurationSummary(root);
    } catch (error) {
        setSectionState(root, section, 'error', safeErrorMessage(error));
    }
}
```

模块实现 Provider/任务路由和知秋账号动态行，使用事件委托处理新增、删除、保存和验证；所有文本使用 `textContent` 或安全 DOM 创建函数，禁止把 API 字符串拼入 `innerHTML`。

- [ ] **Step 5: 接入导航并添加样式**

在 `app.js` 导入 `initConfigurationPage`，`navigateTo('config')` 时调用。CSS 使用现有设计令牌，提供双栏桌面布局、单栏窄窗口布局、清晰 focus 状态和 `ready/missing/error/restart` 状态色。

- [ ] **Step 6: 运行静态前端测试**

Run: `python -m pytest tests/unit/test_configuration_frontend.py -v`

Expected: PASS。

- [ ] **Step 7: 提交配置页面**

```bash
git add app/web/templates/index.html app/web/static/js/configuration.js app/web/static/js/app.js app/web/static/style.css tests/unit/test_configuration_frontend.py
git commit -m "feat: add system configuration page"
```

### Task 6: 文档、浏览器验证与完成门禁

**Files:**
- Modify: `.env.example`
- Modify: `docs/modules/app_web.md`
- Modify: `docs/modules/app_api.md`
- Modify: `docs/modules/data_layer_crawlers.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/DEVELOPMENT_MAP.md`
- Modify: `docs/FILE_GUIDE.md`
- Modify: `docs/REFERENCE.md`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/generated/py_file_index.md` (generated)
- Create: `.ai/reports/test_report_system_configuration_center.md`
- Modify: `.ai/progress/progress_system_configuration_center.md`
- Modify: `.ai/progress/progress.md`
- Modify: `.ai/tasks/task_system_configuration_center.json`

- [ ] **Step 1: 更新用户与开发文档**

在 `.env.example` 增加无真实秘密的 `ZQ_ACCOUNTS_JSON` 示例和多 Provider/任务路由示例。文档明确列出 `/api/config` 端点、配置文件位置、脱敏语义、热更新范围、数据库重启要求和旧知秋格式兼容顺序。

- [ ] **Step 2: 运行聚焦测试和格式检查**

```bash
python -m pytest tests/unit/test_runtime_configuration_compatibility.py tests/unit/test_configuration_service.py tests/unit/test_configuration_api.py tests/unit/test_configuration_frontend.py -v
ruff check services/configuration_service.py app/api/configuration_models.py app/api/routes/configuration.py core/settings/config.py data_layer/crawlers/zq/zhiqiu/account_manager.py tests/unit/test_runtime_configuration_compatibility.py tests/unit/test_configuration_service.py tests/unit/test_configuration_api.py tests/unit/test_configuration_frontend.py
black --check services/configuration_service.py app/api/configuration_models.py app/api/routes/configuration.py core/settings/config.py data_layer/crawlers/zq/zhiqiu/account_manager.py tests/unit/test_runtime_configuration_compatibility.py tests/unit/test_configuration_service.py tests/unit/test_configuration_api.py tests/unit/test_configuration_frontend.py
isort --check-only services/configuration_service.py app/api/configuration_models.py app/api/routes/configuration.py core/settings/config.py data_layer/crawlers/zq/zhiqiu/account_manager.py tests/unit/test_runtime_configuration_compatibility.py tests/unit/test_configuration_service.py tests/unit/test_configuration_api.py tests/unit/test_configuration_frontend.py
```

Expected: 所有聚焦测试和检查通过。

- [ ] **Step 3: 启动本地 API 并做浏览器验证**

Run: `/Users/leon/opt/anaconda3/bin/python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8002`

浏览器验证：进入系统配置；检查就绪卡片；新增/删除 Provider 与知秋账号；用测试临时配置保存高级参数；确认成功和重启提示；切换深浅主题；检查窄窗口；确认 DOM、网络响应和浏览器控制台无秘密或错误。验证后恢复测试配置。

- [ ] **Step 4: 运行项目完整门禁**

```bash
ruff check .
black . --check
isort . --check-only
mypy core/ data_layer/ knowledge_layer/ reasoning/ reporting/ signal_lab/ app/
python -m pytest tests/ -v
python scripts/generate_py_file_index.py
python scripts/check_task_completion.py
python scripts/check_doc_sync.py
```

Expected: 全部门禁通过；若仓库既有失败与本次无关，保留完整输出并按项目阻塞规则记录，不宣称完成。

- [ ] **Step 5: 写测试报告并更新任务状态**

```markdown
Task ID: system-configuration-center-001
Changed source files: 按实际文件列出
Changed test files: 按实际文件列出
Commands run: 按实际命令列出
Command results: 记录退出码和通过数量
Skipped tests: 无，或明确列出
Reason for skipped tests: 无，或明确原因
Remaining risk: 记录数据库重启和外部服务验证限制
Final test decision: passed 或 blocked
```

只有所有必需门禁通过时，才把任务和进度改为 `done`；否则保持 `doing` 或标记 `blocked`。

- [ ] **Step 6: 提交文档和完成记录**

```bash
git add .env.example docs/ .ai/reports/test_report_system_configuration_center.md .ai/progress/ .ai/tasks/task_system_configuration_center.json
git commit -m "docs: document system configuration center"
```

## 计划自检

- 规格覆盖：页面五分区、秘密脱敏、原子持久化、热更新、数据库重启、旧知秋兼容、错误处理、日志、测试和迁移均有对应任务。
- 边界一致：API 模型、服务方法、前端分区名统一使用 `llm/zhiqiu/ifind/database/advanced`。
- 范围控制：未加入云同步、多人权限、钥匙串或任意环境变量编辑。
- 依赖控制：使用项目现有依赖，不安装新的 Python 包。
