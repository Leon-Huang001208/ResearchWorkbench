# Existing foreign Native ledger authentication

User selected this design on 2026-10-07. This is the remaining macOS Web
dual-runtime lifecycle repair, based on d2a0015c; not a new deployment architecture.

## Reproduced failure and existing evidence

At ee3, public Docker no-start installation and first start succeeded in the
private docker-first-home.KbDe9N HOME. Web selected 57444 and both services were
healthy. The next ordinary start failed runtime_ownership_unknown. First-creation
authority had correctly expired; absent target Native endpoints caused observation
of another product's default 8088/3081 listeners.

The existing stdlib bootstrap_service_facts reader, using current trusted code,
authenticated both normal-host Native PID records as a stable owned pair in a
different canonical product root. Runtime command/signature binds --data and the
overlay to that root; Web's private ledger binds data_root/project/command/signature,
with actual argv/start/listener matching. No process environment, authentication
secret, other-checkout code or new HTTP probe was read/executed by this reader.

## Approved behavior

Recognize a complete authenticated different-root Native pair using the existing
private-ledger/owned-launch trust model. Do not infer foreign ownership merely
from another checkout, PID stability, open ports, Docker health, mode or manifest.
The Web root association is the trusted private ledger, not an independent
environment-root or cryptographic attestation. Same-UID malicious replacement
outside this existing trust model must not be claimed solved.

Candidate discovery is bounded to the operating-system user's standard product
root; it must not use a hard-coded user's path, scan all homes/projects, execute
another checkout, or accept a new user override/allow-unknown option. macOS is the
current host scope. Candidate and target roots must be canonical, distinct and
strictly privately owned; alias/reparse/unsafe owner or mode rejects.

Reuse web_bootstrap's exact bounded private JSON, signature, PID start and listener
validation. Require both roles, consistent project/data roots and distinct PID
identities. The observed relevant listener PID sets must match the authenticated
pair exactly; partial pairs, extra unknown listeners, changed record/argv/start,
PID reuse or candidate mismatch refuse. Unknown target state never becomes idle.

For mutations, retain parent/root and record identity observations in RAM only
under the target's real LifecycleLock. Pin target and candidate directory/record
descriptors as needed with the existing no-follow helpers. Bind the observation
to this controller/manager, scope and exact lease; recheck before control mutation,
allocation/spawn, stop/restart/switch and rollback. Do not refresh a changed baseline
inside the same transaction or transfer the witness across calls/controllers/leases.
Clear it and close descriptors in finally. Read-only status may report current
facts but cannot grant a later write capability.

Integrate at existing Native absence/quiescence and Docker selection/control gates,
including stdlib fallback, the normal Native subprocess bridge and native manager.
Do not duplicate the reader or business logic. Native environment installation
must not become a prerequisite for Docker. Existing-root same-root/unknown writers
still refuse; actual Native records keep their existing ownership rules.

Existing known running Docker reuse remains read-only and verified by accepted
image, labels, mounts, ports and real health. Restart must validate restart safety
before stopping a healthy owned container; force is not an unknown-writer bypass.
Stop/restart/rollback remain exact-ID operations. Existing stopped-container binding
conflicts still refuse: no automatic remove/recreate or port rebinding authorization.

No PID, endpoint, mode or manifest is fabricated as evidence. No persistent proof,
new daemon/probe/config/secret backend, dependency, global change, generic guard
weakening or new framework. Private tmpfs/log binds and original auth remain.

## Acceptance

Closest existing test modules must reproduce repeated start after first creation
and cover Docker restart precheck, stop-to-start and first Native switch, with a
complete private pair. Keep no-venv and valid-owned-venv paths separate. Unit OS
facts are explicitly fixtures, not physical proof. Negative matrix includes same
root, directory/record alias/replacement, invalid/partial pairs, extra listeners,
PID reuse, argv/start changes, lease loss/forgery and cross-controller transfer.

Use existing planner/kernel/receipt and project logging/error codes. Logs expose
only stable diagnostic codes, never records/argv/auth/environment. Run changed-set
gates and independent spec then Python/security quality review before physical tests.
Main alone executes public Native/Docker lifecycle and same-data round trip in
isolated HOME/checkouts; no daily service shutdown, real credentials or data deletion.
Old evidence retains its exact source affinity. CI remains NOT_RUN until separately
authorized; the goal is not complete while necessary physical/Mac CI proof is absent.
