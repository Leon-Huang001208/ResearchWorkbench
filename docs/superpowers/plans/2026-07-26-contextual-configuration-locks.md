# 上下文配置锁定提示 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 移除首页的启动环境变量名单，只在受管字段、动态行或集合的配置弹窗内提供友好只读说明，并保持后端拒绝保护。

**Architecture:** 前端继续消费快照中的 `environment_locked_fields`，由一套锁定元数据映射到静态控件和动态行；该层只决定界面与无障碍属性。`ConfigurationService` 继续是保存权限的唯一边界，不新增 API。

**Tech Stack:** Jinja2、原生 ES modules、CSS、Pytest、Node `--check`、Playwright。

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `app/web/templates/index.html` | 删除首页全局锁定提示，增加弹窗按需说明节点。 |
| `app/web/static/js/configuration.js` | 映射并渲染字段、行、集合级锁定；删除首页名单渲染。 |
| `app/web/static/configuration.css` | 只读控件、锁定说明和窄屏样式。 |
| `tests/unit/test_configuration_frontend_static.py` | 首页无名单和局部锁定 UI 契约。 |
| `tests/unit/test_configuration_service.py` | 后端仍拒绝受管覆盖且不泄露值。 |
| `docs/modules/app_web.md`、`docs/CHANGELOG.md` | 用户可见行为说明。 |

### Task 1: 先锁定首页无名单的回归契约

**Files:**
- Modify: `tests/unit/test_configuration_frontend_static.py`
- Test: `tests/unit/test_configuration_frontend_static.py`

- [ ] **Step 1: 写入失败的静态测试**

新增下列测试：

```python
def test_configuration_locks_are_contextual_not_global():
    template = CONFIGURATION_TEMPLATE.read_text(encoding="utf-8")
    source = CONFIGURATION_JS.read_text(encoding="utf-8")

    assert "data-config-environment-lock-notice" not in template
    assert "renderEnvironmentLockedFields" not in source
    assert "LOCKED_FIELD_MESSAGE" in source
    assert "data-config-lock-message" in source
    assert "aria-describedby" in source
    assert "由当前启动配置管理" in source
```

- [ ] **Step 2: 验证测试失败原因正确**

Run: `/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3 -m pytest --noconftest tests/unit/test_configuration_frontend_static.py -v`

Expected: 仅新测试失败，指出首页仍有锁定提示且 JavaScript 尚未有局部说明逻辑。

### Task 2: 实现静态字段的上下文锁定

**Files:**
- Modify: `app/web/templates/index.html:1228-1231, 1330-1340`
- Modify: `app/web/static/js/configuration.js:580-610, 1271-1296`
- Modify: `app/web/static/configuration.css`
- Test: `tests/unit/test_configuration_frontend_static.py`

- [ ] **Step 1: 调整模板挂点**

删除：

```html
<details class="config-environment-lock-notice" data-config-environment-lock-notice hidden></details>
```

在 `#config-edit-modal .modal-footer` 的 `#config-edit-modal-status` 后插入：

```html
<span id="config-edit-modal-lock-note" class="config-modal-lock-note" hidden>
  <i class="codicon codicon-lock" aria-hidden="true"></i>部分字段由当前启动方式固定。
</span>
```

- [ ] **Step 2: 用统一映射替代首页渲染**

删除 `renderSnapshot()` 对 `renderEnvironmentLockedFields` 的调用及其函数。定义：

```javascript
const LOCKED_FIELD_MESSAGE = '此项由当前启动配置管理，不能在这里修改。';
const STATIC_LOCK_FIELD_KEYS = {
  advanced: { log_level: 'LOG_LEVEL', log_dir: 'LOG_DIR', llm_max_workers: 'LLM_EXTRACT_MAX_WORKERS', llm_max_retries: 'LLM_EXTRACT_MAX_RETRIES', chunk_size: 'LLM_EXTRACT_CHUNK_SIZE', chunk_overlap: 'LLM_EXTRACT_CHUNK_OVERLAP', long_text_threshold: 'LLM_EXTRACT_LONG_TEXT_THRESHOLD' },
  database: { database_url: 'DATABASE_URL' },
  web_search: { provider: 'WEB_SEARCH_PROVIDER', rotation_strategy: 'WEB_SEARCH_KEY_ROTATION', quota_limit: 'WEB_SEARCH_KEY_QUOTA_LIMIT', max_results: 'WEB_SEARCH_MAX_RESULTS', timeout: 'WEB_SEARCH_TIMEOUT' },
};
```

