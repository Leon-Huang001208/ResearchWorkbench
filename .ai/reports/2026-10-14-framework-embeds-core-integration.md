# Embedded framework core integration

architecture-review: Native Gold/Dollar data and DSH contracts retained; same-origin iframe presentation and nine static catalog entries added.

Host: macOS. Task: feature development. No paid model calls, deployment, resident service update, new dependency or other-platform dispatch.

Base: d8127c300b1a722b01f41a318bd9d47901067bf8. Source: d11e7b2369c82e571e1a4f6599a4e5711cd5998f and f68372fb07429a9e284e867ab033b07ed24d82c8, cherry-picked into an isolated managed worktree. The controller generated a duplicated slug in the branch name; identity follows the managed receipt rather than manually changing its branch.

## Data mapping

| Dashboard | Native fields | Dates, units and gaps | Unsupported |
| --- | --- | --- | --- |
| Gold | market_context, pricing_drivers, supply_demand, cycle_macro, options, allocation_context, research_state, events, evidence | Per-block as_of/checked_at/status/sources/failure_code; original values and units; snapshot gaps/revision | Backtest, strategy, model-fit |
| Dollar | quantity_q, price_p, fiscal_g, plumbing_m, cross_border_x, transmission, research_state, events, evidence | Native series.unit/date and per-block metadata; score/null/range retained | Backtest, strategy, model-fit |
| Other nine | Repository static builds and imported JSON | imported_at=2026-10-14 means import date only; no live-data claim; coverage=0; Bot rejected | Native collection and Bot |

## Actual initial evidence

- Main checkout venv lacked pytest: environment failure retained in logs/framework-embeds-core/source-frameworks.log.
- Existing test venv reproduced source branch: 6 PASS / 3 FAIL, in source-frameworks-with-tests.log. Gold schema and section failures were caused by replacement with embedded stores; the third was a stale fixture missing credentials.describe.
- Backend repair first attempt: 15 PASS / 1 FAIL. Preset routing test also lacked admitted supplier data; fixture isolates routing while a new negative test proves production data admission remains rejected.
- Backend second attempt: 17 PASS. Frontend first attempt: 17 PASS; later full evidence will be recorded separately.

The exact asset inventory is logs/framework-embeds-core/asset-inventory.json with per-file size and SHA-256. It is local evidence, not a completeness or supplier certification. Source failure report is retained.

## Remaining acceptance

Browser, full Router, macOS clean install, current-candidate CI and independent review pending. Real supplier/model generation and Windows/Linux native execution NOT_RUN. No success is claimed for pending checks.

<!-- architecture-review {"group": "ui", "structure": "unchanged", "reason": "仅在既有浏览器和Host框架边界内增加同源页面资源与展示适配，部署节点、采集快照归属及唯一DSH执行链不变；公共拓扑图无需新增节点，协议和界面变化已同步模块文档。", "diagrams": []} -->

<!-- architecture-review {"group": "research-api", "structure": "unchanged", "reason": "仅在既有浏览器和Host框架边界内增加同源页面资源与展示适配，部署节点、采集快照归属及唯一DSH执行链不变；公共拓扑图无需新增节点，协议和界面变化已同步模块文档。", "diagrams": []} -->

<!-- architecture-review {"group": "frameworks", "structure": "unchanged", "reason": "仅在既有浏览器和Host框架边界内增加同源页面资源与展示适配，部署节点、采集快照归属及唯一DSH执行链不变；公共拓扑图无需新增节点，协议和界面变化已同步模块文档。", "diagrams": []} -->

<!-- architecture-review {"group": "research-api-contract", "structure": "unchanged", "reason": "仅在既有浏览器和Host框架边界内增加同源页面资源与展示适配，部署节点、采集快照归属及唯一DSH执行链不变；公共拓扑图无需新增节点，协议和界面变化已同步模块文档。", "diagrams": []} -->

## Feature implementation evidence

- Spec independent review PASS after iframe remount ack reuse P2 was fixed. Python quality approved; JavaScript quality approved after short-viewport clipping P2 fixed.
- Native iframe adapter preserves all canonical Gold/Dollar fields including allocation_context, flows, source units/links, per-block gaps and native scores. Source imported compiled UI is not executed for core; a canonical data-adapted dashboard preserves gold/blue sidebar-grid language.
- Browser synthetic Runtime: 26 checks PASS, zero page errors, zero Gold/Dollar data/api JSON reads; both themes at 1440/1024/768/390, nine static dated entrances, and iframe bottom reachable at 390x700. Bot protocol exercised without model inference. A first selector failure and fixture model-catalog failure remain in earlier logs; final fixture supplies empty model catalog correctly.
- Router L4 local second attempt passed nine gates; file index initially stale after typed-config addition, regenerated and final standalone check PASS. Final immutable integration gates still required.
- Ruff/Black/isort PASS. Mypy imported closure 14 diagnostics in three baseline files; same 14 baseline diagnostics, no new diagnostics and zero diagnostics in nine changed framework modules. Not described as full Mypy PASS.
- macOS locked clean installation initially failed for missing Node-API headers and then Git network timeout. Task-private existing Node24 plus already locked Koffi Node-API headers and command-scoped system proxy allowed actual fixed DSH build and install; no system/global changes, new project dependencies or Key handling. Lifecycle/Doctor still pending.
- Master advanced to a2a1223d by PR100; managed prepare will merge and independently reverify that newer candidate before publication.

Evidence root: logs/framework-embeds-core/. Source reports and initial failures retained. CI, real model and suppliers, Windows/Linux acceptance not inferred from these local checks.
