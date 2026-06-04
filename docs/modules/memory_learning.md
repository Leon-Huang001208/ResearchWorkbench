# Module: memory_learning

## Responsibility

`memory_learning` provides outcome memory, failure memory, learning journal, and feedback loop capabilities.

---

## Design Rules

- Outcomes should be traceable
- Failures should be categorized
- Learning should be actionable
- Feedback should be integrated
- Add or update tests when memory behavior changes

---

## Files

### `memory_learning/*.py`

Purpose:
- Outcome storage and retrieval
- Failure classification
- Learning journal management
- Similarity-based retrieval
- Feedback integration

Update this section when:
- Memory schema changes
- Failure classification changes
- Outcome feedback behavior changes
- Learning loop changes

---

## Required Tests

- Memory write/read tests
- Similarity retrieval tests
- Failure classification tests
- Weekly review tests

---

## Required Documentation Updates

When files in this module change, check:
- `docs/modules/memory_learning.md`
- `docs/ARCHITECTURE.md`
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`
- `docs/generated/py_file_index.md`

---

## Key Files

| 文件 | 说明 |
|------|------|
| `memory_learning/pattern_learner.py` | 模式学习器：从历史结果中提取可复用模式 |
| `memory_learning/journal.py` | 学习日志管理

---

## Recent Changes

- 2026-06-04: 收敛 `PatternLearner` 推荐结果和波动率计算的类型推断，补齐字典返回值与数值计算的显式类型，行为保持不变。
