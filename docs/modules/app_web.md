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
- The unified research center lives in `research-workbench.js`: one composer selects a normalized subject and Research Template, renders available/planned template cards and recent cross-template runs, and keeps citation gates, claims, decision cards, previews and completed-only downloads in the same workspace. Asset Observation dispatches a shared prefill event; unsupported ETF/index/industry templates remain visibly planned and non-executable. Raw evidence JSON is not exposed; blocked A-share runs use a structured evidence form before resume.
- Fund Intelligence panel logic lives in `app/web/static/js/funds.js` and calls `/api/funds/{symbol}`, `/api/funds/{symbol}/exposure`, `/api/funds/portfolio/exposure`, and `/api/funds/ingest` for fund detail, exposure, portfolio look-through, and structured row ingestion.
- 系统配置首页以紧凑进度和连接状态概览展示配置完成情况；可按状态筛选卡片，在窄屏下卡片会自适应排列。“刷新状态”只重新读取当前状态，并清除本次会话中临时的连接测试结果，不会测试连接或保存配置。
- 配置卡片会打开对应的编辑弹窗。弹窗会清楚显示尚未添加的账号或 Key，并以更紧凑的字段布局呈现可编辑项；支持测试的配置会说明“测试连接不会保存当前更改”，主要操作为“保存更改”。
- 由当前启动配置管理的字段仍会保持只读，并在受影响字段、行或集合附近给出说明；秘密值不会回填到界面。Provider、任务路由和账号/Key 池按原子集合锁定：任一受管项会使该集合只读且不随保存提交，未受管的同分区独立设置仍可保存。
- 当前环境与能力诊断为只读信息：不读取或导出秘密，也不生成动态表单。`psql` 可用仅表示命令可被发现，不代表 PostgreSQL 或 pgvector 已就绪；iFinD SDK 仅是本机依赖提示，Wind 在非 Windows 平台不适用，Windows 仍须以真实 Excel 验证。
- 市场面板仅在可见、处于市场标签页且交易时段内自动刷新。Wind 市场数据的前端轮询与后端工作簿缓存统一为 30 秒；手动刷新仍立即执行。
- 侧栏以唯一“系统”入口承载“系统中心”（默认）和“系统配置”两个页内标签。`app.js` 将旧的 `resource-monitor`/`config` 本地导航值迁移为 `system` 加受限子标签；资源监控仅在“系统中心”可见且文档可见时采样，离开该标签或切到后台会取消定时器、在途请求并释放图表。它先读 300 秒 AlphaFoundry 历史，再按成功 2 秒、连续失败 4/6/8/10 秒退避读取当前快照，页面内至多保留 150 个点；另在首次激活、恢复可见和每 60 秒读取一次 `host-history` 的 24 小时整机容量历史，失败时保留上一份成功曲线。后一条路径只读取历史；持续的分钟采集由非预览 API 运行时负责。
- 资源监控顶部明确区分 AlphaFoundry 与整机容量：Alpha CPU 显示核心等价及整机占比，Alpha 内存显示 RSS 及整机占比；整机卡显示 CPU 用量、近似空闲和逻辑核，以及已用/总/可用内存。进程树仍只呈现 API 根进程及 AlphaFoundry 自己登记的调度器/知识 Worker PID 的聚合 CPU、内存、磁盘读/写速率、线程数和连接数；“连接数”是进程连接计数，不是每进程网络字节数。独立 Worker 标识为精确进程资源，API 内 Wind、PDF、报告或抓取任务只标识共享进程估算。图表依赖可选的 ECharts，图表组件未就绪时数字摘要和进程表仍会更新；API 的降级状态会保留上一帧并显示不可用提示。
- 页面顶部只在有未恢复异常时显示计数，或在采样暂不可用时显示保留上一帧的提示；正常采样不显示 `ok` 徽标。置顶异常改为紧凑行，可确认或人工解决；异常历史默认查询 90 天，并以深色按钮/浮层单选状态和严重度，支持键盘、外部点击和 `Escape` 关闭。`source_scope=alphafoundry` 表示受控应用侧事件，`source_scope=host_capacity` 表示整机容量事件；两者均只在页面/API 显示，不触发原生通知。异常历史请求失败会保留上一份成功记录，而不是清空异常证据。进程表支持按 CPU、内存或磁盘 I/O 请求排序，行可打开详情抽屉；命令摘要、状态和数值均用 DOM `textContent` 填充，避免把进程元数据作为 HTML 插入。不同操作系统或进程权限下，psutil 可能不能提供 I/O 或连接数字，界面显示 `--` 和 API 的公开降级状态，而不展示底层异常。

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
- Resource-monitor static contracts for navigation lifecycle, safe process rendering, sampling bounds, responsive layout, and chart fallback

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

