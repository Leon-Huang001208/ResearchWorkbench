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
- API client interactions
- User interface behavior
- Asset analysis K-line chart uses ECharts for a Wind-style terminal panel with candlestick/volume/MACD/KDJ/RSI rendering, `dataZoom` drag/scroll zoom with visible-range y-axis recalculation, crosshair tooltip, cursor-following color-coded MA/BOLL value labels, cursor-following VOL/MACD/KDJ/RSI panel labels, daily/weekly/monthly aggregation, a one-year first-load request with an initial recent-120-bar viewport, mutually exclusive MA/BOLL/naked-candle overlay modes, and a right-side ordinary chip distribution chart that uses the current visible range start through the active K-line, shares the main price-axis range, and marks chip peak, peak upper/lower boundaries, current price, and average cost.
- External chart libraries load asynchronously so CDN delays do not block the local workbench startup or asset search flow; the asset K-line panel shows a loading notice if ECharts is still unavailable after data returns.
- Report template workbench logic keeps `section_config.yaml` and `prompt_templates.md` as separate editable sources. The editor opens read-only, requires an explicit edit action, saves project-backed sources through `PUT /api/report-projects/{slug}/source`, and falls back to local drafts for non-project templates.
- Placeholder mapping shows every Word placeholder in first-seen order, builds draft mappings for missing entries, infers prompt/static/Excel placeholder types, supports embedded prompt retrieval queries for report projects such as `华安ETF周报`, and displays mapping status without truncating to the first eight placeholders.
- Report rendering uses `/api/report-projects/{slug}/render`, shows download and preview actions, and loads the inline DOCX HTML preview from the returned `preview_url`.
- Fund Intelligence panel logic lives in `app/web/static/js/funds.js` and calls `/api/funds/{symbol}`, `/api/funds/{symbol}/exposure`, `/api/funds/portfolio/exposure`, and `/api/funds/ingest` for fund detail, exposure, portfolio look-through, and structured row ingestion.
- System configuration logic in `app/web/static/js/configuration.js` is statically imported by the Workbench entry module; its configuration-modal event binder must remain declared so a modal interaction defect cannot prevent the full Workbench module graph from loading.

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

- 2026-06-25: 新增基金情报前端面板，左侧导航接入 `section-funds`，通过 `app/web/static/js/funds.js` 调用 Fund Intelligence API 展示基金详情、经理、持仓、行业暴露、组合穿透和结构化 rows 导入结果。
- 2026-06-08: 模板工作台拆分 YAML 占位符映射与 Markdown Prompt 模板源码，源码编辑默认只读并通过 `/api/report-projects/{slug}/source` 写回项目文件；生成成功后显示下载入口和 Word HTML 预览；上传按钮从固定 dock 移到顶部工具栏。
