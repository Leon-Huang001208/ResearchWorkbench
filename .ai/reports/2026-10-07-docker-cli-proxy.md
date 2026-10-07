# Docker host CLI proxy compatibility

Host macOS, functional development, isolated local source/fixtures. Base b9ff60fac;
owner docker_runtime.py, closest Docker/setup tests and required docs/index/inventory. R5 setup/manager
source untouched; main Task3 untracked report preserved/excluded. No real network/service/install,
vendor credentials/global config/remote/dependency/TLS/signature/software-source operation.

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"Only existing host Docker CLI subprocess environment is amended; Native minimal environment, Docker runtime/provider environments and deployment nodes remain unchanged.","diagrams":[]} -->

Only credentials-free loopback HTTP(S) URLs with explicit bounded port are inherited; malformed/control/
oversized/userinfo/path/query/fragment/non-loopback values rejected. Upper/lower validated equality,
empty-disable and empty/nonempty conflicts explicit. NO_PROXY bounded hosts/IP/CIDR/wildcards, with
mandatory localhost/127.0.0.1/::1 bypass. Unsafe pairs filtered for status/Doctor/stop, safe warning/Doctor
projection has no values. Install/build fails explicitly; build validates the exact Popen env snapshot.
Shared minimal_environment unchanged; no ALL_PROXY/Docker endpoint/TLS/provider-secret inheritance;
fixed argv/COMPOSE_DISABLE_ENV_FILE preserved, no build-arg or runtime proxy injection.

Actual initial RED10 in logs/docker-proxy-red.log: real run_bounded→CapturedPopen drops safe URLs;
unsafe proxies silently ignored by install while owned status/stop remain usable. Initial GREEN10/0.63s.
Case/empty/conflict/NO_PROXY/Doctor/privacy negatives23PASS/4.52s (docker-proxy-negative.log).
Public install_selected_runtime(Docker,no-start) uses actual controller+run_bounded+CapturedPopen,
not a private runner. Original env-merge omission replayed locally gives genuine RED1/0.17s
(docker-proxy-public-boundary-red.log), restored merge GREEN1/0.12s. Initial public-test NameError from
a displaced existing assertion is fixture error, not behavioral RED, corrected without relaxing assertion.
Six affected boundary modules508PASS/33.21s (docker-proxy-closure.log); Doctor local_bypass
projection appended after this closure requires final focused verification. No network acceptance claim.

Source inventory adds public setup test to existing dual-runtime group; no new source/dependency/framework.
Main owns real Docker combined build/lifecycle; CLI env does not certify Engine/build networking. Existing
stopped-container auto deletion/recreation remains unauthorized/unimplemented; no HTTPS source change.

Final focused after projection1failed/23passed/1.11s (docker-proxy-final-focused.log): status guard reads
runtime_mode_changed→docker_data_home_unsafe. Cause unconfirmed, not attributed to parallel tools or
called a flake; no mode/private-file validator weakened. Final identical-source integrated Docker/setup/
mode/protocol closure367PASS/28.04s includes that case (docker-proxy-final-closure.log). Earlier failure
retained. Selected JS103PASS/2.400s,11-path doc-sync/constraints/index PASS; shared kernel11/11 SHA
match; host -I -S imports Docker controller without core.settings/pydantic, minimal env excludes proxy.
No actual proxy reachability/build claim, no R5/JS source modifications.

Plan/receipt logs/docker-proxy-{plan,receipt}.json selected L4 and retained validation_failure. Existing
validator returns valid=true,9 local PASS/5 external NOT_RUN, BLOCKED, mergeReady/releaseReady=false.
Format/type tools remain unavailable NOT_RUN; no packages installed. Independent review and main's
actual combined Docker network/build/lifecycle remain required; pending container disposition unchanged.
