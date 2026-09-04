#!/usr/bin/env bash
# Run Research Workbench benchmark evaluation
# Usage: bash benchmarks/run_benchmark.sh [--dataset DATASET_NAME] [--json]
#
# Exit code 0 if evaluation completes successfully, 1 otherwise.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH:-}"

echo "========================================"
echo "  Research Workbench Benchmark Runner"
echo "========================================"
echo ""

# Run evaluation
python benchmarks/evaluate.py "$@"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✅ Benchmark evaluation completed successfully"
else
    echo ""
    echo "❌ Benchmark evaluation failed (exit code: $EXIT_CODE)"
fi

exit $EXIT_CODE
