# Local gate evidence and external handoff

Actual Docker execution logs are private under `~/.local/share/rwb-docker/logs/g01/` with SHA256SUMS.

| Gate | Actual command/result | Local raw log |
| --- | --- | --- |
| research-web-docker-contract | Node combined selected closure, 127 PASS, 2.380694417s | rwb-g01-node-closed.log |
| research-web-architecture | Same combined Node closure PASS, plus independent checker 0 violations | rwb-g01-node-closed.log; rwb-g01-architecture-final.log |
| research-web-verification-full | Policy-selected four Node modules in combined closure PASS | rwb-g01-node-closed.log |
| research-web-container-runtime | Policy-selected supervisor/launch modules in combined Python closure, 949 PASS, 74.23s | rwb-g01-required-python-final.log |
| research-web-installation | setup_web in that actual Python closure PASS | rwb-g01-required-python-final.log |
| research-web-critical-smoke | protocol in that actual Python closure PASS | rwb-g01-required-python-final.log |
| project-constraints-local | All changed files, 0 violations | rwb-g01-constraints-pass.log |
| documentation-governance | 596 files / 0 violations; doc-sync independently passed | rwb-g01-doc-governance.log; rwb-g01-doc-sync-final.log |
| python-file-index | Actual generate_py_file_index.py --check PASS | rwb-g01-py-index.log |

Combined durations are execution durations shared by the covered gate IDs, not summed per-gate timings.
Final new manager tests 17 PASS, actual final arm64 image build, candidate health/stop/up/replace,
dev rebuild/retirement/reactivation, private-port/resources and data/source preservation are separate
current-session evidence in HANDOFF.md. No historical result or synthetic provider response proves them.

External `project-constraints`, `research-web-checks`, `research-web-docker`, `research-web-bootstrap`
are NOT_RUN for this unpublished candidate. Mac CI requires independent user publication authorization.
Linux Docker and Windows/Linux native product CI are device-owned handoffs; Mac does not dispatch them.
Current whole plan remains BLOCKED, mergeReady=false, releaseReady=false. No production migration,
paid supplier call, invited-user authentication, strict Linux research sandbox or public ingress was run.
