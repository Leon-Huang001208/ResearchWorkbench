# Research Workbench Phase 2B MCP Runtime Delivery Plan

## Scope

Deliver the feature-gated Research Web MCP installation, authorization and host runtime on top of the Phase 2A read-only Registry. The work remains Web-only and does not change Tauri, desktop packaging, native notifications, PostgreSQL or the research engine.

## Task 1 — Immutable installation planning and persistence

- Add the approved `mcp>=2,<3` project dependency and remove the repository-local `mcp` import collision without changing the legacy data-server behavior.
- Add strict installation request/preview/manifest models, short-lived confirmation tokens bound to a canonical SHA-256 summary, and atomic local persistence.
- Implement safe package planners for pinned npm, PyPI wheels and MCPB archives. Reject shell strings, ranges/`latest`, lifecycle hooks, missing dependency hashes, implicit environment inheritance, symlink/path escapes and digest drift.
- Add focused tests before implementation and document stable error codes.

## Task 2 — SDK host, transports and OAuth

- Wrap the official SDK for negotiated stdio and Streamable HTTP sessions; expose health probing, capabilities, tools, resources and prompts while excluding sampling, elicitation and experimental Tasks.
- Enforce HTTPS or explicit loopback HTTP, no ambient proxies, bounded redirects (same origin or same host HTTP to HTTPS only), minimal stdio environment and per-installation working directories.
- Add OAuth 2.1 PKCE/state/discovery/audience contracts with secrets stored only under `ResearchWorkbench.MCPRuntime` in the system credential store; prohibit token passthrough.
- Add transport/OAuth/resource/prompt tests using local fixtures and no external network.

## Task 3 — Authorization, approvals and atomic activation

- Persist immutable installation versions, capability/schema snapshots, canonical directory grants, risk classifications and session authorization snapshots.
- Recheck installation version, schema hash, session/automation scope, risk level and approval at each call. Require per-call approval for external-write/high-risk tools; unattended access requires read-only + explicit allow-unattended + task lock.
- Add preview/install/list/update/remove/probe/enable/disable/update/capabilities, session authorization, resource read, prompt get and approval APIs.
- Build the namespaced `mcp__{installation}__{tool}` verified declaration snapshot for the existing private loopback control plane. Activation must probe first, wait for active research to drain, restart only the dedicated runtime, and restore the prior activation snapshot on health failure.
- Add API, drift, authorization, approval, unattended and rollback tests.

## Task 4 — Product UI, docs and delivery evidence

- Upgrade Tool > MCP Market from read-only browsing to explicit preview/confirm/install and installation management without rendering remote HTML or icons.
- Keep install, enable and research authorization visually and behaviorally separate; show exact untruncated argv, source, versions, hashes and environment variable names.
- Cover keyboard/dialog behavior and 1440/1280/768/390 Light/Dark/reduced-motion browser journeys with zero external writes.
- Synchronize Research Web architecture, API atlas, development map, diagrams and `.ai/reports`; run focused/all JS and Python tests plus ruff, black, isort, mypy and repository doc gates.

## Delivery gate

Commit the feature branch, verify it, integrate from the then-latest `origin/master`, verify the merged result, publish without force push, wait for applicable CI, then clean only commits/worktrees already in the default branch. Phase 2C starts only after this gate is complete.
