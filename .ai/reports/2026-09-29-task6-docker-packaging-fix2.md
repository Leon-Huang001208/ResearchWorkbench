# Docker packaging review fix 2

The launcher now selects staged assets only when the explicit non-secret environment value
`RWB_DSH_STAGED` is exactly `1`. Every other value, including absence, empty string, `0`, `true`,
`01` and whitespace variants, leaves Native on its original Git identity and actual closure path.
A staged manifest present in a writable Native checkout is never read or trusted. Regenerating
its inventory after editing JS cannot suppress the existing build-lock mismatch.

The supervisor removes this flag from the shared child environment, then restores the exact
enabled value only for the runtime launcher child. The Web child receives no flag. The image
continues to set exactly `RWB_DSH_STAGED=1`; Docker requires a valid manifest and rejects missing
or modified assets. No dependency, manifest schema, timeout or integrity check was weakened.

Validation:

- RED regression selection: 21 failed / 1 passed, reproducing both selection and propagation defects.
- GREEN regression selection: 22 passed.
- Focused Python launcher/staged/packaging/supervisor tests: 136 passed.
- Node packaging and related architecture/documentation/Actions contracts: 87 passed.
- `py_compile`, Compose config with task-only mount paths, and `git diff --check`: passed.
- Docker build was not retried in this round. The prior Debian apt download failure remains
  an external blocker, and no cached result is represented as validating this new commit.
  Linux up/health/restart and full task-series architecture/index/CI closeout remain outstanding.

Evidence: `/tmp/rwb-task6.VyrlkL/fix2-red.log`, `fix2-green.log`, `fix2-python.log`,
`fix2-node.log`; full history is appended to the task-6 report under `.superpowers/sdd/`.

<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"This repair restricts existing image-manifest selection to an exact explicit runtime flag and restores the Native closure check; no service, protocol, process topology or research execution boundary changes.","diagrams":[]} -->
