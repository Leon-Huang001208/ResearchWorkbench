# PR77 first-start diagnostics follow-up

Tested remote head: a5009b2e079e387b3cfa8661f8a102052f14ebf9. Base: d17459edeff5696d2a2641c4072c2d08e9ae84d0. Actual Docker checkout merge: abb84a6dd6800eeb916c4ac3354e8316d159ad4f, independently extracted from the job checkout fetch record.

## Observed remote result

Run 37347497115, amd64 job 111889672404: locked image build and final import smoke PASS; lifecycle FAIL. Safe artifact 11361700896 explicitly records phase=initial_start and exit_code=1. Initial up/wait failed in about 21 seconds; later health, fixture, restart and persistence stages did not execute. arm64 was cancelled, not passed. This is separate from the local registry transport failure and historical APT exit 100.

Both repaired PR heads were manually pushed and are mergeable. On PR77 head a5009b2e0, Project Constraints 37347497049, Web Checks 37347497197 and macOS Bootstrap 37347497081 PASS. Web Checks actually executed both Python and JavaScript steps. On PR74 head fa20a3474, Project Constraints 37347464411, Web Checks 37347464399 and macOS Bootstrap 37347464452 PASS, tested merge c80a0d16f2697bb8be4b91e19bfeea6ce4106607. Windows gates remain NOT_RUN. These individual runs do not certify the local two-PR combination or this later diagnostic revision.

## Bounded local experiments

- Existing task13-python-check image has the matching Web lock but no Node/DSH; task13-mount-check lacks the project interpreter. Neither is accepted as the final image.
- Human-reviewed script /private/tmp/rwb-pr77-nonroot-preflight.sh: empty Linux nonroot tmpfs fixture, read-only task source, no network/DSH launch. Private directory preparation and PID1 ownership initialization PASS. The tool invocation was denied by the normal Hook; the user ran the prepared script. This does not prove CI bind-mount or full-runtime behavior.
- Tool-executed narrower fixture: nonroot, cap-drop ALL, no-new-privileges, read-only task source, no network, one directly owned synthetic Python child. PID1 ownership refresh, pidfd signal and reap PASS. No user process, data or credential was used.

## Minimal safe classification

The next change only extends the existing private-log scanner with fixed aggregate error/event categories. It never copies raw lines, exception strings, module names, paths or environment values. Scanning caps, secret-pattern check, health requirements, timeouts, nonroot configuration, matrix and cleanup scope remain unchanged. The user applied the protected workflow patch through the normal Hook path.

Closest regression was RED because old output lacked the module/permission/supervisor categories. After the patch, Docker and Actions contracts PASS 25/25. Adversarial fixture values remain absent from the exported JSON; existing sensitive-line count and all_raw_lines_omitted checks remain. This is diagnostic instrumentation, not a claimed root-cause repair.

Full applicable JavaScript closure: 193 PASS, no skips/failures, 5.574582291 seconds. Documentation governance and Python index PASS. Project Constraints PASS for all 120 full-delivery paths. New receipt validates 18 local PASS, five external NOT_RUN, result=BLOCKED. Unchanged Python/module evidence is explicitly reused from the source-equivalent previous revision; its logs and shared run durations are retained. The committed pre-CI receipts are not rewritten as current remote successes.

## Acceptance and remaining blockers

Full branch delta is replanned from latest master; the fix increment is separately visible relative to a5009b2e0. Reuse applies only to unchanged application/entrypoint/Docker image inputs, dependency locks, Python fixtures and platform. New scanner/test and documentation/constraint inputs receive new checks. Prior committed receipts keep their original conclusions. Source-bound CI observation and scanned artifact are saved in logs/pr74-pr77-repair/ci-20261006/.

Docker first-start root cause remains unresolved. The new diagnostic revision needs its own Docker CI; no rerun, dispatch, automatic merge or push is executed. Windows CI/real-machine, actual Native/Docker data reuse, Docker Desktop mount ACL and style tools remain unverified. mergeReady=false, releaseReady=false.

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"Only fixed diagnostic aggregate categories and scanner regression inputs change; runtime topology, ports, API and application source remain unchanged.","diagrams":[]} -->
<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"Records exact remote failure stage and bounded experiments without changing architecture diagrams or historical receipts.","diagrams":[]} -->
