# Task: Build Interactive Web Frontend for AlphaFoundry

**Assignee:** 龙太子 (Dragon Prince)
**Status:** ✅ completed
**Started:** 2026-05-05 20:58 GMT+8
**Completed:** 2026-05-05 21:05 GMT+8

## Deliverables

### 1. `app/web/templates/index.html`
- Full SPA with 5-tab navigation: 📊 资产分析, 🎲 情景分析, ⚡ 信号实验室, 📝 审核, 📥 文档摄入
- Chart.js CDN loaded
- Links to `/static/style.css` and `/static/app.js`
- Semantic HTML with all form inputs, result containers, and loading states

### 2. `app/web/static/style.css`
- Modern dashboard design with CSS variables
- Dark/light theme toggle support (`[data-theme="dark"]`)
- Responsive layout (768px and 480px breakpoints)
- Components: metric cards, stat cards, scenario cards, tables, forms, toast, spinner, info grid
- Sticky header, tab navigation styling

### 3. `app/web/static/app.js`
- `apiCall(method, url, body)` — centralized fetch wrapper with error handling
- Tab switching logic with auto-load on tab switch
- Theme toggle with localStorage persistence
- **Tab 1 (资产分析):** calls `POST /api/assets/analyze`, renders valuation cards, price-volume Chart.js line chart, financial data table, fund flow info grid, event impact list
- **Tab 2 (情景分析):** calls `POST /api/scenarios/generate`, renders probability pie chart, scenario cards (title, probability, assumptions, triggers, invalidation signals), residual uncertainty list
- **Tab 3 (信号实验室):** create signal form → `POST /api/signals/create`, signal list table → `GET /api/signals/list`, validate/promote action buttons
- **Tab 4 (审核):** stats cards → `GET /api/review/stats`, pending list → `GET /api/review/pending`, approve/reject buttons
- **Tab 5 (文档摄入):** text input form → `POST /api/ingest/text`, result summary with extraction stats
- Toast notifications, loading states, XSS-safe escaping

### 4. `app/api/main.py` — Updated
- Added `from fastapi.staticfiles import StaticFiles`
- Mounted `/static` → `app/web/static/`
- Index route now reads and returns `app/web/templates/index.html` content

## Test Results
- `test_api.py`: 20/20 passed ✅
- Full suite: 181/181 passed ✅
- Frontend verification: HTML/CSS/JS all served correctly ✅

## Constraints Met
- Only modified `app/web/` and `app/api/main.py`
- No changes to `core/`, `data_layer/`, `knowledge_layer/`, `reasoning/`, `signal_lab/`, `reporting/`
- No npm, no build tools — pure HTML + CSS + JS
- Chart.js via CDN
