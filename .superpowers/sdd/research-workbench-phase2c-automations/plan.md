# Research Workbench Phase 2C Automation Delivery Plan

## Scope

Deliver feature-gated, version-locked Research Web Automations and outbound delivery on top of the Phase 2B MCP Host. Keep the change Web-only: no Tauri, desktop packaging, native notifications, PostgreSQL, or second research engine.

## Task 1 — Persistent models and scheduling

- Add strict Automation, AutomationRun, schedule, delivery-channel and migration models in the existing local atomic index.
- Lock target kind, id, version and content SHA, plus input, workspace, output and allowed MCP tool snapshots.
- Implement one-time, daily, weekly and monthly IANA schedules with month-end fallback and explicit DST behavior.
- Rebuild only the next in-memory trigger from JSON facts and coalesce downtime to the latest missed run.

## Task 2 — Execution, recovery and MCP guards

- Create an independent Claw session for every trigger, reject overlaps and record skipped/version-blocked/interrupted outcomes.
- Never auto-retry research; create a linked Run for explicit manual retry.
- Recheck Automation MCP locks against active installation version, schema hash, read-only policy and unattended permission for each call.
- Recover only confirmable sessions after restart; do not silently upgrade a capability or rerun interrupted research.

## Task 3 — Delivery and report-schedule migration

- Store channel secrets only in `ResearchWorkbench.Delivery`; expose non-sensitive projections through the API.
- Support SMTP, signed generic Webhook, Feishu, WeCom and DingTalk with independent 5/30/120-second delivery retries and stable event IDs.
- Keep research and delivery status independent, with attachments/artifact references opt-in per Automation.
- Preview and atomically apply selected legacy report-schedule migrations; preserve both sides on failure.

## Task 4 — UI, documentation and delivery evidence

- Upgrade Workflow > Plans with Automation, recent runs, next-run, channel configuration and legacy schedule compatibility areas.
- Add API, schedule, recovery, delivery, security and responsive browser tests for 1440/1280/768/390 Light/Dark/reduced-motion.
- Synchronize architecture, API atlas, development map, appearance, diagrams and `.ai/reports`.
- Commit, integrate from current `origin/master`, verify, publish without force push, wait for CI, and clean only merged worktrees/branches.

## Delivery gate

Keep all three Phase 2 feature flags default-off in this delivery. After CI passes, use a separate managed delivery to default-enable the Registry, Runtime and Automation flags together, re-run applicable tests and CI, then clean both deliveries.
