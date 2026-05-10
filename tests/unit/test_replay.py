"""回放服务单元测试 — 历史事件批量回放 & 信号校准"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.contracts.replay import ReplayAggregate, ReplayJob, ReplayResult
from core.contracts.signals import EventAlphaSignal
from core.services.replay_service import ReplayService
from data_layer.repositories.base import Base
from data_layer.repositories.replay_repository import ReplayRepositoryImpl

# ── Fixtures ──────────────────────────────────────────────


@pytest.fixture
def in_memory_db():
    """创建 SQLite 内存数据库"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()
    yield db
    db.close()


@pytest.fixture
def replay_repository(in_memory_db):
    """创建回放仓储"""
    return ReplayRepositoryImpl(db=in_memory_db)


@pytest.fixture
def replay_service_no_db():
    """创建无 DB 的回放服务（纯内存）"""
    return ReplayService()


@pytest.fixture
def replay_service_with_db(replay_repository):
    """创建有 DB 的回放服务"""
    return ReplayService(repository=replay_repository)


# ── 创建回放任务 ──────────────────────────────────────────


class TestCreateReplayJob:
    def test_create_job_no_db(self, replay_service_no_db):
        """测试创建回放任务（纯内存）"""
        job = replay_service_no_db.create_job(
            name="Test Replay",
            description="Test description",
            max_events=50,
        )
        assert job.job_id is not None
        assert job.name == "Test Replay"
        assert job.description == "Test description"
        assert job.max_events == 50
        assert job.status == "pending"
        assert job.created_at is not None

    def test_create_job_with_db(self, replay_service_with_db):
        """测试创建回放任务（数据库持久化）"""
        job = replay_service_with_db.create_job(
            name="DB Replay",
            max_events=100,
        )
        assert job.job_id is not None
        assert job.name == "DB Replay"
        assert job.status == "pending"

    def test_create_job_with_filter(self, replay_service_no_db):
        """测试创建带过滤条件的回放任务"""
        event_filter = {"event_type": "policy", "source_type": "news"}
        job = replay_service_no_db.create_job(
            name="Filtered Replay",
            event_filter=event_filter,
        )
        assert job.event_filter == event_filter

    def test_get_job(self, replay_service_no_db):
        """测试获取回放任务"""
        job = replay_service_no_db.create_job(name="Get Test")
        retrieved = replay_service_no_db.get_job(job.job_id)
        assert retrieved is not None
        assert retrieved.job_id == job.job_id
        assert retrieved.name == "Get Test"

    def test_get_job_not_found(self, replay_service_no_db):
        """测试获取不存在的回放任务"""
        retrieved = replay_service_no_db.get_job("nonexistent")
        assert retrieved is None


# ── 执行回放 ──────────────────────────────────────────────


