#!/usr/bin/env bash
set -euo pipefail
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_ci_pytest_partitions.py \
  --task-root "$RUNNER_TEMP/rwb-ci-pytest-research-web" \
  --allowed-parent "$RUNNER_TEMP" \
  --task-id "github-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}-research-web" \
  -- tests/research_web/test_model_profiles.py \
     tests/research_web/test_model_connections.py \
     tests/research_web/test_model_credentials.py \
     tests/research_web/test_encrypted_model_credentials.py \
     tests/research_web/test_alphadesk_qa.py \
     tests/research_web/test_protocol.py \
     tests/research_web/test_api.py::test_session_list_reconciles_only_created_idle_stale_running_rows \
     tests/research_web/test_api.py::test_session_list_isolates_stale_detail_reconciliation_failure \
     tests/research_web/test_api.py::test_unknown_admission_not_retried \
     tests/research_web/test_api.py::test_unowned_instance_is_read_only \
  --confcutdir=tests/research_web -q
