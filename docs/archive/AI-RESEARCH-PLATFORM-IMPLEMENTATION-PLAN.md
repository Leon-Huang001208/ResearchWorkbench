# AlphaFoundry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build AlphaFoundry as a local-first AI research intelligence and alpha discovery platform based on `/Users/leon/Downloads/deep-research-report.md`.

**Architecture:** Build a modular monolith with explicit contracts, a PostgreSQL canonical fact store, a model gateway, structured event/assertion extraction, scenario reasoning, template report composition, and research-only signal validation. Existing code is treated as legacy material and must not constrain the new architecture.

**Tech Stack:** Python 3.11+, Pydantic v2, FastAPI, PostgreSQL, pgvector, SQLAlchemy or psycopg, pytest, LangGraph or an internal state-machine equivalent, OpenAI-compatible model gateway, vectorbt, Backtrader.

---

## File Structure

Create this new structure:

```text
core/contracts/
core/interfaces/
core/model_gateway/
core/observability/
data_layer/adapters/
data_layer/repositories/
knowledge_layer/events/
knowledge_layer/assertions/
knowledge_layer/entity_resolution/
reasoning/scenarios/
reasoning/traces/
reporting/composer/
signal_lab/features/
signal_lab/labels/
signal_lab/backtests/
storage/migrations/
tests/contract/
tests/unit/
tests/reasoning/
tests/backtest/
logs/
```

Primary responsibilities:

- `core/contracts/`: Pydantic domain contracts.
- `core/interfaces/`: Protocols for adapters, repositories, model gateway, reasoning, reporting, signal workflows.
- `core/model_gateway/`: OpenAI-compatible provider abstraction.
- `data_layer/`: Vendor adapters, parsers, repositories.
- `knowledge_layer/`: Entity, assertion, event, retrieval, graph projection logic.
- `reasoning/`: Scenario state machine and trace writing.
- `reporting/`: Section-based report composition and Markdown/Word projection.
- `signal_lab/`: Feature, label, scoring, and backtest research workflows.
- `storage/`: SQL schema and migrations.
- `tests/`: Unit, contract, reasoning, and backtest verification.

---

## Task 1: Project Baseline

**Files:**
- Create: `pyproject.toml`
- Create: `core/__init__.py`
- Create: `logs/.gitkeep`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create package baseline**

```toml
[project]
name = "alphafoundry"
version = "0.1.0"
description = "AlphaFoundry: local-first AI research intelligence and alpha discovery platform"
requires-python = ">=3.11"
dependencies = [
  "pydantic>=2.7",
  "fastapi>=0.110",
  "uvicorn>=0.29",
  "psycopg[binary]>=3.1",
  "sqlalchemy>=2.0",
  "python-dotenv>=1.0",
  "httpx>=0.27",
  "pyyaml>=6.0"
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0",
  "pytest-cov>=5.0",
  "ruff>=0.4"
]
research = [
  "pandas>=2.2",
  "numpy>=1.26",
  "vectorbt>=0.26",
  "backtrader>=1.9"
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]

[tool.ruff]
line-length = 100
```

- [ ] **Step 2: Run baseline test discovery**

Run: `python -m pytest -q`

Expected: test session starts and reports no tests collected or current legacy failures unrelated to the new package. If dependencies are missing, ask before installing Python packages and explain each package purpose.

- [ ] **Step 3: Commit baseline**

If the workspace is not a Git repository, run `git init` before the first commit.

```bash
git add pyproject.toml core/__init__.py logs/.gitkeep tests/__init__.py
git commit -m "chore: establish research platform baseline"
```

---

## Task 2: Domain Contracts

**Files:**
- Create: `core/contracts/__init__.py`
- Create: `core/contracts/ids.py`
- Create: `core/contracts/documents.py`
- Create: `core/contracts/events.py`
- Create: `core/contracts/scenarios.py`
- Create: `core/contracts/reports.py`
- Create: `core/contracts/signals.py`
- Test: `tests/contract/test_domain_contracts.py`

