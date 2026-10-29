# Research Web Checks pytest 分片调度器

- Task: `ci-pytest-throughput-20261029-9d12fda7-7cce-4e7c-81f5-e99401711eb4`
- Host/task: macOS infrastructure implementation; exact CI performance remains external.
- Base at worktree creation: `master` at `84b5dab8cdd8cb6f84316ecc0631d4fd562a9b10`. The main line later advanced independently; this follow-up was not rebased onto `270644bf1513e65c50859fb2e3baec6ce06ccfef`.
- Architecture review: no product runtime, API, service, dependency, or research topology changed. The verification-workflow source/test inventory and generated reading index were updated; diagram `08-iteration-docs` remains accurate and unchanged.

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"两个原pytest scope在原Research Web Checks Python步骤内部按nodeID分成两个独立worker；保留同一job、runner、timeout、选择、项目门和平台交接，不新增独立执行/验收节点，08迭代验证图仍准确。","diagrams":[]} -->

## Change

The existing Research Web Checks job now routes its two original Python pytest scopes through `scripts/run_ci_pytest_partitions.py`. The scheduler collects the original scope once, writes the ordered node IDs and task-bound deterministic round-robin split, then holds Popen handles for both workers. Each worker independently collects the same original scope and rejects a collection mismatch before running only its assigned IDs. The split balances parameterized cases even when they come from one large module.

Each worker has its own `basetemp`, pytest cache, JUnit report, result JSON, and stdout/stderr log under a private task temporary root. The scheduler registers task and process owner identity (PID, UID, device, inode, argv), validates input paths and root ownership, and fails closed on collection, test, JUnit, worker startup/exit, malformed evidence, and interruption errors. It cross-checks exact worker schema, held PID, UID, root identity, task-bound plan digest, exact executed node IDs, JUnit `rwb_nodeid` properties, phase outcomes, and the final disjoint union. An interrupted run records both worker PIDs, return codes, and successful waits; signals are sent only through the scheduler's held Popen handles and both workers are reaped. Skips remain visible in JUnit. `PYTHONDONTWRITEBYTECODE=1` prevents concurrent bytecode writes.

The original main Python selection was compared to base and remains identical: 144 path/node selections and the original `--confcutdir=tests/research_web -q`. The second original scope remains unchanged and adds only this runner’s contract test. Job, Ubuntu runner, 45-minute timeout, trigger/concurrency behavior, declared dependencies, JavaScript, editorial engine, Bootstrap, and Windows/Linux routing are unchanged.

The scripts module document, agent workflow guide, development map, Actions budget, FinGPT comparison notes, and architecture inventory now record the scheduler contract. The API/reading index HTML was regenerated only to reflect the source/test inventory; no diagram source changed.

An `always()` evidence step stages only the collection/worker log summaries, two sanitized JUnit reports, result summaries, and node ID manifest under `artifacts/research-web-checks/`; the existing upload action reference is used with three-day retention and a 100 MiB per-run cap. This is test-selection coverage evidence, not Python code coverage.

## Artifact boundary SPEC/QUALITY follow-up

The QUALITY review identified that the previous workflow's `-f` check and `cp` followed a test-controlled symlink. This was reproduced at `logs/ci-throughput/spec-fix-20261029/baseline-result.json`: `/bin/cp` exited 0 and copied the external `EXTERNAL_SENTINEL` target through `worker-0/pytest.log`; the reproducer receipt records owner PID/UID, root device/inode, argv, and runner/workflow SHA-256 values before and after.

The workflow now delegates staging to `scripts/stage_ci_pytest_evidence.py`. It opens the fixed task roots and allowlisted source files through owner-checked directory FDs with `O_NOFOLLOW`, rejects hardlinks/non-regular files and source/parent identity changes, then writes a new exact artifact directory. It reconstructs sanitized JUnit and status/nodeID logs instead of uploading raw stdout, traceback bodies, environment, or JUnit `system-out` content. `actions/upload-artifact@v4` receives only `artifacts/research-web-checks` after successful staging; no wildcard copy chain remains.

Raw public fixture logs and failure bodies are treated as potentially sensitive because tests can include business-like content, credentials, or local runner details. They remain available only in the task's local validation evidence; the workflow artifact contains fixed-schema summaries and allowlisted node IDs, with no raw worker stdout/stderr or failure body.

The focused staging suite passed **6/6** in [artifact-staging-final-2](../../logs/ci-throughput/spec-fix-20261029/artifact-staging-final-2/receipt.json), with stdout, stderr, JUnit, actual argv/PIDs, owner/device/inode and source-before/after hashes bound to the helper/test/workflow SHA values below. Fixtures cover normal evidence, a symlink to an external sentinel, a hardlink to an external sentinel, a symlink task root, a CLI nonzero failure, and a real replacement of the `worker-0` parent directory during open. The normal fixture includes business-body and token-like canaries in raw logs/JUnit output and asserts neither appears in staged files. Earlier `artifact-staging-01` through `artifact-staging-13` logs retain intermediate helper/test-harness failures; only this source-matching receipt is counted as GREEN.

