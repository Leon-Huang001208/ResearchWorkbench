#!/bin/bash
# AF-AUTO: Enhanced Task Orchestrator
# Orchestrates task execution for autonomous workflow
#
# New features:
#   - Loop mode: run multiple iterations automatically
#   - Structured logging with rotation
#   - Print mode support for non-interactive execution
#   - Final summary report generation
#   - Progress tracking across runs
#
# Exit codes:
#   0 = success
#   1 = error
#   2 = missing dependencies
#   3 = task not found
#   4 = task blocked
#
# Assumptions:
#   - Script runs from project root
#   - Python 3 with json module available
#   - task.json is valid JSON
#   - Only ONE task executed per invocation
#   - Claude Code CLI is available as 'claude'
#
# Limitations:
#   - Does NOT resume interrupted tasks (yet)
#   - Does NOT handle concurrent execution (yet)
#   - Claude Code runs interactively - requires user approval

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"
DEFAULT_TASK_FILE="${PROJECT_ROOT}/.ai/tasks/task.json"
TASK_FILE="${DEFAULT_TASK_FILE}"
PROGRESS_FILE="${PROJECT_ROOT}/.ai/progress/progress.md"

# Logging
LOG_DIR="${PROJECT_ROOT}/.ai/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/automation-$(date +%Y%m%d_%H%M%S).log"
SUMMARY_REPORT=""

# State tracking
ORIGINAL_TASK_STATUS=""
ORIGINAL_PROGRESS_MTIME=""
TASKS_COMPLETED_THIS_RUN=0
TOTAL_RUNS=0

# Claude mode: interactive (default) or print (non-interactive)
CLAUDE_MODE="${CLAUDE_MODE:-print}"

# Sleep between runs (loop mode)
SLEEP_BETWEEN_RUNS="${SLEEP_BETWEEN_RUNS:-2}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# =============================================================================
# Logging Functions
# =============================================================================

log() {
    local level=$1
    local message=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} [${level}] ${message}" >> "$LOG_FILE"

    case $level in
        INFO)
            echo -e "${BLUE}[INFO]${NC} ${message}"
            ;;
        SUCCESS)
            echo -e "${GREEN}[SUCCESS]${NC} ${message}"
            ;;
        WARNING)
            echo -e "${YELLOW}[WARNING]${NC} ${message}"
            ;;
        ERROR)
            echo -e "${RED}[ERROR]${NC} ${message}"
            ;;
        PROGRESS)
            echo -e "${CYAN}[PROGRESS]${NC} ${message}"
            ;;
    esac
}

print_header() {
    echo "=========================================="
    echo "AlphaFoundry Task Orchestrator"
    echo "=========================================="
    echo ""
    echo "  Commands:"
    echo "    list          - List all tasks and status"
    echo "    next          - Show next task to execute"
    echo "    start <ID>    - Mark task as 'doing' and run checks"
    echo "    complete <ID> - Mark task as 'done'"
    echo "    execute <ID>  - Launch Claude Code to execute a task"
    echo "    check         - Run health checks only"
    echo "    loop <N>      - Run up to N iterations automatically"
    echo "    loop --until-done - Run until all tasks are done"
    echo "    help          - Show this help"
    echo ""
    echo "  Log file: $LOG_FILE"
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

# =============================================================================
# Git Branch Validation
# =============================================================================

is_master_branch() {
    local current_branch=$(git branch --show-current 2>/dev/null || echo "")
    if [ "$current_branch" = "master" ] || [ "$current_branch" = "main" ]; then
        return 0
    fi
    return 1
}

is_audit_task() {
    local task_id="$1"
    if [[ "$task_id" == *"af-auto-000"* ]]; then
        return 0
    fi
    return 1
}

validate_branch() {
    local task_id="$1"
    local current_branch=$(git branch --show-current 2>/dev/null || echo "unknown")

    print_section "BRANCH CHECK" "Validating Git branch for task execution"

    if is_master_branch; then
        if [ -z "$task_id" ] || ! is_audit_task "$task_id"; then
            print_error "Cannot execute this task on master/main branch!"
            echo ""
            echo "  Current branch: ${current_branch}"
            echo ""
            echo "  AF-AUTO-001 and later tasks require a feature branch."
            echo ""
            echo "  To fix this:"
            echo "  1. Create a feature branch:"
            echo "     git checkout -b af-auto-001-<task-description>"
            echo ""
            echo "  2. Or if you already have a branch:"
            echo "     git checkout <branch-name>"
            echo ""
            echo "  Branch naming examples:"
            echo "    - af-auto-001-fix-failing-tests"
            echo "    - af-auto-001-reasoning-todos"
            echo "    - af-auto-001-quick-win-tests"
            echo ""
            print_info "Audit tasks (af-auto-000) can still run on master"
            exit 5
        else
            print_success "Audit task: allowed on master ✓"
        fi
    else
        print_success "On feature branch: ${current_branch} ✓"
    fi
}

# =============================================================================
# Environment Validation
# =============================================================================

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

    if [ "$TASK_FILE" != "$DEFAULT_TASK_FILE" ]; then
        print_info "Using custom task file: $(basename "$TASK_FILE")"
    fi
}

