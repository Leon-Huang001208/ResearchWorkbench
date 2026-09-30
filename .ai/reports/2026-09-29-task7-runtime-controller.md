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

## Task 7 review fix round 1 (2026-09-30)

The review identified three defects in the first commit: conditional mode writes
could race across processes, root Click logging options could skip Docker routing,
and bounded-command failure stopped only the direct process. The follow-up uses
a persistent private mode lock across compare, write, and readback; parses the
two supported root logging options before dispatch while preserving original
Native argv; and owns a POSIX session or Windows Job for timeout/output cleanup.
An explicit higher-ancestor rename-and-restore test proves that the retained
POSIX descriptor reads the original record instead of a temporary decoy.

The focused mode/controller/CLI suite passed **151 tests**. The mode/controller
subset passed **125 tests**; the protocol smoke passed **19 tests**; the static
Docker contract passed **7 tests**; the architecture Node suite passed **62
tests**, and the combined governance/architecture Node suite passed **80 tests**.
The existing setup entrypoint check passed **1 test**. Python compilation,
`sh -n rwb`, and `git diff --check` passed. A launcher smoke with a resolved
temporary HOME returned Native, exit 0, and no home entries. The first smoke
used macOS's `/var` symlink alias and correctly failed closed with
`runtime_mode_unsafe_path`; it did not create any home entry.

The policy planner selected L4. Documentation governance passed, but the
generated Python index is stale and Project Constraints reports the missing
README review receipt plus four unmapped runtime source files from earlier
tasks. Those remain task-series closure work; this Task 7 review fix does not
claim a complete policy receipt or external CI pass. The Windows Job path has
an executable cross-platform descendant regression test, but no native Windows
run was performed here. No Docker image or real service was started or stopped.

## Task 7 review fix round 2 (2026-09-30)

`run_bounded` now handles `KeyboardInterrupt` and other cancellation exceptions
after process launch by terminating the owned POSIX session or Windows Job and
reaping the direct process before re-raising the original exception. The same
cleanup covers an exception during reader-thread startup. If cleanup itself
fails, a path-free error code is logged and attached as an exception note;
timeout and output-limit failures retain their stable codes.

A real POSIX SIGINT regression was RED before the fix: the direct command still
held its listening port after the runner exited. A second RED test found no
cleanup-failure note. Both were GREEN after the fix. The SIGINT test also proves
the direct process was reaped, the descendant's port was released, and an
unrelated process survived. A separate injected cleanup failure retained the
timeout error code and exposed the cleanup failure. The full mode/controller/CLI
suite passed **154 tests**. Python compilation and `git diff --check` passed. The policy planner
still selects L4; its stale index, README receipt, architecture mappings and
unrun external gates remain open at the task-series boundary.
