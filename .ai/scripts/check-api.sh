#!/bin/bash
# AF-AUTO-000: Check API health
# Verifies FastAPI server and endpoints (smart: uses existing if running)
#
# Exit codes:
#   0 = success
#   1 = error
#   2 = missing dependencies
#
# Assumptions:
# - Script runs from project root
# - Python 3 available
# - API might already be running on 8000
# - Will NOT start server if not running

set -euo pipefail

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"
API_HOST="127.0.0.1"
API_PORT="8000"
API_URL="http://${API_HOST}:${API_PORT}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Print header
print_header() {
    echo "=========================================="
    echo "AlphaFoundry API Health Check"
    echo "=========================================="
    echo ""
    echo "⚠  WARNING: Will NOT start server - only checks if running"
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

print_info() {
    echo -e "${YELLOW}ℹ${NC} $1"
}

print_footer() {
    echo ""
    echo "=========================================="
    if [ $1 -eq 0 ]; then
        echo "API health check complete!"
    else
        echo "API health check had issues (exit code: $1)"
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

    if [ ! -d "app" ]; then
        print_error "Missing app directory"
        exit 2
    fi
}

# Check if API is already running
check_api_running() {
    print_section "1" "4" "Checking if API is running..."

    set +e
    curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${API_URL}/health" 2>&1
    CURL_EXIT=$?
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${API_URL}/health" 2>/dev/null || echo "000")
    set -e

    if [ "$HTTP_CODE" = "200" ]; then
        print_success "API is running on ${API_URL}"
        return 0
    fi

    if [ "$CURL_EXIT" -eq 7 ] || [ "$CURL_EXIT" -eq 28 ]; then
        print_warning "API NOT running on ${API_URL}"
        print_info "To start API: python -m uvicorn app.api.main:app --host ${API_HOST} --port ${API_PORT}"
        return 1
    fi

    print_warning "API check returned HTTP ${HTTP_CODE} (curl exit: ${CURL_EXIT})"
    return 1
}

# FastAPI import check (independent of running server)
check_api_import() {
    print_section "2" "4" "Checking FastAPI app import..."

    set +e
    python -c "
from app.api.main import app
print(f'Successfully imported {len(app.routes)} routes')
print('FastAPI app is configured correctly')
" 2>&1

    IMPORT_EXIT=$?
    set -e

    if [ "$IMPORT_EXIT" -eq 0 ]; then
        print_success "FastAPI app import verified"
        return 0
    fi

    print_error "FastAPI app import failed (exit code: ${IMPORT_EXIT})"
    return 1
}

# Check health endpoint
check_health_endpoint() {
    print_section "3" "4" "Checking /health endpoint..."

    set +e
    RESPONSE=$(curl -s --max-time 5 "${API_URL}/health" 2>&1)
    CURL_EXIT=$?
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${API_URL}/health" 2>/dev/null || echo "000")
    set -e

    if [ "$HTTP_CODE" = "200" ]; then
        echo "$RESPONSE" | head -3
        print_success "/health endpoint responds correctly"
        return 0
    fi

    print_warning "/health check failed (HTTP ${HTTP_CODE})"
    return 1
}

# Check docs endpoint
check_docs_endpoint() {
    print_section "4" "4" "Checking /docs endpoint..."

    set +e
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${API_URL}/docs" 2>/dev/null || echo "000")
    set -e

    if [ "$HTTP_CODE" = "200" ]; then
        print_success "/docs endpoint accessible"
        return 0
    fi

    print_warning "/docs check returned HTTP ${HTTP_CODE}"
    return 1
}

# Main execution
main() {
    print_header
    cd "$PROJECT_ROOT"

    local overall_exit=0
    local api_running=0

    # Validate first
    validate_project_root || overall_exit=1

    # Check import always
    if [ $overall_exit -eq 0 ]; then
        check_api_import || overall_exit=1
    fi

    # Check API running first
    if check_api_running; then
        api_running=1
    else
        print_info "Skipping endpoint checks (API not running)"
    fi

    # Only check endpoints if API is running
    if [ $api_running -eq 1 ]; then
        check_health_endpoint || true # Don't fail on this
        check_docs_endpoint || true  # Don't fail on this
    fi

    print_footer $overall_exit
    return $overall_exit
}

# Run main if not sourced
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
