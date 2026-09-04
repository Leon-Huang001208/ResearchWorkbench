# 报告占位符显式类型优先 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使报告模板占位符在用户或已保存配置明确提供 `type` 时优先使用该类型，而不会被保留的段落 `mode` 重置为 `paragraph`。

**Architecture:** `getCanonicalPlaceholderType()` 只规范化明确传入的类型值；当且仅当 type 为空时才从历史段落 `mode` 回退为 `paragraph`。所有同时混合“显式 type”和“名称推断”的调用点改为两阶段解析：先规范化 mapping 的 type/mode，再在无结果时调用 `inferPlaceholderType()`，保持历史仅含 `mode` 的配置行为不变。

**Tech Stack:** 原生 ES module JavaScript、pytest 静态前端回归测试、FastAPI 本地服务器、Playwright MCP。

---

## 文件结构

- 修改 `app/web/static/js/templates.js`
  - 负责报告模板工作台的类型归一化、编辑草稿、生成预检和 YAML 输出。
  - 把解析优先级固定为：显式 `type` > 历史 paragraph `mode` > 名称推断。
- 修改 `tests/unit/test_report_template_workbench_frontend.py`
  - 负责模板工作台 JavaScript 的静态回归保护。
  - 锁定显式类型优先与历史 `mode` fallback 的源码结构。
- 修改 `docs/modules/app_web.md`
  - 记录模板工作台的占位符类型优先级约定。
- 修改 `docs/CHANGELOG.md`
  - 记录修复的用户可见行为。
- 新建/更新 `.ai/reports/test_report_rwb_auto_011_placeholder_type_priority.md`
  - 记录命令、浏览器复现与最终验证结果。
- 新建/更新 `.ai/progress/progress_rwb_auto_011_placeholder_type_priority.md` 和 `.ai/progress/progress.md`
  - 记录本任务的实施、验证和风险。
- 新建/更新 `.ai/tasks/task_rwb_auto_011_placeholder_type_priority.json`
  - 仅在全部必需门禁通过后标记为 `done`；保留任务描述。

### Task 1: 写入失败回归测试

**Files:**
- Modify: `tests/unit/test_report_template_workbench_frontend.py:566-579`

- [ ] **Step 1: 在段落类型测试之后添加显式类型优先断言**

```python
def test_explicit_placeholder_type_precedes_legacy_paragraph_mode():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    canonical_type_start = source.index("function getCanonicalPlaceholderType(type = '', mapping = {}) {")
    canonical_type_end = source.index("\n}\n\nfunction isParagraphMode", canonical_type_start)
    canonical_type = source[canonical_type_start:canonical_type_end]

    assert "if (normalized) return normalized;" in canonical_type
    assert canonical_type.index("if (normalized) return normalized;") < canonical_type.index(
        "if (mapping?.mode && isParagraphMode(mapping.mode)) return 'paragraph';"
    )
    assert "getCanonicalPlaceholderType(mapping.type, mapping)\n        || inferPlaceholderType(placeholderName)" in source
    assert "getCanonicalPlaceholderType(draft.type, draft) || inferPlaceholderType(name)" in source
```

- [ ] **Step 2: 运行测试并确认在修复前失败**

Run:

```bash
python -m pytest tests/unit/test_report_template_workbench_frontend.py::test_explicit_placeholder_type_precedes_legacy_paragraph_mode -v
```

Expected: FAIL，因为当前 helper 在 `mode` 判定前不会返回常规显式类型，且调用点仍使用 `mapping.type || inferPlaceholderType(...)`。

- [ ] **Step 3: 确认测试仅覆盖行为契约而非无关格式**

确认新测试：

- 同时断言 helper 内的优先级；
- 断言编辑/保存路径使用两阶段解析；
- 不断言空白、缩进或无关 UI 文案。

### Task 2: 实现两阶段类型解析

**Files:**
- Modify: `app/web/static/js/templates.js:2565,2585,2742-2749,3498,3862,5668,6486,7031`

- [ ] **Step 1: 修改 canonical helper，使显式类型优先于 mode**

将 helper 主体更新为：

