"""Native orchestration for the daily market commentary workflow.

Only the narrative skill calls cross the runtime boundary.  Data collection,
quality gates and rendering remain deterministic AlphaFoundry responsibilities.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from core.contracts.runtime import (
    AlphaEvent,
    CapabilityKind,
    EvidenceRecord,
    ExecutionHandle,
    QualityGate,
    ReportChart,
    ReportDocument,
    ReportSection,
    RuntimeDescriptor,
    RuntimeUnavailableError,
    SkillSpec,
    ToolSpec,
    WorkflowRunResult,
    WorkflowSpec,
    WorkflowStep,
)
from core.observability import get_logger
from services.daily_market_commentary_spec import (
    DailyMarketCommentarySpec,
    load_daily_market_commentary_spec,
)

logger = get_logger(__name__)


class MarketCommentaryTools(Protocol):
    def get_market_snapshot(self) -> dict[str, Any]: ...
    def get_market_breadth(self) -> dict[str, Any]: ...
    def get_industry_returns(self) -> list[dict[str, Any]]: ...
    def get_market_leaders(self) -> list[dict[str, Any]]: ...
    def search_news(self) -> list[dict[str, Any]]: ...
    def get_market_turnover(self) -> dict[str, Any]: ...
    def get_theme_indices(self) -> list[dict[str, Any]]: ...
    def get_etf_index_signals(self) -> list[dict[str, Any]]: ...


class MarketCommentarySkillRuntime(Protocol):
    """Runtime port used only by the narrative steps of this workflow."""

    descriptor: RuntimeDescriptor

    def create_session(self, *, run_id: str) -> ExecutionHandle: ...
    def register_tools(self, tools: list[ToolSpec]) -> None: ...
    def register_skills(self, skills: list[SkillSpec]) -> None: ...
    def run_skill(
        self, *, handle: ExecutionHandle, skill: SkillSpec, payload: dict[str, Any]
    ) -> dict[str, Any]: ...


def daily_market_commentary_tools() -> list[ToolSpec]:
    """The deterministic Tool catalog exposed to the deployed DSH bridge."""
    object_schema = {"type": "object", "properties": {}, "additionalProperties": True}
    array_schema = {
        "type": "array",
        "items": {"type": "object", "properties": {}, "additionalProperties": True},
    }
    return [
        ToolSpec(
            capability_id=capability_id,
            version="1.0.0",
            description=description,
            input_schema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string", "minLength": 1},
                    "execution_id": {"type": "string", "minLength": 1},
                },
                "required": ["run_id", "execution_id"],
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "properties": {"value": output_schema},
                "required": ["value"],
                "additionalProperties": False,
            },
            permissions=["market:read"],
            idempotency_key=f"daily-market-commentary:{capability_id}",
        )
        for capability_id, description, output_schema in [
            ("market.snapshot", "读取市场快照", object_schema),
            ("market.breadth", "读取市场宽度", object_schema),
            ("market.industry_returns", "读取行业收益", array_schema),
            ("market.leaders", "读取领涨领跌方向", array_schema),
            ("news.search", "读取已授权的新闻证据", array_schema),
            ("market.turnover", "读取全市场成交额", object_schema),
            ("market.theme_indices", "读取主题指数表现", array_schema),
            ("market.etf_index_signals", "读取 ETF 映射的指数与行业信号", array_schema),
        ]
    ]


def daily_market_commentary_skills() -> list[SkillSpec]:
    """Canonical skill contracts; generated DSH SKILL.md files are derivatives."""
    summary_schema = {
        "type": "object",
        "properties": {"summary": {"type": "string", "minLength": 1}},
        "required": ["summary"],
        "additionalProperties": False,
    }
    return [
        SkillSpec(
            capability_id=capability_id,
            version="1.0.0",
            description=description,
            input_schema={"type": "object", "properties": {}, "additionalProperties": True},
            output_schema=output_schema,
            dependencies=dependencies,
            permissions=["market:read", "evidence:read"],
            timeout_seconds=120,
            idempotency_key=f"daily-market-commentary:{capability_id}",
            artifact_types=["skill-result"],
        )
        for capability_id, description, dependencies, output_schema in [
            (
                "market-close-review",
                "基于市场快照完成收盘复盘",
                ["market.snapshot", "market.breadth"],
                summary_schema,
            ),
            (
                "market-attribution",
                "基于行业、领涨方向和证据给出涨跌归因",
                ["market.industry_returns", "market.leaders", "news.search"],
                summary_schema,
            ),
            (
                "counter-evidence-review",
                "检查与当前归因相冲突的反向证据",
                ["news.search"],
                {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string", "minLength": 1},
                        "conflict": {"type": "boolean"},
                    },
                    "required": ["summary", "conflict"],
                    "additionalProperties": False,
                },
            ),
            (
                "report-narrative",
                "将已通过门禁的结果编排为报告叙事",
                ["market-close-review", "market-attribution", "counter-evidence-review"],
                summary_schema,
            ),
        ]
    ]


class InMemoryMarketCommentaryTools:
    """Deterministic provider used by contract tests and API request fixtures."""

    def __init__(
        self,
        *,
        snapshot: dict[str, Any],
        breadth: dict[str, Any],
        industries: list[dict[str, Any]],
        leaders: list[dict[str, Any]],
        news: list[dict[str, Any]],
        turnover: dict[str, Any] | None = None,
        themes: list[dict[str, Any]] | None = None,
        etf_signals: list[dict[str, Any]] | None = None,
    ):
        self._snapshot, self._breadth = snapshot, breadth
        self._industries, self._leaders, self._news = industries, leaders, news
        self._turnover = turnover or {}
        self._themes = themes or []
        self._etf_signals = etf_signals or []

    @classmethod
    def with_minimal_valid_data(cls) -> InMemoryMarketCommentaryTools:
        return cls(
            snapshot={"indices": [{"name": "沪深300", "change_percent": 0.1}]},
            breadth={"up": 2000, "down": 1800},
            industries=[{"name": "电子", "change_percent": 0.5}],
            leaders=[{"name": "电子", "change_percent": 0.5}],
            news=[
                {
                    "source_ref": "market-news-1",
                    "source_name": "市场资讯",
                    "summary": "市场成交保持活跃。",
                }
            ],
            turnover={"amount": 1000000000000, "unit": "CNY"},
            themes=[{"name": "人工智能", "change_percent": 0.4}],
            etf_signals=[{"mapped_direction": "电子", "change_percent": 0.5}],
        )

    def get_market_snapshot(self) -> dict[str, Any]:
        return self._snapshot

    def get_market_breadth(self) -> dict[str, Any]:
        return self._breadth

    def get_industry_returns(self) -> list[dict[str, Any]]:
        return self._industries

    def get_market_leaders(self) -> list[dict[str, Any]]:
        return self._leaders

    def search_news(self) -> list[dict[str, Any]]:
        return self._news

    def get_market_turnover(self) -> dict[str, Any]:
        return self._turnover

    def get_theme_indices(self) -> list[dict[str, Any]]:
        return self._themes

    def get_etf_index_signals(self) -> list[dict[str, Any]]:
        return self._etf_signals


class LiveAkShareMarketCommentaryTools:
    """Read-only public-market Tool provider for an instant commentary run.

    The provider remains inside AlphaFoundry: DSH receives only the validated
    values produced by these methods, never direct access to AKShare or a
    market-data credential.  It intentionally does not persist snapshots.
    """

    _INDEX_NAMES = ("上证指数", "深证成指", "创业板指", "沪深300")

    def __init__(self, *, news_limit: int = 10, sector_limit: int = 10):
        self._news_limit = news_limit
        self._sector_limit = sector_limit
        self._industries: list[dict[str, Any]] | None = None
        self._all_a_spot: Any | None = None

    def get_market_snapshot(self) -> dict[str, Any]:
        try:
            import akshare as ak

            from data_layer.crawlers.akshare.board import _without_proxy_env

            with _without_proxy_env():
                frame = ak.stock_zh_index_spot_sina()
            indices = []
            for name in self._INDEX_NAMES:
                rows = frame[frame["名称"].astype(str) == name]
                if rows.empty:
                    continue
                row = rows.iloc[0]
                change = _as_float(row.get("涨跌幅"))
                latest = _as_float(row.get("最新价"))
                if change is None or latest is None:
                    continue
                indices.append(
                    {
                        "name": name,
                        "last": latest,
                        "change_percent": change,
                        "source": "akshare:sina_index_spot",
                    }
                )
            if not indices:
                raise RuntimeError("未获取到可用的指数快照")
            return {"indices": indices, "source": "akshare"}
        except Exception as exc:
            logger.exception("live market snapshot tool failed")
            raise RuntimeError("市场快照工具不可用") from exc

    def get_market_breadth(self) -> dict[str, Any]:
        try:
            import akshare as ak

            from data_layer.crawlers.akshare.board import (
                _without_proxy_env,
                _without_tqdm_output,
            )

            with _without_proxy_env(), _without_tqdm_output():
                frame = self._get_all_a_spot(ak)
            changes = frame["涨跌幅"].map(_as_float)
            up = int((changes > 0).sum())
            down = int((changes < 0).sum())
            flat = int((changes == 0).sum())
            if up + down + flat == 0:
                raise RuntimeError("全 A 行情不含有效涨跌幅")
            return {
                "up": up,
                "down": down,
                "flat": flat,
                "source": "akshare:all_a_spot",
            }
        except Exception as exc:
            logger.exception("live market breadth tool failed")
            raise RuntimeError("市场宽度工具不可用") from exc

    def get_market_turnover(self) -> dict[str, Any]:
        try:
            import akshare as ak

            frame = self._get_all_a_spot(ak)
            column = next((name for name in ("成交额", "成交量") if name in frame.columns), None)
            if column is None:
                return {"available": False, "reason": "source_column_missing"}
            amount = sum(value for value in frame[column].map(_as_float) if value is not None)
            return {"amount": amount, "unit": "CNY", "source": "akshare:all_a_spot"}
        except Exception as exc:  # noqa: BLE001 - external provider must safely degrade
            logger.warning("live market turnover tool unavailable", error_type=type(exc).__name__)
            return {"available": False, "reason": "source_unavailable"}

    def get_industry_returns(self) -> list[dict[str, Any]]:
        if self._industries is not None:
            return self._industries
        try:
            from data_layer.crawlers.akshare.board import fetch_sector_board

            snapshot = fetch_sector_board(force_refresh=True)
            industries = [
                {
                    "name": item.name,
                    "change_percent": item.change_pct,
                    "net_flow": item.net_flow,
                    "up_count": item.up_count,
                    "down_count": item.down_count,
                    "leading_stock": item.leading_stock_name,
                    "source": "akshare:ths_industry",
                }
                for item in snapshot.sectors
                if item.name
            ]
            if not industries:
                raise RuntimeError("未获取到行业板块行情")
            self._industries = industries
            return industries
        except Exception as exc:
            logger.exception("live industry returns tool failed")
            raise RuntimeError("行业涨跌工具不可用") from exc

    def get_market_leaders(self) -> list[dict[str, Any]]:
        industries = self.get_industry_returns()
        ordered = sorted(
            industries,
            key=lambda item: float(item["change_percent"]),
            reverse=True,
        )
        leaders = ordered[: self._sector_limit] + list(reversed(ordered[-self._sector_limit :]))
        return [
            {
                "name": item["name"],
                "change_percent": item["change_percent"],
                "leading_stock": item["leading_stock"],
                "source": item["source"],
            }
            for item in leaders
        ]

    def get_theme_indices(self) -> list[dict[str, Any]]:
        """Expose a bounded theme projection; DSH never calls its data source."""
        return self.get_market_leaders()

    def get_etf_index_signals(self) -> list[dict[str, Any]]:
        try:
            import akshare as ak

            from data_layer.crawlers.akshare.board import _without_proxy_env

            with _without_proxy_env():
                frame = ak.fund_etf_spot_em()
            change_column = next(
                (name for name in ("涨跌幅", "涨跌幅%") if name in frame.columns), None
            )
            name_column = next(
                (name for name in ("名称", "基金简称") if name in frame.columns), None
            )
            if change_column is None or name_column is None:
                return []
            rows = []
            for _, row in frame.iterrows():
                change = _as_float(row.get(change_column))
                name = str(row.get(name_column) or "").strip()
                if change is not None and name:
                    rows.append(
                        {
                            "mapped_direction": name,
                            "change_percent": change,
                            "source": "akshare:etf_spot",
                        }
                    )
            return sorted(rows, key=lambda item: abs(float(item["change_percent"])), reverse=True)[
                :10
            ]
        except Exception as exc:  # noqa: BLE001 - external provider must safely degrade
            logger.warning("live ETF index signals unavailable", error_type=type(exc).__name__)
            return []

    def search_news(self) -> list[dict[str, Any]]:
        try:
            from data_layer.crawlers.akshare.news import AkShareNewsFetcher

            items = AkShareNewsFetcher().fetch_all_news(limit=self._news_limit)
            news = [
                {
                    "source_ref": item.url or f"akshare:{item.source}:{index}",
                    "source_name": item.source,
                    "summary": item.content,
                    "published_at": item.publish_time.isoformat(),
                }
                for index, item in enumerate(items, start=1)
                if item.content and item.source
            ]
            if not news:
                raise RuntimeError("未获取到可引用的市场新闻")
            return news
        except Exception as exc:
            logger.exception("live market news tool failed")
            raise RuntimeError("市场新闻工具不可用") from exc

    def _get_all_a_spot(self, ak: Any):
        if self._all_a_spot is None:
            from data_layer.crawlers.akshare.board import (
                _without_proxy_env,
                _without_tqdm_output,
            )

            with _without_proxy_env(), _without_tqdm_output():
                self._all_a_spot = ak.stock_zh_a_spot()
        return self._all_a_spot


def _as_float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


class InMemorySkillRuntime:
    """Protocol-conformance fixture; production DSH calls belong in an adapter."""

    def __init__(self, descriptor: RuntimeDescriptor):
        self.descriptor = descriptor

    def create_session(self, *, run_id: str) -> ExecutionHandle:
        return ExecutionHandle(
            run_id=run_id,
            runtime_id=self.descriptor.runtime_id,
            execution_id=f"fixture_{run_id}",
            resumable=self.descriptor.capabilities.resume,
        )

    def register_tools(self, tools: list[ToolSpec]) -> None:
        del tools

    def register_skills(self, skills: list[SkillSpec]) -> None:
        del skills

    def run_skill(
        self, *, handle: ExecutionHandle, skill: SkillSpec, payload: dict[str, Any]
    ) -> dict[str, Any]:
        del handle
        if not self.descriptor.capabilities.skills:
            raise RuntimeUnavailableError(
                f"Runtime {self.descriptor.runtime_id} does not support skills"
            )
        if skill.capability_id == "market-close-review":
            return {"summary": "市场收盘复盘已完成。"}
        if skill.capability_id == "market-attribution":
            leader = payload["leaders"][0]["name"] if payload["leaders"] else "暂无"
            return {"summary": f"领涨方向为{leader}，归因需以已收集证据为准。"}
        if skill.capability_id == "counter-evidence-review":
            return {"summary": "已执行反向证据检查，未发现未解决冲突。", "conflict": False}
        if skill.capability_id == "report-narrative":
            return {"summary": "市场表现、行业线索与新闻证据已整理为收盘点评。"}
        raise ValueError(f"Unknown skill: {skill.capability_id}")


class DailyMarketCommentaryWorkflow:
    workflow_id = "daily-market-commentary"
    version = "2.0.0"

    def __init__(
        self,
        *,
        tools: MarketCommentaryTools,
        runtime: MarketCommentarySkillRuntime,
        spec: DailyMarketCommentarySpec | None = None,
    ):
        self._tools = tools
        self._runtime = runtime
        self._config = spec or load_daily_market_commentary_spec()

    def build_spec(self) -> WorkflowSpec:
        rows = [
            ("market-snapshot", "market.snapshot", CapabilityKind.TOOL),
            ("market-breadth", "market.breadth", CapabilityKind.TOOL),
            ("industry-returns", "market.industry_returns", CapabilityKind.TOOL),
            ("market-turnover", "market.turnover", CapabilityKind.TOOL),
            ("market-leaders", "market.leaders", CapabilityKind.TOOL),
            ("market-themes", "market.theme_indices", CapabilityKind.TOOL),
            ("etf-index-signals", "market.etf_index_signals", CapabilityKind.TOOL),
            ("news-search", "news.search", CapabilityKind.TOOL),
            ("market-close-review", "market-close-review", CapabilityKind.SKILL),
            ("market-attribution", "market-attribution", CapabilityKind.SKILL),
            ("counter-evidence-review", "counter-evidence-review", CapabilityKind.SKILL),
            ("quality-gates", "evaluator.market_commentary", CapabilityKind.EVALUATOR),
            ("report-narrative", "report-narrative", CapabilityKind.SKILL),
            ("render-report", "renderer.report_document", CapabilityKind.RENDERER),
        ]
        return WorkflowSpec(
            workflow_id=self.workflow_id,
            version=self._config.version,
            title=self._config.title,
            steps=[
                WorkflowStep(
                    step_id=step_id,
                    capability_id=capability_id,
                    kind=kind,
                    depends_on=[] if index < 8 else [rows[index - 1][0]],
                    output_name=step_id,
                )
                for index, (step_id, capability_id, kind) in enumerate(rows)
            ],
        )

    def run(self, *, run_id: str, as_of: datetime, question: str) -> WorkflowRunResult:
        workflow = self.build_spec()
        if not self._runtime.descriptor.capabilities.skills:
            raise RuntimeUnavailableError(
                f"Runtime {self._runtime.descriptor.runtime_id} does not support skills"
            )
        events: list[AlphaEvent] = []
        skills = {item.capability_id: item for item in daily_market_commentary_skills()}

        def event(event_type: str, **payload: Any) -> None:
            events.append(
                AlphaEvent(
                    event_id=f"evt_{uuid4().hex}",
                    event_type=event_type,
                    run_id=run_id,
                    sequence=len(events),
                    occurred_at=datetime.now(UTC),
                    payload=payload,
                )
            )

        try:
            event("RunCreated", workflow_id=workflow.workflow_id, question=question)
            self._runtime.register_tools(daily_market_commentary_tools())
            self._runtime.register_skills(list(skills.values()))
            handle = self._runtime.create_session(run_id=run_id)
            event("RuntimeSessionCreated", execution_id=handle.execution_id)
            snapshot = self._tools.get_market_snapshot()
            event("StepCompleted", step_id="market-snapshot")
            breadth = self._tools.get_market_breadth()
            event("StepCompleted", step_id="market-breadth")
            industries = self._tools.get_industry_returns()
            event("StepCompleted", step_id="industry-returns")
            turnover = self._tools.get_market_turnover()
            event("StepCompleted", step_id="market-turnover")
            leaders = self._tools.get_market_leaders()
            event("StepCompleted", step_id="market-leaders")
            themes = self._tools.get_theme_indices()
            event("StepCompleted", step_id="market-themes")
            etf_signals = self._tools.get_etf_index_signals()
            event("StepCompleted", step_id="etf-index-signals")
            news = self._tools.search_news()
            event("StepCompleted", step_id="news-search")
            close = self._runtime.run_skill(
                handle=handle,
                skill=skills["market-close-review"],
                payload={"snapshot": snapshot, "breadth": breadth, "turnover": turnover},
            )
            event("StepCompleted", step_id="market-close-review")
            attribution = self._runtime.run_skill(
                handle=handle,
                skill=skills["market-attribution"],
                payload={
                    "industries": industries,
                    "leaders": leaders,
                    "themes": themes,
                    "etf_index_signals": etf_signals,
                    "news": news,
                    "focus_direction_count": self._config.data_policy.focus_direction_count,
                    "attribution_priority": self._config.data_policy.attribution_priority,
                },
            )
            event("StepCompleted", step_id="market-attribution")
            counter = self._runtime.run_skill(
                handle=handle,
                skill=skills["counter-evidence-review"],
                payload={"news": news},
            )
            event("StepCompleted", step_id="counter-evidence-review")
            evidence = [
                EvidenceRecord(
                    evidence_id=f"evidence-{index}",
                    source_ref=item["source_ref"],
                    source_name=item["source_name"],
                    summary=item["summary"],
                    observed_at=_parse_datetime(item.get("published_at")),
                    conflict=bool(item.get("conflict", False)),
                )
                for index, item in enumerate(news, start=1)
                if item.get("source_ref") and item.get("source_name") and item.get("summary")
            ]
            gates = self._evaluate(snapshot, breadth, industries, evidence, counter, self._config)
            event(
                "StepCompleted", step_id="quality-gates", passed=all(gate.passed for gate in gates)
            )
            if not all(gate.passed for gate in gates):
                event("RunBlocked", gates=[gate.gate_key for gate in gates if not gate.passed])
                return WorkflowRunResult(
                    run_id=run_id,
                    status="blocked",
                    workflow=workflow,
                    evidence=evidence,
                    gates=gates,
                    events=events,
                )
            narrative = self._runtime.run_skill(
                handle=handle,
                skill=skills["report-narrative"],
                payload={
                    "close": close,
                    "attribution": attribution,
                    "counter": counter,
                    "sections": [item.model_dump() for item in self._config.sections],
                    "style": "公募基金指数研究员：专业、克制、聚焦、有判断但不过度预测。",
                },
            )
            event("StepCompleted", step_id="report-narrative")
            document = ReportDocument(
                title=f"{as_of.year}年{as_of.month}月{as_of.day}日每日市场点评",
                as_of=as_of,
                evidence_refs=[item.source_ref for item in evidence],
                sections=_build_sections(self._config, close, attribution, counter, narrative),
                charts=_build_charts(self._config, snapshot, industries, themes),
            )
            event("StepCompleted", step_id="render-report")
            event("RunCompleted", artifact_type="report_document")
            return WorkflowRunResult(
                run_id=run_id,
                status="completed",
                workflow=workflow,
                report_document=document,
                evidence=evidence,
                gates=gates,
                events=events,
            )
        except RuntimeUnavailableError:
            raise
        except Exception as exc:
            logger.exception("daily market commentary failed", run_id=run_id, error=str(exc))
            event("RunFailed", error=str(exc))
            return WorkflowRunResult(
                run_id=run_id,
                status="failed",
                workflow=workflow,
                events=events,
                error_message="每日市场点评执行失败",
            )

    @staticmethod
    def _evaluate(
        snapshot: dict[str, Any],
        breadth: dict[str, Any],
        industries: list[dict[str, Any]],
        evidence: list[EvidenceRecord],
        counter: dict[str, Any],
        config: DailyMarketCommentarySpec,
    ) -> list[QualityGate]:
        return [
            QualityGate(
                gate_key="citation_coverage",
                passed=len(evidence) >= config.quality_policy.min_evidence_count,
                message="引用覆盖检查",
            ),
            QualityGate(
                gate_key="numeric_and_period",
                passed=bool(snapshot.get("indices")) and "up" in breadth and "down" in breadth,
                message="数值与期间完整性检查",
            ),
            QualityGate(
                gate_key="conflict_detection",
                passed=not bool(counter.get("unresolved_numeric_date_source_conflict", False)),
                message="未解决数值、期间或关键来源冲突检查",
                details={"interpretive_conflict_as_risk": bool(counter.get("conflict", False))},
            ),
            QualityGate(
                gate_key="required_sections", passed=bool(industries), message="必需章节输入检查"
            ),
        ]


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    return datetime.fromisoformat(value)


def _outlook_content(narrative: str, counter: dict[str, Any]) -> str:
    if counter.get("conflict"):
        return f"{narrative}\n\n风险观察：{counter.get('summary', '存在需持续验证的反向证据。')}"
    return narrative


def _build_sections(
    config: DailyMarketCommentarySpec,
    close: dict[str, Any],
    attribution: dict[str, Any],
    counter: dict[str, Any],
    narrative: dict[str, Any],
) -> list[ReportSection]:
    contents = [
        close["summary"],
        attribution["summary"],
        _outlook_content(narrative["summary"], counter),
    ]
    return [
        ReportSection(
            heading=section.heading,
            content=contents[index] if index < len(contents) else narrative["summary"],
        )
        for index, section in enumerate(config.sections)
    ]


def _build_charts(
    config: DailyMarketCommentarySpec,
    snapshot: dict[str, Any],
    industries: list[dict[str, Any]],
    themes: list[dict[str, Any]],
) -> list[ReportChart]:
    charts: list[ReportChart] = []
    for chart in config.charts:
        if not chart.enabled:
            continue
        if chart.chart_id == "broad-index-relative-performance":
            data = list(snapshot.get("indices") or [])
        else:
            data = sorted(
                industries + themes,
                key=lambda item: float(item.get("change_percent", 0)),
                reverse=True,
            )
            data = data[:5] + data[-5:]
        charts.append(
            ReportChart(
                chart_id=chart.chart_id, title=chart.title, chart_type=chart.chart_type, data=data
            )
        )
    return charts
