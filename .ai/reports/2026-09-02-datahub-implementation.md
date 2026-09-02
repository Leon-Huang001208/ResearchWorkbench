# DataHub backend implementation — Task 1

Date: 2026-09-02. Worktree: `/Users/leon/Desktop/Projects/AlphaFoundry/.worktrees/dsh-web-v1`.
Scope: DataHub backend, fixed providers, immutable snapshots, native approval/auth bridge, API/service/launcher wiring, four Skills/persona/templates, tests and documentation. No UI source changes.

## Delivered behavior

- Five fixed public capabilities, business-only query contracts; NAV explicit range drains actual top-level TotalCount/PageSize/PageIndex rather than requested page size. Snapshot/empty/failed/partial/complete are distinct.
- Fifteen-second query, 100 pages, 5000 rows, 1MiB/response, 16MiB/query; no redirects, retries, proxy/environment auth or arbitrary endpoint.
- Cross-page identical duplicate de-duplication with partial coverage; conflicts removed from available rows; changed total/page size/repeated pages/invalid dates/numbers fail conservatively.
- Private original response and authoritative manifest; descriptor-relative NOFOLLOW IO, link/owner/permission checks, SHA256 verification; new UUID folders atomically published under read-only inputs/datasets.
- Session/parameter/schema scoped TTL caches, explicit refresh, persistent stable call receipts and pre-query cancel tombstone; cancellation/shutdown prevents snapshot publication.
- Authenticated internal query/cancel only after native directory/ancestry and native approval; private random product token never enters model prompt/script env/Web/logs. No model-key access.
- Read-only public catalog/detail/rows/download; SSE summaries; datasets excluded from ordinary files/delivery. Explicit upgrade copies verified data into a new owner/new UUID, preserves origin ID/hash/date, makes zero provider requests.
- Four Skills/persona require manifest review before two-child dataset sharing, no child refetch, limited supported calculations and consistent source IDs in XLSX/DOCX/HTML.

## TDD evidence

Interpreter in all commands below: `/Users/leon/Desktop/Projects/AlphaFoundry-runtime-agnostic-core/.venv/bin/python`.

| RED command / observation | GREEN evidence |
| --- | --- |
| `python -m pytest tests/research_web/test_datahub.py::test_datahub_module_exists --confcutdir=tests/research_web -q`: 1 failed, DataHub implementation missing. Initial fixture-based exploratory run had 28 setup failures for the same missing module; explicit assertion then established RED. | New contracts/providers/snapshots progressed to 28 passed/1 test fixture failure, then 30 passed including API. |
| `python -m pytest tests/research_web/test_datahub.py -k pagination_inconsistencies --confcutdir=tests/research_web -q`: same-date duplicate incorrectly complete, 1 failed/5 passed. | Conservative partial status with pagination_complete=true when source ends but unique count is below provider total. |
| `python -m pytest tests/research_web/test_api.py::test_datahub_read_only_catalog_authenticated_queries_and_upgrade --confcutdir=tests/research_web -q`: 404 capability endpoint. | Capability/auth/read/download/upgrade test passes, without network outside MockTransport. |
| `node --test --test-name-pattern='approved native query' tests/javascript/research_web_public_data.test.mjs`: old JS rejected date parameters. | All 6 rewritten native bridge tests pass; old upstream-parser tests were migrated into Python DataHub coverage. |
| `python -m pytest tests/research_web/test_datahub.py -k 'real_holdings or csv_preserves' --confcutdir=tests/research_web -q`: 2 failed, real br header not recognized and negative numeric text escaped. | Real structure normalized for matching, units preserved; numeric text remains numeric-compatible while formula text escapes. |
| `python -m pytest tests/research_web/test_datahub.py::test_profile_malformed_real_cells_do_not_merge_fields_and_decorated_missing_is_null --confcutdir=tests/research_web -q`: code/type cells merged. | Stop at nested following th/td; decorated missing fee returns null with original text. |
| `python -m pytest tests/research_web/test_datahub.py::test_launcher_prepares_private_bridge_config_without_secret_environment --confcutdir=tests/research_web -q`: datahub_url argument absent. | Trusted launcher configuration works on synthetic source/data; token absent from env/YAML. |
| `python -m pytest tests/research_web/test_datahub.py -k page_size_change --confcutdir=tests/research_web -q`: wrong failure reason for changed provider page size. | Page-size change, row budget and total-byte budget have explicit partial reasons. |
| `python -m pytest tests/research_web/test_datahub.py -k non_ascii --confcutdir=tests/research_web -q`: hmac non-ASCII TypeError. | Auth rejects non-ASCII and empty userinfo safely. One intermediate test append caused a collection SyntaxError, corrected before this RED run. |

