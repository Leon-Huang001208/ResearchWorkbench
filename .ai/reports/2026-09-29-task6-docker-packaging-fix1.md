# Docker packaging review fix 1

Task-local implementation is verified; Linux image startup remains blocked by external Debian
index downloads. No Windows, amd64, remote CI, or full-delivery acceptance is claimed.

## Changes and evidence

- Reproduced missing `data_layer` by importing only Dockerfile-selected Python source in an isolated
  subprocess that rejects checkout fallback. Added only the package initializers, iFinD exception
  types and HTTP client required by current Web imports. The final image now performs its own
  non-root Web/CLI/supervisor/healthcheck import and staged DSH/profile smoke before export.
- The complete pinned DSH checkout still passes the existing installer verifier before staging.
  `docker/stage_dsh.py` derives production dependencies from installed upstream package metadata;
  it excludes development dependencies, tests, fixtures, docs, benchmarks and website resources.
  `app/research_web/staged_runtime.py` validates the generated bounded inventory, pinned source
  facts and file/symlink digests before the launcher writes state. Native trees without the manifest
  keep the existing Git and closure calculation. No second dependency specification was added.
- Actual read-only inspection and staging of the pinned macOS DSH source passed: 529 production
  packages, 28,001 inventoried entries, 282 MB; excluded-path count zero; profile healing produced
  284 links; staged CLI `--help` and original-closure state lock passed. This is not Linux proof.
- Node focused plus adjacent contracts: 87 passed; final focused packaging: 7 passed.
- Python import/staging/launcher/supervisor: 114 passed. Runtime contract alone: 85 passed.
  A prior combined run returned 197 passed and 2 unchanged contract failures reporting
  `runtime_contract_changed` instead of expected input-validation errors; both are retained in
  the evidence log and the isolated contract rerun passed without code or guard changes.
- Compose config and down succeeded; task-filtered container/network lists are empty.
- Bounded arm64 ECR retry reused Python caches but failed at Debian `apt-get update` with exit 100.
  No runnable image exists, so up/health/restart are not run. No daemon/system settings changed.
- `.venv` lacks black/isort/ruff/mypy; no packages were installed and no lint/type result is claimed.
- Documentation governance and `git diff --check` pass. Generated Python index and full architecture
  source/README/group synchronization remain part of the task-series documentation closeout.

Exact commands, hashes, earlier failures and build cache identity are in
`.superpowers/sdd/2026-09-29-native-docker-dual-runtime/task-6-report.md`; logs are retained under
the task-owned `/tmp/rwb-task6.VyrlkL` directory.

<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"The approved fix validates a derived image asset inventory inside the existing build and launch boundary; it adds no running service, protocol, research execution loop, or runtime topology edge.","diagrams":[]} -->