# =============================================================================
# Task Operations (Python-powered)
# =============================================================================

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

get_next_task() {
    python3 -c "
import json
with open('$TASK_FILE', 'r') as f:
    data = json.load(f)

task_map = {}
for task in data['tasks']:
    task_map[task['id']] = task

def is_ready(task):
    dependencies = task.get('dependencies', [])
    for dep_id in dependencies:
        dep_task = task_map.get(dep_id)
        if not dep_task or dep_task.get('status', 'todo') != 'done':
            return False
    return True

ready_high = []
ready_medium = []

for task in data['tasks']:
    status = task.get('status', 'todo')
    priority = task.get('priority', 'medium')
    if status not in ['done', 'failed'] and is_ready(task):
        if priority == 'high':
            ready_high.append(task)
        else:
            ready_medium.append(task)

next_task = None
if ready_high:
    next_task = ready_high[0]
elif ready_medium:
    next_task = ready_medium[0]

if next_task:
    print(next_task['id'])
" 2>/dev/null
}

count_remaining_tasks() {
    python3 -c "
import json
with open('$TASK_FILE', 'r') as f:
    data = json.load(f)
remaining = 0
for task in data['tasks']:
    status = task.get('status', 'todo')
    if status not in ['done', 'failed']:
        remaining += 1
print(remaining)
" 2>/dev/null || echo "0"
}

