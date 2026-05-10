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
- .ai/scripts/run-automation.sh - Run full automation suite

## Key Commands
- Run tests: python -m pytest tests/ -v
- Start API: python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
- Bootstrap DB: python scripts/bootstrap_db.py

## Guidelines
1. Don't modify business logic during audit tasks
2. Use repository-relative paths (never absolute paths)
3. Commit only .ai directory changes for audit tasks
4. Update task.json and progress.md for each completed task
