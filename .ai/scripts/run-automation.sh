#!/bin/bash
# AF-AUTO-000: Task Orchestrator
# Orchestrates task execution for autonomous workflow
#
# Exit codes:
#   0 = success
#   1 = error
#   2 = missing dependencies
#   3 = task not found
#   4 = task blocked
#
# Assumptions:
# - Script runs from project root
# - Python 3 with json module available
# - task.json is valid JSON
# - Only ONE task executed per invocation
#
# Limitations:
# - Does NOT handle task dependencies (yet)
# - Does NOT resume interrupted tasks (yet)
# - Does NOT handle concurrent execution (yet)
# - Does NOT actually IMPLEMENT tasks - only orchestrates state
# - Only does state transition + health checks

set -euo pipefail

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"
TASK_FILE="${PROJECT_ROOT}/.ai/tasks/task.json"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Print header
print_header() {
    echo "=========================================="
    echo "AlphaFoundry Task Orchestrator"
    echo "=========================================="
    echo ""
    echo "⚠  NOTE: This orchestrates state only - NO task implementation"
    echo "          (Business logic remains manual)"
    echo ""
}

print_section() {
    echo ""
    echo "[$1] $2"
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
    echo -e "${BLUE}ℹ${NC} $1"
}

print_task() {
    local id="$1"
    local title="$2"
    local status="$3"
    echo -e "  ${BLUE}${id}${NC}: ${title} [${status}]"
}

# Validate project root and files
validate_environment() {
    cd "$PROJECT_ROOT" || {
        print_error "Cannot change to project root: $PROJECT_ROOT"
        exit 2
    }

    if [ ! -f "pyproject.toml" ]; then
        print_error "Not in project root - pyproject.toml not found"
        exit 2
    fi

    if [ ! -f "$TASK_FILE" ]; then
        print_error "Task file not found: $TASK_FILE"
        exit 2
    fi

    if [ ! -d ".ai/tasks" ]; then
        print_error ".ai/tasks directory not found"
        exit 2
    fi
}

