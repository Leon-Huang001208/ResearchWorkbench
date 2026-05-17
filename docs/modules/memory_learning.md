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