- [ ] **Step 3: 创建可复用的控件锁定 helper**

在 `applyEnvironmentLocks` 前实现并调用：

```javascript
function isEnvironmentLocked(key) {
  return new Set(configurationSnapshot?.environment_locked_fields || []).has(key);
}
function lockControl(control) {
  const label = control.closest('label');
  if (!label || label.dataset.configLocked === 'true') return false;
  const message = element('small', 'config-lock-message', LOCKED_FIELD_MESSAGE);
  message.id = `config-lock-${crypto.randomUUID()}`;
  message.dataset.configLockMessage = '';
  control.disabled = true;
  control.setAttribute('aria-describedby', message.id);
  label.dataset.configLocked = 'true';
  label.classList.add('environment-locked');
  label.append(message);
  return true;
}
```

`applyEnvironmentLocks` 遍历 `STATIC_LOCK_FIELD_KEYS[section]`，仅对受管键调用 `lockControl`；`setModalLockNote(visible)` 在打开每个 modal 前清除旧状态，再按锁定数量切换 `#config-edit-modal-lock-note.hidden`。

- [ ] **Step 4: 添加视觉与窄屏规则**

在 `configuration.css` 追加：

```css
.environment-locked { opacity: .72; }
.environment-locked input:disabled, .environment-locked select:disabled { cursor: not-allowed; }
.config-lock-message, .config-modal-lock-note { color: var(--text-muted); font-size: 12px; }
.config-modal-lock-note { margin-right: auto; }
```

在已有 modal 窄屏 media query 中令 `.config-modal-lock-note` 宽度为 `100%`，防止挤压 footer 按钮。

- [ ] **Step 5: 验证静态契约通过**

Run: `/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3 -m pytest --noconftest tests/unit/test_configuration_frontend_static.py -v && node --check app/web/static/js/configuration.js`

Expected: 测试全部通过，模块可解析。

### Task 3: 让动态模型、路由与集合锁定不再晚报错

**Files:**
- Modify: `app/web/static/js/configuration.js:200-490, 1100-1320`
- Modify: `app/web/static/configuration.css`
- Test: `tests/unit/test_configuration_frontend_static.py`

- [ ] **Step 1: 扩展静态契约到动态锁定**

在 Task 1 的测试中加入：

```python
assert "applyProviderRowLocks" in source
assert "applyTaskRouteLocks" in source
assert "setDynamicRowLocked" in source
assert "LLM_PROVIDER_${index}_" in source
assert "TASK_${task.toUpperCase()}_PROVIDER" in source
```

- [ ] **Step 2: 实现全行锁定 helper**

在动态行创建函数之后加入：

```javascript
function setDynamicRowLocked(row, lockedControls) {
  const fullyLocked = lockedControls.length > 0 && lockedControls.every(control => control.disabled);
  if (!fullyLocked || row.dataset.configLocked === 'true') return false;
  row.dataset.configLocked = 'true';
  row.classList.add('config-dynamic-row-locked');
  row.querySelectorAll('[data-remove-row], button').forEach(button => { button.disabled = true; });
  row.prepend(element('p', 'config-dynamic-lock-message', LOCKED_FIELD_MESSAGE));
  return true;
}
```

`lockedControls` 只包括业务编辑控件；“显示 / 复制”秘密值辅助按钮继续遵守既有秘密保护，不得因为锁定而回填秘密值。

- [ ] **Step 3: 映射 Provider 和任务路由**

`applyProviderRowLocks()` 遍历 `.config-provider-row`，以 `index + 1` 生成 `LLM_PROVIDER_${index}_NAME`、`_PROTOCOL`、`_BASE_URL`、`_API_KEY`，并按 `[data-field]` 调用 `lockControl`。`applyTaskRouteLocks()` 从 `task` 计算 `TASK_${task.toUpperCase()}_PROVIDER` 和 `_MODEL`；任一键受管时锁定相应控件及任务名称，最后调用 `setDynamicRowLocked`。

