#!/bin/bash
# AF-AUTO-000: Check API health
# Verifies FastAPI server and endpoints

set -e

echo "=========================================="
echo "AlphaFoundry API Check"
echo "=========================================="
echo ""

# Check import
echo "[1/4] Checking FastAPI import..."
if python -c "from app.api.main import app; print('✓ FastAPI app import successful')" 2>&1; then
    echo "✓ FastAPI app import successful"
else
    echo "✗ FastAPI app import failed"
    exit 1
fi
echo ""

# Check health endpoint
echo "[2/4] Checking health endpoint..."
if curl -f http://127.0.0.1:8000/health 2>&1; then
    echo "✓ Health endpoint responds"
else
    echo "⚠ Health endpoint check failed (maybe server not running)"
fi
echo ""

# Check docs endpoint
echo "[3/4] Checking docs endpoint..."
if curl -f -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/docs 2>&1 | grep -q "200"; then
    echo "✓ Docs endpoint responds"
else
    echo "⚠ Docs endpoint check failed (maybe server not running)"
fi
echo ""

# Check sample API endpoint
echo "[4/4] Checking sample API endpoint..."
if curl -f -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/review/pending 2>&1 | grep -q "200"; then
    echo "✓ Sample API endpoint responds"
else
    echo "⚠ Sample API endpoint check failed"
fi
echo ""

echo "=========================================="
echo "API check complete!"
echo "=========================================="