- [ ] **Step 1: Write contract tests**

```python
from datetime import UTC, datetime

from core.contracts import (
    AlphaSignal,
    AssetAnalysisSnapshot,
    CanonicalEvent,
    CanonicalId,
    DocumentEnvelope,
    ScenarioHypothesis,
    ScenarioSet,
    SectionOutput,
    SectionSpec,
)


def test_canonical_id_accepts_global_asset_mapping():
    item = CanonicalId(
        canonical_id="equity.US.NVDA",
        asset_type="equity",
        market="US",
        venue="NASDAQ",
        symbol="NVDA",
        vendor_ids={"ifind": "NVDA.O", "wind": "NVDA.O"},
        name_zh="英伟达",
        name_en="NVIDIA",
    )
    assert item.vendor_ids["ifind"] == "NVDA.O"


def test_document_envelope_preserves_raw_and_canonical_text():
    doc = DocumentEnvelope(
        doc_id="doc_001",
        source_type="report",
        title="AI compute supply chain",
        published_at=datetime(2026, 5, 3, tzinfo=UTC),
        source_name="internal",
        raw_text="raw",
        canonical_text="canonical",
    )
    assert doc.raw_text == "raw"
    assert doc.canonical_text == "canonical"


def test_asset_snapshot_requires_evidence_refs_as_list():
    snapshot = AssetAnalysisSnapshot(
        canonical_id="equity.US.NVDA",
        as_of=datetime(2026, 5, 3, tzinfo=UTC),
        evidence_refs=["assertion_001"],
    )
    assert snapshot.evidence_refs == ["assertion_001"]


def test_event_has_review_default_enabled():
    event = CanonicalEvent(
        event_id="event_001",
        event_type="export_control",
        summary="New export restriction affects GPU shipments.",
        impact_direction="negative",
        confidence=0.72,
        entities=[],
        assertions=[],
        evidence_spans=[],
        source_doc_id="doc_001",
    )
    assert event.needs_review is True


def test_scenario_set_probability_contract():
    scenario = ScenarioHypothesis(
        scenario_id="scenario_base",
        title="Base case",
        horizon="mid",
        probability=0.6,
        assumptions=["Supply remains tight"],
        key_triggers=["New order data"],
        invalidation_signals=["Demand slowdown"],
        impact_map={"semis": "positive"},
        evidence_assertion_ids=["assertion_001"],
        confidence=0.7,
    )
    scenario_set = ScenarioSet(
        set_id="set_001",
        question="How does AI compute demand evolve?",
        hypotheses=[scenario],
        normalization_check=True,
        residual_uncertainty=["Policy timing"],
    )
    assert scenario_set.hypotheses[0].probability == 0.6


def test_report_section_output_binds_evidence_and_scenarios():
    spec = SectionSpec(
        key="market_view",
        title="市场观点",
        target_words=300,
        required_facets=["event", "macro"],
    )
    output = SectionOutput(
        key=spec.key,
        content="主情景仍是供需偏紧。",
        evidence_refs=["assertion_001"],
        scenario_refs=["scenario_base"],
    )
    assert output.key == "market_view"


def test_alpha_signal_defaults_to_research_only():
    signal = AlphaSignal(
        signal_id="signal_001",
        subject_id="equity.US.NVDA",
        horizon="20d",
        thesis="AI compute tightness supports relative returns.",
        score=0.82,
        confidence=0.68,
        scenario_refs=["scenario_base"],
        evidence_refs=["assertion_001"],
    )
    assert signal.status == "research_only"
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/contract/test_domain_contracts.py -q`

Expected: FAIL because `core.contracts` does not exist.

- [ ] **Step 3: Implement contracts**

```python
# core/contracts/ids.py
from typing import Literal

from pydantic import BaseModel, Field


class CanonicalId(BaseModel):
    canonical_id: str
    asset_type: Literal["equity", "etf", "future", "spot_commodity", "fx", "index", "bond", "fund"]
    market: str
    venue: str
    symbol: str
    vendor_ids: dict[str, str] = Field(default_factory=dict)
    name_zh: str | None = None
    name_en: str | None = None
```

