# Agent Workflow Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Create a portable, shared agent workflow for Codex and Claude Code, with explicit task routing and reusable project skills, without changing application behavior.

**Architecture:** A tracked root AGENTS.md becomes the cross-tool rule layer. CLAUDE.md imports it and retains only portable Claude-specific guidance. A tracked routing document and three workflow skills under .agents/skills/ provide reusable task decisions; ignored .claude/ files remain optional local context.

**Tech Stack:** Markdown, Git worktrees, existing Python documentation-check scripts, agent-skill SKILL.md metadata.

---

## File map

| Path | Change | Responsibility |
|---|---|---|
| AGENTS.md | Create | Compact, tracked rules shared by all coding agents. |
| CLAUDE.md | Modify | Import the shared rules and retain only portable Claude-specific context. |
| docs/AGENT_WORKFLOW.md | Create | Routing decision table, boundaries, and evidence policy. |
| docs/FILE_GUIDE.md | Modify | Index tracked agent instructions and workflow skills; mark .claude/ as local-only. |
| docs/REFERENCE.md | Modify | Correct the root-tree reference so it does not imply ignored .claude/ content is shared. |
| .agents/skills/{ui-iterate,bugfix-minimal,ship-check}/SKILL.md | Create | Triggerable shared process guidance. |
| .agents/skills/{ui-iterate,bugfix-minimal,ship-check}/README.md | Create | Human-readable documentation for each new skill. |

### Task 1: Create the shared agent contract

**Files:**
- Create: AGENTS.md
- Reference: docs/ARCHITECTURE.md, docs/DEVELOPMENT_MAP.md, docs/desktop_packaging.md, docs/AGENT_WORKFLOW.md

- [ ] **Step 1: Confirm the isolated branch has no tracked shared rule file**

Run:

~~~bash
test ! -e AGENTS.md
git ls-tree -r --name-only HEAD | rg '^(AGENTS\.md|\.claude/)'
~~~

Expected: the commands confirm that neither a tracked root AGENTS.md nor tracked .claude/ rules are available on a fresh branch.

- [ ] **Step 2: Create the concise shared rule file**

Write AGENTS.md with these exact sections and requirements:

~~~md
# AlphaFoundry Agent Rules

## Start here
- Reply in Chinese unless the user requests another language.
- Before modifying an existing file, read it and its relevant module documentation.
- Read docs/ARCHITECTURE.md and docs/DEVELOPMENT_MAP.md before source-code changes.
- Use docs/AGENT_WORKFLOW.md to choose local, worktree, or background execution.

## Engineering requirements
- New or changed code must include structured logging through the project logging facilities and explicit error handling.
- Python source changes require relevant tests, documentation updates, a task report under .ai/reports/, and the completion checks required by the affected subsystem.
- Do not claim a command, test, browser check, or platform validation passed unless it ran in the current task and its result was checked.
- Do not install Python packages without user approval and a stated purpose.

## Commands and platforms
- Use the Python interpreter documented by the active platform environment; never copy another operating system's absolute interpreter path.
- Use python -m pytest, ruff check ., black . --check, isort . --check-only, and the relevant mypy targets when they apply to the changed scope.
- Desktop-related changes must follow docs/desktop_packaging.md: native Windows CI builds and health checks are required before claiming Windows support, and release work also requires a real Windows installation smoke test.

## Safety and delivery
- Do not overwrite unrelated changes; use an isolated Git worktree for concurrent, risky, or long-running changes.
- Do not perform destructive, release, secret, or external coordination actions without explicit user authorization.
- Final handoff states changed files, commands actually run, evidence, unverified items, and remaining risks.

## Reusable workflows
- Use .agents/skills/ui-iterate/ for native Web UI work.
- Use .agents/skills/bugfix-minimal/ for a focused regression fix.
- Use .agents/skills/ship-check/ before declaring a task ready for review or handoff.
~~~