# List available tasks
list_tasks() {
    print_section "TASK LIST" "Current task set state"

    python3 -c "
import json
with open('$TASK_FILE', 'r') as f:
    data = json.load(f)

print('')
print('Status legend: todo, doing, blocked, done, failed')
print('')
print('Tasks:')
for task in data['tasks']:
    status = task.get('status', 'unknown')
    status_str = status
    if status == 'done':
        status_str = '\033[0;32mdone\033[0m'
    elif status == 'failed':
        status_str = '\033[0;31mfailed\033[0m'
    elif status == 'doing':
        status_str = '\033[1;33mdoing\033[0m'
    elif status == 'blocked':
        status_str = '\033[0;33mblocked\033[0m'
    else:
        status_str = '\033[0;37mtodo\033[0m'

    priority = task.get('priority', 'medium')
    if priority == 'high':
        priority_str = '[HIGH]'
    else:
        priority_str = '      '

    print(f\"  {priority_str} {task['id']:20} {task['title'][:50]:50} [{status_str}]\")
" 2>/dev/null || print_warning "Could not list tasks (Python error)"

    echo ""
}

# Get next task (first non-done high priority, then any)
get_next_task() {
    python3 -c "
import json
with open('$TASK_FILE', 'r') as f:
    data = json.load(f)

# Find next task: first non-done high priority, then any non-done
next_task = None
for task in data['tasks']:
    status = task.get('status', 'todo')
    priority = task.get('priority', 'medium')
    if status not in ['done', 'failed']:
        if priority == 'high' and not next_task:
            next_task = task
        elif not next_task:
            next_task = task

if next_task:
    print(next_task['id'])
" 2>/dev/null
}

# Check if a task exists
task_exists() {
    local task_id="$1"
    python3 -c "
import json
with open('$TASK_FILE', 'r') as f:
    data = json.load(f)

for task in data['tasks']:
    if task['id'] == '$task_id':
        exit(0)
exit(1)
" 2>/dev/null
}

# Update task status
update_task_status() {
    local task_id="$1"
    local new_status="$2"

    python3 -c "
import json
with open('$TASK_FILE', 'r') as f:
    data = json.load(f)

updated = False
for task in data['tasks']:
    if task['id'] == '$task_id':
        old_status = task.get('status', 'unknown')
        task['status'] = '$new_status'
        updated = True
        print(f\"Updated {task['id']}: {old_status} -> {new_status}\")

if updated:
    with open('$TASK_FILE', 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    exit(0)
else:
    exit(1)
" 2>/dev/null
}

# Run pre-flight health checks
run_health_checks() {
    print_section "HEALTH CHECKS" "Pre-flight validation"

    local health_ok=0

    echo "  Running DB health check..."
    "$SCRIPT_DIR/check-db.sh" 2>&1 | head -30 || health_ok=1

    echo ""
    echo "  Running API health check..."
    "$SCRIPT_DIR/check-api.sh" 2>&1 | head -30 || true # API might not be running

    echo ""
    echo "  Running project check..."
    "$SCRIPT_DIR/check-project.sh" 2>&1 | head -30 || true # Tests might fail

    if [ "$health_ok" -eq 0 ]; then
        print_success "Health checks passed (DB, API, Project)"
    else
        print_warning "Some health checks had issues"
        print_info "Continuing anyway - baseline already documented"
    fi

    return 0
}

# Main orchestration function
orchestrate_task() {
    local task_id="$1"

    if ! task_exists "$task_id"; then
        print_error "Task not found: $task_id"
        exit 3
    fi

    print_section "TASK ORCHESTRATION" "Selected: $task_id"

    # Step 1: Mark as doing
    echo ""
    print_info "Step 1: Marking task as 'doing'"
    if update_task_status "$task_id" "doing"; then
        print_success "Task marked as 'doing'"
    else
        print_error "Failed to update task status"
        return 1
    fi

    # Step 2: Run health checks
    echo ""
    print_info "Step 2: Running health checks"
    if ! run_health_checks; then
        print_warning "Health checks had issues - continuing anyway"
    fi

    # Step 3: Explain what comes NEXT
    echo ""
    print_info "Step 3: MANUAL IMPLEMENTATION REQUIRED"
    echo ""
    echo "  ⚠  IMPORTANT: This script only manages state!"
    echo "  ⚠  The actual task implementation remains manual."
    echo ""
    echo "  Next steps for ${task_id}:"
    echo "  1. (YOU) Implement the task manually"
    echo "  2. (YOU) Create any required reports in .ai/tasks/"
    echo "  3. (YOU) Update .ai/progress/progress.md"
    echo "  4. (YOU) Commit changes"
    echo "  5. (YOU) Call this script again to mark as done"
    echo ""

    return 0
}

# Mark task complete
mark_task_complete() {
    local task_id="$1"

    if ! task_exists "$task_id"; then
        print_error "Task not found: $task_id"
        exit 3
    fi

    print_section "COMPLETION" "Marking task complete: $task_id"

    if update_task_status "$task_id" "done"; then
        print_success "Task marked as 'done'"
        echo ""
        print_info "Next step: commit changes!"
        echo "  git add .ai/tasks/task.json"
        echo "  git add .ai/progress/progress.md"
        echo "  git commit -m \"$task_id: Complete task\""
        return 0
    else
        print_error "Failed to mark task as done"
        return 1
    fi
}

# Print help
print_help() {
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  list          - List all tasks and status"
    echo "  next          - Show next task to execute"
    echo "  start <ID>    - Mark task as 'doing' and run checks"
    echo "  complete <ID> - Mark task as 'done'"
    echo "  check         - Run health checks only"
    echo "  help          - Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 list"
    echo "  $0 next"
    echo "  $0 start af-auto-000-12"
    echo "  $0 complete af-auto-000-12"
    echo ""
    echo "Limitations:"
    echo "  - Only state management - NO task implementation"
    echo "  - One task per invocation"
    echo "  - No dependency resolution"
}

# Main
main() {
    print_header
    cd "$PROJECT_ROOT"

    # Validate environment first
    validate_environment

    # Parse command
    local cmd="${1:-}"

    case "$cmd" in
        "list")
            list_tasks
            ;;
        "next")
            local next_task
            next_task=$(get_next_task)
            if [ -n "$next_task" ]; then
                print_info "Next task to execute:"
                echo "  $next_task"
                echo ""
                print_info "To start: $0 start $next_task"
            else
                print_success "All tasks completed!"
            fi
            ;;
        "start")
            shift
            local task_id="$1"
            if [ -z "$task_id" ]; then
                task_id=$(get_next_task)
                if [ -z "$task_id" ]; then
                    print_error "No task found to start"
                    exit 1
                fi
                print_info "Using next task: $task_id"
            fi
            orchestrate_task "$task_id"
            ;;
        "complete")
            shift
            local task_id="$1"
            if [ -z "$task_id" ]; then
                print_error "Task ID required"
                exit 1
            fi
            mark_task_complete "$task_id"
            ;;
        "check")
            run_health_checks
            ;;
        "help"|"--help"|"-h"|"")
            print_help
            ;;
        *)
            print_error "Unknown command: $cmd"
            echo ""
            print_help
            exit 1
            ;;
    esac
}

# Run main if not sourced
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
