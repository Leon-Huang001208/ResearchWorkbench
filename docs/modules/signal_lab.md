# Module: signal_lab

## Responsibility

`signal_lab` provides feature engineering, label engineering, signal scoring, and event study and backtesting capabilities.

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

Update this section when:
- New features are added
- Feature calculation changes
- Feature group structure changes

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