```js
function getCanonicalPlaceholderType(type = '', mapping = {}) {
    const normalized = String(type || '').trim();
    if (['prompt', 'ai_text', 'composite_market_review'].includes(normalized)) return 'paragraph';
    if (['report_period', 'excel_cell', 'excel_range'].includes(normalized)) return 'field';
    if (normalized === 'config_text') return 'static_text';
    if (normalized === 'excel_chart') return 'chart';
    if (normalized) return normalized;
    if (mapping?.mode && isParagraphMode(mapping.mode)) return 'paragraph';
    return '';
}
```

- [ ] **Step 2: 把来源摘要与配置状态改为两阶段解析**

在各自的 `placeholderName` 上下文中，将：

```js
getCanonicalPlaceholderType(mapping.type || inferPlaceholderType(placeholderName), mapping)
```

替换为：

```js
getCanonicalPlaceholderType(mapping.type, mapping)
    || inferPlaceholderType(placeholderName)
```

这保留了“没有 type、有有效 mode”的历史 mapping 作为 paragraph 的行为。

- [ ] **Step 3: 把草稿构建、编辑器渲染和保存前归一化改为两阶段解析**

对 `stored`/`mapping`/`draft` 中的每个原有模式：

```js
getCanonicalPlaceholderType(<mapping>.type || inferPlaceholderType(<name>), <mapping>)
```

替换为：

```js
getCanonicalPlaceholderType(<mapping>.type, <mapping>)
    || inferPlaceholderType(<name>)
```

必须覆盖以下逻辑位置：

- `buildDraftPlaceholderMappings()`；
- `renderSelectedPlaceholderDetail()`；
- `collectSelectedPlaceholderDraft()` 的最终 `draft.type` 归一化；
- `getPlaceholderReadinessIssue()`；
- `buildPlaceholderYamlEntry()`。

保留 `getCanonicalPlaceholderType(value, draft)` 这类用户输入路径不变，因为 `value` 本身就是明确选择的类型。

- [ ] **Step 4: 运行新增回归测试并确认通过**

Run:

```bash
python -m pytest tests/unit/test_report_template_workbench_frontend.py::test_explicit_placeholder_type_precedes_legacy_paragraph_mode -v
```

Expected: PASS。

- [ ] **Step 5: 运行模板工作台全部静态回归测试**

Run:

```bash
python -m pytest tests/unit/test_report_template_workbench_frontend.py -v
```

Expected: PASS。

### Task 3: 同步文档与任务审计记录

**Files:**
- Modify: `docs/modules/app_web.md:42-46`
- Modify: `docs/CHANGELOG.md`
- Create or Modify: `.ai/reports/test_report_rwb_auto_011_placeholder_type_priority.md`
- Create or Modify: `.ai/progress/progress_rwb_auto_011_placeholder_type_priority.md`
- Modify: `.ai/progress/progress.md`
- Create or Modify: `.ai/tasks/task_rwb_auto_011_placeholder_type_priority.json`

- [ ] **Step 1: 更新 app/web 模块文档**

在模板工作台的占位符映射描述后添加：

```markdown
- 占位符输出形态按“显式 `type` > 历史段落 `mode` > 名称推断”解析；切换到短字段、固定文案、表格或图表时保留原段落配置，以便后续切回正文段落恢复设置。
```

- [ ] **Step 2: 更新 CHANGELOG 的 Unreleased / Fixed**

添加：

```markdown
- **报告模板工作台**：修复已有段落写作模式的占位符切换为短字段、固定文案、表格或图表后被重新还原为正文段落的问题。
```

- [ ] **Step 3: 创建测试报告**

使用以下结构记录实际结果，不能预填为通过：

```markdown
# Test Report: rwb-auto-011-placeholder-type-priority

Task ID: rwb-auto-011-placeholder-type-priority
Changed source files:
Changed test files:
Changed docs:
Commands run:
Command results:
Browser verification:
Skipped tests:
Reason for skipped tests:
Remaining risk:
Final test decision:
```

- [ ] **Step 4: 更新进度和任务状态前先记录未完成状态**