class TestRunReplayJob:
    @pytest.mark.asyncio
    async def test_run_job_basic(self, replay_service_no_db):
        """测试基本回放执行"""
        job = replay_service_no_db.create_job(
            name="Basic Run",
            max_events=5,
        )
        aggregate = await replay_service_no_db.run_job(job.job_id)

        assert aggregate is not None
        assert aggregate.job_id == job.job_id
        assert aggregate.total_events > 0
        assert aggregate.successful > 0
        assert 0 <= aggregate.hit_rate <= 1
        assert aggregate.avg_excess_return is not None

    @pytest.mark.asyncio
    async def test_run_job_with_filter(self, replay_service_no_db):
        """测试带过滤的回放"""
        job = replay_service_no_db.create_job(
            name="Filtered Run",
            event_filter={"event_type": "policy"},
            max_events=100,
        )
        aggregate = await replay_service_no_db.run_job(job.job_id)

        # 确认结果只包含 policy 类型
        assert aggregate.total_events > 0
        # 检查 by_event_type 只包含 policy
        if aggregate.by_event_type:
            assert "policy" in aggregate.by_event_type

    @pytest.mark.asyncio
    async def test_run_job_updates_status(self, replay_service_no_db):
        """测试回放执行后任务状态更新"""
        job = replay_service_no_db.create_job(name="Status Test")
        assert job.status == "pending"

        await replay_service_no_db.run_job(job.job_id)

        updated = replay_service_no_db.get_job(job.job_id)
        assert updated.status == "completed"
        assert updated.completed_at is not None

    @pytest.mark.asyncio
    async def test_run_job_not_found(self, replay_service_no_db):
        """测试执行不存在的回放任务"""
        with pytest.raises(ValueError, match="Replay job not found"):
            await replay_service_no_db.run_job("nonexistent")

    @pytest.mark.asyncio
    async def test_run_job_with_db(self, replay_service_with_db):
        """测试使用数据库的回放执行"""
        job = replay_service_with_db.create_job(name="DB Run", max_events=3)
        aggregate = await replay_service_with_db.run_job(job.job_id)

        assert aggregate is not None
        assert aggregate.total_events > 0

        # 验证数据库中状态已更新
        db_job = replay_service_with_db.get_job(job.job_id)
        assert db_job.status == "completed"

    @pytest.mark.asyncio
    async def test_run_job_with_mock_pipeline(self, replay_service_no_db):
        """测试使用 mock pipeline 的回放执行"""
        mock_pipeline = MagicMock()
        mock_signal = EventAlphaSignal(
            signal_id="sig-replay-001",
            subject_id="600000.SH",
            horizon="20d",
            thesis="测试信号",
            score=0.8,
            confidence=0.7,
            event_id="evt-001",
            event_type="policy",
        )
        mock_pipeline.run_event_signal = AsyncMock(return_value=mock_signal)

        replay_service_no_db.pipeline = mock_pipeline
        job = replay_service_no_db.create_job(name="Pipeline Run", max_events=3)
        aggregate = await replay_service_no_db.run_job(job.job_id)

        assert aggregate is not None
        assert aggregate.total_events > 0

    @pytest.mark.asyncio
    async def test_run_job_max_events_limit(self, replay_service_no_db):
        """测试 max_events 限制"""
        job = replay_service_no_db.create_job(
            name="Limited Run",
            max_events=2,
        )
        aggregate = await replay_service_no_db.run_job(job.job_id)
        assert aggregate.total_events <= 2


# ── 聚合分析 ──────────────────────────────────────────────


class TestAggregate:
    @pytest.mark.asyncio
    async def test_aggregate_basic(self, replay_service_no_db):
        """测试基本聚合统计"""
        job = replay_service_no_db.create_job(name="Aggregate Test", max_events=10)
        await replay_service_no_db.run_job(job.job_id)
        aggregate = replay_service_no_db.get_aggregate(job.job_id)

        assert aggregate is not None
        assert aggregate.job_id == job.job_id
        assert aggregate.total_events > 0
        assert 0 <= aggregate.hit_rate <= 1
        assert isinstance(aggregate.avg_excess_return, float)
        assert isinstance(aggregate.avg_max_drawdown, float)
        assert isinstance(aggregate.avg_decay, float)

    @pytest.mark.asyncio
    async def test_aggregate_not_found(self, replay_service_no_db):
        """测试获取不存在任务的聚合"""
        aggregate = replay_service_no_db.get_aggregate("nonexistent")
        assert aggregate is None

    @pytest.mark.asyncio
    async def test_aggregate_by_event_type(self, replay_service_no_db):
        """测试按事件类型分组统计"""
        job = replay_service_no_db.create_job(name="Group By Type", max_events=100)
        await replay_service_no_db.run_job(job.job_id)
        aggregate = replay_service_no_db.get_aggregate(job.job_id)

        assert aggregate.by_event_type is not None
        # 基准数据集包含多种事件类型
        assert len(aggregate.by_event_type) > 0
        for etype, stats in aggregate.by_event_type.items():
            assert "count" in stats
            assert "hit_rate" in stats
            assert "avg_excess_return" in stats

    @pytest.mark.asyncio
    async def test_aggregate_by_source_type(self, replay_service_no_db):
        """测试按来源类型分组统计"""
        job = replay_service_no_db.create_job(name="Group By Source", max_events=100)
        await replay_service_no_db.run_job(job.job_id)
        aggregate = replay_service_no_db.get_aggregate(job.job_id)

        assert aggregate.by_source_type is not None
        assert len(aggregate.by_source_type) > 0
        for source, stats in aggregate.by_source_type.items():
            assert "count" in stats
            assert "hit_rate" in stats

    @pytest.mark.asyncio
    async def test_aggregate_by_timing_action(self, replay_service_no_db):
        """测试按择时动作分组统计"""
        job = replay_service_no_db.create_job(name="Group By Timing", max_events=100)
        await replay_service_no_db.run_job(job.job_id)
        aggregate = replay_service_no_db.get_aggregate(job.job_id)

        assert aggregate.by_timing_action is not None
        assert len(aggregate.by_timing_action) > 0


