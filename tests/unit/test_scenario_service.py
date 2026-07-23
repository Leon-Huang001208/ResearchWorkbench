"""
测试情景服务
"""

from unittest.mock import Mock, patch

from services.scenario_service import ScenarioService


class TestScenarioService:
    """测试情景服务"""

    def test_generate_scenario_set_basic(self):
        """测试生成情景集合"""
        service = ScenarioService()
        scenario_set = service.generate_scenario_set(topic="人工智能产业发展对股票市场的影响")

        assert scenario_set is not None
        assert scenario_set.question == "人工智能产业发展对股票市场的影响"
        assert len(scenario_set.hypotheses) > 0

        for hypothesis in scenario_set.hypotheses:
            assert hypothesis.title
            assert hypothesis.probability >= 0
            assert hypothesis.probability <= 1

    def test_generate_scenario_set_with_subjects(self):
        """测试带主题 ID 的情景生成"""
        service = ScenarioService()
        scenario_set = service.generate_scenario_set(
            topic="新能源汽车政策", subject_ids=["600000.SH", "000001.SZ"]
        )

        assert scenario_set is not None
        assert len(scenario_set.hypotheses) > 0

    def test_generate_thesis_report(self, tmp_path):
        """测试生成专题研究报告"""
        output_path = tmp_path / "report.md"

        service = ScenarioService()
        report_content = service.generate_thesis_report(
            topic="美联储政策走向", output_path=output_path
        )

        assert report_content
        assert "# 美联储政策走向" in report_content
        assert "## 情景分析" in report_content

        # 验证文件已保存
        assert output_path.exists()
        saved_content = output_path.read_text(encoding="utf-8")
        assert saved_content == report_content

    def test_generate_thesis_report_without_output(self):
        """测试不保存文件的报告生成"""
        service = ScenarioService()
        report_content = service.generate_thesis_report(topic="宏观经济展望")

        assert report_content
        assert len(report_content) > 0

    def test_hypothesis_structure(self):
        """测试情景假设的结构"""
        service = ScenarioService()
        scenario_set = service.generate_scenario_set(topic="测试主题")

        for hypothesis in scenario_set.hypotheses:
            assert hypothesis.scenario_id
            assert hypothesis.title
            assert hypothesis.probability is not None
            # 可选字段可能存在也可能不存在，不强制断言

    @patch("services.scenario_service.ReasoningEngine")
    def test_with_mock_reasoning_engine(self, mock_engine_class):
        """测试使用模拟推理引擎"""
        # 设置模拟
        mock_engine = Mock()
        mock_state = Mock()
        mock_state.trace_id = "test-trace-123"
        mock_state.hypotheses = []
        mock_state.residual_uncertainty = ["测试不确定性"]
        mock_engine.run.return_value = mock_state
        mock_engine_class.return_value = mock_engine

        service = ScenarioService(reasoning_engine=mock_engine)
        scenario_set = service.generate_scenario_set(topic="测试主题")

        assert scenario_set.set_id == "test-trace-123"
        mock_engine.run.assert_called_once()