```python
# core/contracts/documents.py
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DocumentEnvelope(BaseModel):
    doc_id: str
    source_type: Literal[
        "policy",
        "news",
        "report",
        "pdf",
        "ppt",
        "filing",
        "vendor_snapshot",
        "internal_note",
    ]
    title: str
    published_at: datetime | None = None
    source_name: str
    language: str = "zh"
    metadata: dict = Field(default_factory=dict)
    raw_text: str
    canonical_text: str


class AssetAnalysisSnapshot(BaseModel):
    canonical_id: str
    as_of: datetime
    financial: dict = Field(default_factory=dict)
    fund_flow: dict = Field(default_factory=dict)
    price_volume: dict = Field(default_factory=dict)
    valuation: dict = Field(default_factory=dict)
    shareholder: dict = Field(default_factory=dict)
    industry: dict = Field(default_factory=dict)
    event_impact: list[str] = Field(default_factory=list)
    macro_exposure: dict = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
```

```python
# core/contracts/events.py
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class CanonicalEvent(BaseModel):
    event_id: str
    event_type: str
    summary: str
    event_time: datetime | None = None
    impact_direction: Literal["positive", "negative", "mixed", "unknown"]
    confidence: float
    needs_review: bool = True
    entities: list[dict]
    assertions: list[dict]
    evidence_spans: list[dict]
    source_doc_id: str
```

```python
# core/contracts/scenarios.py
from typing import Literal

from pydantic import BaseModel


class ScenarioHypothesis(BaseModel):
    scenario_id: str
    title: str
    horizon: Literal["short", "mid", "long"]
    probability: float
    assumptions: list[str]
    key_triggers: list[str]
    invalidation_signals: list[str]
    impact_map: dict
    evidence_assertion_ids: list[str]
    confidence: float


class ScenarioSet(BaseModel):
    set_id: str
    question: str
    hypotheses: list[ScenarioHypothesis]
    normalization_check: bool
    residual_uncertainty: list[str]
```

```python
# core/contracts/reports.py
from typing import Literal

from pydantic import BaseModel


class SectionSpec(BaseModel):
    key: str
    title: str
    target_words: int
    required_facets: list[str]
    scenario_required: bool = True
    evidence_policy: Literal["strict", "allow_synthesis"] = "strict"


class SectionOutput(BaseModel):
    key: str
    content: str
    evidence_refs: list[str]
    scenario_refs: list[str]
    warnings: list[str] = []
```

```python
# core/contracts/signals.py
from typing import Literal

from pydantic import BaseModel


class AlphaSignal(BaseModel):
    signal_id: str
    subject_id: str
    horizon: Literal["1d", "5d", "20d", "60d"]
    thesis: str
    score: float
    confidence: float
    scenario_refs: list[str]
    evidence_refs: list[str]
    status: Literal["research_only", "candidate", "paper_trade"] = "research_only"


class TradeCandidate(BaseModel):
    candidate_id: str
    signal_id: str
    action: Literal["long", "short", "neutral"]
    sizing_hint: float
    risk_notes: list[str]
```

```python
# core/contracts/__init__.py
from core.contracts.documents import AssetAnalysisSnapshot, DocumentEnvelope
from core.contracts.events import CanonicalEvent
from core.contracts.ids import CanonicalId
from core.contracts.reports import SectionOutput, SectionSpec
from core.contracts.scenarios import ScenarioHypothesis, ScenarioSet
from core.contracts.signals import AlphaSignal, TradeCandidate

__all__ = [
    "AlphaSignal",
    "AssetAnalysisSnapshot",
    "CanonicalEvent",
    "CanonicalId",
    "DocumentEnvelope",
    "ScenarioHypothesis",
    "ScenarioSet",
    "SectionOutput",
    "SectionSpec",
    "TradeCandidate",
]
```

