# 配置目录与环境能力中心 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在既有系统配置页面中提供统一、脱敏的配置目录和多平台环境能力诊断，不改变现有编辑、保存、连接测试和锁定行为。

**Architecture:** `services/configuration_catalog.py` 是配置元数据唯一来源。ConfigurationService 将目录和无副作用的环境检测并入已有配置快照，`/api/config` 通过严格 Pydantic 模型发布；前端只在现有健康总览和首次配置引导之间呈现只读诊断区。

**Tech Stack:** Python 3.11、FastAPI、Pydantic v2、pytest、原生 ES modules、Node.js。

---

### Task 1: 定义配置目录元数据

**Files:**
- Create: `services/configuration_catalog.py`
- Create: `tests/unit/test_configuration_catalog.py`

- [ ] **Step 1: 写失败测试**

```python
from services.configuration_catalog import get_configuration_catalog


def test_catalog_describes_existing_sections_without_values():
    catalog = get_configuration_catalog()
    assert [item["key"] for item in catalog["sections"]] == [
        "llm", "zhiqiu", "ifind", "database", "advanced", "web_search",
    ]
    database = next(item for item in catalog["sections"] if item["key"] == "database")
    assert database["restart_required"] is True
    assert database["fields"] == [{
        "key": "database_url", "label": "数据库连接地址", "kind": "secret",
        "environment_keys": ["DATABASE_URL"],
    }]
    assert "DATABASE_URL=" not in repr(catalog)
```

- [ ] **Step 2: 确认失败**

Run: `python -m pytest tests/unit/test_configuration_catalog.py -q`

Expected: `ModuleNotFoundError`，因为目录模块尚不存在。

- [ ] **Step 3: 实现只含元数据的不可变目录**

```python
SECTION_CATALOG = (
    {"key": "database", "label": "数据库", "scope": "global",
     "platforms": ("macos", "windows"), "restart_required": True,
     "testable": True,
     "fields": ({"key": "database_url", "label": "数据库连接地址",
                 "kind": "secret", "environment_keys": ("DATABASE_URL",)},)},
)


def get_configuration_catalog() -> dict[str, list[dict[str, object]]]:
    """Return a fresh JSON-safe copy without reading settings or `.env`."""
    return {"sections": [_copy_section(section) for section in SECTION_CATALOG]}
```

Include all six existing sections. `_copy_section` must recursively convert tuples to lists. Do not include defaults, current values, paths, database URLs, passwords, or keys.

- [ ] **Step 4: 验证并提交**

Run: `python -m pytest tests/unit/test_configuration_catalog.py -q`

Expected: PASS.

```bash
git add services/configuration_catalog.py tests/unit/test_configuration_catalog.py
git commit -m "feat: define configuration catalog metadata"
```

### Task 2: 在配置服务中加入安全环境检测

**Files:**
- Modify: `services/configuration_service.py`
- Modify: `tests/unit/test_configuration_service.py`

- [ ] **Step 1: 写失败测试**

```python
def test_snapshot_includes_safe_platform_capabilities(monkeypatch, tmp_path):
    service = ConfigurationService(env_path=tmp_path / ".env", runtime_settings=Settings())
    monkeypatch.setattr(configuration_service.platform, "system", lambda: "Windows")
    monkeypatch.setattr(configuration_service.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(configuration_service.shutil, "which", lambda name: "C:/pg/bin/psql.exe")

    environment = service.get_snapshot()["environment"]
    assert environment["platform"] == "windows"
    assert environment["architecture"] == "x64"
    assert environment["capabilities"][0]["key"] == "postgresql_client"
    assert environment["capabilities"][0]["status"] == "available"
    assert "psql.exe" not in json.dumps(environment)
```

Add cases for missing `psql`, macOS `wind_excel=not_applicable`, SDK discovery failure=`unknown`, and `RuntimeContext(data_dir=None)`.

- [ ] **Step 2: 确认失败**

Run: `python -m pytest tests/unit/test_configuration_service.py -k "platform_capabilities or environment_summary" -q`

Expected: FAIL because the snapshot has no `environment` member.

- [ ] **Step 3: 实现每项独立降级的检测器**

```python
def _environment_snapshot(self) -> dict[str, Any]:
    platform_name = _normalize_platform(platform.system())
    return {
        "platform": platform_name,
        "architecture": _normalize_architecture(platform.machine()),
        "runtime_mode": self.runtime_context.mode,
        "paths": _safe_runtime_paths(self.runtime_context, self.runtime_settings),
        "capabilities": [
            _postgresql_client_capability(),
            _ifind_sdk_capability(platform_name),
            _wind_excel_capability(platform_name),
        ],
    }
```

Use `shutil.which("psql")` as a boolean only; use `importlib.util.find_spec` for iFinD without importing it. Wind returns `not_applicable` outside Windows and `unknown` on Windows with an instruction to test it in Excel. Each detector catches discovery failures, logs only `capability`, `platform`, `error_type`, and returns `unknown`. Extend `get_snapshot()` with `catalog` and `environment`, while retaining the existing production-Web rejection first.

- [ ] **Step 4: 验证并提交**

Run: `python -m pytest tests/unit/test_configuration_catalog.py tests/unit/test_configuration_service.py -q`

Expected: PASS.

```bash
git add services/configuration_service.py tests/unit/test_configuration_service.py
git commit -m "feat: expose configuration environment diagnostics"
```

### Task 3: 发布严格的 API 快照契约

**Files:**
- Modify: `app/api/configuration_models.py`
- Modify: `tests/unit/app/api/test_configuration_security.py`
- Modify: `tests/unit/app/api/routes/test_configuration_token.py`

- [ ] **Step 1: 写失败测试**