进度文件需记录当前修改、已运行命令及剩余完整门禁。任务 JSON 在此时保持 `doing`，不删除或改写任务描述。

### Task 4: 浏览器验收与完整门禁

**Files:**
- Modify: `.ai/reports/test_report_rwb_auto_011_placeholder_type_priority.md`
- Modify: `.ai/progress/progress_rwb_auto_011_placeholder_type_priority.md`
- Modify: `.ai/progress/progress.md`
- Modify: `.ai/tasks/task_rwb_auto_011_placeholder_type_priority.json`
- Generated: `docs/generated/py_file_index.md`（仅生成器实际产生变更时纳入）

- [ ] **Step 1: 启动本地服务并进入报告模板配置页**

Run:

```bash
python3 -m uvicorn app.api.main:app --host 127.0.0.1 --port 8765
```

用 Playwright MCP：

1. 打开 `http://127.0.0.1:8765`；
2. 进入“报告生产”；
3. 选择“华安ETF周报”；
4. 切换到“配置”；
5. 打开“A股市场回顾”的基础配置编辑弹窗。

- [ ] **Step 2: 验证原始复现路径已修复**

在弹窗中：

1. 点击“短字段”；
2. 接受确认框；
3. 断言 `.placeholder-purpose-card.selected` 的 `data-placeholder-output-shape-option` 是 `field`；
4. 断言 `[data-placeholder-field="type"]` 的值是 `field`；
5. 关闭并重新打开配置弹窗；
6. 再次断言选中卡片与隐藏字段均为 `field`；
7. 截图保存到 `output/playwright/report-placeholder-type-field.png`。

不要点击最终“保存配置”，以免在诊断/验收中未经额外确认写入用户的报告项目配置。

- [ ] **Step 3: 运行项目规定的完成门禁**

Run:

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

Expected: 每条命令都成功退出。若任一命令失败，修复可安全修复的问题并重跑；若无法安全修复，按 blocking policy 写入阻塞报告且不得把任务标为完成。

- [ ] **Step 4: 完成审计记录并更新任务状态**

只有全部门禁成功后：

1. 将实际命令结果、截图路径和风险写入测试报告；
2. 将完整验证结果写入两个进度文件；
3. 把任务 JSON 状态由 `doing` 更新为 `done`；
4. 保留任务描述和所有现有条目。

- [ ] **Step 5: 请求代码审查**

使用 `code-reviewer` 审查修改的 JavaScript、测试和文档，重点检查：

- 显式 type、legacy type 和 mode 的优先级；
- 无 type 历史 mapping 的兼容性；
- 是否遗漏 YAML/保存路径；
- 是否有超出修复范围的改动。

若发现 CRITICAL 或 HIGH 问题，修复后重跑相关测试及受影响门禁。

- [ ] **Step 6: 提交（仅在用户要求提交时执行）**

若用户明确要求提交：

```bash
git add app/web/static/js/templates.js tests/unit/test_report_template_workbench_frontend.py docs/modules/app_web.md docs/CHANGELOG.md docs/superpowers/specs/2026-07-24-report-placeholder-explicit-type-priority-design.md docs/superpowers/plans/2026-07-24-report-placeholder-explicit-type-priority.md .ai/reports/test_report_rwb_auto_011_placeholder_type_priority.md .ai/progress/progress_rwb_auto_011_placeholder_type_priority.md .ai/progress/progress.md .ai/tasks/task_rwb_auto_011_placeholder_type_priority.json
git commit -m "fix: preserve explicit report placeholder types"
```

不要 push。

## Plan self-review

- **Spec coverage:** Task 2 实现显式 `type` 优先、保留 `mode`、保持无 type 历史兼容和 YAML 保存路径；Task 1 写入回归测试；Task 3 同步文档/审计；Task 4 覆盖浏览器验收与必需门禁。
- **Placeholder scan:** 无 TBD/TODO、无“类似上一步”等不完整指令；每个代码变更和命令均给出具体内容。
- **Type consistency:** 使用的字段名与现有实现一致：`type`、`mode`、`placeholderMappingDrafts`、`inferPlaceholderType()`、`getCanonicalPlaceholderType()`。