- [ ] **Step 4: Run tests and verify pass**

Run: `python -m pytest tests/contract/test_domain_contracts.py -q`

Expected: PASS.

- [ ] **Step 5: Commit contracts**

```bash
git add core/contracts tests/contract/test_domain_contracts.py
git commit -m "feat: add research platform domain contracts"
```

---

## Task 3: Storage Schema

**Files:**
- Create: `storage/schema.sql`
- Create: `storage/migrations/001_initial_schema.sql`
- Test: `tests/contract/test_storage_schema.py`

- [ ] **Step 1: Write schema contract tests**

```python
from pathlib import Path


def test_schema_contains_canonical_fact_tables():
    sql = Path("storage/schema.sql").read_text(encoding="utf-8")
    for table in [
        "CREATE TABLE entity",
        "CREATE TABLE source_document",
        "CREATE TABLE assertion",
        "CREATE TABLE canonical_event",
        "CREATE TABLE reasoning_trace",
    ]:
        assert table in sql


def test_schema_preserves_rights_and_review_fields():
    sql = Path("storage/schema.sql").read_text(encoding="utf-8")
    assert "rights_ref" in sql
    assert "reviewer_status" in sql
    assert "trace_ref" in sql


def test_schema_prepares_team_and_project_isolation():
    sql = Path("storage/schema.sql").read_text(encoding="utf-8")
    assert "team_id" in sql
    assert "project_id" in sql
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/contract/test_storage_schema.py -q`

Expected: FAIL because `storage/schema.sql` does not exist.

- [ ] **Step 3: Implement schema**

```sql
CREATE TABLE entity (
  entity_id        text PRIMARY KEY,
  canonical_id     text UNIQUE NOT NULL,
  entity_type      text NOT NULL,
  canonical_name   text NOT NULL,
  aliases          jsonb NOT NULL DEFAULT '[]'::jsonb,
  vendor_ids       jsonb NOT NULL DEFAULT '{}'::jsonb,
  properties       jsonb NOT NULL DEFAULT '{}'::jsonb,
  team_id          text,
  project_id       text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE source_document (
  doc_id           text PRIMARY KEY,
  source_type      text NOT NULL,
  title            text,
  published_at     timestamptz,
  source_name      text NOT NULL,
  content_hash     text NOT NULL,
  rights_ref       text,
  parser_version   text NOT NULL,
  object_uri       text NOT NULL,
  metadata         jsonb NOT NULL DEFAULT '{}'::jsonb,
  team_id          text,
  project_id       text,
  created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE assertion (
  assertion_id         text PRIMARY KEY,
  subject_entity_id    text REFERENCES entity(entity_id),
  predicate            text NOT NULL,
  object_entity_id     text,
  object_value         jsonb,
  observed_at          timestamptz,
  valid_from           timestamptz,
  valid_to             timestamptz,
  confidence           numeric NOT NULL,
  source_doc_id        text REFERENCES source_document(doc_id),
  source_span          jsonb NOT NULL,
  extractor_version    text NOT NULL,
  reviewer_status      text NOT NULL DEFAULT 'draft',
  reviewer             text,
  reviewed_at          timestamptz,
  trace_ref            text,
  team_id              text,
  project_id           text
);

CREATE TABLE canonical_event (
  event_id          text PRIMARY KEY,
  event_type        text NOT NULL,
  summary           text NOT NULL,
  event_time        timestamptz,
  impact_direction  text NOT NULL,
  confidence        numeric NOT NULL,
  needs_review      boolean NOT NULL DEFAULT true,
  source_doc_id     text REFERENCES source_document(doc_id),
  payload           jsonb NOT NULL DEFAULT '{}'::jsonb,
  team_id           text,
  project_id        text,
  created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE reasoning_trace (
  trace_id                  text PRIMARY KEY,
  request_type              text NOT NULL,
  question                  text NOT NULL,
  subject_ids               jsonb NOT NULL DEFAULT '[]'::jsonb,
  retrieved_doc_ids         jsonb NOT NULL DEFAULT '[]'::jsonb,
  retrieved_assertion_ids   jsonb NOT NULL DEFAULT '[]'::jsonb,
  graph_paths               jsonb NOT NULL DEFAULT '[]'::jsonb,
  intermediate_hypotheses   jsonb NOT NULL DEFAULT '[]'::jsonb,
  final_answer              text,
  provider                  text NOT NULL,
  model_name                text NOT NULL,
  prompt_version            text NOT NULL,
  total_latency_ms          integer NOT NULL,
  total_tokens              integer NOT NULL,
  team_id                   text,
  project_id                text,
  created_at                timestamptz NOT NULL DEFAULT now()
);
```

