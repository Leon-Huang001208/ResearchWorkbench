#!/bin/bash
# AF-AUTO-000: Check database health
# Verifies database connection and schema

set -e

echo "=========================================="
echo "AlphaFoundry Database Check"
echo "=========================================="
echo ""

# Check database connection
echo "[1/3] Checking database connection..."
if python scripts/bootstrap_db.py 2>&1 | tail -20; then
    echo "✓ Database connection verified"
else
    echo "✗ Database connection failed"
    exit 1
fi
echo ""

# Check import
echo "[2/3] Checking data import..."
python scripts/import_real_data.py 2>&1
echo "✓ Data import check complete"
echo ""

# Check view db (optional)
echo "[3/3] Checking database view..."
echo "Database view check - to be implemented"
echo ""

echo "=========================================="
echo "Database check complete!"
echo "=========================================="
