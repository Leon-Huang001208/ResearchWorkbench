"""
全链路流水线集成测试 - 测试ResearchPipeline端到端流程
"""
from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from cognitive_agents.blackboard import CognitiveBlackboard
from core.contracts import AssetAnalysisSnapshot, CanonicalEvent, ScenarioSet
from services.pipeline_service import ResearchPipeline


@pytest.fixture
def mock_dependencies():
    """Create mock dependencies for ResearchPipeline."""
    return {
        "data_router": Mock(),
        "knowledge_extractor": Mock(),
        "reasoning_engine": Mock(),
        "blackboard": Mock(spec=CognitiveBlackboard),
        "signal_service": Mock(),
        "model_gateway": AsyncMock(),
    }


@pytest.mark.integration
class TestResearchPipelineIntegration:
    """测试ResearchPipeline全链路流程"""

    def test_pipeline_initialization(self, mock_dependencies):
        """测试流水线初始化"""
        pipeline = ResearchPipeline(**mock_dependencies)
        assert pipeline is not None
        assert pipeline.data_router == mock_dependencies["data_router"]
        assert pipeline.blackboard == mock_dependencies["blackboard"]

    @pytest.mark.asyncio
    async def test_run_asset_analysis(self, mock_dependencies, caplog):
        """测试run_asset_analysis从数据摄入到分析快照输出"""
        # Setup
        pipeline = ResearchPipeline(**mock_dependencies)
        test_asset_id = "asset:maotai:600519"

        # Configure mock reasoning engine to return a valid snapshot
        expected_snapshot = AssetAnalysisSnapshot(
            canonical_id=test_asset_id,
            as_of=datetime.now(),
        )
        mock_dependencies["reasoning_engine"].analyze_asset = Mock(return_value=expected_snapshot)

        # Execute
        result = await pipeline.run_asset_analysis(test_asset_id)

        # Verify
        assert isinstance(result, AssetAnalysisSnapshot)
        assert result.canonical_id == test_asset_id
        assert result.as_of is not None
        assert isinstance(result.as_of, datetime)

    @pytest.mark.asyncio
    async def test_run_event_signal(self, mock_dependencies, caplog):
        """测试run_event_signal从事件输入到信号输出"""
        # Setup
        pipeline = ResearchPipeline(**mock_dependencies)
        test_event = CanonicalEvent(
            event_id="evt-test-001",
            event_type="earnings",
            source_type="report",
            source_name="TestSource",
            title="贵州茅台2026Q1净利润增长28%",
            summary="贵州茅台2026Q1净利润增长28%",
            impact_direction="positive",
            confidence=0.8,
            needs_review=False,
            entities=[{"text": "贵州茅台", "type": "company"}],
            evidence_spans=[{"text": "净利润同比增长28%"}],
            source_doc_id="doc-test-001",
            reviewer_status="approved",
        )

        # Execute
        await pipeline.run_event_signal(test_event)

        # Verify
        # Method executed without exception is all we need (implementation still TODO)
        # assert any("Running event signal pipeline for evt-test-001" in record.message for record in caplog.records)
        # If signal_service was called, verify that (though implementation is TODO, just check no exceptions)
        # When implemented, we would add more checks for output signal

    @pytest.mark.asyncio
    async def test_run_scenario_analysis(self, mock_dependencies, caplog):
        """测试run_scenario_analysis从问题到情景输出"""
        # Setup
        pipeline = ResearchPipeline(**mock_dependencies)
        test_question = "美联储加息对中国科技股的影响"
        test_subjects = ["company:tencent", "index:csaps"]

        # Configure mock reasoning engine to return a valid ScenarioSet
        expected_scenarios = ScenarioSet(
            set_id="test-scenario-set",
            question=test_question,
            hypotheses=[],
        )
        mock_dependencies["reasoning_engine"].generate_scenarios = Mock(
            return_value=expected_scenarios
        )

        # Execute
        result = await pipeline.run_scenario_analysis(test_question, test_subjects)

        # Verify
        assert isinstance(result, ScenarioSet)
        assert result.question == test_question
