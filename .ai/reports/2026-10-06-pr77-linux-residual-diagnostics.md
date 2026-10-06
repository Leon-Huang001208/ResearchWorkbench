# PR77 remaining Linux startup failure

Status: user applied the fixed-counter patch; local validation complete. Linux and Windows investigation/acceptance are explicitly deferred by the user (先不用考虑Linux，和Windows一样不用考虑). No further platform, registry/network or CI retry work in this iteration.

Remote head e98da8449daa85161e4aecd8b357757f886b1172, latest base9e231b6c3be5279d24cac8d43453fbf9a626cca6, tested merge09bdb8b40b756da36dfbb06852d8f8fed2874d93 independently from Checks checkout. Constraints37414383646, Checks37414383692, macOS Bootstrap37414383613 PASS. Docker37414383667 amd64 image/import PASS but initial_start FAIL; arm64 CANCELLED. Artifact11389813925 contains162 container lines (below200 tail cap), runtime_wait RuntimeError child exit1, no launcher diagnostic, MODULE_NOT_FOUND counters0. Source-bound safe fields live under logs/pr74-pr77-repair/ci-37414383667/.

The selected-production-hoist defect remains independently verified locally: original derived Mac tree fails native helper resolution and Node initialization; repaired same fixture has valid source/inventory, ready DSH listener, no module failures. New Linux CI is not a success and shows a remaining failure. Do not equate the local repair or absent diagnostic with complete Linux proof.

Local full Linux reproduction remains externally blocked by registry auth transport. Existing task13 Python fixture has matching Python lock but no Git/Node/DSH; mount fixture has none of the required programs. No cached tagged Node/Python base images. Current known proxy ports7890/7891 are not listening; public auth.docker.io DNS yielded157.240.12.35 and2a03:2880:f117:83:face:b00c:0:25de while Docker connection times out. No proxy/DNS/Docker/global configuration, secrets or dependencies changed. Registry/network work is now deferred with Linux by user instruction; no unchanged build retry.

Minimal next classifier adds only fixed launch/readiness and whitelisted error-class/code counts. owned_dsh_launch uses exact word boundary so owned_dsh_launch_failed cannot count as success. RED regression covers both launch events and fixture TypeError/native-error values; raw text omission and secret scan remain unchanged. User applied the protected patch. Full local JavaScript closure202 PASS in5.505876166s, including exact success/failure counter separation and omission of private fixture error/native path values. No runtime behavior, timeout, health, matrix, permission or log-upload relaxation.

The residual Linux failure is deferred, not claimed fixed. Windows/real-machine/Docker Desktop remain unverified; mergeReady=false,releaseReady=false. No rerun/dispatch/PR merge.

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"Only finite existing event/error counters change; runtime topology, code, dependency and health contracts unchanged.","diagrams":[]} -->
<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"Records residual Linux failure separately from verified Mac hoist repair and local network blockade; no diagrams change.","diagrams":[]} -->

The deferred platform gates are retained as NOT_RUN/BLOCKED in the mechanical receipt; policy, required gates and historical CI results are not rewritten. macOS Native Bootstrap remains the observed PASS for exact remote head e98da8449 and merge09bdb8b on latest master9e231b6c3; it does not prove Mac Docker Desktop. Current revision changes only fixed scanner counters/tests/reports; application, dependency, installation and macOS workflow inputs are unchanged. No further remote publication is requested because it would trigger platform CI.

Final read-only JavaScript/privacy review found no actionable P1/P2. Fixed counter patch is retained for future resumed diagnostics; current local closeout does not certify deferred Linux/Windows or Mac Docker Desktop.
