# Test Report: <task_id>

## Task

- Task ID:
- Task name:
- Date:
- Branch:

---

## Changed Source Files

- ...

---

## Changed Test Files

- ...

---

## Changed Documentation Files

- ...

---

## Commands Run

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

---

## Results

| Check                 | Result            | Notes |
| --------------------- | ----------------- | ----- |
| ruff                  | pass/fail/not run |       |
| black --check         | pass/fail/not run |       |
| isort --check-only    | pass/fail/not run |       |
| mypy                  | pass/fail/not run |       |
| pytest                | pass/fail/not run |       |
| py file index         | pass/fail/not run |       |
| task completion check | pass/fail/not run |       |
| doc sync check        | pass/fail/not run |       |

---

## UI Verification

Required for UI changes.

- Browser tested: yes/no
- Pages tested:
- Interactions tested:
- Screenshots:
- Notes:

---

## Skipped Checks

If any check was skipped, explain:

- Check:
- Reason:
- Risk:
- Required follow-up:

---

## Final Decision

- [ ] This task is safe to mark as done.
- [ ] This task is blocked and must not be marked as done.