Write the same SQL content to `storage/migrations/001_initial_schema.sql`.

- [ ] **Step 4: Run tests and verify pass**

Run: `python -m pytest tests/contract/test_storage_schema.py -q`

Expected: PASS.

- [ ] **Step 5: Commit schema**

```bash
git add storage tests/contract/test_storage_schema.py
git commit -m "feat: add canonical storage schema"
```

---

## Task 4: Interfaces

**Files:**
- Create: `core/interfaces/__init__.py`
- Create: `core/interfaces/data.py`
- Create: `core/interfaces/model.py`
- Create: `core/interfaces/reasoning.py`
- Create: `core/interfaces/reporting.py`
- Test: `tests/contract/test_interfaces.py`

- [ ] **Step 1: Write interface tests**

```python
from typing import get_type_hints

from core.interfaces import DataAdapter, ModelGateway, ReasoningEngine, ReportComposer


def test_data_adapter_protocol_exposes_fetch_documents():
    hints = get_type_hints(DataAdapter.fetch_documents)
    assert "return" in hints


def test_model_gateway_protocol_exposes_structured_generation():
    assert hasattr(ModelGateway, "generate_structured")


def test_reasoning_engine_protocol_exposes_scenario_run():
    assert hasattr(ReasoningEngine, "run_scenarios")


def test_report_composer_protocol_exposes_compose_section():
    assert hasattr(ReportComposer, "compose_section")
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/contract/test_interfaces.py -q`

Expected: FAIL because `core.interfaces` does not exist.

- [ ] **Step 3: Implement interfaces**

```python
# core/interfaces/data.py
from typing import Protocol

from core.contracts import DocumentEnvelope


class DataAdapter(Protocol):
    def fetch_documents(self) -> list[DocumentEnvelope]:
        """Fetch source documents from a vendor or local source."""
```

```python
# core/interfaces/model.py
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ModelGateway(Protocol):
    def generate_structured(self, prompt: str, schema: type[T]) -> T:
        """Generate structured model output validated by a Pydantic schema."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for retrieval."""
```

```python
# core/interfaces/reasoning.py
from typing import Protocol

from core.contracts import ScenarioSet


class ReasoningEngine(Protocol):
    def run_scenarios(self, question: str, subject_ids: list[str]) -> ScenarioSet:
        """Run multi-scenario reasoning for a research question."""
```

```python
# core/interfaces/reporting.py
from typing import Protocol

from core.contracts import AssetAnalysisSnapshot, ScenarioSet, SectionOutput, SectionSpec


class ReportComposer(Protocol):
    def compose_section(
        self,
        spec: SectionSpec,
        snapshot: AssetAnalysisSnapshot,
        scenarios: ScenarioSet,
    ) -> SectionOutput:
        """Compose one audited report section."""
```

```python
# core/interfaces/__init__.py
from core.interfaces.data import DataAdapter
from core.interfaces.model import ModelGateway
from core.interfaces.reasoning import ReasoningEngine
from core.interfaces.reporting import ReportComposer

__all__ = ["DataAdapter", "ModelGateway", "ReasoningEngine", "ReportComposer"]
```

- [ ] **Step 4: Run tests and verify pass**