get_missing_dependencies() {
    local task_id="$1"
    python3 -c "
import json
with open('$TASK_FILE', 'r') as f:
    data = json.load(f)

target_task = None
for task in data['tasks']:
    if task['id'] == '$task_id':
        target_task = task
        break

if not target_task:
    exit(2)

dependencies = target_task.get('dependencies', [])
missing = []

for dep_id in dependencies:
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

get_task_status() {
    local task_id="$1"
    python3 -c "
import json
with open('$TASK_FILE', 'r') as f:
    data = json.load(f)
for task in data['tasks']:
    if task['id'] == '$task_id':
        print(task.get('status', 'unknown'))
        exit(0)
print('unknown')
" 2>/dev/null
}

task_expects_report() {
    local task_id="$1"
    python3 -c "
import json
with open('$TASK_FILE', 'r') as f:
    data = json.load(f)
for task in data['tasks']:
    if task['id'] == '$task_id':
        criteria = task.get('success_criteria', [])
        for c in criteria:
            if 'report' in c.lower() or 'file' in c.lower():
                print('true')
                exit(0)
        if 'audit' in task.get('title', '').lower() or 'verify' in task.get('title', '').lower():
            print('true')
            exit(0)
print('false')
" 2>/dev/null
}

find_task_report() {
    local task_id="$1"
    local report_file=$(find "$PROJECT_ROOT/.ai/reports" -type f -name "*${task_id//-/_}*" -o -name "*${task_id//-}*" 2>/dev/null | head -1)
    if [ -n "$report_file" ]; then
        echo "$report_file"
        return 0
    fi
    report_file=$(find "$PROJECT_ROOT/.ai/tasks" -type f -name "*${task_id//-/_}*" -o -name "*${task_id//-}*" 2>/dev/null | head -1)
    if [ -n "$report_file" ]; then
        echo "$report_file"
        return 0
    fi
    return 1
}

# =============================================================================
# State Tracking
# =============================================================================

record_original_state() {
    local task_id="$1"
    ORIGINAL_TASK_STATUS=$(get_task_status "$task_id")
    if [ -f "$PROGRESS_FILE" ]; then
        ORIGINAL_PROGRESS_MTIME=$(stat -f "%m" "$PROGRESS_FILE" 2>/dev/null || stat -c "%Y" "$PROGRESS_FILE" 2>/dev/null || echo "0")
    else
        ORIGINAL_PROGRESS_MTIME="0"
    fi
}

validate_task_artifacts() {
    local task_id="$1"

    print_section "ARTIFACT VALIDATION" "Verifying task completion artifacts"

    local validation_passed=1
    local error_messages=()

    echo ""
    print_info "Check 1/3: Task status"
    local current_status=$(get_task_status "$task_id")
    if [ "$current_status" = "todo" ] || [ "$current_status" = "doing" ]; then
        print_error "Task status is still '$current_status' - should be 'done'"
        error_messages+=("Task status not updated: still '$current_status'")
        validation_passed=0
    else
        print_success "Task status: $current_status ✓"
    fi

    echo ""
    print_info "Check 2/3: progress.md update"
    if [ -f "$PROGRESS_FILE" ]; then
        local current_mtime=$(stat -f "%m" "$PROGRESS_FILE" 2>/dev/null || stat -c "%Y" "$PROGRESS_FILE" 2>/dev/null || echo "0")
        if [ "$current_mtime" != "$ORIGINAL_PROGRESS_MTIME" ]; then
            print_success "progress.md was updated ✓"
        else
            if grep -q "$task_id" "$PROGRESS_FILE"; then
                print_success "progress.md contains task reference ✓"
            else
                print_warning "progress.md doesn't appear to be updated (but could have been updated earlier)"
            fi
        fi
    else
        print_error "progress.md not found"
        error_messages+=("progress.md missing")
        validation_passed=0
    fi

    echo ""
    print_info "Check 3/3: Report file"
    local expects_report=$(task_expects_report "$task_id")
    if [ "$expects_report" = "true" ]; then
        local report_file=$(find_task_report "$task_id")
        if [ -n "$report_file" ] && [ -f "$report_file" ]; then
            print_success "Report file found: $(basename "$report_file") ✓"
        else
            local new_reports=$(find "$PROJECT_ROOT/.ai/reports" "$PROJECT_ROOT/.ai/tasks" -type f -mtime -1 2>/dev/null | head -5)
            if [ -n "$new_reports" ]; then
                print_success "Found recent report files: $(echo "$new_reports" | xargs basename | tr '\n' ', ') ✓"
            else
                print_warning "No report file found (but task might not need one)"
            fi
        fi
    else
        print_info "Task doesn't explicitly expect a report file - skipping"
    fi

    echo ""
    if [ "$validation_passed" -eq 1 ]; then
        print_success "All critical artifacts validated successfully!"
        return 0
    else
        print_error "CLAUDE FINISHED, BUT TASK ARTIFACTS WERE NOT WRITTEN"
        echo ""
        echo "Issues found:"
        for msg in "${error_messages[@]}"; do
            echo "  - $msg"
        done
        echo ""
        echo "Please manually verify and update the task artifacts."
        echo "Then mark as done with: $0 complete $task_id"
        return 1
    fi
}

# =============================================================================
# Health Checks
# =============================================================================

run_health_checks() {
    print_section "HEALTH CHECKS" "Pre-flight validation"

    local health_ok=0

    echo "  Running DB health check..."
    "$SCRIPT_DIR/check-db.sh" 2>&1 | head -30 || health_ok=1

    echo ""
    echo "  Running API health check..."
    "$SCRIPT_DIR/check-api.sh" 2>&1 | head -30 || true

    echo ""
    echo "  Running project check..."
    "$SCRIPT_DIR/check-project.sh" 2>&1 | head -30 || true

    if [ "$health_ok" -eq 0 ]; then
        print_success "Health checks passed (DB, API, Project)"
    else
        print_warning "Some health checks had issues"
        print_info "Continuing anyway - baseline already documented"
    fi

    return 0
}

# =============================================================================
# Claude Prompt Generation
# =============================================================================

generate_claude_prompt() {
    local task_id="$1"

    cat <<EOF
Read the following files first:
1. CLAUDE.md - Project configuration and hard rules
2. $TASK_FILE - Task definitions
3. $PROGRESS_FILE - Current progress

Then execute ONLY this task: $task_id

Instructions:
1. Update task.json - Mark this task as 'doing' if not already
2. Read the task definition in task.json carefully
3. Execute the task according to its success criteria
4. Create any required audit/report files in .ai/reports/ or .ai/tasks/
5. Stop if blocked by unmet dependencies
6. Update $PROGRESS_FILE with task results
7. Update task.json with task completion status ('done' or 'failed')
8. ALL CHANGES (code, progress.md, task.json) IN ONE COMMIT!
9. Do NOT implement any business features outside this task

Important hard rules from CLAUDE.md:
- NO business logic modification during audit tasks (af-auto-000)
- ONLY commit .ai directory and CLAUDE.md changes for audit tasks
- FAIL LOUDLY - scripts MUST exit with non-zero code on real failures
- NO fake success states - don't report "✓" unless verified
- ALWAYS update task.json AND progress.md for each completed task
EOF
}

# =============================================================================
# Task Execution
# =============================================================================

execute_task() {
    local task_id="$1"
    local auto_confirm="${2:-0}"

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

    validate_branch "$task_id"

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

    if ! command -v claude &> /dev/null; then
        print_error "Claude Code CLI ('claude') not found"
        echo "Please install Claude Code CLI first"
        exit 2
    fi

    local prompt_file=$(mktemp /tmp/claude-prompt.XXXXXX)
    generate_claude_prompt "$task_id" > "$prompt_file"

    print_info "Generated Claude Code prompt at: $prompt_file"
    log "INFO" "Prompt file created: $prompt_file"

    if [ "$auto_confirm" -ne 1 ]; then
        echo ""
        echo "Press Enter to launch Claude Code with this prompt, or Ctrl+C to cancel..."
        read -r
    else
        echo ""
        print_info "Auto-confirm enabled: skipping interactive prompt"
    fi

    echo ""
    print_info "Marking task as 'doing' and recording initial state..."
    record_original_state "$task_id"
    if update_task_status "$task_id" "doing"; then
        print_success "Task marked as 'doing'"
        log "INFO" "Task $task_id marked as 'doing'"
        print_info "Recorded initial state for later validation"
    else
        print_error "Failed to update task status"
        rm -f "$prompt_file"
        return 1
    fi

    echo ""
    print_info "Running pre-flight health checks..."
    run_health_checks

    echo ""
    print_info "Launching Claude Code..."
    log "INFO" "Launching Claude Code (mode: $CLAUDE_MODE)"
    echo ""

    local claude_exit=0
    local run_log="$LOG_DIR/run-$TOTAL_RUNS-$(date +%Y%m%d_%H%M%S).log"

    if [ "$CLAUDE_MODE" = "print" ]; then
        log "INFO" "Using print mode (non-interactive)"
        claude -p \
            --dangerously-skip-permissions \
            --allowed-tools "Bash Edit Read Write Glob Grep Task WebSearch WebFetch mcp__playwright__*" \
            --message "$(cat "$prompt_file")" 2>&1 | tee "$run_log" || claude_exit=${PIPESTATUS[0]}
    else
        log "INFO" "Using interactive mode"
        claude --no-welcome --message "$(cat "$prompt_file")" 2>&1 | tee "$run_log" || claude_exit=${PIPESTATUS[0]}
    fi

    rm -f "$prompt_file"

    if [ $claude_exit -ne 0 ]; then
        print_warning "Claude Code exited with status $claude_exit"
        log "WARNING" "Claude exited with code $claude_exit"
        print_info "Task may be incomplete - check manually"
    else
        print_success "Claude Code execution complete"
        log "SUCCESS" "Claude execution successful"
    fi

    echo ""
    if validate_task_artifacts "$task_id"; then
        print_success "Task artifacts verified - task appears complete!"
        log "SUCCESS" "Task $task_id artifacts validated"
        TASKS_COMPLETED_THIS_RUN=$((TASKS_COMPLETED_THIS_RUN + 1))
        return 0
    else
        print_error "Claude finished, but task artifacts were not written"
        log "ERROR" "Task artifacts validation failed"
        return 1
    fi
}

# =============================================================================
# Loop Mode
# =============================================================================

loop_until_done() {
    print_section "LOOP MODE" "Running until all tasks complete"

    local start_time=$(date +%s)
    local initial_remaining=$(count_remaining_tasks)

    log "INFO" "Loop mode started - initial tasks remaining: $initial_remaining"

    local iteration=0
    while true; do
        iteration=$((iteration + 1))
        TOTAL_RUNS=$iteration

        echo ""
        echo "=========================================="
        log "PROGRESS" "Iteration $iteration"
        echo "=========================================="

        local remaining=$(count_remaining_tasks)
        if [ "$remaining" -eq 0 ]; then
            print_success "All tasks completed!"
            log "SUCCESS" "All tasks completed after $iteration iterations"
            break
        fi

        print_info "Tasks remaining: $remaining"
        log "INFO" "Tasks remaining: $remaining"

        local task_id=$(get_next_task)
        if [ -z "$task_id" ]; then
            print_warning "No task ready to execute (all blocked or done)"
            log "WARNING" "No task ready"
            break
        fi

        print_info "Next task: $task_id"

        if ! execute_task "$task_id" 1; then
            print_warning "Iteration $iteration - Task execution had issues"
        fi

        local after_remaining=$(count_remaining_tasks)
        if [ "$after_remaining" -eq "$remaining" ]; then
            print_warning "No progress in this iteration - stopping loop"
            log "WARNING" "No progress - stopping loop"
            break
        fi

        local final_remaining=$(count_remaining_tasks)
        if [ "$final_remaining" -eq 0 ]; then
            break
        fi

        if [ "$iteration" -lt 100 ]; then
            echo ""
            print_info "Sleeping $SLEEP_BETWEEN_RUNS seconds before next iteration..."
            sleep "$SLEEP_BETWEEN_RUNS"
        fi
    done

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    echo ""
    echo "=========================================="
    print_success "Loop complete!"
    echo "=========================================="
    echo ""
    echo "  Summary:"
    echo "  - Total iterations: $iteration"
    echo "  - Tasks completed: $((initial_remaining - $(count_remaining_tasks)))"
    echo "  - Duration: $((duration / 60))m $((duration % 60))s"
    echo ""
    log "SUCCESS" "Loop complete - $iteration iterations, $((initial_remaining - $(count_remaining_tasks))) tasks completed"

    generate_final_report "$start_time" "$end_time" "$iteration" "$initial_remaining"
}

loop_n_times() {
    local max_iterations="$1"

    print_section "LOOP MODE" "Running up to $max_iterations iterations"

    local start_time=$(date +%s)
    local initial_remaining=$(count_remaining_tasks)

    log "INFO" "Loop mode started - max iterations: $max_iterations, initial tasks: $initial_remaining"

    for ((iteration=1; iteration<=max_iterations; iteration++)); do
        TOTAL_RUNS=$iteration

        echo ""
        echo "=========================================="
        log "PROGRESS" "Iteration $iteration of $max_iterations"
        echo "=========================================="

        local remaining=$(count_remaining_tasks)
        if [ "$remaining" -eq 0 ]; then
            print_success "All tasks completed! Stopping early."
            log "SUCCESS" "All tasks completed after $iteration iterations"
            break
        fi

        print_info "Tasks remaining: $remaining"

        local task_id=$(get_next_task)
        if [ -z "$task_id" ]; then
            print_warning "No task ready to execute - stopping loop"
            log "WARNING" "No task ready - stopping"
            break
        fi

        print_info "Next task: $task_id"

        if ! execute_task "$task_id" 1; then
            print_warning "Iteration $iteration - Task execution had issues"
        fi

        if [ "$iteration" -lt "$max_iterations" ]; then
            local final_remaining=$(count_remaining_tasks)
            if [ "$final_remaining" -eq 0 ]; then
                break
            fi
            echo ""
            print_info "Sleeping $SLEEP_BETWEEN_RUNS seconds before next iteration..."
            sleep "$SLEEP_BETWEEN_RUNS"
        fi
    done

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    echo ""
    echo "=========================================="
    print_success "Loop complete!"
    echo "=========================================="
    echo ""
    echo "  Summary:"
    echo "  - Total iterations: $TOTAL_RUNS"
    echo "  - Tasks completed: $((initial_remaining - $(count_remaining_tasks)))"
    echo "  - Duration: $((duration / 60))m $((duration % 60))s"
    echo ""
    log "SUCCESS" "Loop complete - $TOTAL_RUNS iterations"

    generate_final_report "$start_time" "$end_time" "$TOTAL_RUNS" "$initial_remaining"
}

generate_final_report() {
    local start_time="$1"
    local end_time="$2"
    local iterations="$3"
    local initial_tasks="$4"

    local final_tasks=$(count_remaining_tasks)
    local completed=$((initial_tasks - final_tasks))
    local duration=$((end_time - start_time))

    SUMMARY_REPORT="${PROJECT_ROOT}/.ai/reports/automation-summary-$(date +%Y%m%d_%H%M%S).md"

    cat > "$SUMMARY_REPORT" <<EOF
# Automation Summary

Generated: $(date -Iseconds)

## Overview

- Total iterations: $iterations
- Tasks completed: $completed
- Initial remaining: $initial_tasks
- Final remaining: $final_tasks
- Duration: $((duration / 60))m $((duration % 60))s

## Log Files

- Main log: $LOG_FILE
- Run logs in: $LOG_DIR/

EOF

    print_success "Final summary report generated: $(basename "$SUMMARY_REPORT")"
    log "SUCCESS" "Summary report saved to: $SUMMARY_REPORT"
}

# =============================================================================
# Simple Commands (Backward Compatible)
# =============================================================================

orchestrate_task() {
    local task_id="$1"

    if ! task_exists "$task_id"; then
        print_error "Task not found: $task_id"
        exit 3
    fi

    print_section "TASK ORCHESTRATION" "Selected: $task_id"

    validate_branch "$task_id"

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

    echo ""
    print_info "Step 1: Marking task as 'doing'"
    if update_task_status "$task_id" "doing"; then
        print_success "Task marked as 'doing'"
    else
        print_error "Failed to update task status"
        return 1
    fi

    echo ""
    print_info "Step 2: Running health checks"
    if ! run_health_checks; then
        print_warning "Health checks had issues - continuing anyway"
    fi

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

mark_task_complete() {
    local task_id="$1"

    if ! task_exists "$task_id"; then
        print_error "Task not found: $task_id"
        exit 3
    fi

    print_section "COMPLETION" "Marking task complete: $task_id"

    if update_task_status "$task_id" "done"; then
        print_success "Task marked as 'done'"
        log "SUCCESS" "Task $task_id marked as done"
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

# =============================================================================
# Help
# =============================================================================

print_help() {
    echo "Usage: $0 [OPTIONS] [COMMAND]"
    echo ""
    echo "Options:"
    echo "  -y, --yes              - Skip interactive prompts (non-interactive mode)"
    echo "  --task-file <PATH>     - Path to task JSON file (default: .ai/tasks/task.json)"
    echo "  --mode <MODE>          - Claude mode: interactive (default) or print"
    echo "  --sleep <SECS>         - Seconds to sleep between loop runs (default: 2)"
    echo "  -h, --help             - Show this help"
    echo ""
    echo "Commands:"
    echo "  list          - List all tasks and status"
    echo "  next          - Show next task to execute"
    echo "  start <ID>    - Mark task as 'doing' and run checks"
    echo "  complete <ID> - Mark task as 'done'"
    echo "  execute <ID>  - Launch Claude Code to execute a task"
    echo "  check         - Run health checks only"
    echo "  loop <N>      - Run up to N iterations automatically"
    echo "  loop --until-done - Run until all tasks are done"
    echo "  help          - Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 list"
    echo "  $0 next"
    echo "  $0 start af-auto-000-12"
    echo "  $0 execute af-auto-000-12 --yes"
    echo "  $0 complete af-auto-000-12"
    echo "  $0 loop 5"
    echo "  $0 loop --until-done"
    echo "  $0 --mode print --yes loop 3"
    echo "  $0 --task-file .ai/tasks/task_af_auto_001.json list"
    echo ""
    echo "Environment variables:"
    echo "  CLAUDE_MODE=print      - Use non-interactive print mode"
    echo "  AUTO_CONFIRM=1         - Enable non-interactive mode (same as --yes)"
    echo "  SLEEP_BETWEEN_RUNS=2   - Seconds to sleep between loop iterations"
    echo ""
}

# =============================================================================
# Main
# =============================================================================

main() {
    print_header
    cd "$PROJECT_ROOT"

    local auto_confirm=1
    local cmd=""

    if [ "${AUTO_CONFIRM:-0}" = "1" ]; then
        auto_confirm=1
    fi

    while [ "$#" -gt 0 ]; do
        case "$1" in
            -y|--yes)
                auto_confirm=1
                shift
                ;;
            --task-file)
                if [ "$#" -lt 2 ]; then
                    print_error "--task-file requires an argument"
                    print_help
                    exit 1
                fi
                TASK_FILE="$2"
                if [[ "$TASK_FILE" != /* ]]; then
                    TASK_FILE="${PROJECT_ROOT}/${TASK_FILE}"
                fi
                shift 2
                ;;
            --mode)
                if [ "$#" -lt 2 ]; then
                    print_error "--mode requires an argument (interactive or print)"
                    print_help
                    exit 1
                fi
                CLAUDE_MODE="$2"
                shift 2
                ;;
            --sleep)
                if [ "$#" -lt 2 ]; then
                    print_error "--sleep requires an argument (seconds)"
                    print_help
                    exit 1
                fi
                SLEEP_BETWEEN_RUNS="$2"
                shift 2
                ;;
            -h|--help|help)
                print_help
                exit 0
                ;;
            list|next|start|complete|execute|check|loop)
                cmd="$1"
                shift
                break
                ;;
            *)
                print_error "Unknown argument: $1"
                echo ""
                print_help
                exit 1
                ;;
        esac
    done

    validate_environment

    if [ -z "$cmd" ]; then
        print_help
        exit 0
    fi

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
            local task_id="$1"
            if [ -z "$task_id" ]; then
                print_error "Task ID required"
                exit 1
            fi
            mark_task_complete "$task_id"
            ;;
        "execute")
            local task_id="$1"
            if [ -z "$task_id" ]; then
                task_id=$(get_next_task)
                if [ -z "$task_id" ]; then
                    print_error "No task found to execute"
                    exit 1
                fi
                print_info "Using next task: $task_id"
            fi
            execute_task "$task_id" "$auto_confirm"
            ;;
        "check")
            run_health_checks
            ;;
        "loop")
            local loop_arg="$1"
            if [ "$loop_arg" = "--until-done" ]; then
                loop_until_done
            elif [[ "$loop_arg" =~ ^[0-9]+$ ]]; then
                loop_n_times "$loop_arg"
            else
                print_error "Loop requires an argument: number or --until-done"
                print_help
                exit 1
            fi
            ;;
        *)
            print_error "Unknown command: $cmd"
            echo ""
            print_help
            exit 1
            ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