- [ ] **Step 3: Verify the shared contract is portable and complete**

Run:

~~~bash
rg -n 'C:\\|/Users/|\.claude/rules|Windows CI|docs/AGENT_WORKFLOW.md|ship-check' AGENTS.md
test "$(wc -l < AGENTS.md)" -le 80
git diff --check -- AGENTS.md
~~~

Expected: no machine-specific interpreter path or mandatory .claude/rules reference; the file contains the routing, Windows-CI, and skill references; whitespace validation passes.

- [ ] **Step 4: Commit the shared contract**

~~~bash
git add AGENTS.md
git commit -m "docs: add shared agent contract"
~~~

### Task 2: Make Claude guidance portable and non-duplicative

**Files:**
- Modify: CLAUDE.md
- Reference: AGENTS.md, docs/ARCHITECTURE.md, docs/DEVELOPMENT_MAP.md

- [ ] **Step 1: Preserve only Claude-specific architecture facts**

Read CLAUDE.md. Retain its architecture diagram and the model gateway, blackboard, Signal Lab, and connector lifecycle invariants. Remove requirements now owned by AGENTS.md.

- [ ] **Step 2: Replace the non-portable entry-point content**

Make CLAUDE.md start with:

~~~md
# Claude Code additions

@AGENTS.md

This file contains only Claude Code guidance that is not already shared through AGENTS.md.
~~~

Keep a compact Claude-specific workflow section:

~~~md
## Claude-specific workflow
- Use Playwright MCP after application code changes when a live browser check is feasible; capture a screenshot when it is the evidence for a visual or interaction change.
- .claude/ is ignored local context. Read optional files there only when they exist; do not treat their absence as a blocker and do not require them for normal repository work.
- Use Claude subagents only for independent repository exploration or verification tasks; keep narrow edits in the primary session.
~~~

Replace the hard-coded interpreter section with:

~~~md
## Runtime selection

Use the Python interpreter provided by the active operating system environment. On Windows, activate the documented alphafoundry environment before invoking Python; on macOS and Linux, use the repository's configured development interpreter. Never copy a platform-specific absolute interpreter path into a cross-platform command.
~~~

Retain the development command block, but replace literal Python invocations with python -m where appropriate. Remove repeated mandatory test, documentation, final-response, and task-report lists that AGENTS.md now owns.

- [ ] **Step 3: Check import and optional-local behavior**

Run:

~~~bash
rg -n '^@AGENTS\.md$|\.claude/ is ignored local context|C:\\Users|/Users/|docs/AGENT_WORKFLOW.md' CLAUDE.md
git diff --check -- CLAUDE.md
~~~

Expected: exactly one active AGENTS.md import; no hard-coded machine path; ignored local rules are explicitly optional; whitespace validation passes.

- [ ] **Step 4: Commit the Claude entry-point revision**

~~~bash
git add CLAUDE.md
git commit -m "docs: align Claude entry point with shared rules"
~~~

### Task 3: Publish routing policy and correct repository documentation

**Files:**
- Create: docs/AGENT_WORKFLOW.md
- Modify: docs/FILE_GUIDE.md
- Modify: docs/REFERENCE.md
- Reference: docs/desktop_packaging.md, .github/workflows/desktop-verify.yml

- [ ] **Step 1: Create the routing guide**

Add a Task routing table with these rows:

| Route | Select it when | Required evidence | Do not use it when |
|---|---|---|---|
| Local fast loop | The change is narrow, needs immediate judgment, and does not conflict with another active modification. | Targeted command or browser result and a concise diff review. | The task is long-running, modifies a shared area concurrently, or needs an alternative implementation explored. |
| Isolated worktree | The task is concurrent, risky, spans multiple files, or needs a clean comparison branch. | Worktree path, branch, targeted validation, and an explicit integration plan. | The task only needs a trivial read-only inspection or a one-line local confirmation. |
| Background or remote task | Acceptance criteria are stable and the work is deterministic but long-running: repository exploration, CI-log analysis, review, or a bounded implementation. | Task scope, diff or report, commands run, and unverified constraints. | It requires an interactive secret, destructive action, release decision, or continual human design judgment. |

