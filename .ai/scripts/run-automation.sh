#!/bin/bash
# AF-AUTO-000: Run automation suite
# Executes the full audit workflow

set -e

echo "=========================================="
echo "AlphaFoundry Automation Suite"
echo "=========================================="
echo ""

# Get project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"
cd "$PROJECT_ROOT"

echo "Working directory: $PROJECT_ROOT"
echo ""

# Run checks in order
echo "[1/3] Running database check..."
"$SCRIPT_DIR/check-db.sh" || true
echo ""

echo "[2/3] Running API check..."
"$SCRIPT_DIR/check-api.sh" || true
echo ""

echo "[3/3] Running project check..."
"$SCRIPT_DIR/check-project.sh" || true
echo ""

echo "=========================================="
echo "Automation suite complete!"
echo "=========================================="
