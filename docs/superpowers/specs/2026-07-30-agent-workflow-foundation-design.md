# Agent Workflow Foundation Design

## Goal

Make Research Workbench's shared agent workflow explicit and reusable across Codex and Claude Code without changing the current FastAPI + native JavaScript frontend architecture.

## Scope

Phase 1 establishes a single cross-tool rule layer, a documented task-routing policy, and three reusable project workflow skills:

- a tracked root `AGENTS.md` for rules that every coding agent must follow;
- a smaller `CLAUDE.md` that keeps Claude-specific entry points and delegates shared rules to `AGENTS.md`;
- a task-routing guide for local fast-loop, isolated worktree, and background/remote work;
- project skills for UI iteration, minimal bug fixes, and final delivery checks.

Phase 2 is deliberately limited to making the existing browser regression path reproducible and CI-visible. It does not introduce React, Vite, Storybook, Vitest, Tailwind, or a component-library migration.

## Current Constraints

- The primary application is FastAPI with native HTML, CSS, and JavaScript under `app/web/`; it is not a Vite or React application.
- Desktop changes must retain native macOS and Windows CI coverage, including sidecar build, Tauri bundle build, and health checks.
- The primary worktree currently holds an untracked root `AGENTS.md`, while the committed branch baseline has no tracked `AGENTS.md`. The working copy also contains a `.claude/rules/` tree that is ignored by Git; `CLAUDE.md` refers to it even though new clones and worktrees cannot read it. Phase 1 therefore creates and version-controls the shared file, and it must not make portable behavior depend on ignored local rules.
- Existing browser regression scripts use `playwright-core` and a locally installed Chrome, but they are not represented by a root package script or a project-installed test dependency.
- Worktrees are already in active use and must remain the default isolation mechanism for concurrent changes.

## Architecture

```text
                 Shared workflow requirements
                            |
                            v
                       AGENTS.md
                 /          |           \
                v           v            v
         Codex sessions  CLAUDE.md  project workflow skills
                              |
                              v
                optional local Claude rules

Task request --> route decision --> local fast loop | isolated worktree | background/remote task
                                  --> required evidence --> review / CI
```

`AGENTS.md` contains concise, platform-neutral requirements and links to the authoritative detailed documentation. It must not duplicate long Claude-specific procedures.

`CLAUDE.md` imports `AGENTS.md`, retains a concise project architecture summary and Claude-specific guidance that is valid in a fresh clone, and replaces the hard-coded Windows-only Python command with an explicit platform-aware command-selection rule. It may point to optional local `.claude/rules/` guidance when present, but it must not require it for normal repository work.

The new routing guide is the authority for selecting an execution mode. It defines small, interactive debugging and narrow UI confirmation as local work; concurrent or risky changes as isolated worktree work; and deterministic, long-running research, CI investigation, and review as background or remote work. It does not require any specific cloud subscription or provider.

## Components

### Shared agent rules

The tracked root `AGENTS.md` will cover:

- repository purpose and the source locations for architecture and module documentation;
- required logging, error handling, test, documentation, and evidence expectations;
- platform-aware command selection instead of a machine-specific interpreter path;
- the mandatory desktop cross-platform validation contract;
- a compact routing summary and an explicit prohibition on claiming unrun validation;
- links to the routing guide and the task-specific skills.

Ignored local `.claude/rules/` guidance remains optional personal or machine-local context. Any rule required for safe shared work belongs in the tracked `AGENTS.md` or another tracked document it links to.

### Claude entry point

`CLAUDE.md` will begin by importing `AGENTS.md`. It will retain only the portable architecture summary and Claude-specific guidance, while mentioning optional local rule files without making them prerequisites. Shared requirements will be removed rather than maintained twice.

### Task routing guide

The guide will live under `docs/` and contain a decision table, examples, boundaries, and evidence requirements. It will state that worktrees isolate concurrent modifications but do not make Windows validation optional for desktop work.

### Project workflow skills

Each skill uses a short `SKILL.md` and is discoverable by a trigger-focused description:

- `ui-iterate`: native Web UI changes that need design-rule lookup, targeted browser verification, and compact diffs.
- `bugfix-minimal`: regressions where the task must be reproduced, narrowed to root cause, and fixed without opportunistic refactoring.
- `ship-check`: completion, handoff, or review preparation where the agent must report exactly what it validated and what remains unverified.

Skills contain reusable decision guidance and refer to `AGENTS.md` for repository-wide mandates. They do not encode machine-specific paths, secrets, or provider-specific cloud commands.

## Error Handling and Safety

- Instructions must distinguish validation that ran from validation that remains required.
- Desktop-related work must label macOS-only results as macOS-only and never infer Windows support without native Windows CI evidence.
- A task with unrelated pre-existing workspace modifications must use an isolated worktree rather than stage or overwrite those changes.
- The routing guide must leave deployment, release, destructive operations, and environment-secret changes under explicit user authorization.

## Testing and Verification

Phase 1 is documentation and instruction content. Verification consists of:

1. checking Markdown links and referenced repository paths;
2. confirming `AGENTS.md` and `CLAUDE.md` do not impose contradictory Python-runtime rules or require ignored `.claude/` files;
3. checking each new skill has required frontmatter, a trigger-focused description, and a matching documentation reference;
4. running existing documentation synchronization and task-completion checks where their prerequisites are available.

Phase 2 will add a focused Node test command and a CI workflow invocation for the existing browser regression scripts. It will not be started until its separate implementation plan is approved.

## Non-goals

- No frontend framework, build-tool, design-system, or component-library migration.
- No Storybook, Vite, Vitest, React, or Tailwind adoption in this phase.
- No production deployment, release, or automation credential changes.
- No modification to existing user work in the primary workspace.
