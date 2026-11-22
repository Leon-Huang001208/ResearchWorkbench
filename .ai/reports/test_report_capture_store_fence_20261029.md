# Source publication and shared Store persistence

macOS Web; original PR245 task, genuine master refresh. This is a same-Store
thread-level consistency repair, not proof of HTTP scheduling or full import authorization.

Before the repair, source publication staged file/evidence references before acquiring
the Store save lock. A watchlist writer could persist that whole index, then the source
writer's injected pre-replace failure rolled memory and owned body back while leaving
orphan references on disk. The original diagnostic and both legacy/verified-producer RED
epochs are retained. The verified-producer regression failed at the disk/memory assertion
in 0.35 seconds, with actual stdlib HTTPResponse framing and the production validator.

The existing retention fence now encloses the shared Store RLock, fresh row lookup,
snapshot, staging, save and failed-publication rollback/body cleanup. There is no await
inside it, and watchlist writers do not acquire the retention fence in reverse order.
Logging and failure propagation remain in the existing publication/Store facilities.

Actual results:

- Three Event-controlled cases passed in 0.28 seconds: capture failure, import failure,
  and common success. They use the real persistence primitive and verify index, body,
  evidence proof and memory consistency; no sleep-based scheduling assumption.
- Independent Python review approved this fix only and independently reran all three
  in 0.26 seconds, with Seatbelt network denial and zero credential-backend calls.
- The full three-module source/proof/alias regression closure passed 40 unique cases
  in groups of 15/15/10 after the repair. Detailed receipts are under
  `logs/base-refresh-20261029/python/`.
- Black, isort and Ruff passed on the changed source and new test module, using existing
  cached tools without installation. Initial missing tool-dependency attempts are retained.
- A configured mypy diagnostic reported 17 transitive errors in seven files. A shadow-file
  run against the pre-fix source reported the exact same ordered errors. This is not a
  mypy PASS or a claim that untyped function bodies were checked.
- Before this repair, 212 ordinary API cases passed on the refreshed baseline; they do
  not constitute the final repaired candidate's complete API gate. One production
  sandbox DocCase remains separately pending current-source boundary verification.

The original CI Python step registers the three new cases with a five-second budget;
no dependency, runner, job, timeout, source authorization or production permission is
expanded. Final Router, complete candidate checks, review and same-candidate CI remain
pending; repairAttempts stays three. No model, provider, credential or resident operation
was performed.
