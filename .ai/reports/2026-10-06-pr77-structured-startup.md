# PR77 structured startup diagnostics

Status: local diagnostics verified; Docker root cause remains unresolved.

Remote head 27d1d0e2bfa4025c67b8216acc6d6daec10c923e, base d17459edeff5696d2a2641c4072c2d08e9ae84d0. Merge a64195c6a677e0b33da74c9a0a5a5a597c74a333 is from PR API, not independently extracted from checkout. Constraints 37357018654, Web Checks 37357018756 and macOS Bootstrap 37357019151 PASS. Docker 37357018909: amd64 build/import PASS, initial_start exit 1; arm64 CANCELLED. Safe artifact reports supervisor_failed=1; other selected counters zero within the last 200 container lines. Absence from that tail does not establish absence from the complete startup.

The new diagnostic retains only fixed stage/class and bounded errno/child return codes. Before logging setup it uses the same safe payload through the project logger; CI accepts console and JSON event forms. Unknown fields/classes/stages are omitted. No exception text, paths, commands, environment or child output is exported. Existing exception handling, failure exit, signal cleanup, health budgets, nonroot rules and matrix remain unchanged. The user manually applied the protected workflow patch.

RED scanner regression lacked startup_failures. After applying the patch Docker/Actions tests PASS 25. Full supervisor regression PASS 71 in 19.52 seconds, using approved loopback fixture execution and memory keyring. The sandbox-only attempt failed because socket.bind is forbidden: 28 failures,43 passes; this is retained separately and is not product evidence.

Old evidence reuse is limited to unchanged source/test/dependency/platform inputs, with source comparison against 27d1d0e2 recorded separately. Changed supervisor and scanner receive fresh module evidence. Historical reports and receipts are not rewritten.

Fresh full local JavaScript closure: 194 PASS in 5.494491333 seconds. Container supervisor + runtime launch: 127 PASS in 25.10 seconds. Complete 124-path constraints, documentation governance, managed runtime hashes and Python index PASS. The sets ledger verifies unchanged source bytes against 27d1d0e2; receipt preserves prior durations for reused checks. Style tools remain NOT_RUN (not installed).

Pending: local combination update and remote Docker run for this exact revision. Windows/real-machine/Docker Desktop gates remain unverified; mergeReady=false, releaseReady=false. No push, rerun, dispatch or merge executed.

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"Only fixed failure diagnostics change in the existing supervisor; runtime topology, ports, health and cleanup remain unchanged.","diagrams":[]} -->
<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"Documents controlled startup failure fields and incomplete remote evidence; no diagram topology change.","diagrams":[]} -->

Read-only review found a real Compose-format defect: service prefixes make post-logging JSON events unparseable. New shell-executed collector regression is RED before adding --no-log-prefix. The user applied the one-line --no-log-prefix correction; the shell-executed collector regression now passes as part of the refreshed 194-test closure. This removes the Compose prefix only and does not expand uploaded log content. The initial RED result is retained; validation_failure replanning remains at L4.
