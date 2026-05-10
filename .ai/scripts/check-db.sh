#!/bin/bash
# AF-AUTO-000: Check database health
# Verifies database connection and schema (NO destructive operations)
#
# Exit codes:
#   0 = success
#   1 = error
#   2 = missing dependencies
#
# Assumptions:
# - Script runs from project root
# - Python 3 available
# - PostgreSQL configured in core/settings/config.py

set -euo pipefail

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Print header
print_header() {
    echo "=========================================="
    echo "AlphaFoundry Database Health Check"
    echo "=========================================="
    echo ""
    echo "⚠  WARNING: NO data import - only health checks"
    echo ""
}

print_section() {
    echo ""
    echo "[$1/$2] $3"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_footer() {
    echo ""
    echo "=========================================="
    if [ $1 -eq 0 ]; then
        echo "Database health check complete!"
    else
        echo "Database health check had issues (exit code: $1)"
    fi
    echo "=========================================="
}

# Validate we're in the right directory
validate_project_root() {
    cd "$PROJECT_ROOT" || {
        print_error "Cannot change to project root: $PROJECT_ROOT"
        exit 2
    }

    if [ ! -f "pyproject.toml" ]; then
        print_error "Not in project root - pyproject.toml not found"
        exit 2
    fi

    if [ ! -d "data_layer" ]; then
        print_error "Missing data_layer directory"
        exit 2
    fi
}

# Check database connection only (no schema changes)
check_db_connection() {
    print_section "1" "3" "Checking database connection..."

    set +e
    python -c "
from core.settings.config import settings
from data_layer.repositories.base import engine, check_database_connection
print(f'Connecting to: {settings.DATABASE_URL}')
check_database_connection()
print('Connection successful!')
" 2>&1

    CONN_EXIT=$?
    set -e

    if [ "$CONN_EXIT" -eq 0 ]; then
        print_success "Database connection verified"
    else
        print_error "Database connection failed (exit code: $CONN_EXIT)"
        return 1
    fi

    return 0
}

# Check schema exists (no changes)
check_db_schema() {
    print_section "2" "3" "Checking database schema..."

    set +e
    python -c "
from sqlalchemy import inspect
from data_layer.repositories.base import engine
from data_layer.repositories.models import *

inspector = inspect(engine)
tables = inspector.get_table_names()

# Check for critical tables
critical_tables = ['canonical_event', 'source_document', 'assertion', 'alpha_signal']
found_count = 0
for table in critical_tables:
    if table in tables:
        print(f'  Found table: {table}')
        found_count += 1

print(f'Found {found_count}/{len(critical_tables)} critical tables')
print(f'Total tables: {len(tables)}')
" 2>&1

    SCHEMA_EXIT=$?
    set -e

    if [ "$SCHEMA_EXIT" -eq 0 ]; then
        print_success "Schema check completed"
    else
        print_warning "Schema check had issues (exit code: $SCHEMA_EXIT)"
        return 1
    fi

    return 0
}

# Check for existing data (no modifications)
check_existing_data() {
    print_section "3" "3" "Checking for existing data..."

    set +e
    python -c "
from data_layer.repositories.base import SessionLocal
from data_layer.repositories.models import SourceDocument, CanonicalEvent

db = SessionLocal()
try:
    doc_count = db.query(SourceDocument).count()
    event_count = db.query(CanonicalEvent).count()
    print(f'  Source Documents: {doc_count}')
    print(f'  Canonical Events: {event_count}')
    print('  (No data modified - only counted)')
finally:
    db.close()
" 2>&1

    DATA_EXIT=$?
    set -e

    if [ "$DATA_EXIT" -eq 0 ]; then
        print_success "Data check completed (no modifications)"
    else
        print_warning "Data check had issues (exit code: $DATA_EXIT)"
        return 1
    fi

    return 0
}

# Main execution
main() {
    print_header
    cd "$PROJECT_ROOT"

    local overall_exit=0

    # Validate first
    validate_project_root || overall_exit=1

    if [ $overall_exit -eq 0 ]; then
        check_db_connection || overall_exit=1
    fi

    if [ $overall_exit -eq 0 ]; then
        check_db_schema || true # Don't fail on schema issues
    fi

    if [ $overall_exit -eq 0 ]; then
        check_existing_data || true # Don't fail on data issues
    fi

    print_footer $overall_exit
    return $overall_exit
}

# Run main if not sourced
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
