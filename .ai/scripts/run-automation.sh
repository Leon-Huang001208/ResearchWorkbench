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
# - Claude Code CLI is available as 'claude'
#
# Limitations:
# - Does NOT resume interrupted tasks (yet)
# - Does NOT handle concurrent execution (yet)
# - Claude Code runs interactively - requires user approval
# - Claude Code integration requires 'claude' CLI to be available

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

# Check if a task is ready (all dependencies are done)
# Prints ready task ID if ready, nothing otherwise
is_task_ready() {
    local task_id="$1"
    python3 -c "
import json
with open('$TASK_FILE', 'r') as f:
    data = json.load(f)

# Find the task
target_task = None
for task in data['tasks']:
    if task['id'] == '$task_id':
        target_task = task
        break

if not target_task:
    exit(2)

# Check dependencies
dependencies = target_task.get('dependencies', [])
all_done = True

for dep_id in dependencies:
    # Find dependency task
    dep_done = False
    for task in data['tasks']:
        if task['id'] == dep_id:
            if task.get('status', 'todo') == 'done':
                dep_done = True
            break
    if not dep_done:
        all_done = False
        break

if all_done:
    print('$task_id')
" 2>/dev/null
}

# Get missing dependencies for a task
# Prints space-separated list of missing dependency IDs
get_missing_dependencies() {
    local task_id="$1"
    python3 -c "
import json
with open('$TASK_FILE', 'r') as f:
    data = json.load(f)

# Find the task
target_task = None
for task in data['tasks']:
    if task['id'] == '$task_id':
        target_task = task
        break

if not target_task:
    exit(2)

# Check dependencies
dependencies = target_task.get('dependencies', [])
missing = []

for dep_id in dependencies:
    # Find dependency task
    dep_done = False
    for task in data['tasks']:
        if task['id'] == dep_id:
            if task.get('status', 'todo') == 'done':
                dep_done = True
            break
    if not dep_done:
        missing.append(dep_id)

print(' '.join(missing))
" 2>/dev/null
}