Provider 和任务路由由后端整组替换持久化，因此任一键受管时采用原子集合锁定：整个对应集合只读并从保存 payload 省略，不承诺同组未受管字段仍可编辑；同分区未受管标量字段继续可保存。

在 `renderModalForm` 的 `renderProviders/renderTaskRoutes` 之后、以及“新增服务 / 新增路由”事件后调用这两个函数。

- [ ] **Step 4: 锁定无法逐行映射的集合操作**

为知丘、iFinD、联网 Key 池建立集合键规则。只要其 JSON、旧格式账号键或 Key 池键在快照的受管列表中，禁用集合新增按钮、全部删除按钮与行内编辑控件，并在集合标题后追加一次 `config-collection-lock-message`。消息始终使用 `LOCKED_FIELD_MESSAGE`，不得显示 `ZQ_ACCOUNTS_JSON`、`IFIND_*`、`WEB_SEARCH_API_KEYS`。

- [ ] **Step 5: 为动态说明添加样式并验证**

追加：

```css
.config-dynamic-row-locked { border-color: color-mix(in srgb, var(--border-primary) 82%, transparent); }
.config-dynamic-lock-message, .config-collection-lock-message { grid-column: 1 / -1; margin: 0; color: var(--text-muted); font-size: 12px; }
```

Run: `/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3 -m pytest --noconftest tests/unit/test_configuration_frontend_static.py -v && node --check app/web/static/js/configuration.js && git diff --check`

Expected: 静态测试、JavaScript 解析和差异检查通过。

### Task 4: 复验后端保护、文档和真实交互

**Files:**
- Modify: `tests/unit/test_configuration_service.py`
- Modify: `docs/modules/app_web.md`
- Modify: `docs/CHANGELOG.md`
- Test: `tests/unit/test_configuration_service.py`

- [ ] **Step 1: 用 pytest 断言后端继续拒绝且不泄露运行时值**

在 `test_environment_values_lock_configuration_fields` 顶部加入 `import pytest`，将现有 `try/except/else` 改为：

```python
with pytest.raises(RuntimeError, match="系统环境变量锁定") as exc_info:
    service.update_section("advanced", {"log_level": "ERROR"})
assert "WARNING" not in str(exc_info.value)
assert env_path.read_text(encoding="utf-8") == "LOG_LEVEL=INFO\n"
```

- [ ] **Step 2: 更新文档**

在 `docs/modules/app_web.md` 写明：首页不显示锁定名单；弹窗只显示字段、行或集合级友好说明；API 键名仅作内部判断。`docs/CHANGELOG.md` 的 `[Unreleased]` 记录提示已迁移为上下文说明。

- [ ] **Step 3: 运行自动验证**

Run:

```bash
/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3 -m pytest tests/unit/test_configuration_service.py -v
/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3 -m pytest --noconftest tests/unit/test_configuration_frontend_static.py -v
node --check app/web/static/js/configuration.js
```

Expected: 服务端锁定拒绝、秘密保护、前端静态契约和模块解析全部通过。若本机缺少项目 Python 依赖，只记录阻塞，不安装任何依赖，除非用户明确授权。

- [ ] **Step 4: 在真实本地后端完成浏览器验收**

1. 首页不显示锁定数量、变量名或名单。
2. 受管的高级配置/数据库/搜索字段禁用并有友好说明，邻近字段仍可保存。
3. 全受管 Provider 或账号集合只显示一次行级/集合级说明，并禁用新增、删除与编辑。
4. 通过开发者工具移除 `disabled` 后保存，后端仍返回锁定拒绝，且不泄露秘密值。
5. Tab 焦点跳过禁用控件与删除按钮；读屏可读出锁定说明。

- [ ] **Step 5: 提交实现**

```bash
git add app/web/templates/index.html app/web/static/js/configuration.js app/web/static/configuration.css tests/unit/test_configuration_frontend_static.py tests/unit/test_configuration_service.py docs/modules/app_web.md docs/CHANGELOG.md
git commit -m "feat(config): make environment locks contextual"
```