The final Python QUALITY follow-up found that a forged `status=passed` result could still contain a failed phase or JUnit failure. Both cases were reproduced as RED in [phase-junit-red-final](../../logs/ci-throughput/spec-fix-20261029/phase-junit-red-final/receipt.json), where the source-bound tests failed because the staging helper did not reject the inconsistent summaries. The helper now validates exact per-node phase schema/order, requires passed phases for a PASS summary, matches skip state between pytest phases and JUnit, and rejects JUnit failure/error for passed workers. The xfail fixture remains a skipped case in the sanitized JUnit. The complete updated staging suite passed **9/9** in [phase-junit-green](../../logs/ci-throughput/spec-fix-20261029/phase-junit-green/receipt.json), with current helper/test/workflow and unchanged scheduler source hashes, raw stdout/stderr/JUnit, argv/PID/UID/device/inode, and before/after source fingerprints. `phase-junit-red-final` binds the same test SHA but the prior helper SHA; `phase-junit-green` binds the final helper SHA.

## First hosted execution failure and diagnostic follow-up

The first hosted Research Web Checks run for candidate `4edbcf8b432f368424e80fc2f04da355b1d2ab2d` collected 7,381 node IDs, then both workers exited 1 before executing tests or writing nonempty JUnit reports. The worker error text was omitted from the artifact. A private, exact-version reproduction showed the cause: `test_model_provider_upgrade.py::test_target_manifest_preserves_old_lock_except_authorized_v5_combination` expands `upgrade.ASSET_MODES`, a `frozenset`, directly in `@pytest.mark.parametrize`. Independent pytest processes collected the same 23 node IDs in different orders. Across the full original scope, both workers collected the same 7,381-ID set as the parent, but each had 21 order mismatches, all within that one test at positions 6718–6739. The worker's strict ordered collection guard stopped execution.

A 10-case real-entrypoint fixture with an unordered set reproduced the original failure shape: both workers aborted during collection, executed zero tests and produced no JUnit cases. `pytest.main()` returned the collection exit, then `_worker_result` rejected the zero-case JUnit report and its existing fallback recorded exit 1 with a `PartitionError`. The source fix sorts `upgrade.ASSET_MODES` for that test. It preserves all 23 cases and leaves the exact worker collection guard unchanged.

The private reproduction used Python 3.12.13, pytest 9.2.0 and pluggy 1.7.0; CI used Python 3.12.15 with the same pytest/pluggy versions. Exact wheel SHAs, PyPI URL, private install process and module `__file__` checks are in `logs/ci-throughput/pytest92-pluggy17-87798093d4ee49cabe2e9721321fbeef/evidence/`. Three independently seeded collect-only runs were RED before the fix (23 IDs each; identical sets, different orders) and GREEN afterward (same 23 IDs, identical order, zero test bodies). After sorting the original parametrization, the full 7,381-ID, 144-path collection was GREEN in the parent and both real worker-plugin collect-only processes; both workers matched the parent order exactly and executed zero test bodies. The 23 test bodies passed on pytest 9.2.0 and on cached pytest 9.1.1 in batches of 20 and 3. The 41 partition/staging helper tests also passed on both versions in batches of 20, 11 and 10. No full hosted CI was rerun.

The generated Python source index was regenerated to include the new taxonomy helpers; its `--check` gate is part of the local post-change closure.

The taxonomy regression RED was observed on the existing real-worker failure fixture (`KeyError: failureTaxonomy`) and on staging (`worker-0 result schema is invalid`). After the schema-v3 and ordering fix, all 41 helper cases passed under both pytest versions; the targeted 23 profile cases passed under both versions. Ruff, Black, isort, mypy for both scripts and tests, documentation governance, Python index verification, Project Constraints over the complete local changed set, and documentation sync passed. The local results do not replace a new hosted run; none was triggered.

## Verification

