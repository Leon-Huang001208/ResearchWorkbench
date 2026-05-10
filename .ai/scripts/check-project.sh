#!/bin/bash
# AF-AUTO-000: Check project baseline
# Checks tests, core services, and project structure

set -e

echo "=========================================="
echo "AlphaFoundry Project Check"
echo "=========================================="
echo ""

# Check project structure
echo "[1/4] Checking project structure..."
if [ -f "pyproject.toml" ] && [ -d "core" ] && [ -d "app" ]; then
    echo "✓ Project structure looks good"
else
    echo "✗ Project structure missing key directories/files"
    exit 1
fi
echo ""

# Check tests
echo "[2/4] Checking test baseline..."
echo "(This may take a while...)"
if python -m pytest tests/ -v --tb=short 2>&1 | head -50; then
    echo "✓ Tests ran (see output above for details)"
else
    echo "⚠ Tests had some failures"
fi
echo ""

# Check core services
echo "[3/4] Checking core services..."
SERVICE_COUNT=$(find core/services -name "*.py" ! -name "__init__.py" | wc -l)
echo "✓ Found $SERVICE_COUNT core services"
echo ""

# Check test coverage (if available)
echo "[4/4] Checking test coverage..."
echo "Test coverage check - to be implemented"
echo ""

echo "=========================================="
echo "Project check complete!"
echo "=========================================="
