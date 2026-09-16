# Integration Coordinator Batch 1

## Scope

Implemented the first delivery batch of the approved data-source and local-integration plan:

- versioned five-stage integration status and five outcome buckets;
- atomic, private persistence of safe evidence and per-source auto-probe consent;
- startup and manual probe batches with deduplication, timeout, cancellation and bounded concurrency;
- unified status, batch and consent API while preserving legacy single-probe APIs;
- persisted DataHub probe restoration with configuration-fingerprint invalidation;
- Tabbit saved configuration versus Runtime-applied configuration;
- all 15 brand-neutral DataHub tools registered independently of current Provider availability;
- Settings UI full re-probe action, five-stage source detail and five-bucket summaries.

No dependency was added or installed. Provider expansion, Office authorization automation, file sync and local MCP execution remain later batches and are reported as not delivered where registered.

## Verification

- Targeted Research Web Python regression suite: `194 passed, 1 skipped, 1 warning`.
- Targeted Settings, connection, local-integration and core JavaScript suite: `66 passed`.
- `mypy` passed for the eight Python files changed by this batch. The seven existing
  `DetectionEnvironment` errors at `app/research_web/local_integrations/manager.py:158`
  remain a known baseline outside the new `run_probe()` change; the repository CI mypy
  target does not include this file.
- Ruff, Black and isort checks passed for the 13 relevant Python files.
- Node syntax checks passed for the four changed frontend modules.
- Research Web architecture validation passed with no violations.
- Documentation synchronization validation passed.
- `docs/generated/py_file_index.md` was regenerated and validated.
- Proxy variables were explicitly removed for Python suites that instantiate HTTP
  clients; the host SOCKS proxy references an optional package not declared by this
  project.

## Browser acceptance

The changed UI and API were exercised in a real Chrome session at
`http://127.0.0.1:18088` against the isolated Research Web fixture server. This proves
the browser/API flow, not model execution or vendor Runtime availability.

- The data-source page rendered all 21 registered sources. A real full re-probe batch
  completed with 2 available, 2 requiring user action, 1 system failure and 16 not yet
  delivered. The read-only probes reached CLS and Eastmoney Fund and reported both
  healthy.
- Enabling and disabling Wind auto-probe displayed different confirmation text and
  persisted successfully through the consent API.
- The local-integration full probe completed with 1 available, 3 requiring user action,
  7 system failures and 3 not yet delivered.
- Tabbit simultaneously displayed the saved setting as disabled and the Runtime-applied
  setting as enabled, together with the required-restart warning.
- The browser console contained only successful `200` and `202` request records and no
  script errors.

## Review and residual risk

- Independent security review approved the batch after the same-origin and explicit
  user-action protections were added to write APIs.
- Independent code-quality review approved the batch after the new mypy issue was
  corrected.
- Residual threat: same-origin script execution (for example, an XSS elsewhere in the
  application) can act with the current user's authority.
- Residual threat: another process running as the same local OS user can forge loopback
  HTTP requests. These risks require broader browser hardening or local-process identity
  controls and are not represented as solved by this batch.

The delivery receipt and remote CI result are recorded by the managed publish lifecycle;
they must not be inferred from the local evidence above.
