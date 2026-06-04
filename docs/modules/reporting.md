# Module: reporting

## Responsibility

`reporting` provides report composition, templates, markdown/Word projections, and research outputs.

---

## Design Rules

- Reports should be reproducible
- Templates should be versioned
- Output formats should be consistent
- Keep generation logic testable
- Add or update tests when reporting logic changes

---

## Files

### `reporting/*.py`

Purpose:
- Report generator implementations
- Template management
- Markdown and Word output
- Report section composition

Update this section when:
- New report types are added
- Templates change
- Output format changes
- Report section composition changes

---

## Required Tests

- Report generation tests
- Template rendering tests
- Output format verification

---

## Required Documentation Updates

When files in this module change, check:
- `docs/modules/reporting.md`
- `docs/REFERENCE.md`
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`
- `docs/generated/py_file_index.md`

---

## Recent Changes

- 2026-06-04: 收敛 reporting composer/projection 的 mypy 历史债务，补齐模板缓存、fact card 列表、Excel worksheet/chart 数据的显式类型，输出格式保持不变。