Run: `python -m pytest tests/contract/test_interfaces.py -q`

Expected: PASS.

- [ ] **Step 5: Commit interfaces**

```bash
git add core/interfaces tests/contract/test_interfaces.py
git commit -m "feat: define platform interfaces"
```

---

## Task 5: Deterministic Scenario Engine MVP

**Files:**
- Create: `reasoning/scenarios/__init__.py`
- Create: `reasoning/scenarios/deterministic_engine.py`
- Test: `tests/reasoning/test_deterministic_scenarios.py`

- [ ] **Step 1: Write scenario tests**

```python
from reasoning.scenarios import DeterministicScenarioEngine


def test_engine_returns_three_scenarios_with_probability_sum_near_one():
    engine = DeterministicScenarioEngine()
    result = engine.run_scenarios("AI compute demand outlook", ["theme.ai_compute"])
    assert len(result.hypotheses) == 3
    total = sum(item.probability for item in result.hypotheses)
    assert 0.99 <= total <= 1.01
    assert result.normalization_check is True


def test_engine_includes_triggers_and_invalidation_signals():
    engine = DeterministicScenarioEngine()
    result = engine.run_scenarios("Oil shock impact", ["commodity.oil"])
    first = result.hypotheses[0]
    assert first.key_triggers
    assert first.invalidation_signals
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/reasoning/test_deterministic_scenarios.py -q`

Expected: FAIL because `reasoning.scenarios` does not exist.

- [ ] **Step 3: Implement deterministic scenario engine**

```python
# reasoning/scenarios/deterministic_engine.py
from core.contracts import ScenarioHypothesis, ScenarioSet


class DeterministicScenarioEngine:
    def run_scenarios(self, question: str, subject_ids: list[str]) -> ScenarioSet:
        hypotheses = [
            ScenarioHypothesis(
                scenario_id="base_case",
                title="Base case",
                horizon="mid",
                probability=0.55,
                assumptions=["Current evidence remains directionally valid."],
                key_triggers=["Fresh vendor data confirms the current trend."],
                invalidation_signals=["New evidence contradicts the current trend."],
                impact_map={"primary_subjects": subject_ids, "direction": "mixed"},
                evidence_assertion_ids=[],
                confidence=0.55,
            ),
            ScenarioHypothesis(
                scenario_id="upside_case",
                title="Upside case",
                horizon="mid",
                probability=0.25,
                assumptions=["Positive catalyst arrives earlier than expected."],
                key_triggers=["Policy, demand, or supply data surprises positively."],
                invalidation_signals=["Catalyst is delayed or priced in."],
                impact_map={"primary_subjects": subject_ids, "direction": "positive"},
                evidence_assertion_ids=[],
                confidence=0.45,
            ),
            ScenarioHypothesis(
                scenario_id="downside_case",
                title="Downside case",
                horizon="mid",
                probability=0.20,
                assumptions=["Negative shock or demand weakness dominates."],
                key_triggers=["Macro, policy, or supply chain data deteriorates."],
                invalidation_signals=["Risk event fades without fundamental damage."],
                impact_map={"primary_subjects": subject_ids, "direction": "negative"},
                evidence_assertion_ids=[],
                confidence=0.45,
            ),
        ]
        total = sum(item.probability for item in hypotheses)
        return ScenarioSet(
            set_id="deterministic_scenario_set",
            question=question,
            hypotheses=hypotheses,
            normalization_check=0.99 <= total <= 1.01,
            residual_uncertainty=["Evidence retrieval is not connected in the deterministic MVP."],
        )
```

```python
# reasoning/scenarios/__init__.py
from reasoning.scenarios.deterministic_engine import DeterministicScenarioEngine

__all__ = ["DeterministicScenarioEngine"]
```

- [ ] **Step 4: Run tests and verify pass**

Run: `python -m pytest tests/reasoning/test_deterministic_scenarios.py -q`

Expected: PASS.

- [ ] **Step 5: Commit scenario engine**