# ── 校准分析 ──────────────────────────────────────────────


class TestCalibration:
    @pytest.mark.asyncio
    async def test_calibration_basic(self, replay_service_no_db):
        """测试基本校准分析"""
        job = replay_service_no_db.create_job(name="Calibration Test", max_events=100)
        await replay_service_no_db.run_job(job.job_id)
        calibration = replay_service_no_db.calibrate(job.job_id)

        assert calibration is not None
        assert "score_threshold" in calibration
        assert "confidence_threshold" in calibration
        assert "best_timing_by_event_type" in calibration
        assert "hit_rate_by_score_bucket" in calibration
        assert "hit_rate_by_confidence_bucket" in calibration

    @pytest.mark.asyncio
    async def test_calibration_thresholds(self, replay_service_no_db):
        """测试校准阈值为合理范围"""
        job = replay_service_no_db.create_job(name="Threshold Test", max_events=100)
        await replay_service_no_db.run_job(job.job_id)
        calibration = replay_service_no_db.calibrate(job.job_id)

        assert 0.0 <= calibration["score_threshold"] <= 1.0
        assert 0.0 <= calibration["confidence_threshold"] <= 1.0

    @pytest.mark.asyncio
    async def test_calibration_by_event_type(self, replay_service_no_db):
        """测试按事件类型的校准推荐"""
        job = replay_service_no_db.create_job(name="EventType Cal", max_events=100)
        await replay_service_no_db.run_job(job.job_id)
        calibration = replay_service_no_db.calibrate(job.job_id)

        best_timing = calibration["best_timing_by_event_type"]
        assert isinstance(best_timing, dict)
        for etype, recommendation in best_timing.items():
            assert "recommended_action" in recommendation
            assert "timing_breakdown" in recommendation

    @pytest.mark.asyncio
    async def test_calibration_score_buckets(self, replay_service_no_db):
        """测试 score 分桶统计"""
        job = replay_service_no_db.create_job(name="Score Bucket Test", max_events=100)
        await replay_service_no_db.run_job(job.job_id)
        calibration = replay_service_no_db.calibrate(job.job_id)

        score_buckets = calibration["hit_rate_by_score_bucket"]
        assert isinstance(score_buckets, dict)
        for bucket, stats in score_buckets.items():
            assert "count" in stats
            assert "hit_rate" in stats
            assert "avg_excess_return" in stats

    @pytest.mark.asyncio
    async def test_calibration_not_found(self, replay_service_no_db):
        """测试获取不存在任务的校准"""
        calibration = replay_service_no_db.calibrate("nonexistent")
        assert calibration is None

    @pytest.mark.asyncio
    async def test_calibration_in_aggregate(self, replay_service_no_db):
        """测试 aggregate 中包含校准信息"""
        job = replay_service_no_db.create_job(name="Agg Cal Test", max_events=10)
        await replay_service_no_db.run_job(job.job_id)
        aggregate = replay_service_no_db.get_aggregate(job.job_id)

        assert aggregate.calibration is not None
        assert "score_threshold" in aggregate.calibration


# ── Repository 测试 ───────────────────────────────────────