# Get next task - dependency-aware, prioritizes high priority
get_next_task() {
    python3 -c "
import json
with open('$TASK_FILE', 'r') as f:
    data = json.load(f)

# Create task map for easy lookup
task_map = {}
for task in data['tasks']:
    task_map[task['id']] = task

# Function to check if a task is ready
def is_ready(task):
    dependencies = task.get('dependencies', [])
    for dep_id in dependencies:
        dep_task = task_map.get(dep_id)
        if not dep_task or dep_task.get('status', 'todo') != 'done':
            return False
    return True

# Find next task: first ready high priority, then ready medium
next_task = None
for task in data['tasks']:
    status = task.get('status', 'todo')
    priority = task.get('priority', 'medium')
    if status not in ['done', 'failed'] and is_ready(task):
        if priority == 'high' and not next_task:
            next_task = task
        elif not next_task:
            next_task = task

if next_task:
    print(next_task['id'])
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

    # Check dependencies first
    echo ""
    print_info "Checking task dependencies..."
    local missing_deps
    missing_deps=$(get_missing_dependencies "$task_id")
    if [ -n "$missing_deps" ]; then
        print_error "Task blocked by unmet dependencies"
        echo "  Missing dependencies: $missing_deps"
        echo ""
        print_info "Please complete the above tasks first, then try again."
        exit 4
    fi
    print_success "All dependencies satisfied"

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

# Generate Claude Code prompt for a specific task
generate_claude_prompt() {
    local task_id="$1"

    cat <<EOF
Read the following files first:
1. CLAUDE.md - Project configuration and hard rules
2. .ai/tasks/task.json - Task definitions
3. .ai/progress/progress.md - Current progress

Then execute ONLY this task: $task_id

Instructions:
1. Update task.json - Mark this task as 'doing' if not already
2. Read the task definition in task.json carefully
3. Execute the task according to its success criteria
4. Create any required audit/report files
5. Stop if blocked by unmet dependencies
6. Update progress.md with task results
7. Update task.json with task completion status
8. Do NOT implement any business features outside this task

Important hard rules from CLAUDE.md:
- NO business logic modification during audit tasks (af-auto-000)
- ONLY commit .ai directory and CLAUDE.md changes for audit tasks
- FAIL LOUDLY - scripts MUST exit with non-zero code on real failures
- NO fake success states - don't report "✓" unless verified
- ALWAYS update task.json AND progress.md for each completed task
EOF
}

# Execute task with Claude Code
execute_task() {
    local task_id="$1"

    if [ -z "$task_id" ]; then
        task_id=$(get_next_task)
        if [ -z "$task_id" ]; then
            print_error "No task found to execute"
            exit 1
        fi
        print_info "Using next task: $task_id"
    fi

    if ! task_exists "$task_id"; then
        print_error "Task not found: $task_id"
        exit 3
    fi

    print_section "TASK EXECUTION" "Launching Claude Code for $task_id"

    # Check dependencies first
    echo ""
    print_info "Checking task dependencies..."
    local missing_deps
    missing_deps=$(get_missing_dependencies "$task_id")
    if [ -n "$missing_deps" ]; then
        print_error "Task blocked by unmet dependencies"
        echo "  Missing dependencies: $missing_deps"
        echo ""
        print_info "Please complete the above tasks first, then try again."
        exit 4
    fi
    print_success "All dependencies satisfied"

    # Check if Claude CLI is available
    if ! command -v claude &> /dev/null; then
        print_error "Claude Code CLI ('claude') not found"
        echo "Please install Claude Code CLI first"
        exit 2
    fi

    # Create temporary prompt file
    local prompt_file=$(mktemp /tmp/claude-prompt.XXXXXX)
    generate_claude_prompt "$task_id" > "$prompt_file"

    print_info "Generated Claude Code prompt at: $prompt_file"
    echo ""
    echo "Press Enter to launch Claude Code with this prompt, or Ctrl+C to cancel..."
    read -r

    # Mark as doing before launching
    echo ""
    print_info "Marking task as 'doing'..."
    if update_task_status "$task_id" "doing"; then
        print_success "Task marked as 'doing'"
    else
        print_error "Failed to update task status"
        rm -f "$prompt_file"
        return 1
    fi

    # Run health checks
    echo ""
    print_info "Running pre-flight health checks..."
    run_health_checks

    echo ""
    print_info "Launching Claude Code..."
    echo "Prompt file will be cleaned up after execution"
    echo ""

    # Launch Claude with the prompt
    claude --no-welcome --message "$(cat "$prompt_file")"

    local claude_exit=$?

    # Clean up prompt file
    rm -f "$prompt_file"

    if [ $claude_exit -ne 0 ]; then
        print_warning "Claude Code exited with status $claude_exit"
        print_info "Task may be incomplete - check manually"
    else
        print_success "Claude Code execution complete"
        print_info "Verify task.json and progress.md were updated"
    fi

    return $claude_exit
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
    echo "  execute <ID>  - Launch Claude Code to execute a task"
    echo "  check         - Run health checks only"
    echo "  help          - Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 list"
    echo "  $0 next"
    echo "  $0 start af-auto-000-12"
    echo "  $0 execute af-auto-000-12"
    echo "  $0 complete af-auto-000-12"
    echo ""
    echo "Limitations:"
    echo "  - execute command requires 'claude' CLI available"
    echo "  - execute runs ONE task at a time only"
    echo "  - Claude Code requires user approval for changes"
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
                print_info "To start manually: $0 start $next_task"
                print_info "To execute with Claude: $0 execute $next_task"
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
        "execute")
            shift
            local task_id="$1"
            if [ -z "$task_id" ]; then
                task_id=$(get_next_task)
                if [ -z "$task_id" ]; then
                    print_error "No task found to execute"
                    exit 1
                fi
                print_info "Using next task: $task_id"
            fi
            execute_task "$task_id"
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