Also include sections named Routing rules, Desktop exception, Evidence and handoff, and Examples. State that a worktree prevents file conflicts but never replaces native Windows CI or real-Windows release smoke testing for desktop work.

- [ ] **Step 2: Update docs/FILE_GUIDE.md**

Replace the current .claude/ root description with these rows:

~~~md
| AGENTS.md | 已跟踪的跨工具 Agent 规则入口 |
| .agents/skills/ | 已跟踪的项目工作流与金融数据 skills |
| .claude/ | 本机 Claude 可选配置；被 Git 忽略，不作为共享规则来源 |
~~~

Add docs/AGENT_WORKFLOW.md to the active-document list with the description Agent 任务路由、隔离与交付证据规范.

- [ ] **Step 3: Correct docs/REFERENCE.md**

In the root-tree section, replace the shared .claude/ entry with:

~~~text
├── AGENTS.md                  # 跨工具 Agent 共享规则
├── .agents/skills/            # 已跟踪的项目 skills
├── .claude/                   # 本机可选 Claude 配置（Git 忽略）
~~~

- [ ] **Step 4: Verify all three documents agree**

~~~bash
rg -n 'AGENT_WORKFLOW|跨工具 Agent|本机.*Claude|Windows CI|安装级' \
  docs/AGENT_WORKFLOW.md docs/FILE_GUIDE.md docs/REFERENCE.md
git diff --check -- docs/AGENT_WORKFLOW.md docs/FILE_GUIDE.md docs/REFERENCE.md
~~~

Expected: each document labels .claude/ as optional/local and points to the tracked shared workflow; whitespace validation passes.

- [ ] **Step 5: Commit workflow documentation**

~~~bash
git add docs/AGENT_WORKFLOW.md docs/FILE_GUIDE.md docs/REFERENCE.md
git commit -m "docs: document agent task routing"
~~~

### Task 4: Add and verify reusable workflow skills

**Files:**
- Create: .agents/skills/ui-iterate/SKILL.md
- Create: .agents/skills/ui-iterate/README.md
- Create: .agents/skills/bugfix-minimal/SKILL.md
- Create: .agents/skills/bugfix-minimal/README.md
- Create: .agents/skills/ship-check/SKILL.md
- Create: .agents/skills/ship-check/README.md
- Create: .ai/reports/test_report_agent_workflow_foundation.md
- Reference: AGENTS.md, docs/frontend/FRONTEND_WORKFLOW.md, docs/frontend/COMPONENT_RULES.md, docs/AGENT_WORKFLOW.md

- [ ] **Step 1: Establish the skills' red tests before authoring them**

**REQUIRED BACKGROUND:** Read test-driven-development and writing-skills before running this step.

Use one fresh agent per pressure scenario without giving it a project-skill file. Record observed gaps in the task report:

~~~text
UI scenario: “Refine the native Button states in app/web without changing public APIs; prove hover, disabled, loading, and danger behavior.”
Bug scenario: “A focused report-project request returns the wrong template after a recent change. Find the smallest root cause and fix it without refactoring unrelated code.”
Handoff scenario: “Prepare a task that changed a route, test, and documentation for review. State only verified results.”
~~~

Expected baseline failures: the UI response omits a state or browser evidence; the bug response proposes a broad refactor or lacks a reproduction; the handoff response claims validation without command evidence or omits risks.

- [ ] **Step 2: Write the three minimal SKILL.md files**

Each file frontmatter follows:

~~~md
---
name: skill-directory-name
description: Use when specific trigger conditions only; do not summarize the workflow.
---
~~~

