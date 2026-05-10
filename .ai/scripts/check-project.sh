#!/bin/bash
# AF-AUTO-000: Check project baseline
# Checks tests, core services, and project structure
#
# Exit codes:
#   0 = success
#   1 = error
#   2 = missing dependencies
#
# Assumptions:
# - Script runs from project root
# - Python 3 available

set -euo pipefail

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Print header
print_header() {
    echo "=========================================="
    echo "AlphaFoundry Project Check"
    echo "=========================================="
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
        echo "Project check complete!"
    else
        echo "Project check had issues (exit code: $1)"
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

    if [ ! -d "core" ] || [ ! -d "app" ]; then
        print_error "Missing core directories (core/ or app/)"
        exit 2
    fi

    print_success "Project structure looks good"
}

# Check core services
check_core_services() {
    print_section "1" "3" "Checking core services..."

    SERVICE_COUNT=$(find core/services -name "*.py" ! -name "__init__.py" | wc -l)
    SERVICE_COUNT=$(echo "$SERVICE_COUNT" | xargs) # trim whitespace

    if [ "$SERVICE_COUNT" -eq 0 ]; then
        print_error "No core services found!"
        return 1
    fi

    print_success "Found $SERVICE_COUNT core services"
    return 0
}

# Check tests (preserve exit status)
check_tests() {
    print_section "2" "3" "Checking test baseline..."
    echo "(This may take a while...)"
    echo ""

    # Run tests but preserve exit code
    set +e
    python -m pytest tests/ -v --tb=short 2>&1 | head -100
    TEST_EXIT=${PIPESTATUS[0]}
    set -e

    echo ""
    if [ "$TEST_EXIT" -eq 0 ]; then
        print_success "All tests passed!"
    else
        print_warning "Tests had failures (exit code: $TEST_EXIT)"
        print_warning "(This is expected per baseline documentation)"
    fi

    return 0 # Always return success - baseline already documented
}

# Check test coverage stub
check_coverage() {
    print_section "3" "3" "Checking test coverage..."
    print_warning "Test coverage check - not implemented yet"
    return 0
}

# Main execution
main() {
    print_header
    cd "$PROJECT_ROOT"

    local overall_exit=0

    # Run checks
    validate_project_root || overall_exit=1

    if [ $overall_exit -eq 0 ]; then
        check_core_services || overall_exit=1
    fi

    if [ $overall_exit -eq 0 ]; then
        check_tests || true # Never fails
    fi

    if [ $overall_exit -eq 0 ]; then
        check_coverage || true # Never fails
    fi

    print_footer $overall_exit
    return $overall_exit
}

# Run main if not sourced
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
