# PR77 Runtime child exit diagnosis

Status: local launcher diagnostics verified; root cause remains unresolved. Root cause is unresolved; no new commit/push/rerun/dispatch/merge.

## Exact remote evidence

Head 58aac39f96aed4bb35e4a95392cfe145df9fed5c; base d17459edeff5696d2a2641c4072c2d08e9ae84d0. Tested merge 87a09b49d6ec6cab295a92e987554653d9cdfafd independently extracted from both Web Checks and Docker checkout logs. Constraints 37407251706, Checks 37407251725 and macOS Bootstrap 37407251672 PASS; both Checks contract steps executed. Docker 37407251701 amd64 build/import PASS, lifecycle FAIL; arm64 CANCELLED. Artifact 11388060225 contains initial_start exit1 and exact startup failure stage=runtime_wait,class=RuntimeError,runtime_returncode=1,web_returncode=null. This proves Runtime child exited before Web started; it does not distinguish launcher prepare failure from Node failure after exec. Safe observations are under logs/pr74-pr77-repair/ci-37407251701/.

## Bounded hypotheses and limitations

- Existing task13-python-check, matching Python lock: nonroot10001, read-only task app/core, no network, writable temporary fixture. validate_research_python PASS in 1.156 seconds. This only excludes readiness failure in that fixture; not final CI image equivalence.
- Synthetic staged .git identity (HEAD/objects/refs) returns correct commit through Git rev-parse; no Node/source execution.
- Read-only source inspection shows profile fallback writes to profile home; no concrete immutable-source write defect established.
- Full task image build again failed fetching Dockerfile frontend registry auth, DNS/connection timeout. CI build succeeds, so this is separate transport blockage. No proxy/Docker/global configuration changed.
- prepare fixture command was denied by PreToolUse Hook. Independent fixture prerequisite check shows Git absent; fixture also lacks Node/DSH, so that command was not run manually and is not accepted as reproduction. Do not bypass the Hook or claim full image acceptance.

## Minimal safe next diagnostic

The launcher retains original caught exceptions and SystemExit(1), adds fixed node/prepare/module/Tabbit-package/adapter/config/exec stages and bounded error class/errno, and stops recording exception strings. Seven direct failure injection tests were RED before instrumentation and PASS afterward; all assert exit1 and absence of private fixture exception text. CI must unwrap only the fixed runtime child event, then enforce exact five-field enums and bounded integers; no original message/output is uploaded. Scanner nested-event test was RED before the patch. The user applied it; the full 194-test JavaScript closure now passes in 5.785557958 seconds.

No timeout, nonroot, health, matrix, ownership, persistence or dependency lock relaxation. Windows, real-machine and Docker Desktop acceptance remain unverified. mergeReady=false,releaseReady=false.

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"Adds bounded failure-stage facts to the existing launcher without changing runtime topology or startup semantics.","diagrams":[]} -->
<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"Records exact tested merge, Runtime child failure and separate local transport blockade; no diagram change.","diagrams":[]} -->

Fresh launcher + supervisor closure: 134 PASS in 24.58 seconds. Python file index and git diff --check PASS. Read-only review found no new P1/P2; workflow decoder GREEN regression now passes.
