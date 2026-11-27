#!/usr/bin/env bash
set -euo pipefail

# The original runner, evidence and timeout contract; only this domain list narrows.
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_ci_pytest_partitions.py \
  --task-root "$RUNNER_TEMP/rwb-ci-pytest-research-web" \
  --allowed-parent "$RUNNER_TEMP" \
  --task-id "github-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}-research-web" \
  -- \
  tests/research_web/test_datahub.py \
  tests/research_web/test_datahub_akshare_semantics.py \
  tests/research_web/test_datahub_baostock.py \
  tests/research_web/test_datahub_baostock_cashflow.py \
  tests/research_web/test_datahub_bea_archive.py \
  tests/research_web/test_datahub_broker.py \
  tests/research_web/test_datahub_catalog.py \
  tests/research_web/test_datahub_cjpy.py \
  tests/research_web/test_datahub_execution_health.py \
  tests/research_web/test_datahub_finance_mcp.py \
  tests/research_web/test_datahub_planning.py \
  tests/research_web/test_finance_market_contract.py \
  tests/research_web/test_mcp_task_contracts.py \
  tests/research_web/test_asset_loading.py \
  tests/research_web/test_asset_workspace.py \
  tests/research_web/test_asset_history.py \
  tests/research_web/test_datahub_financial_time_contract.py \
  tests/research_web/test_datahub_kapsarc.py \
  tests/research_web/test_datahub_numeric_sources.py \
  tests/research_web/test_datahub_official_numeric.py \
  tests/research_web/test_datahub_openbb.py \
  tests/research_web/test_datahub_public_worker.py \
  tests/research_web/test_datahub_reliability.py \
  tests/research_web/test_datahub_spdr.py \
  tests/research_web/test_datahub_storage_activity.py \
  tests/research_web/test_datahub_warehouse.py \
  tests/research_web/test_research_warehouse_management.py \
  tests/research_web/test_market_store.py \
  tests/research_web/test_warehouse_diagnostics.py \
  tests/research_web/test_datahub_wgc.py \
  tests/research_web/test_datahub_wind.py \
  tests/research_web/test_datahub_wind_api.py \
  tests/research_web/test_datahub_wind_excel_weekly.py \
  tests/research_web/test_external_sources.py \
  tests/research_web/test_connection_center.py \
  tests/research_web/test_protocol.py \
  tests/research_web/test_workbench_operations.py \
  tests/research_web/test_fingpt_retirement.py \
  tests/research_web/test_store.py \
  tests/research_web/test_capabilities_native.py \
  tests/research_web/test_weknora_formal_scope.py \
  tests/research_web/test_multiuser_accounts.py \
  tests/research_web/test_multiuser_gateway.py \
  tests/research_web/test_multiuser_cli.py \
  tests/research_web/test_mcp_facade_config.py \
  tests/research_web/test_mcp_facade_datahub.py \
  tests/research_web/test_mcp_facade_http.py \
  tests/research_web/test_mcp_facade_lifecycle.py \
  tests/research_web/test_mcp_facade_oauth.py \
  tests/research_web/test_mcp_facade_read_policy.py \
  tests/research_web/test_mcp_facade_store.py \
  tests/research_web/test_mcp_facade_tools.py \
  --confcutdir=tests/research_web -q
