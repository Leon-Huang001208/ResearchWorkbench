# Dollar custody series repair

Host: macOS. Task: focused bugfix / public-data acceptance. No inference, model credential changes, resident update, new dependency or other-platform dispatch.

## Reproduction and change

Baseline e45d3bc13a2e7e162f9b6c264ffaf16913a5800a incorrectly maps IMF US reserves excluding gold (TRESEGUSM052N) to foreign official Treasury custody. Prior real acceptance's captured metadata confirmed this mismatch; local regression RED requires WMTSECL1 and fails before editing.

Use [WMTSECL1](https://fred.stlouisfed.org/series/WMTSECL1), Federal Reserve H.4.1 weekly Wednesday custody level. Convert USD millions /1000, retain observation date and separate source URL; describe foreign official and international account scope, not all foreign holdings. The obsolete WMTSECL is not used. This restores intended indicator, not a scoring/method change; original X formula and schemas preserved.

Unavailable source keeps legacy values explicitly stale and blocks published state; no fallback to wrong reserves or artificial current date. Existing error/logging path retained. Gold allocation fixture and unrelated real-data gaps are out of this repair. Old visible preview preserved for comparison; corrected preview will be kept independently.

## Evidence

logs/dollar-custody-fix/red.log: reproduced failure before edit. green.log: initial five collector tests PASS. Focused regression: 20 PASS. All six Router local gates, Ruff/Black/isort/mypy PASS. Real public-source collection: six jobs PASS; WMTSECL1 observation 2026-10-07 = 2,565,477 USD millions /1000 = 2,565.477 USD billions; wrong-series request count zero. Evidence in logs/dollar-custody-fix/live/custody-proof.json. This initial run used uncommitted repair bytes atop the baseline; exact committed candidate will be checked independently. API/rendered model/Bot revision, clean installation and CI evidence remain pending. Browser automation NOT_RUN: security policy rejected local preview URL protocol validation, so no alternate browser/CDP workaround is attempted; manual preview links will be provided. No unrun check is represented as PASS.

<!-- architecture-review {"group":"frameworks","structure":"unchanged","reason":"限定既有Dollar采集器的数据源身份与展示溯源纠正，原生存储、调度、评分及唯一DSH执行链未变；无需改变公共拓扑图。","diagrams":[]} -->
