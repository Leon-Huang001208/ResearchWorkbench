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

Update this section when:
- New pages are added
- Layout structure changes
- Template organization changes

### `app/web/static/*.js`

Purpose:
- Frontend JavaScript logic
- API client interactions
- User interface behavior
- Asset analysis K-line chart uses ECharts for a Wind-style terminal panel with candlestick/volume/MACD/KDJ/RSI rendering, `dataZoom` drag/scroll zoom with visible-range y-axis recalculation, crosshair tooltip, cursor-following color-coded MA/BOLL value labels, cursor-following VOL/MACD/KDJ/RSI panel labels, daily/weekly/monthly aggregation, an initial recent-120-bar viewport, mutually exclusive MA/BOLL/naked-candle overlay modes, and a right-side ordinary chip distribution chart that uses the current visible range start through the active K-line, shares the main price-axis range, and marks chip peak, peak upper/lower boundaries, current price, and average cost.

Update this section when:
- New JS modules are added
- API interaction patterns change
- UI behavior changes

### `app/web/static/*.css`

Purpose:
- Styling for the web interface
- Visual design and layout

Update this section when:
- Visual design changes
- Layout styling changes
- New components are styled

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

---

## Required Documentation Updates

When files in this module change, check:
- `docs/modules/app_web.md`
- `docs/ARCHITECTURE.md`
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`
- `docs/generated/py_file_index.md`
