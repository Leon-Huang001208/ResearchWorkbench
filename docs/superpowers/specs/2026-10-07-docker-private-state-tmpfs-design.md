# Docker private runtime state: approved bounded design

Host: macOS; Web functional repair, no desktop or other-platform acceptance.
Human approved this exact private-tmpfs design in the current chat on 2026-10-07.
Implementation baseline: 981e20f10f190e905a6c4b24d233f162e739f578.

## Evidence and decision

The exact baseline image installed successfully, but its one real startup failed
at runtime_probe: the strict state guard observed a direct-parent UID/GID reverse
transition after yielding. One-time initialization did not make subsequent bind
identity stable. Preserve the failure; do not add reverse exemptions or retries.

Chosen: container-private /state tmpfs, with explicit rw,nosuid,nodev,noexec,
uid=10001,gid=10001,mode=700,size=1m. Authentication lives in /state/runtime and is
recreated by normal supervisor startup after every stop/start. The fixed runtime
ports, CLI, auth protocol and business/data paths stay unchanged.

Alternatives rejected: continuing the unstable state bind; a named volume adds
persistent resource ownership and disposal beyond what ephemeral auth needs.
The existing /tmp and /home/rwb tmpfs remain unchanged.

## Persistent boundaries

Bind the same former state-root logs child to /state/logs using
${RWB_STATE_DIR}/logs, with create_host_path=false. Validate/create that private
host logs directory through the existing private-directory checks, under normal
lifecycle ownership. Existing logs and old state/runtime remain untouched; no
copy, migration, cleanup or use of legacy auth records. Research data stays at
/data/research-web and credentials at /run/rwb-secrets/private with their existing
host sources. Supervisor's already-persistent product log path also stays intact.

Inspect exact mandatory mount destinations/types/sources/RW plus the /state
HostConfig.Tmpfs security and ownership options before reuse and after creation.
Missing, duplicate, unexpected, readonly state, wrong options, bind/volume
substitution or changed logs/data/credential sources fail closed. The immutable
image/install/launch/Compose ownership checks remain mandatory. No fallback to
old mounted auth and no automatic disposal of legacy stopped containers.

Remove the ineffective state-only initialization and its exceptional mapping
acceptance. Generic runtime_state_directory, auth writer, normal health, and
Native validators remain strict and unchanged. Existing credential/data leaf
first-creation behavior is not broadened. No global Docker, daemon, proxy,
Harness, dependencies or trust configuration changes.

## Acceptance

Actual RED/GREEN contracts cover Compose, inspect negative matrix, private logs
creation, no alias/foreign directories, strict state preparation, install hash
binding and retention of old state. Use existing tests/planner/receipt, not a new
framework. Independently review specification, then code/security.

Main runs one current-source public isolated installer/build and the real Docker
start/status/Doctor/health/restart/stop/start-again, secret-free test credentials
permissions and Native→Docker→Native session/CSV roundtrip. No daily ports,
services, credentials, real data or volumes are touched. Failed image/startup
does not pass later lifecycle gates; no unchanged repeated builds.

Docker tmpfs can be swapped by the Docker VM kernel: this design is ephemeral
runtime lifecycle storage, not a guarantee that secrets never touch disk.
Reference: https://docs.docker.com/engine/storage/tmpfs/ .
Mac CI and latest-master integration remain required independent gates; remote
mutations still need explicit authorization. Windows/Linux remain unverified
handoffs, not Mac task prerequisites.
