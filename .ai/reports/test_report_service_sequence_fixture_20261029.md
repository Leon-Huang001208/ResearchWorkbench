# Isolate the virtual lifecycle sequencing test

macOS Web acceptance; original PR245 task. No product service-manager code changes.

The original test mocked high-level missing probes, spawning, status and browser, but
left low-level listener facts real. On the Mac mini, 3081 had a resident listener and
the parent Seatbelt rejected execution of setuid `/bin/ps` with EPERM. The product
correctly refused `runtime_ownership_unknown`. Original failure, diagnostic and source
baseline receipts remain; no resident was stopped, contacted or reconfigured.

Only this test explicitly opts into a function-scoped virtual listener fixture.
Closed facts exercise the original ordering assertion. Unknown and synthetic
listening/inaccessible facts must trigger the actual refusal gate before any
spawn/browser event, kernel bind or endpoint publication. Bind/publication spies
delegate to the original implementations. Production quiescence, recovery, leases
and endpoint selection are not replaced. Other real busy-port and ownership tests
do not use the fixture.

Root ran all three models: 3 passed in 0.63 seconds. Independent SPEC review reran
3/3 and approved; separate Python quality review approved the exact source hash
`f6d6b6c4c85219895e21a70d82541169f7529ea7dcb44990a70e770a48117786`
after AST/compile and source inspection, and did not claim another pytest run.
Existing original-case external diagnostics are not final candidate gate passes.

The existing CI Python module gains two cases, with two seconds reserved in the
existing step. No dependency, runner, job, timeout, product permission, native
readiness assertion or actual service is changed. Full candidate verification
remains pending. This is unit-model evidence, not real resident or Native evidence.
