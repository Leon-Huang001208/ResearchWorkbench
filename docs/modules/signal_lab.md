# Module: signal_lab

## Responsibility

`signal_lab` provides feature engineering, label engineering, signal scoring, and event study and backtesting capabilities.

It now also contains the first dynamic multi-factor MVP: point-in-time factor
matrix construction, IC / RankIC evaluation, rolling IC dynamic weights, and
event-factor-timing fusion.

The WebUI visualizes this MVP inside the existing Signal Lab section by runtime
DOM injection from `app/web/static/js/signal-lab.js`. Do not modify dashboard or
template modules for this view.

---

## Design Rules

- Features should be reproducible
- Labels should be clearly defined
- Scoring should be transparent
- Backtests should be auditable
- Add or update tests when signal logic changes

---

## Files

### `signal_lab/features/*.py`

Purpose:
- Feature calculation implementations
- Feature group definitions
- Feature engineering pipelines

Feature groups:

| Group | File | Features | Data Source |
| ----- | ---- | -------- | ----------- |
| `WindConsensusFeatures` | `groups/wind_consensus.py` | cons_net_profit (fy1/fy2/ftm), cons_eps (fy1/fy2/ftm), cons_target_price_upside, cons_rating_score, cons_rating_num | Wind Excel |
| `WindMarginFeatures` | `groups/wind_margin.py` | margin_balance, short_balance, margin_buy, net_margin_flow, short_ratio | Wind Excel |
| `WindBlockFeatures` | `groups/wind_block.py` | lhb_net_buy, lhb_buy_sell_ratio, lhb_intensity | Wind Excel |
| `PriceVolumeFeatures` | `groups/price_volume.py` | price_change, moving_average, volume_ratio | Market data |
| `ValuationFeatures` | `groups/valuation.py` | pe, pb, ps, dividend_yield | Market data |
| `FinancialFeatures` | `groups/financial.py` | roe, roa, revenue_growth, profit_growth | Financials |
| `FundFlowFeatures` | `groups/fund_flow.py` | net_inflow, main_force, retail | Fund flow |
| `IndustryFeatures` | `groups/industry.py` | industry_pct, sector_rank | Industry |
| `MacroFeatures` | `groups/macro.py` | gdp, cpi, pmi, interest_rate | Macro |

Update this section when:
- New features are added
- Feature calculation changes
- Feature group structure changes

### `signal_lab/factors/*.py`

Purpose:
- Dynamic multi-factor contracts and local exports
- Point-in-time factor matrix construction
- IC / RankIC / decile spread evaluation
- Rolling IC weighted factor scoring
- Event alpha + factor alpha + timing readiness fusion

Update this section when:
- Factor taxonomy changes
- Factor matrix semantics change
- Evaluation metrics change
- Dynamic weighting logic changes
- Event-factor fusion weights or risk penalties change

### `services/dynamic_factor_visualization_service.py`

Purpose:
- Build the read-only Alpha Control Room payload for the WebUI
- Use the dynamic factor MVP components end-to-end
- Clearly mark sample/demo data until a production Factor Store is connected

Update this section when:
- Dynamic factor visualization payload shape changes
- Demo payload is replaced with real Factor Store data
- WebUI requires new factor, timing, or fusion fields

### `signal_lab/labels/*.py`

Purpose:
- Label generation logic
- Forward return calculation
- Event-driven labeling

Update this section when:
- Label definition changes
- Forward horizon changes
- Labeling logic changes

### `signal_lab/scoring/*.py`

Purpose:
- Signal scoring algorithms
- Composite scoring
- Confidence and strength assessment

Update this section when:
- Scoring logic changes
- Composite weights change
- Assessment criteria change

### `signal_lab/backtests/*.py`

Purpose:
- Backtest engines
- Performance metrics
- Portfolio simulation

Update this section when:
- Backtest logic changes
- Metric calculation changes
- Portfolio rules change

---

## Required Tests

- Feature calculation tests
- Factor matrix construction tests
- Factor IC / RankIC evaluation tests
- Dynamic factor weighting tests
- Event-factor fusion tests
- Label generation tests
- Scoring logic tests
- Backtest correctness tests
- Edge case tests

---

## Required Documentation Updates

When files in this module change, check:
- `docs/modules/signal_lab.md`
- `docs/ARCHITECTURE.md`
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`
- `docs/generated/py_file_index.md`

---

## Recent Changes

- `signal_lab/features/indicators/engine.py` — 指标计算引擎重构
- `signal_lab/features/indicators/models.py` — 指标数据模型定义
- `signal_lab/features/indicators/talib_provider.py` — TA-Lib 技术指标提供商

## Related Subsystems

- `connectors/market/` — 市场数据连接器（如 `WindMarketConnector`）为信号实验室提供结构化行情/财务数据
