Task ID: wind-kline-terminal-ad-hoc

Changed source files:
- app/web/templates/index.html
- app/web/static/style.css
- app/web/static/js/asset.js

Changed test files:
- None. This is a frontend layout and ECharts option change; verification used a temporary Playwright script under output/.

Changed docs:
- docs/superpowers/specs/2026-06-03-wind-style-kline-design.md
- docs/modules/app_web.md
- docs/FILE_GUIDE.md
- docs/CHANGELOG.md

Commands run:
- node --check app/web/static/js/asset.js
- python scripts/check_doc_sync.py
- python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8002
- ALPHAFOUNDRY_WEB_URL=http://127.0.0.1:8002 node output/verify_wind_kline_ui.js

Command results:
- JS syntax check passed.
- Documentation sync check passed.
- Local Web service returned /health 200.
- Browser verification passed. The script rendered mocked K-line and chip data, verified ECharts instances, and confirmed chip markLines included chip peak, upper boundary, lower boundary, current price, and average cost.
- Follow-up browser verification also confirmed date range buttons are absent, BOLL/VOL/MACD/KDJ/RSI panel labels are present, and the chip distribution chart height is constrained to the main K-line price panel.
- Second follow-up browser verification confirmed MA120/MA250 series are present, the initial dataZoom shows only the latest 120 bars from a 320-bar dataset, and weekly/monthly period buttons aggregate the full daily series.
- Third follow-up browser verification confirmed the chip distribution y-axis min/max exactly matches the main K-line y-axis min/max, MA buttons are color-coded and active in MA mode, and BOLL/naked-candle overlay modes correctly toggle series visibility.
- Fourth follow-up browser verification confirmed the main K-line y-axis recalculates after zooming out, the visible y-axis contains all visible candle high/low values, the chip distribution y-axis stays aligned with the recalculated main y-axis, the top-left MA/BOLL value label changes when the mouse moves to another candle and uses colored spans, and the right-top overlay controls are reduced to MA/BOLL/naked-candle mode buttons.
- Fifth follow-up browser verification confirms MA250 uses the same gray color in the line series and top-left MA label, and VOL/MACD/KDJ/RSI panel labels change when the mouse moves to another K-line position.

Skipped tests:
- Full repository Python gates were not run.

Reason for skipped tests:
- This change did not modify Python files.
- The working tree already contained many unrelated modified files from other tasks, so full-repo formatting and tests would not isolate this frontend change.

Remaining risk:
- Real data visual density may vary by symbol and historical range.
- The browser MCP instance was occupied, so verification used playwright-core with local Chrome instead.

Final test decision:
- Passed for the requested frontend K-line/chip distribution change.