- 2026-08-10: 整合配置弹窗改版：账号与 Key 池在可访问的集合区域中展示，保留当前安全数据库摘要和 LLM 标签式编辑；高级配置按运行时、LLM 与文本分块分组，窄屏仍维持纵向可读布局。
- 2026-08-07: 系统中心的“系统中心 / 系统配置”共用同一内容轨道；配置页不再以居中的窄容器渲染，两个页面的页内导航保持相同左缘；移除“控制台”冗余提示。
- 2026-08-07: 将“系统监控”与“系统配置”收拢为单一“系统”入口，采用页内“系统中心 / 系统配置”标签并迁移旧本地导航；资源页取消常态 `ok` 徽标，以异常或采样不可用提示替代，异常历史改为可键盘操作的深色单选浮层，置顶事件采用紧凑行。
- 2026-08-05: 系统监控第二期新增 AlphaFoundry 受控 Worker/任务归因、待处理异常置顶、确认/解决操作与默认 90 天异常历史；API 内任务明确标注为共享资源估算，不伪造任务级 CPU，异常接口短暂失败时保留上一份记录。
- 2026-07-26: 完善系统配置界面：首页提供紧凑进度、连接状态概览和状态筛选，卡片在窄屏下自适应排列；“刷新状态”只重新读取状态，不测试连接或保存配置。编辑弹窗显示空账号/Key 状态、采用紧凑字段布局，并明确说明连接测试不会保存更改；“保存更改”为主要保存操作。环境管理的配置仍保持锁定，秘密值不回填。
- 2026-07-26: 系统配置页新增健康总览和卡片操作说明；首次配置引导已在后续迭代中简化为紧凑进度。连接测试结果仅在当前会话中显示，重新检测配置后会清除，避免把短暂检测结果误作持久运行状态。
- 2026-07-26: 增加只读环境能力诊断，展示安全的运行环境、路径与能力信息；其状态不替代真实数据库连接或 Windows Excel/Wind 验证。
- 2026-07-26: 环境变量锁定提示迁移为配置弹窗内的字段、动态行或受管集合上下文说明；Provider、任务路由和账号/Key 池采用原子集合锁定，任一受管键均使整个集合只读且不提交，首页不展示受管名单，前端内部键名仅用于锁定判断。
- 2026-07-24: 报告模板工作台占位符输出类型采用稳定优先级：已显式配置的 `type`（含 legacy alias 归一化）优先；仅当 `type` 缺失时才采用有效历史段落 `mode`；两者均无时才按占位符名称推断。显式非段落类型会忽略但保留遗留段落 `mode`，用户切回 `paragraph` 时可以恢复该模式。
- 2026-06-25: 新增基金情报前端面板，左侧导航接入 `section-funds`，通过 `app/web/static/js/funds.js` 调用 Fund Intelligence API 展示基金详情、经理、持仓、行业暴露、组合穿透和结构化 rows 导入结果。
- 2026-06-08: 模板工作台拆分 YAML 占位符映射与 Markdown Prompt 模板源码，源码编辑默认只读并通过 `/api/report-projects/{slug}/source` 写回项目文件；生成成功后显示下载入口和 Word HTML 预览；上传按钮从固定 dock 移到顶部工具栏。