- RED: the first end-to-end fixture run exposed an unsupported `--cache-dir` option; the pytest cache is now set with `-o cache_dir=...`. The next run exposed that pytest creates `basetemp` lazily; worker-owned directories are now initialized explicitly.
- SPEC RED: 11 focused cases failed before the aggregation repair: same-count JUnit with an unexpected nodeID and forged result records with missing/wrong schema, worker index, PID, plan digest, actual node IDs, or JUnit.
- GREEN: `tests/unit/test_ci_pytest_partitions.py` — 30 cases passed in two 15-case rounds using the fixed Python 3.12.13 environment and the five existing pytest cache roots. Raw output, JUnit and PID/UID/device/inode/source-hash receipts are in [round A](../../logs/ci-throughput/spec-fix-20261029/pytest-partitions-a/receipt.json) and [round B](../../logs/ci-throughput/spec-fix-20261029/pytest-partitions-b/receipt.json). The cases cover malformed result rejection, exact JUnit nodeID mapping, balanced splits, root ownership, isolated outputs, visible skip, setup/call/teardown outcomes, collection/test failure, exact final union, and two real worker PIDs reaped after SIGTERM. Fixture projects were private to pytest’s temporary root and used `--confcutdir=tests`.
- The real interruption fixture observed both scheduler-held worker Popen PIDs in the final `workerProcesses` summary, with nonzero signal exits and `waited=true`; the test matches those PIDs to the registered owner files.
- `node --test tests/javascript/actions_quota_governance.test.mjs` — 19 passed after adding the staging path/security contract; captured at [actions-quota-final-evidence](../../logs/ci-throughput/spec-fix-20261029/actions-quota-final-evidence/receipt.json).
- `node --test tests/javascript/documentation_governance.test.mjs tests/javascript/repository_cross_platform_contract.test.mjs` — 11 passed; captured at [docs-contracts-final-evidence](../../logs/ci-throughput/spec-fix-20261029/docs-contracts-final-evidence/receipt.json).
- `node --test tests/javascript/incremental_validation_skill.test.mjs tests/javascript/verification_platform_task_entry.test.mjs tests/javascript/verification_delivery_summary.test.mjs` — 20 passed; captured at [verification-contracts-final-evidence](../../logs/ci-throughput/spec-fix-20261029/verification-contracts-final-evidence/receipt.json).
- `node scripts/check_documentation_governance.mjs --project .` — PASS; 930 files checked, zero violations.
- `node scripts/build_research_web_api_atlas.mjs` and `--check` — PASS; 411 declarations, 408 unique operations, 15 categories. The generated reading index includes the current verification workflow inventory.
- `node scripts/check_research_architecture.mjs --project . --base 84b5dab8cdd8cb6f84316ecc0631d4fd562a9b10` — PASS; zero violations, diagram remains unchanged.
- `python scripts/check_doc_sync.py --project . --base 84b5dab8cdd8cb6f84316ecc0631d4fd562a9b10` — PASS; documentation ownership, generated index, and architecture synchronization pass.
- Project Constraints local changed-file review — PASS; zero violations. Final source-bound stdout, stderr, argv, PID/UID/root identity and receipts are under `logs/ci-throughput/spec-fix-20261029/` (`project-constraints-final-evidence`, `doc-sync-final-evidence`, `research-architecture-final-evidence`, `documentation-governance-final-evidence`, `python-index-final-evidence`, `atlas-check-final-evidence`, `git-diff-final-evidence`, and `verification-plan-final-evidence`).
- Existing workflow selection compared against base — PASS; 144 original main selections preserved, one unit contract module added.
- `scripts/generate_py_file_index.py` and `--check` — PASS.
- Standard-library syntax, partition-union, exact-order rejection, input-path, and owned-root smoke checks — PASS (7 assertions).
- `git diff --check` — PASS. Ruff, Black, isort, and mypy are not available in the specified existing environment; no packages were installed.

Source identity (uncommitted worktree based on the recorded base above):

- `scripts/run_ci_pytest_partitions.py` SHA-256: `b84a1aa11c8ab44bd8b488f079a4c15c42267c816fb3e67a637f4d7d397c0770`
- `tests/unit/test_ci_pytest_partitions.py` SHA-256: `2ffc192c71770bf5ea5f9bd64786fc837cbaf0f44e467eb57f0799e00e20b5fb`
- `.github/workflows/research-web-checks.yml` SHA-256: `3ccc93b0e8fbbfb3dec7d0c30e38ef9b08a3354f6f46e7d04fc47d7233ad9f02`
- `scripts/stage_ci_pytest_evidence.py` SHA-256: `94818888742a9d16ec6ef9f20450a0e6b283475e91e995b24b8d62c0dceff05a`
- `tests/unit/test_ci_pytest_evidence_staging.py` SHA-256: `7c78be6ca7ba48f3a1212f34aefabd7c39d6e35fa910ceb63c88bada91b7bf0e`
- `tests/javascript/actions_quota_governance.test.mjs` SHA-256: `e3b610fba33e8eca758bb6cfe5b7814a04bcce6a6404838d2014038f2fead7ae`

## Not run / limits

- Full Research Web Checks candidate CI and the other required delivery gates: `NOT_RUN` by the parent task instruction; this worktree is intentionally not committed, pushed, or dispatched.
- New master commit `270644bf1513e65c50859fb2e3baec6ce06ccfef` is not in this worktree; perform normal three-way latest-main integration and review that delta before commit/PR.
- The plan selected L4 validations for larger policy/receipt/architecture/critical-smoke suites. Those were not run because each local test round is capped at 20 cases; they remain required for the normal delivery path.
- The change is not evidence that the current suite will finish within 45 minutes. Exact CI runtime, complete artifact size, and acceptance remain to be measured on the first normally authorized candidate CI. PR245 repairAttempts and its existing history were not changed.
- No pytest-cov/code-coverage measurement was added because it was not previously collected and would add runtime overhead.
