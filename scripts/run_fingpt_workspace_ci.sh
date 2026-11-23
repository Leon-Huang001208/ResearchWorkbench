#!/usr/bin/env bash
set -euo pipefail
# Unchanged Store/OAuth internals and unrelated market/report APIs retain their
# already-passed baseline results; this branch exercises the changed boundary.
PYTEST_PLUGINS=tests.research_web.event_test_support PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_ci_pytest_partitions.py \
  --task-root "$RUNNER_TEMP/rwb-ci-pytest-fingpt-workspace" \
  --allowed-parent "$RUNNER_TEMP" \
  --task-id "github-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}-fingpt-workspace" \
  -- tests/research_web/test_fingpt_identity.py \
  tests/research_web/test_fingpt_proxy.py \
  tests/research_web/test_fingpt_retirement.py \
  tests/research_web/test_multiuser_accounts.py \
  tests/research_web/test_multiuser_gateway.py \
  tests/research_web/test_multiuser_cli.py \
  tests/research_web/test_multiuser_resident.py \
  tests/research_web/test_mcp_facade_config.py \
  tests/research_web/test_mcp_facade_http.py \
  tests/research_web/test_mcp_facade_datahub.py \
  tests/research_web/test_weknora_client.py \
  tests/research_web/test_weknora_service.py \
  tests/research_web/test_weknora_formal_scope.py \
  tests/research_web/test_api.py::test_data_only_and_mcp_contexts_are_hidden_without_hiding_financial_tasks \
  tests/research_web/test_service_manager.py::test_web_readiness_enforces_product_static_asset_byte_boundary \
  tests/research_web/test_model_provider_upgrade.py::test_reviewed_cli_binds_explicit_revisions \
  tests/research_web/test_model_provider_upgrade.py::test_reviewed_cli_rejects_incomplete_or_misplaced_revision_arguments \
  tests/research_web/test_model_provider_upgrade.py::test_reviewed_operate_binds_current_accepted_and_recovers_dynamic_versions \
  tests/research_web/test_model_provider_upgrade.py::test_reviewed_operations_preserve_modes_and_restore_dynamic_previous \
  --confcutdir=tests/research_web -q
