# Module: app/web

## Responsibility

`app/web` provides the Web Workbench UI, including dashboard, research interface, candidate review, and learning center.

---

## Design Rules

- Keep frontend logic organized by feature
- Use consistent styling patterns
- Follow accessibility best practices
- Make API dependencies explicit
- Test main user flows in browser
- Update UI docs when surface changes

---

## Files

### `app/web/templates/*.html`

Purpose:
- Jinja2 templates for HTML pages
- Page structure and layout
- Report template workbench layout, including the top-toolbar upload action, source editor, YAML/Prompt source switcher, edit/save controls, generate/download actions, and generated Word preview container

Update this section when:
- New pages are added
- Layout structure changes
- Template organization changes

### `app/web/static/*.js`

Purpose:
- Frontend JavaScript logic
- The Workbench registers a page-level `keydown` handler during `DOMContentLoaded`: `F5`, macOS `Cmd+R`, and Windows/Linux `Ctrl+R` prevent their browser default and call `window.location.reload()`, even when an input has focus; no native Tauri shortcut, sidecar restart, or HMR behavior is involved.
- API client interactions
- User interface behavior
- Asset analysis K-line chart uses ECharts for a Wind-style terminal panel with candlestick/volume/MACD/KDJ/RSI rendering, `dataZoom` drag/scroll zoom with visible-range y-axis recalculation, crosshair tooltip, cursor-following color-coded MA/BOLL value labels, cursor-following VOL/MACD/KDJ/RSI panel labels, daily/weekly/monthly aggregation, a one-year first-load request with an initial recent-120-bar viewport, mutually exclusive MA/BOLL/naked-candle overlay modes, and a right-side ordinary chip distribution chart that uses the current visible range start through the active K-line, shares the main price-axis range, and marks chip peak, peak upper/lower boundaries, current price, and average cost.
- External chart libraries load asynchronously so CDN delays do not block the local workbench startup or asset search flow; the asset K-line panel shows a loading notice if ECharts is still unavailable after data returns.
- Report template workbench logic keeps `report_config.yaml` and `prompt_templates.md` as separate editable sources. The editor opens read-only, requires an explicit edit action, saves project-backed sources through `PUT /api/report-projects/{slug}/source`, and falls back to local drafts for non-project templates.
- Placeholder mapping shows every Word placeholder in first-seen order, builds draft mappings for missing entries, and uses the explicit `type` as the output shape. `paragraph` has an explicit `mode`; the Excel-data-plus-evidence writing flow uses `type: paragraph` with `mode: data_template_plus_evidence_ai`. Retired paragraph aliases (`prompt`, `ai_text`, `composite_market_review`) are not normalized or saved, so one project has one unambiguous configuration model.
- Report rendering uses `/api/report-projects/{slug}/render`, shows download and preview actions, and loads the inline DOCX HTML preview from the returned `preview_url`.
- Fund Intelligence panel logic lives in `app/web/static/js/funds.js` and calls `/api/funds/{symbol}`, `/api/funds/{symbol}/exposure`, `/api/funds/portfolio/exposure`, and `/api/funds/ingest` for fund detail, exposure, portfolio look-through, and structured row ingestion.
- 系统配置首页以紧凑进度和连接状态概览展示配置完成情况；可按状态筛选卡片，在窄屏下卡片会自适应排列。“刷新状态”只重新读取当前状态，并清除本次会话中临时的连接测试结果，不会测试连接或保存配置。
- 配置卡片会打开对应的编辑弹窗。弹窗会清楚显示尚未添加的账号或 Key，并以更紧凑的字段布局呈现可编辑项；支持测试的配置会说明“测试连接不会保存当前更改”，主要操作为“保存更改”。
- 由当前启动配置管理的字段仍会保持只读，并在受影响字段、行或集合附近给出说明；秘密值不会回填到界面。Provider、任务路由和账号/Key 池按原子集合锁定：任一受管项会使该集合只读且不随保存提交，未受管的同分区独立设置仍可保存。
- 当前环境与能力诊断为只读信息：不读取或导出秘密，也不生成动态表单。`psql` 可用仅表示命令可被发现，不代表 PostgreSQL 或 pgvector 已就绪；iFinD SDK 仅是本机依赖提示，Wind 在非 Windows 平台不适用，Windows 仍须以真实 Excel 验证。
- 市场面板仅在可见、处于市场标签页且交易时段内自动刷新。Wind 市场数据的前端轮询与后端工作簿缓存统一为 30 秒；手动刷新仍立即执行。

