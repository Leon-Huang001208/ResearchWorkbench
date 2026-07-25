# Dynamic Factor MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first dynamic multi-factor alpha layer that can evaluate point-in-time factor matrices, learn rolling IC weights, and fuse factor alpha with event signals and timing readiness.

**Architecture:** Add a focused `signal_lab/factors/` package. Keep the MVP deterministic and transparent: contracts define factor records, `FactorMatrixBuilder` pivots records into a cross-sectional matrix, `FactorEvaluator` computes IC/RankIC/decile spread, `RollingICWeightedModel` converts historical IC into dynamic factor weights, and `EventFactorFusion` combines factor alpha with event alpha, timing readiness, and risk penalties.

**Tech Stack:** Python 3.11, Pydantic v2, pandas, numpy, pytest-style tests.

---

### Task 1: Factor Contracts And Matrix Builder

**Files:**
- Create: `core/contracts/factors.py`
- Create: `signal_lab/factors/contracts.py`
- Create: `signal_lab/factors/matrix.py`
- Test: `tests/unit/test_dynamic_factors.py`

- [ ] **Step 1: Write tests for matrix construction**

Create tests that instantiate factor definitions and values, then assert that a point-in-time matrix is pivoted by `subject_id` and ordered by registered factor definitions.

- [ ] **Step 2: Implement contracts and builder**

Define `FactorDefinition`, `FactorValue`, `FactorMatrix`, and `FactorMatrixBuilder`.

- [ ] **Step 3: Verify**

Run the focused factor test module. If pytest is unavailable or crashes in the local environment, run the test functions through a small direct Python smoke runner.

### Task 2: Factor Evaluation

**Files:**
- Create: `signal_lab/factors/evaluation.py`
- Test: `tests/unit/test_dynamic_factors.py`

- [ ] **Step 1: Write tests for IC, RankIC, and decile spread**

Use a small deterministic cross-section where factor ranks and forward returns are aligned.

- [ ] **Step 2: Implement evaluator**

Compute Pearson IC, Spearman RankIC, top-bottom decile spread, coverage, and sample size. Handle missing values safely.

- [ ] **Step 3: Verify**

Run the focused tests and a compile check.

### Task 3: Dynamic Factor Model

**Files:**
- Create: `signal_lab/factors/models.py`
- Test: `tests/unit/test_dynamic_factors.py`

- [ ] **Step 1: Write tests for rolling IC dynamic weights**

Pass historical factor evaluation records and assert positive IC factors receive higher normalized weights while negative IC factors are allowed to become negative alpha contributors.

- [ ] **Step 2: Implement model**

Compute rolling average RankIC/IC scores, normalize absolute weights, score standardized factor matrices, and expose factor contributions.

- [ ] **Step 3: Verify**

Run tests and compile check.

### Task 4: Event-Factor Fusion

**Files:**
- Create: `signal_lab/factors/fusion.py`
- Test: `tests/unit/test_dynamic_factors.py`

- [ ] **Step 1: Write tests for final alpha fusion**

Assert that event score, factor score, timing readiness, crowding, skeptic risk, and alpha decay combine into bounded final alpha scores with interpretable contributors.

- [ ] **Step 2: Implement fusion**

Use a transparent weighted formula and clamp scores to `[0, 1]`.

- [ ] **Step 3: Verify**

Run tests and compile check.

### Task 5: Package Exports And Documentation

**Files:**
- Create: `signal_lab/factors/__init__.py`
- Modify: `core/contracts/__init__.py`
- Modify: `docs/modules/signal_lab.md`
- Modify: `docs/AUTO_CLOSED_LOOP_AND_DYNAMIC_FACTOR_ROADMAP.md`

- [ ] **Step 1: Export public classes**

Expose the factor contracts and services from `signal_lab.factors` and `core.contracts`.

- [ ] **Step 2: Update docs**

Document the new dynamic factor MVP and clarify that it is the first implementation slice of the larger roadmap.

- [ ] **Step 3: Final verification**

Run focused tests, `python -m compileall` for touched Python packages, and `ruff check` on touched files.