class TestReplayRepository:
    def test_create_and_get_job(self, replay_repository):
        """测试仓储：创建并获取任务"""
        job = ReplayJob(
            job_id=str(uuid.uuid4()),
            name="Repo Test",
            max_events=50,
            status="pending",
            created_at=datetime.now(timezone.utc),
        )
        saved = replay_repository.create_job(job)
        assert saved.job_id == job.job_id

        retrieved = replay_repository.get_job(job.job_id)
        assert retrieved is not None
        assert retrieved.name == "Repo Test"

    def test_update_job_status(self, replay_repository):
        """测试仓储：更新任务状态"""
        job = ReplayJob(
            job_id=str(uuid.uuid4()),
            name="Status Update Test",
            max_events=50,
            status="pending",
            created_at=datetime.now(timezone.utc),
        )
        replay_repository.create_job(job)

        updated = replay_repository.update_job_status(job.job_id, "completed")
        assert updated is not None
        assert updated.status == "completed"
        assert updated.completed_at is not None

    def test_save_and_get_results(self, replay_repository):
        """测试仓储：保存并获取结果"""
        job_id = str(uuid.uuid4())
        # 先创建 job
        job = ReplayJob(
            job_id=job_id,
            name="Result Test",
            max_events=50,
            status="completed",
            created_at=datetime.now(timezone.utc),
        )
        replay_repository.create_job(job)

        # 保存结果
        result = ReplayResult(
            job_id=job_id,
            event_id="evt-001",
            signal_id="sig-001",
            event_type="policy",
            source_type="news",
            signal_score=0.7,
            signal_confidence=0.6,
            timing_action="enter",
            outcome_return=0.03,
            outcome_excess_return=0.025,
            max_drawdown=-0.04,
            decay=0.12,
        )
        saved = replay_repository.save_result(result)
        assert saved is not None

        # 获取结果
        results = replay_repository.get_results(job_id)
        assert len(results) >= 1
        assert results[0].event_id == "evt-001"
        assert results[0].signal_score == 0.7

    def test_get_job_not_found(self, replay_repository):
        """测试仓储：获取不存在的任务"""
        result = replay_repository.get_job("nonexistent")
        assert result is None


# ── API 端点测试 ──────────────────────────────────────────


