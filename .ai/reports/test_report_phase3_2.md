# Phase 3.2 Test Report — Citation Verifier + Numeric Checker

**日期**: 2026-07-16  
**任务**: 第三阶段 3.2 — 引用验证器 + 数字检查器  
**状态**: ✅ 全部通过

---

## 修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `core/contracts/compiler.py` | 修改 | +6 `CritiqueCategory` 枚举值 |
| `reporting/compiler/citation_verifier.py` | **新建** | CitationVerifier 类（~195 行） |
| `reporting/compiler/numeric_checker.py` | **新建** | NumericChecker 类（~290 行） |
| `reporting/compiler/revision_pass.py` | 修改 | +6 `_fix_*` 方法 |
| `reporting/compiler/compiler.py` | 修改 | Step 8.5 集成双验证器 |
| `tests/unit/reporting/compiler/test_citation_verifier.py` | **新建** | 10 个测试 |
| `tests/unit/reporting/compiler/test_numeric_checker.py` | **新建** | 10 个测试 |
| `docs/modules/reporting.md` | 修改 | Phase 3.2 章节 + Recent Changes |
| `docs/CHANGELOG.md` | 修改 | Phase 3.2 条目 |
| `docs/generated/py_file_index.md` | 修改 | 重新生成 |

---

## 测试结果

### 全量编译器测试: 86 passed, 0 failed ✅

```
tests/unit/reporting/compiler/
  test_citation_verifier.py ........... (10/10) ✅
  test_numeric_checker.py ............ (10/10) ✅
  test_compiler.py .................. (8/8)  ✅
  test_critic_full.py ............... (14/14) ✅
  test_fact_extractor.py ............ (8/8)  ✅
  test_fact_extractor_assertions.py . (7/7)  ✅
  test_outline_planner.py ........... (7/7)  ✅
  test_revision_pass.py ............. (10/10) ✅
  test_table_chart_renderer.py ...... (8/8)  ✅
  test_citation_binder.py ........... (4/4)  ✅
Total: 86/86 ✅
```

### 质量门

| 检查 | 结果 |
|------|------|
| ruff | ✅ Passed |
| black --check | ✅ Passed (7 files unchanged) |
| isort --check-only | ✅ Passed |
| mypy | ✅ Passed (0 issues in 4 source files) |

### Playwright 验证

- 应用正常启动：`http://127.0.0.1:8765` ✅
- 健康检查：`{"status":"ok","app_env":"dev","persistence":{"database_connected":true,"status":"ready"}}` ✅
- 截图：[phase3_2_app_screenshot.png](phase3_2_app_screenshot.png)

---

## 边界问题修复

4 个实现细节 bug 在测试阶段发现并修复：

1. **`_find_sentence_with_citation` 句子定位偏移**  
   - 根因: `sent_start` 初始化为 `idx`（引用标记位置），未找到分句点时句子从标记中间截断  
   - 修复: 初始化为 0，无前置分句点时从文本起始位置截取

2. **`_extract_unit_near_number` 单位子串误匹配**  
   - 根因: 短单位 `"元"` 先于长单位 `"亿元"` 匹配，且 before_text（5 字符窗口）误捕获上一数字的单位  
   - 修复: 按长度降序排列单位列表；优先检查 after_text（紧邻数字之后），before_text 仅作备选

3. **`_extract_period_near_number` 期间取首不取近**  
   - 根因: `pattern.search()` 返回窗口内第一个匹配，而非距离数字最近的匹配  
   - 修复: 遍历 `pattern.finditer()`，计算每个匹配的中点与数字位置的距离，选择最近的

4. **测试中 `test_verify_multiple_sections` 搜索字段错误**  
   - 根因: 断言在 `issue.description` 中搜索 `"f3"`，但未引用 fact ID 出现在 `issue.suggested_fix` 中  
   - 修复: 断言改为同时搜索 `description`（覆盖率关键词）和 `suggested_fix`（fact ID）

---

## 架构说明

- 两个 verifier 均不调用 LLM，全部规则驱动
- 输出 `list[CritiqueIssue]`，复用现有 `CritiqueCategory` 枚举，无缝接入 `CritiqueReport` → `RevisionPass` 流程
- 6 个新 category 中 4 个可自动修复（CITATION_PRECISION/ORPHAN_CITATION/UNIT_MISMATCH/PERIOD_MISMATCH），2 个标记需人工审核（SOURCE_DIVERSITY/FABRICATED_NUMBER）
- 编译器版本保持 2.0（minor extension）

---

## 剩余风险

无。所有测试通过，质量门全部通过，文档已同步。