```bash
git add reasoning tests/reasoning/test_deterministic_scenarios.py
git commit -m "feat: add deterministic scenario engine"
```

---

## Task 6: Template Report Composer MVP

**Files:**
- Create: `reporting/composer/__init__.py`
- Create: `reporting/composer/template_composer.py`
- Test: `tests/unit/test_report_composer.py`

- [ ] **Step 1: Write composer tests**

```python
from datetime import UTC, datetime

from core.contracts import AssetAnalysisSnapshot, ScenarioHypothesis, ScenarioSet, SectionSpec
from reporting.composer import TemplateReportComposer


def test_composer_returns_section_output_with_refs():
    composer = TemplateReportComposer()
    snapshot = AssetAnalysisSnapshot(
        canonical_id="equity.US.NVDA",
        as_of=datetime(2026, 5, 3, tzinfo=UTC),
        evidence_refs=["assertion_001"],
    )
    scenarios = ScenarioSet(
        set_id="set_001",
        question="AI compute outlook",
        hypotheses=[
            ScenarioHypothesis(
                scenario_id="base_case",
                title="Base case",
                horizon="mid",
                probability=0.6,
                assumptions=["Supply remains tight"],
                key_triggers=["Order growth"],
                invalidation_signals=["Demand slowdown"],
                impact_map={"semis": "positive"},
                evidence_assertion_ids=["assertion_001"],
                confidence=0.7,
            )
        ],
        normalization_check=True,
        residual_uncertainty=[],
    )
    spec = SectionSpec(
        key="market_view",
        title="市场观点",
        target_words=200,
        required_facets=["event", "macro"],
    )
    output = composer.compose_section(spec, snapshot, scenarios)
    assert output.key == "market_view"
    assert output.evidence_refs == ["assertion_001"]
    assert output.scenario_refs == ["base_case"]
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/unit/test_report_composer.py -q`

Expected: FAIL because `reporting.composer` does not exist.

- [ ] **Step 3: Implement composer**

```python
# reporting/composer/template_composer.py
from core.contracts import AssetAnalysisSnapshot, ScenarioSet, SectionOutput, SectionSpec


class TemplateReportComposer:
    def compose_section(
        self,
        spec: SectionSpec,
        snapshot: AssetAnalysisSnapshot,
        scenarios: ScenarioSet,
    ) -> SectionOutput:
        scenario_refs = [item.scenario_id for item in scenarios.hypotheses]
        leading = scenarios.hypotheses[0] if scenarios.hypotheses else None
        if leading is None:
            content = f"{spec.title}: 当前证据不足，需进一步跟踪。"
            warnings = ["No scenarios were provided."]
        else:
            content = (
                f"{spec.title}: 针对 {snapshot.canonical_id}，"
                f"主情景为“{leading.title}”，概率为 {leading.probability:.0%}。"
                "该段落由结构化证据和情景集合生成，后续需要绑定人工审核。"
            )
            warnings = []
        return SectionOutput(
            key=spec.key,
            content=content,
            evidence_refs=snapshot.evidence_refs,
            scenario_refs=scenario_refs,
            warnings=warnings,
        )
```

```python
# reporting/composer/__init__.py
from reporting.composer.template_composer import TemplateReportComposer

__all__ = ["TemplateReportComposer"]
```

- [ ] **Step 4: Run tests and verify pass**

Run: `python -m pytest tests/unit/test_report_composer.py -q`

Expected: PASS.

- [ ] **Step 5: Commit composer**

```bash
git add reporting tests/unit/test_report_composer.py
git commit -m "feat: add template report composer"
```

---

## Task 7: Research Signal Contracts and Deterministic Labeler

**Files:**
- Create: `signal_lab/labels/__init__.py`
- Create: `signal_lab/labels/relative_return.py`
- Test: `tests/backtest/test_relative_return_labeler.py`

- [ ] **Step 1: Write labeler tests**

