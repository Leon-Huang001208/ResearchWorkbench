#!/usr/bin/env bash
set -euo pipefail

# Contracted slice for the account gateway's read-only architecture documents.
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_ci_pytest_partitions.py \
  --task-root "$RUNNER_TEMP/rwb-ci-pytest-research-web" \
  --allowed-parent "$RUNNER_TEMP" \
  --task-id "github-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}-research-web" \
  -- \
  tests/research_web/test_multiuser_gateway.py \
  tests/research_web/test_documentation.py \
  tests/research_web/test_documentation_center.py \
  --confcutdir=tests/research_web -q
