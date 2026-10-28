# Framework fixture credential isolation

Original PR245 task, macOS Web; no product change or credential operation.

The original framework fixture replaced public keyring functions only inside
`framework_api`. The bounded acceptance runner's unavailable-backend sentinel
observed raw fallback attempts, causing teardown ERROR after 20 test calls passed.
The sentinel blocked the actual OS backend; this was not proof of real Keychain access.

The module now imports the existing function-scoped autouse `isolated_keyring`
fixture from `test_api`, and removes the old manual helper. Host initialization,
pure context cases, factory aliases and public methods share the same per-case
memory vault. Existing backend-denial and teardown checks remain; all product
code and business assertions are unchanged.

Root's complete module run: **22 passed**, one existing warning, **42.19 seconds**.
This execution exceeded the intended maximum of 20 cases per group by two; the
original owner/argv/JUnit and resource admission/floor safeguards are retained,
and it is recorded as 22, not relabelled. Subsequent groups use exact collected IDs.

Independent review approved the fixture repair, ran eight credential safety
controls plus eight pure gold-context cases: **16 passed**, zero skips, zero
real-backend attempts; Ruff and diff checks passed. This is fixture evidence,
not whole-PR, Native, resident or model/provider acceptance.

No new dependency, CI case, step, runner, timeout or public API is introduced.
Original failed epoch and diagnostic counters are retained under
`logs/base-refresh-20261029/python/` and review evidence under
`logs/cdf60b38-verification/framework-fixture-review/`.