Update this section when:
- New JS modules are added
- API interaction patterns change
- UI behavior changes

### `app/web/static/*.css`

Purpose:
- Styling for the web interface
- Visual design and layout
- Report preview styling (`.report-preview-*`, `.docx-preview-*`) and template source switcher/read-only/editor states
- Template upload action now lives in the template page top toolbar (`.iphone-upload-btn`) instead of the old fixed dock

Update this section when:
- Visual design changes
- Layout styling changes
- New components are styled
- Fund Intelligence styles include compact metric cards, holdings tables, exposure bars, portfolio look-through output, and structured ingestion status.

### `app/web/main.py`

Purpose:
- FastAPI routes for serving the web interface
- Template rendering endpoints

Update this section when:
- New routes are added
- Template rendering logic changes

---

## Required Tests

- Browser verification via Playwright MCP
- Page load verification
- Main interaction flow testing
- Frontend static regression tests for template workbench markup, source switching, placeholder mapping, upload button placement, and preview styles

---

## Required Documentation Updates

When files in this module change, check:
- `docs/modules/app_web.md`
- `docs/ARCHITECTURE.md`
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`
- `docs/generated/py_file_index.md`

---

## Recent Changes

- 2026-07-26: 完善系统配置界面：首页提供紧凑进度、连接状态概览和状态筛选，卡片在窄屏下自适应排列；“刷新状态”只重新读取状态，不测试连接或保存配置。编辑弹窗显示空账号/Key 状态、采用紧凑字段布局，并明确说明连接测试不会保存更改；“保存更改”为主要保存操作。环境管理的配置仍保持锁定，秘密值不回填。
- 2026-07-26: 系统配置页新增健康总览和卡片操作说明；首次配置引导已在后续迭代中简化为紧凑进度。连接测试结果仅在当前会话中显示，重新检测配置后会清除，避免把短暂检测结果误作持久运行状态。
- 2026-07-26: 增加只读环境能力诊断，展示安全的运行环境、路径与能力信息；其状态不替代真实数据库连接或 Windows Excel/Wind 验证。
- 2026-07-26: 环境变量锁定提示迁移为配置弹窗内的字段、动态行或受管集合上下文说明；Provider、任务路由和账号/Key 池采用原子集合锁定，任一受管键均使整个集合只读且不提交，首页不展示受管名单，前端内部键名仅用于锁定判断。
- 2026-07-24: 报告模板工作台占位符输出类型采用稳定优先级：已显式配置的 `type`（含 legacy alias 归一化）优先；仅当 `type` 缺失时才采用有效历史段落 `mode`；两者均无时才按占位符名称推断。显式非段落类型会忽略但保留遗留段落 `mode`，用户切回 `paragraph` 时可以恢复该模式。
- 2026-06-25: 新增基金情报前端面板，左侧导航接入 `section-funds`，通过 `app/web/static/js/funds.js` 调用 Fund Intelligence API 展示基金详情、经理、持仓、行业暴露、组合穿透和结构化 rows 导入结果。
- 2026-06-08: 模板工作台拆分 YAML 占位符映射与 Markdown Prompt 模板源码，源码编辑默认只读并通过 `/api/report-projects/{slug}/source` 写回项目文件；生成成功后显示下载入口和 Word HTML 预览；上传按钮从固定 dock 移到顶部工具栏。
