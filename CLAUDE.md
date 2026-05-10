# AlphaFoundry - Claude Configuration
#
# This file defines Claude's understanding of the project
# for automated tasks and AI-assisted development.

## Project Overview
name: AlphaFoundry
type: Local-first, enterprise-ready buy-side investment research platform
languages: Python (main), HTML/CSS/JS (web UI)

## Project Structure
- core/ - Core business logic and contracts
- data_layer/ - Data access and persistence
- knowledge_layer/ - Knowledge extraction and management
- reasoning/ - Scenario analysis and reasoning
- timing_engine/ - Market timing models
- memory_learning/ - Learning from outcomes
- signal_lab/ - Feature engineering and backtesting
- reporting/ - Report generation
- app/ - API and web UI
- scripts/ - Utility scripts
- tests/ - Tests
- .ai/ - AI assistant working directory

## Task Management
- Task file: .ai/tasks/task.json
- Progress file: .ai/progress/progress.md
- Reports directory: .ai/reports/

## Status Definitions
- todo: Task not started
- doing: Task currently in progress
- blocked: Task blocked on dependencies or issues
- done: Task completed successfully
- failed: Task failed

## Current Task Set
- af-auto-000: Initial repository audit and validation

## Scripts
- .ai/scripts/check-project.sh - Check project structure and tests
- .ai/scripts/check-db.sh - Check database health
- .ai/scripts/check-api.sh - Check API health
- .ai/scripts/run-automation.sh - Orchestrate task execution

## Key Commands
- Run tests: python -m pytest tests/ -v
- Start API: python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
- Bootstrap DB: python scripts/bootstrap_db.py

## Hard Rules - THESE MUST NOT BE BROKEN

### Safety Rules
1. NO business logic modification during audit tasks (af-auto-000)
2. ONLY commit .ai directory and CLAUDE.md changes for audit tasks
3. FAIL LOUDLY - scripts MUST exit with non-zero code on real failures
4. NO fake success states - don't report "✓" unless verified
5. ALWAYS update task.json AND progress.md for each completed task
6. Use repository-relative paths ONLY - NO absolute paths

### Script Rules
7. Scripts MUST validate they are run from project root
8. Scripts MUST validate required files exist before execution
9. Scripts MUST document all assumptions and limitations
10. Scripts MUST exit codes: 0 = success, 1 = error, 2 = dependency failure

### Repository Health Rules
11. Tests are allowed to fail - baseline is already documented
12. Database connection check is NOT a full import
13. API check is NOT a full server restart (use existing if running
14. NO destructive operations in automation

## Control Layer Limitations & Assumptions
- Assumes PostgreSQL running on localhost:5432
- Assumes API might already be running on 8000
- Assumes git repository is clean
- Does NOT make irreversible changes
- Does NOT handle network failures gracefully
- Does NOT manage task dependencies (yet)
- Does NOT resume interrupted tasks (yet)
- Does NOT handle concurrent execution (yet)