```python
def test_snapshot_response_accepts_safe_catalog_and_environment():
    response = ConfigurationSnapshotResponse.model_validate({
        **minimal_snapshot_payload(),
        "catalog": {"sections": []},
        "environment": {
            "platform": "windows", "architecture": "x64", "runtime_mode": "desktop",
            "paths": {"config": "C:/safe/.env", "data": None, "logs": "C:/safe/logs"},
            "capabilities": [],
        },
    })
    assert response.environment.platform == "windows"
```

Add API coverage asserting the existing CSRF requirement still applies and serialized data excludes a password-bearing URL.

- [ ] **Step 2: 确认失败**

Run: `python -m pytest tests/unit/app/api/test_configuration_security.py tests/unit/app/api/routes/test_configuration_token.py -q`

Expected: FAIL because strict response validation rejects the two new fields.

- [ ] **Step 3: 增加严格模型**

```python
class ConfigurationCapability(StrictModel):
    key: str
    label: str
    status: Literal["available", "not_detected", "not_applicable", "unknown"]
    detail: str
    remediation: list[str] = Field(default_factory=list)


class ConfigurationEnvironmentResponse(StrictModel):
    platform: Literal["macos", "windows", "linux", "unknown"]
    architecture: str
    runtime_mode: str
    paths: ConfigurationPathsResponse
    capabilities: list[ConfigurationCapability]
```

Define matching catalog field/section models, then make `catalog` and `environment` required `ConfigurationSnapshotResponse` fields. Keep all update/test request models unchanged.

- [ ] **Step 4: 验证并提交**

Run: `python -m pytest tests/unit/app/api/test_configuration_security.py tests/unit/app/api/routes/test_configuration_token.py tests/unit/test_configuration_service.py -q`

Expected: PASS.

```bash
git add app/api/configuration_models.py tests/unit/app/api/test_configuration_security.py tests/unit/app/api/routes/test_configuration_token.py
git commit -m "feat: publish configuration capability contract"
```

### Task 4: 在现有系统配置页呈现只读诊断区

**Files:**
- Modify: `app/web/templates/index.html`
- Modify: `app/web/static/js/configuration.js`
- Modify: `app/web/static/style.css`
- Modify: `tests/unit/test_configuration_frontend_static.py`

- [ ] **Step 1: 写失败测试**

```python
def test_configuration_console_adds_read_only_diagnostics_without_replacing_existing_ui():
    template = CONFIGURATION_TEMPLATE.read_text(encoding="utf-8")
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    assert 'data-config-health-summary' in template
    assert 'data-config-environment-diagnostics' in template
    assert 'renderEnvironmentDiagnostics(snapshot)' in source
    assert 'snapshot.environment' in source
    assert 'snapshot.catalog' in source
    assert 'openConfigModal' in source
```

Add a Node test for exported pure `getCapabilityPresentation`, covering all four supported states without DOM access.

- [ ] **Step 2: 确认失败**

Run: `python -m pytest tests/unit/test_configuration_frontend_static.py -q`

Expected: FAIL because no diagnostics section/rendering function exists.

- [ ] **Step 3: 添加协同的只读 UI**

```html
<section class="config-environment-diagnostics" data-config-environment-diagnostics aria-label="当前环境与能力" hidden>
  <div class="config-environment-heading">
    <span>当前环境</span><strong data-config-environment-summary></strong>
    <p data-config-environment-paths></p>
  </div>
  <ul data-config-capability-list></ul>
</section>
```

Place it after `data-config-health-summary` and before `data-config-onboarding`. Render via `textContent`, `replaceChildren`, and created DOM nodes only. Hide it when an older backend lacks `snapshot.environment`. Only use `snapshot.catalog` as a label fallback. Do not mutate readiness, database runtime readiness, card click handling, modal logic, setup wizard, or environment-lock helpers. Scope styles to `.config-environment-diagnostics` and existing status colors; do not create overlays or focus traps.

- [ ] **Step 4: 验证并提交**

Run: `python -m pytest tests/unit/test_configuration_frontend_static.py -q && node --check app/web/static/js/configuration.js`

Expected: PASS.

```bash
git add app/web/templates/index.html app/web/static/js/configuration.js app/web/static/style.css tests/unit/test_configuration_frontend_static.py
git commit -m "feat: show configuration environment diagnostics"
```

### Task 5: 文档、回归与原生桌面门禁

**Files:**
- Modify: `docs/modules/app_web.md`
- Modify: `docs/desktop_packaging.md`

- [ ] **Step 1: 更新运行约束文档**

Document that diagnostics are read-only; `psql` detection is neither server nor pgvector validation; Windows Wind requires Excel validation; operational database health remains `/api/setup/readiness` and the database connection test; desktop changes require native Windows CI.

- [ ] **Step 2: 运行完整针对性回归**

Run:

```bash
python -m pytest \
  tests/unit/test_configuration_catalog.py \
  tests/unit/test_configuration_service.py \
  tests/unit/app/api/test_configuration_security.py \
  tests/unit/app/api/routes/test_configuration_token.py \
  tests/unit/app/api/routes/test_configuration_database_probe.py \
  tests/unit/app/api/routes/test_setup_readiness.py \
  tests/unit/test_configuration_frontend_static.py \
  tests/unit/test_setup_wizard_frontend_static.py -q
node --check app/web/static/js/configuration.js
git diff --check
```

Expected: all tests pass, JavaScript syntax validation exits 0, and `git diff --check` has no output.

- [ ] **Step 3: 提交并验证 CI**

```bash
git add docs/modules/app_web.md docs/desktop_packaging.md
git commit -m "docs: describe configuration capability diagnostics"
```

After merging and pushing `master`, confirm `desktop-verify.yml` completes on native `macOS Apple Silicon` and `Windows x64`; do not claim Windows support from local macOS tests.
