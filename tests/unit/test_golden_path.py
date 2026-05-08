"""Golden Path 集成测试 — Issue #3。

测试完整流程：输入 CanonicalEvent -> 返回 EventAlphaSignal
验证信号被持久化（通过 SignalService 查询）
验证择时结果被持久化
使用 SQLite 内存数据库 + mock LLM
"""
import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from data_layer.repositories.base import Base
from data_layer.repositories.signal_repository import SignalRepositoryImpl
from data_layer.repositories.timing_repository import TimingRepositoryImpl
from core.contracts import CanonicalEvent, EventAlphaSignal
from core.services.pipeline_service import ResearchPipeline
from core.services.signal_service import SignalService
from core.services.event_extractor import EventExtractor, ExtractedSignalParams
from core.interfaces import ModelGateway, ModelResponse
from memory_learning.journal import LearningJournal
from timing_engine import MetaTimingEngine, TimingModelRegistry


# ── Fixtures ────────────────────────────────────────────


@pytest.fixture
def db_session():
    """In-memory SQLite session with all tables."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def signal_service(db_session):
    """SignalService with real repository."""
    repo = SignalRepositoryImpl(db_session)
    return SignalService(repository=repo)


@pytest.fixture
def timing_repo(db_session):
    """TimingRepositoryImpl with real session."""
    return TimingRepositoryImpl(db_session)


@pytest.fixture
def mock_model_gateway():
    """Mock ModelGateway that returns structured JSON for event extraction."""
    gateway = Mock(spec=ModelGateway)

    def mock_chat(messages, **kwargs):
        """Return a valid JSON response simulating event extraction."""
        json_response = (
            '{"event_type": "policy", '
            '"subject_ids": ["600000.SH", "000001.SZ"], '
            '"thesis": "央行降准释放流动性利好银行板块", '
            '"impact_path": ["降准 -> 银行净息差改善 -> 盈利提升"], '
            '"bullish_companies": ["600000.SH"], '
            '"bearish_companies": [], '
            '"score": 0.75, '
            '"confidence": 0.8, '
            '"diffusion_stage": "early_awareness", '
            '"industry_impacts": ["finance"], '
            '"market_regime": "liquidity_bull"}'
        )
        return ModelResponse(
            content=json_response,
            model_name="test-model",
            provider="mock",
            tokens_used=100,
            latency_ms=50,
        )

    gateway.chat = mock_chat
    return gateway


@pytest.fixture
def sample_event():
    """创建一个测试用 CanonicalEvent。"""
    return CanonicalEvent(
        event_id=f"evt-{uuid.uuid4().hex[:8]}",
        event_type="policy",
        summary="央行宣布降准0.5个百分点，释放长期流动性约1万亿元",
        event_time=datetime.now(timezone.utc),
        impact_direction="positive",
        confidence=0.85,
        needs_review=False,
        entities=[
            {"canonical_id": "600000.SH", "name": "浦发银行"},
            {"canonical_id": "000001.SZ", "name": "平安银行"},
        ],
        assertions=[
            {"content": "降准将改善银行净息差约5-10bp"},
        ],
        evidence_spans=[
            {"ref": "doc-policy-001", "span": "page1"},
        ],
        source_doc_id="doc-policy-001",
    )


# ── 核心测试：Golden Path 完整流程 ────────────────────


class TestGoldenPath:
    """测试 Golden Path: 事件输入 -> 提取 -> 信号生成 -> 择时 -> 持久化 -> 返回"""

    @pytest.mark.asyncio
    async def test_full_golden_path_with_llm(
        self, sample_event, signal_service, timing_repo, mock_model_gateway, db_session
    ):
        """完整 Golden Path 测试：使用 mock LLM 提取。"""
        event_extractor = EventExtractor(model_gateway=mock_model_gateway)
        journal = LearningJournal()

        pipeline = ResearchPipeline(
            signal_service=signal_service,
            timing_repository=timing_repo,
            event_extractor=event_extractor,
            learning_journal=journal,
        )

        # 运行 Golden Path
        signal = await pipeline.run_event_signal(sample_event)

        # 1. 验证返回的是 EventAlphaSignal（非 placeholder）
        assert isinstance(signal, EventAlphaSignal)
        assert signal.signal_id is not None
        assert signal.event_id == sample_event.event_id
        assert signal.subject_id != "placeholder-subject"
        assert signal.thesis != "Placeholder thesis for event signal"
        assert "placeholder" not in signal.thesis.lower()

        # 2. 验证 LLM 提取的参数被正确使用
        assert signal.event_type == "policy"
        assert signal.subject_id == "600000.SH"
        assert signal.thesis == "央行降准释放流动性利好银行板块"
        assert signal.score > 0.5
        assert signal.confidence > 0.5
        assert len(signal.impact_path) > 0
        assert "600000.SH" in signal.bullish_companies

        # 3. 验证信号被持久化（通过 SignalService 查询）
        persisted_signals = signal_service.list_signals(subject_id="600000.SH")
        assert len(persisted_signals) >= 1
        persisted = persisted_signals[0]
        assert isinstance(persisted, EventAlphaSignal)
        assert persisted.event_id == sample_event.event_id

        # 4. 验证择时评估被执行
        assert signal.timing_decision is not None
        assert signal.timing_decision.action in ("enter", "wait", "block", "reduce", "exit")
        assert 0.0 <= signal.timing_decision.readiness_score <= 1.0

        # 5. 验证择时结果被持久化
        timing_decisions = timing_repo.list(signal_id=signal.signal_id)
        assert len(timing_decisions) >= 1
        assert timing_decisions[0].action == signal.timing_decision.action

        # 6. 验证 LearningJournal 有记录
        episodes = journal.list_episodes(event_type="policy")
        # 如果 timing action 是 enter 或 wait，应该有 episode
        if signal.timing_decision.action in ("enter", "wait"):
            assert len(episodes) >= 1

    @pytest.mark.asyncio
    async def test_golden_path_keyword_fallback(self, sample_event, signal_service, timing_repo):
        """测试关键词 fallback 路径（无 LLM）。"""
        # 不传 model_gateway，EventExtractor 会 fallback 到关键词提取
        event_extractor = EventExtractor(model_gateway=None)

        pipeline = ResearchPipeline(
            signal_service=signal_service,
            timing_repository=timing_repo,
            event_extractor=event_extractor,
        )

        signal = await pipeline.run_event_signal(sample_event)

        # 验证返回了非 placeholder 信号
        assert isinstance(signal, EventAlphaSignal)
        assert signal.signal_id is not None
        assert signal.event_id == sample_event.event_id
        # 关键词提取也能识别 policy 类型（因为摘要包含"降准"）
        assert signal.event_type in ("policy", "macro")
        assert signal.confidence > 0.0
        # 信号被持久化
        persisted = signal_service.list_signals(subject_id=signal.subject_id)
        assert len(persisted) >= 1

    @pytest.mark.asyncio
    async def test_golden_path_no_persistence_services(self, sample_event):
        """测试没有 SignalService/TimingRepository 时的降级运行。"""
        pipeline = ResearchPipeline()  # 无 signal_service, 无 timing_repository

        signal = await pipeline.run_event_signal(sample_event)

        # 应该仍然返回有效信号
        assert isinstance(signal, EventAlphaSignal)
        assert signal.signal_id is not None
        assert signal.event_id == sample_event.event_id
        # 择时仍然会运行（pipeline 自带默认引擎和 registry）
        assert signal.timing_decision is not None

    @pytest.mark.asyncio
    async def test_golden_path_timing_persisted(
        self, sample_event, signal_service, timing_repo, db_session
    ):
        """验证择时结果被持久化到数据库。"""
        pipeline = ResearchPipeline(
            signal_service=signal_service,
            timing_repository=timing_repo,
        )

        signal = await pipeline.run_event_signal(sample_event)

        # 择时结果应该持久化了
        if signal.timing_decision is not None:
            saved = timing_repo.list(signal_id=signal.signal_id)
            assert len(saved) >= 1
            saved_decision = saved[0]
            assert saved_decision.action == signal.timing_decision.action
            assert abs(saved_decision.readiness_score - signal.timing_decision.readiness_score) < 0.01


class TestEventExtractor:
    """测试 EventExtractor 的提取逻辑。"""

    @pytest.mark.asyncio
    async def test_keyword_extraction_a_share_codes(self):
        """关键词提取能识别 A 股代码。"""
        extractor = EventExtractor(model_gateway=None)
        result = await extractor.extract("600000.SH 发布一季报，净利润同比增长30%")

        assert "600000.SH" in result.subject_ids
        assert result.event_type == "earnings"

    @pytest.mark.asyncio
    async def test_keyword_extraction_policy(self):
        """关键词提取能识别政策事件。"""
        extractor = EventExtractor(model_gateway=None)
        result = await extractor.extract("国务院发布新能源补贴新规，利好光伏行业")

        assert result.event_type == "policy"
        assert "new_energy" in result.industry_impacts
        assert result.score > 0.5  # 利好 -> 偏高

    @pytest.mark.asyncio
    async def test_keyword_extraction_bearish(self):
        """关键词提取能识别利空。"""
        extractor = EventExtractor(model_gateway=None)
        result = await extractor.extract("某公司暴雷，净利润大幅下滑，减持")

        assert result.score < 0.5  # 利空 -> 偏低

    @pytest.mark.asyncio
    async def test_keyword_extraction_empty_text(self):
        """空文本返回默认值。"""
        extractor = EventExtractor(model_gateway=None)
        result = await extractor.extract("")

        assert result.event_type == "unknown"
        assert result.subject_ids == []

    @pytest.mark.asyncio
    async def test_llm_extraction_success(self, mock_model_gateway):
        """LLM 提取能正确解析 JSON 响应。"""
        extractor = EventExtractor(model_gateway=mock_model_gateway)
        result = await extractor.extract("央行降准利好银行")

        assert result.event_type == "policy"
        assert "600000.SH" in result.subject_ids
        assert result.thesis == "央行降准释放流动性利好银行板块"
        assert result.score == 0.75
        assert result.confidence == 0.8

    @pytest.mark.asyncio
    async def test_llm_fallback_on_error(self):
        """LLM 失败时自动 fallback 到关键词提取。"""
        # 创建一个会抛异常的 mock gateway
        failing_gateway = Mock(spec=ModelGateway)
        failing_gateway.chat = Mock(side_effect=RuntimeError("API unavailable"))

        extractor = EventExtractor(model_gateway=failing_gateway)
        result = await extractor.extract("600000.SH 营收增长，利好")

        # 应该 fallback 到关键词提取
        assert result.event_type == "earnings"
        assert "600000.SH" in result.subject_ids


class TestPipelineAPIResponse:
    """测试 pipeline API 返回的数据结构。"""

    @pytest.mark.asyncio
    async def test_signal_has_required_fields_for_frontend(self, sample_event):
        """验证信号返回的数据结构前端可用。"""
        pipeline = ResearchPipeline()
        signal = await pipeline.run_event_signal(sample_event)

        data = signal.model_dump()

        # 前端 generateEventSignal() 需要的关键字段
        assert "signal_id" in data
        assert "event_id" in data
        assert "subject_id" in data
        assert "thesis" in data
        assert "score" in data
        assert "confidence" in data
        assert "event_type" in data
        assert "horizon" in data
        assert "timing_decision" in data

        # timing_decision 字段结构
        if data["timing_decision"] is not None:
            td = data["timing_decision"]
            assert "action" in td
            assert "readiness_score" in td
            assert "blockers" in td
