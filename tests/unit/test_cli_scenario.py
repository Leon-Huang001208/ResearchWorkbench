"""
测试 scenario CLI 命令
"""
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from app.cli.commands.scenario import scenario_command


class TestScenarioCLI:
    """测试 scenario CLI 命令"""

    def test_scenario_basic(self):
        """测试基本 scenario 命令"""
        runner = CliRunner()

        with patch("app.cli.commands.scenario.ScenarioService") as mock_service_class:
            # 设置模拟服务
            mock_service = MagicMock()
            mock_service.generate_thesis_report.return_value = "# 测试报告\n\n## 摘要..."
            mock_service_class.return_value = mock_service

            result = runner.invoke(scenario_command, ["--topic", "人工智能产业发展"])

            assert result.exit_code == 0
            assert "Generating scenario analysis for" in result.output
            mock_service.generate_thesis_report.assert_called_once()

    def test_scenario_with_output(self, tmp_path):
        """测试带输出文件的 scenario 命令"""
        runner = CliRunner()
        output_file = tmp_path / "report.md"

        with patch("app.cli.commands.scenario.ScenarioService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.generate_thesis_report.return_value = "# 测试报告"
            mock_service_class.return_value = mock_service

            result = runner.invoke(
                scenario_command, ["--topic", "美联储政策", "--output", str(output_file)]
            )

            assert result.exit_code == 0
            assert "Report saved to" in result.output
            mock_service.generate_thesis_report.assert_called_once()

    def test_scenario_with_subjects(self):
        """测试带主题 ID 的 scenario 命令"""
        runner = CliRunner()

        with patch("app.cli.commands.scenario.ScenarioService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.generate_thesis_report.return_value = "# 测试报告"
            mock_service_class.return_value = mock_service

            result = runner.invoke(
                scenario_command,
                ["--topic", "新能源汽车", "--subject", "600000.SH", "--subject", "000001.SZ"],
            )

            assert result.exit_code == 0
            call_args = mock_service.generate_thesis_report.call_args
            assert call_args[1]["subject_ids"] == ["600000.SH", "000001.SZ"]

    def test_scenario_missing_topic(self):
        """测试缺少必需的 topic 参数"""
        runner = CliRunner()

        result = runner.invoke(scenario_command, [])

        assert result.exit_code != 0
        assert "Missing option" in result.output

    def test_scenario_error_handling(self):
        """测试错误处理"""
        runner = CliRunner()

        with patch("app.cli.commands.scenario.ScenarioService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.generate_thesis_report.side_effect = Exception("测试错误")
            mock_service_class.return_value = mock_service

            result = runner.invoke(scenario_command, ["--topic", "测试主题"])

            assert result.exit_code != 0
            assert "Failed to generate report" in result.output
