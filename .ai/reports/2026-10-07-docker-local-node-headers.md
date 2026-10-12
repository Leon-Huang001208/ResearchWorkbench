# Docker DSH builder local Node headers

Host macOS, functional source repair/local contract acceptance. Base efff4651a. Own Dockerfile,
closest docker_runtime_contract JS test and mandatory docs/report. R5/runtime-control/PIP/shared-env/
Cordis source untouched; main Task3 untracked report preserved. No actual build/image/run/network/
installation/global config/remote/dependency/credential/TLS/signature/software-source operation.

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"The existing dsh-builder copies headers from its same pinned Node stage and selects local nodedir; final runtime and deployment nodes are unchanged.","diagrams":[]} -->

Main actual efff public Docker build failed at dsh-builder frozen pnpm fs-ext: node24.19 headers GET
entered Undici HTTP proxy handler with incompatible SOCKS setting; APT had succeeded. Main RO image
check exit0 found nodev24.19.0, header macros24/19/0 and config.gypi/common.gypi. Parent RO review
confirmed node-gyp12.4 local nodedir path /usr/local/include/node/config.gypi. These are parent evidence,
not tool runs by this implementer. Original failed build retained; no final-image/lifecycle PASS claimed.

Two-line Dockerfile change: dsh-builder COPY --from=node-runtime /usr/local/include/node entire tree;
ENV npm_config_nodedir=/usr/local only that stage. Binary remains from same pinned node-runtime.
Final runtime copies no headers/ENV. No opportunistic proxy framework/locks/deps/source/TLS changes.
Actual contract RED1 while original12 tests pass (docker-node-headers-red.log), then GREEN13/0.116s
(docker-node-headers-green.log). Stage slicing proves same-source headers/binary, nodedir before install,
unique builder-only copy/ENV; original single-source versions, non-root/runtime/security negatives preserved.
Existing source inventory already lists Dockerfile and this test; no new source/test path required.

Main owns one new-basis real public Docker build and lifecycle verification. Any later Node/proxy failure
must be separately bounded, not guessed now. Stopped-container recreation remains unauthorized/pending.

Selected container_supervisor/runtime_launch137PASS/25.68s; selected JS104PASS/2.437s, original negative
logging retained. First doc-sync/constraints failed missing runtime owner doc, corrected corresponding doc,
not checkers; final nine-path gates/index PASS, shared kernel11/11 SHA match. L4 plan retains
validation_failure; existing receipt validator valid=true,7 local PASS/3 external NOT_RUN, BLOCKED,
mergeReady/releaseReady=false. No true image/network/runtime claim; independent review/main rebuild required.
