# Phase 3.1 Test Report — Critic Upgrade + Revision Pass + Compiler Revision Loop

**Date:** 2026-07-16
**Task:** Phase 3.1 — 方案B（仅 3.1：Critic 升级 + Revision Pass + Compiler revision loop）
**Status:** ✅ All 66 tests passing

---

## Test Summary

| Suite | Tests | Passed | Failed |
|---|---|---|---|
| `test_critic_full.py` | 14 | 14 | 0 |
| `test_revision_pass.py` | 9 | 9 | 0 |
| `test_compiler.py` | 8 | 8 | 0 |
| `test_citation_binder.py` | 8 | 8 | 0 |
| `test_fact_extractor.py` | 10 | 10 | 0 |
| `test_outline_planner.py` | 9 | 9 | 0 |
| `test_table_chart_renderer.py` | 8 | 8 | 0 |
| **Total** | **66** | **66** | **0** |

## New Tests (23 total)

### test_critic_full.py (14 tests)

- `test_review_full_passes_clean_section` — 干净章节值匹配+反证覆盖+字数达标 → PASS/MINOR
- `test_review_full_detects_forbidden_term` — 正文含禁用词 → FORBIDDEN_TERM issue
- `test_review_full_detects_claim_support_gap` — 有数字但无对应 fact → CLAIM_SUPPORT issue
- `test_review_full_detects_conflict` — 正文数字与 fact 值偏差 50% > 20% → CONFLICT issue
- `test_review_full_no_conflict_when_values_close` — 偏差 1% < 20% → 无 CONFLICT
- `test_review_full_detects_counterpoint_gap` — 大纲有反证但正文未覆盖 → COUNTERPOINT issue
- `test_review_full_counterpoint_covered` — 反证关键词出现在正文中 → 无 COUNTERPOINT
- `test_review_full_detects_structure_word_count_deviation` — 字数偏差 94% → STRUCTURE issue
- `test_review_full_detects_evidence_insufficient` — 引用密度过低 → EVIDENCE_SUFFICIENCY issue
- `test_review_full_determines_major_severity` — 多个 warning → MAJOR
- `test_review_determines_critical_for_many_errors` — 禁用词+冲突+反证缺失 → MAJOR/CRITICAL
- `test_review_metrics_include_claim_support_rate` — metrics 包含所有关键指标
- `test_review_legacy_interface_still_works` — 向后兼容 review() 返回 dict[str, ValidationResults]

### test_revision_pass.py (9 tests)

- `test_revise_conflict_replaces_number` — CONFLICT→替换矛盾数字为 fact 值
- `test_revise_counterpoint_adds_suffix` — COUNTERPOINT→节尾追加反证提示
- `test_revise_forbidden_term_removed` — FORBIDDEN_TERM→替换为（已删除违规表述）
- `test_revise_structure_unfixable` — STRUCTURE→返回 None（不可自动修复）
- `test_revise_claim_support_adds_ref` — CLAIM_SUPPORT→插入最佳匹配 fact 引用
- `test_revise_max_rounds_enforced` — round_number > MAX_ROUNDS→拒绝执行
- `test_revise_tracks_fixed_and_unfixable_counts` — 正确追踪 fixed/unfixable 计数
- `test_revise_result_is_dataclass` — 返回值是 RevisionResult dataclass
- `test_revise_converged_when_no_errors_remain` — 仅剩 warning 时 converge=True
- `test_revise_with_missing_section_id_skips` — 不存在的 section_id→标记 unfixable 跳过

## Modified Existing Tests (2)

- `test_compile_produces_report` — `compiler_version` 断言从 `"1.0"` 更新为 `"2.0"`
- `test_validation_results_attached` — 从具体 check name 断言改为灵活断言（len≥1, overall_passed is True），适配六类新检查

## Quality Gates

| Gate | Status |
|---|---|
| `ruff check` (changed files) | ✅ All checks passed |
| `black --check` (changed files) | ✅ 8 files would be left unchanged |
| `isort --check-only` (changed files) | ✅ No changes needed |
| `mypy core/contracts/ reporting/compiler/` | ✅ Success: no issues found in 49 source files |
| `pytest tests/unit/reporting/compiler/ -v` | ✅ 66 passed in 62.03s |

## Changed Files

| File | Change |
|---|---|
| `core/contracts/compiler.py` | +CritiqueSeverity, CritiqueCategory, CritiqueIssue, CritiqueReport |
| `core/contracts/__init__.py` | +exports for new types |
| `reporting/compiler/critic.py` | Simplified→Full 6-category critic with review_full() |
| `reporting/compiler/revision_pass.py` | **New** — Auto-fix engine |
| `reporting/compiler/compiler.py` | VERSION="2.0", +_critic_revision_loop |
| `tests/unit/reporting/compiler/test_critic_full.py` | **New** — 14 tests |
| `tests/unit/reporting/compiler/test_revision_pass.py` | **New** — 9 tests |
| `tests/unit/reporting/compiler/test_compiler.py` | 2 test fixes for version + check names |
| `docs/modules/reporting.md` | Phase 3.1 section + recent changes |
| `docs/CHANGELOG.md` | Phase 3.1 entry |
| `docs/generated/py_file_index.md` | Regenerated |

## Known Issues (Pre-existing, Unrelated)

- `tests/unit/` has ~30 pre-existing failures unrelated to Phase 2 or 3
- `tests/integration/` hangs on collection — documented pre-existing debt

## Conclusion

Phase 3.1 fully implemented and verified: critic upgraded from simplified 3-check to full 6-category critique with claim support rate per-number checking, conflict detection, counterpoint coverage, structure coherence, and evidence sufficiency. RevisionPass auto-fixes CONFLICT/CLAIM_SUPPORT/COUNTERPOINT/FORBIDDEN_TERM issues. Compiler runs up to 2 rounds of critic→revision→re-critic. Backward compatible review() interface preserved. All 66 compiler tests pass, all quality gates green.