```python
from signal_lab.labels import compute_relative_return_label


def test_relative_return_label_subtracts_benchmark_return():
    result = compute_relative_return_label(asset_return=0.08, benchmark_return=0.03)
    assert result == 0.05


def test_relative_return_label_rounds_floating_noise():
    result = compute_relative_return_label(asset_return=0.1, benchmark_return=0.07)
    assert result == 0.03
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/backtest/test_relative_return_labeler.py -q`

Expected: FAIL because `signal_lab.labels` does not exist.

- [ ] **Step 3: Implement labeler**

```python
# signal_lab/labels/relative_return.py
def compute_relative_return_label(asset_return: float, benchmark_return: float) -> float:
    return round(asset_return - benchmark_return, 10)
```

```python
# signal_lab/labels/__init__.py
from signal_lab.labels.relative_return import compute_relative_return_label

__all__ = ["compute_relative_return_label"]
```

- [ ] **Step 4: Run tests and verify pass**

Run: `python -m pytest tests/backtest/test_relative_return_labeler.py -q`

Expected: PASS.

- [ ] **Step 5: Commit labeler**

```bash
git add signal_lab tests/backtest/test_relative_return_labeler.py
git commit -m "feat: add relative return labeler"
```

---

## Task 8: API Skeleton

**Files:**
- Create: `app/api/__init__.py`
- Create: `app/api/main.py`
- Test: `tests/unit/test_api_app.py`

- [ ] **Step 1: Write API tests**

```python
from fastapi.testclient import TestClient

from app.api.main import app


def test_health_endpoint_returns_ok():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/unit/test_api_app.py -q`

Expected: FAIL because `app.api.main` does not exist.

- [ ] **Step 3: Implement FastAPI app**

```python
# app/api/main.py
from fastapi import FastAPI

app = FastAPI(title="AlphaFoundry", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

```python
# app/api/__init__.py
from app.api.main import app

__all__ = ["app"]
```

- [ ] **Step 4: Run tests and verify pass**

Run: `python -m pytest tests/unit/test_api_app.py -q`

Expected: PASS.

- [ ] **Step 5: Commit API skeleton**

```bash
git add app tests/unit/test_api_app.py
git commit -m "feat: add research platform api skeleton"
```

---

## Task 9: Verification Suite

**Files:**
- Modify: `pyproject.toml`
- Create: `docs/VERIFICATION.md`

- [ ] **Step 1: Add verification commands to documentation**

```markdown
# Verification

Run the focused MVP checks:

```bash
python -m pytest tests/contract -q
python -m pytest tests/reasoning -q
python -m pytest tests/unit -q
python -m pytest tests/backtest -q
```

Run the full suite:

```bash
python -m pytest -q
```

Run lint:

```bash
python -m ruff check .
```
```

- [ ] **Step 2: Run full tests**

Run: `python -m pytest -q`

Expected: PASS for the new platform tests.

- [ ] **Step 3: Run lint**

Run: `python -m ruff check .`

Expected: PASS or actionable lint findings. Fix findings before commit.

- [ ] **Step 4: Commit verification docs**

```bash
git add docs/VERIFICATION.md pyproject.toml
git commit -m "docs: add verification workflow"
```

---

## Implementation Order

1. Project baseline.
2. Domain contracts.
3. Storage schema.
4. Interfaces.
5. Deterministic scenario engine.
6. Template report composer.
7. Relative return labeler.
8. API skeleton.
9. Verification suite.

This order builds a testable slice first: contracts, schema, interfaces, deterministic reasoning, report section generation, signal label primitive, and API health.

---

## Self-Review

- Spec coverage: The plan covers canonical contracts, storage schema, interfaces, model-independent reasoning, report composition, signal labels, API skeleton, tests, and verification.
- Placeholder scan: No placeholder tasks are present.
- Type consistency: Contract names used in tests match implementation snippets.
- Scope: This is the first implementation slice of the full three-month rebuild. It intentionally excludes vendor adapters, real model calls, pgvector queries, LangGraph runtime, and backtest engine integration until the core contracts are stable.