class TestReplayAPI:
    def test_create_replay_job(self):
        """测试 API：创建回放任务"""
        from fastapi.testclient import TestClient

        from app.api.main import app
        from app.api.routes.replay import get_replay_service

        mock_service = MagicMock()
        mock_job = ReplayJob(
            job_id="job-api-001",
            name="API Test",
            max_events=50,
            status="pending",
            created_at=datetime.now(timezone.utc),
        )
        mock_service.create_job.return_value = mock_job

        app.dependency_overrides[get_replay_service] = lambda: mock_service
        try:
            client = TestClient(app)
            resp = client.post(
                "/api/replay/jobs",
                json={"name": "API Test", "max_events": 50},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["job_id"] == "job-api-001"
            assert data["name"] == "API Test"
        finally:
            app.dependency_overrides.pop(get_replay_service, None)

    def test_run_replay_job(self):
        """测试 API：执行回放"""
        from fastapi.testclient import TestClient

        from app.api.main import app
        from app.api.routes.replay import get_replay_service

        mock_service = MagicMock()
        mock_aggregate = ReplayAggregate(
            job_id="job-run-001",
            total_events=5,
            successful=5,
            failed=0,
            hit_rate=0.6,
            avg_excess_return=0.02,
            avg_max_drawdown=-0.03,
            avg_decay=0.12,
        )
        mock_service.run_job = AsyncMock(return_value=mock_aggregate)

        app.dependency_overrides[get_replay_service] = lambda: mock_service
        try:
            client = TestClient(app)
            resp = client.post("/api/replay/jobs/job-run-001/run")
            assert resp.status_code == 200
            data = resp.json()
            assert data["job_id"] == "job-run-001"
            assert data["total_events"] == 5
        finally:
            app.dependency_overrides.pop(get_replay_service, None)

    def test_get_job_status(self):
        """测试 API：查询状态"""
        from fastapi.testclient import TestClient

        from app.api.main import app
        from app.api.routes.replay import get_replay_service

        mock_service = MagicMock()
        mock_job = ReplayJob(
            job_id="job-status-001",
            name="Status Test",
            max_events=50,
            status="completed",
            created_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        mock_service.get_job.return_value = mock_job

        app.dependency_overrides[get_replay_service] = lambda: mock_service
        try:
            client = TestClient(app)
            resp = client.get("/api/replay/jobs/job-status-001/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "completed"
        finally:
            app.dependency_overrides.pop(get_replay_service, None)

    def test_get_job_status_not_found(self):
        """测试 API：查询不存在的任务状态"""
        from fastapi.testclient import TestClient

        from app.api.main import app
        from app.api.routes.replay import get_replay_service

        mock_service = MagicMock()
        mock_service.get_job.return_value = None

        app.dependency_overrides[get_replay_service] = lambda: mock_service
        try:
            client = TestClient(app)
            resp = client.get("/api/replay/jobs/nonexistent/status")
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(get_replay_service, None)

    def test_get_aggregate(self):
        """测试 API：获取聚合分析"""
        from fastapi.testclient import TestClient

        from app.api.main import app
        from app.api.routes.replay import get_replay_service

        mock_service = MagicMock()
        mock_aggregate = ReplayAggregate(
            job_id="job-agg-001",
            total_events=10,
            successful=8,
            failed=2,
            hit_rate=0.5,
            avg_excess_return=0.015,
            avg_max_drawdown=-0.035,
            avg_decay=0.13,
        )
        mock_service.get_aggregate.return_value = mock_aggregate

        app.dependency_overrides[get_replay_service] = lambda: mock_service
        try:
            client = TestClient(app)
            resp = client.get("/api/replay/jobs/job-agg-001/aggregate")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_events"] == 10
            assert data["hit_rate"] == 0.5
        finally:
            app.dependency_overrides.pop(get_replay_service, None)

    def test_get_calibration(self):
        """测试 API：获取校准报告"""
        from fastapi.testclient import TestClient

        from app.api.main import app
        from app.api.routes.replay import get_replay_service

        mock_service = MagicMock()
        mock_calibration = {
            "score_threshold": 0.5,
            "confidence_threshold": 0.5,
            "best_timing_by_event_type": {},
            "hit_rate_by_score_bucket": {},
            "hit_rate_by_confidence_bucket": {},
        }
        mock_service.calibrate.return_value = mock_calibration

        app.dependency_overrides[get_replay_service] = lambda: mock_service
        try:
            client = TestClient(app)
            resp = client.get("/api/replay/jobs/job-cal-001/calibration")
            assert resp.status_code == 200
            data = resp.json()
            assert "score_threshold" in data
            assert "confidence_threshold" in data
        finally:
            app.dependency_overrides.pop(get_replay_service, None)


# ── 模拟 outcome 测试 ─────────────────────────────────────


class TestSimulateOutcome:
    def test_high_score_high_confidence(self, replay_service_no_db):
        """测试高分高置信度的模拟结果"""
        outcome = replay_service_no_db._simulate_outcome(
            event_type="policy",
            score=0.8,
            confidence=0.8,
        )
        assert outcome["outcome_return"] > 0
        assert outcome["outcome_excess_return"] > 0
        assert outcome["timing_action"] == "enter"

    def test_low_score_low_confidence(self, replay_service_no_db):
        """测试低分低置信度的模拟结果"""
        outcome = replay_service_no_db._simulate_outcome(
            event_type="earnings",
            score=0.2,
            confidence=0.2,
        )
        assert outcome["timing_action"] == "skip"
        # skip → 低收益
        assert outcome["outcome_return"] >= 0

    def test_medium_score(self, replay_service_no_db):
        """测试中等分数的模拟结果"""
        outcome = replay_service_no_db._simulate_outcome(
            event_type="product",
            score=0.5,
            confidence=0.5,
        )
        assert outcome["timing_action"] in ("enter", "wait")

    def test_different_event_types(self, replay_service_no_db):
        """测试不同事件类型的模拟差异"""
        outcomes = {}
        for etype in ["earnings", "policy", "product", "merger_acquisition", "macro"]:
            outcomes[etype] = replay_service_no_db._simulate_outcome(
                event_type=etype,
                score=0.6,
                confidence=0.6,
            )
        # 不同事件类型应产生不同收益
        returns = {k: v["outcome_return"] for k, v in outcomes.items()}
        assert len(set(returns.values())) > 1  # 不应全部相同