The ui-iterate skill requires: read AGENTS.md and the frontend design documents; identify the specific existing selector/component; preserve public API unless authorized; enumerate relevant visual states; make the smallest diff; run targeted browser evidence where feasible; state every unverified state.

The bugfix-minimal skill requires: reproduce before editing; identify the narrowest root cause; write or update the closest regression test; avoid unrelated refactoring; run the focused test after the fix; distinguish a verified fix from an unverified hypothesis.

The ship-check skill requires: inventory changed files; map each source change to test/document/evidence requirements; run only applicable checks; report commands and results exactly; label omitted checks and platform limitations; stop instead of claiming completion when a required check fails.

- [ ] **Step 3: Write matching concise README.md files**

Each README has a title, 触发场景, 使用方式, and 交付物. It links to its sibling SKILL.md, refers to AGENTS.md for repository-wide rules, and does not repeat the full workflow.

- [ ] **Step 4: Run the green pressure scenarios**

Use a fresh agent for each scenario. Provide only the matching skill path and the same scenario text from Step 1. Confirm the output now includes the state/reproduction/evidence gates and does not invent validation. Save the before/after results in .ai/reports/test_report_agent_workflow_foundation.md.

- [ ] **Step 5: Validate metadata and documentation pairs**

~~~bash
for skill in ui-iterate bugfix-minimal ship-check; do
  test -f ".agents/skills/$skill/SKILL.md"
  test -f ".agents/skills/$skill/README.md"
  rg -q "^name: $skill$" ".agents/skills/$skill/SKILL.md"
  rg -q '^description: Use when ' ".agents/skills/$skill/SKILL.md"
  rg -q "SKILL.md" ".agents/skills/$skill/README.md"
done
git diff --check -- .agents/skills .ai/reports/test_report_agent_workflow_foundation.md
~~~

Expected: all six skill files have discoverable metadata and matching human documentation; the report records the red/green evidence; whitespace validation passes.

- [ ] **Step 6: Commit skills and evidence**

~~~bash
git add .agents/skills/ui-iterate .agents/skills/bugfix-minimal .agents/skills/ship-check \
  .ai/reports/test_report_agent_workflow_foundation.md
git commit -m "docs: add reusable agent workflow skills"
~~~

### Task 5: Run final documentation and scope verification

**Files:**
- Verify: all files listed in the file map
- Reference: docs/superpowers/specs/2026-07-30-agent-workflow-foundation-design.md

- [ ] **Step 1: Check approved scope**

~~~bash
git diff --name-only f448f91bce27add14a4fb032412c1fb286442213..HEAD
git status --short
~~~

Expected committed changes are limited to the approved design document, shared rules, Claude entry point, routing/docs indexes, three skills, and the skill evidence report; no application source, dependency manifest, CI workflow, or desktop packaging file changes.

- [ ] **Step 2: Run documentation-oriented completion checks**

~~~bash
python scripts/check_task_completion.py
python scripts/check_doc_sync.py
git diff --check f448f91bce27add14a4fb032412c1fb286442213..HEAD
~~~

Expected: both project scripts report no source files requiring additional test or documentation sync, and Git reports no whitespace errors.

- [ ] **Step 3: Read final files as an agent would**

~~~bash
sed -n '1,220p' AGENTS.md
sed -n '1,220p' CLAUDE.md
sed -n '1,260p' docs/AGENT_WORKFLOW.md
for skill in ui-iterate bugfix-minimal ship-check; do
  sed -n '1,220p' ".agents/skills/$skill/SKILL.md"
done
~~~

Expected: no shared requirement depends on an ignored .claude/ path; all reusable workflows direct agents to evidence-based, non-destructive execution.

- [ ] **Step 4: Commit the plan record if it is not already committed with implementation**

~~~bash
git add docs/superpowers/plans/2026-07-30-agent-workflow-foundation.md
git commit -m "docs: add agent workflow implementation plan"
~~~
