# Task 7 runtime controller and bootstrap

Implemented stdlib routing for `rwb runtime` and Docker-mode `rwb web`, with exact
Native venv delegation, bounded Docker commands, stable installation labels and
ownership-checked lifecycle operations. Switching preflights the target, checks
both runtime owners, requires explicit stopping of the current runtime, verifies
both ports and stopped state, then conditionally writes the mode atomically.
It never starts the selected target. Missing mode reports Native without writes.

Source/test mapping: `docker_runtime.py` and `bootstrap.py` are covered by
`test_docker_runtime.py`; `runtime_mode.py` by `test_runtime_mode.py`; package entry
and both launchers by `test_cli_lazy.py` plus the existing setup entrypoint check.
The interrupted controller/test residue was inspected and preserved; this task
adds the missing bootstrap/launchers and repairs reproduced ownership, error-code,
exit-code, mode concurrency and legacy delegation defects.

Validation: focused runtime/mode/CLI tests 123 passed; existing cross-platform
setup entrypoint static check 1 passed. Python compilation, shell syntax and
`git diff --check` passed. Temporary-HOME launcher smoke reported Native with no
filesystem write. Actual read-only Docker availability and Compose config passed;
image preflight returned `docker_build_not_ready`, consistent with the task 6
external download blocker. No image build/start, real service stop, dependency
installation, user-home write, daemon/system change or publication was performed.

The deterministic new ancestor-metadata regression was RED before narrowing
read validation to full immediate-parent metadata plus pinned ancestor node
identities. Existing symlink, replacement and atomic-write tests remain GREEN.
Conditional mode writes reject a changed record instead of overwriting it.

Windows batch execution, real Linux image lifecycle, full clean-install CI and
task-series generated index/architecture/doc/README receipts remain unverified.
Ruff, Black, isort and mypy are unavailable in the existing venv/PATH; none were
installed and no lint/format/type pass is claimed. Product documentation and CI
were explicitly reserved for later tasks. Full evidence and RED/GREEN chronology
are in `.superpowers/sdd/2026-09-29-native-docker-dual-runtime/task-7-report.md`.

<!-- architecture-review {"group":"runtime","structure":"changed","reason":"Adds the approved stdlib host bootstrap and Docker ownership controller while preserving Native execution and the single DSH engine; documentation, architecture inventory and diagram synchronization belong to the task-series closeout.","diagrams":[]} -->
