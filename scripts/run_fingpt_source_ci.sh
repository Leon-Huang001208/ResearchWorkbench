#!/usr/bin/env bash
set -euo pipefail

git -c gc.auto=0 -c maintenance.auto=false fetch --no-tags --no-write-fetch-head --no-auto-maintenance --depth=1 origin \
  b800e50366d1a0868372bbf173822976066c143f \
  db2ae9a48ceca365852072e622aa6627aa7d0b83 \
  1529c3189b008b9861a2bee1511f051feefa76eb
PYTEST_PLUGINS=tests.research_web.event_test_support PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_ci_pytest_partitions.py \
  --task-root "$RUNNER_TEMP/rwb-ci-pytest-research-web" \
  --allowed-parent "$RUNNER_TEMP" \
  --task-id "github-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}-research-web" \
  -- \
  tests/research_web/test_protocol.py \
  tests/research_web/test_api.py \
  tests/research_web/test_research_bots.py \
  tests/research_web/test_automation_routes.py \
  tests/research_web/test_automation_schedule.py \
  tests/research_web/test_automation_research_task.py \
  tests/research_web/test_datahub.py \
  tests/research_web/test_discovery.py \
  tests/research_web/test_discovery_routes.py \
  tests/research_web/test_discovery_tracking.py \
  tests/research_web/test_alphadesk_qa.py \
  tests/research_web/test_alphadesk_qa_formats.py \
  tests/research_web/test_qa_acceptance_budget.py \
  tests/research_web/test_research_quality.py \
  tests/research_web/test_research_quality_scope.py \
  tests/research_web/test_research_business_evidence.py \
  tests/research_web/test_bound_analysis.py \
  tests/research_web/test_research_report.py \
  tests/research_web/test_research_report_binding.py \
  tests/research_web/test_research_source_reading.py \
  tests/research_web/test_external_sources.py \
  tests/research_web/test_dossiers.py \
  tests/research_web/test_report_formats.py \
  tests/research_web/test_report_rendering.py \
  tests/research_web/test_report_revision.py \
  tests/research_web/test_report_calculations.py \
  tests/research_web/test_report_workflows.py \
  tests/research_web/test_report_workflow_integration.py \
  tests/research_web/test_owned_method_execution.py \
  tests/research_web/test_scenario_method_sources.py \
  tests/research_web/test_model_provider_upgrade.py \
  tests/research_web/test_gateway_upgrade.py \
  tests/research_web/test_iteration_resources.py \
  tests/research_web/test_capabilities_admission.py::test_research_bot_native_skill_loading_is_bound_to_frozen_capabilities \
  tests/research_web/test_weknora_formal_scope.py \
  tests/research_web/test_store.py \
  tests/research_web/test_capabilities_native.py \
  tests/research_web/test_service_manager.py::test_web_readiness_enforces_product_static_asset_byte_boundary \
  --confcutdir=tests/research_web -q
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_ci_pytest_partitions.py \
  --task-root "$RUNNER_TEMP/rwb-ci-pytest-unit" \
  --allowed-parent "$RUNNER_TEMP" \
  --task-id "github-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}-unit" \
  -- tests/unit/test_fingpt_legacy_cutover.py tests/unit/test_ci_pytest_partitions.py \
  tests/unit/test_ci_pytest_evidence_staging.py --confcutdir=tests/unit -q