## Actual final validation

- `DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness python -m pytest tests/research_web --confcutdir=tests/research_web -q`: **115 passed in 13.58s**. Includes real macOS Seatbelt nested datasets read-only/private control canary; synthetic provider responses, no real research tools.
- `DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness node --test tests/javascript/research_web*.test.mjs`: **32 passed**, zero skipped, pinned actual DSH schema converter included.
- `python -m ruff check app/research_web tests/research_web`: passed.
- `python -m black app/research_web tests/research_web --check`: passed, 30 files unchanged.
- `python -m isort app/research_web tests/research_web --check-only`: passed.
- `python -m mypy app/research_web --exclude '/skills/' --follow-imports=skip`: passed, 18 source files. Reports normal untyped-body notices; no claim of full strict typing.
- `python -m mypy app/research_web/datahub --follow-imports=skip --check-untyped-defs`: first found two annotation/call-argument issues, fixed; **passed on 6 source files**.
- Formatting applied only to owned changed Python files using isort and black.
- `git diff --check`: passed.
- `python scripts/check_task_completion.py`: passed before/after staging.
- `python scripts/check_doc_sync.py`: passed; script reports no matching source-prefix rules for app/research_web (documentation updated manually, not evidence of exhaustive doc coverage).
- Final self-review added a RED assertion for formula-style CSV headers (not only values), then fixed header escaping; target DataHub suite **37 passed**, ruff/black/isort and check-untyped-defs mypy passed again.

## Source/test/document mapping

| Source | Tests | Docs |
| --- | --- | --- |
| datahub/contracts.py, providers.py | test_datahub.py validation, actual 20-row pagination, duplicate/conflict/size/deadline, real HTML structures | research-web-datahub.md / public-data.md |
| datahub/security.py, snapshots.py, __init__.py | private config/link/hash/session/cache/receipt/cancel/upgrade tests; test_sandbox.py real canary | research-web-datahub.md |
| datahub/routes.py, main.py, service.py, store.py | test_api.py and full original API/artifact/delivery regression | research-web.md, DEVELOPMENT_MAP.md, CHANGELOG.md |
| runtime/public-data.mjs, launch_runtime.py | native JS 6 tests and synthetic launcher test | research-web-public-data.md / datahub.md |
| four SKILL.md + research.cordis.yml | original guard/schema/full regression; source inspection; actual model behavior still pending | each Skill's templates/report.md + datahub.md |

## Limitations / handoff

No service start/restart, credentials inspection, installs, external writes, main-workspace/3080 changes or subagents were performed by this implementation worker.
The parent separately performed and recorded live source probes: NAV2025 243 rows/13 pages; profile16 fields; distributions25 rows; holdings2025 220 rows over four report periods. Those are parent evidence, not this worker's live-model acceptance.
UI, real native approval-to-provider-to-two-agent-to-report behavior and browser checks are the parent's next tasks. Skill instructions do not prove every future generated workbook obeys them.
No Linux/Windows/multi-user/distribution release claims. Single worker and local filesystem only; no global disk quota or large-catalog performance claim. Whole repository checks/Windows CI are not applicable to this Web-only bounded module.
