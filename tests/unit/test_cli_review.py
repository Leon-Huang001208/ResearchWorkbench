"""
测试 review CLI 命令
"""
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from app.cli.commands.review import review_group


class TestReviewCLI:
    """测试 review CLI 命令组"""

    def test_review_list_empty(self):
        """测试 review list 命令（无待审核）"""
        runner = CliRunner()

        with patch("app.cli.commands.review.ReviewService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.list_pending_assertions.return_value = []
            mock_service_class.return_value = mock_service

            result = runner.invoke(review_group, ["list"])

            assert result.exit_code == 0
            assert "Pending review items" in result.output
            assert "No pending assertions" in result.output

    def test_review_list_with_items(self):
        """测试 review list 命令（有待审核）"""
        runner = CliRunner()

        with patch("app.cli.commands.review.ReviewService") as mock_service_class:
            mock_service = MagicMock()
            mock_assertion1 = MagicMock()
            mock_assertion1.assertion_id = "assert-1"
            mock_assertion1.subject_entity_id = "600000.SH"
            mock_assertion1.predicate = "净利润增长"
            mock_assertion1.object_value = "28%"
            mock_assertion1.confidence = 0.85
            mock_assertion1.source_doc_id = "doc-1"

            mock_assertion2 = MagicMock()
            mock_assertion2.assertion_id = "assert-2"
            mock_assertion2.subject_entity_id = None
            mock_assertion2.predicate = "政策变化"
            mock_assertion2.object_value = None
            mock_assertion2.object_entity_id = "policy-1"
            mock_assertion2.confidence = 0.75
            mock_assertion2.source_doc_id = "doc-2"

            mock_service.list_pending_assertions.return_value = [mock_assertion1, mock_assertion2]
            mock_service_class.return_value = mock_service

            result = runner.invoke(review_group, ["list"])

            assert result.exit_code == 0
            assert "assert-1" in result.output
            assert "assert-2" in result.output
            assert "净利润增长" in result.output

    def test_review_list_with_limit(self):
        """测试带 limit 选项的 review list 命令"""
        runner = CliRunner()

        with patch("app.cli.commands.review.ReviewService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.list_pending_assertions.return_value = []
            mock_service_class.return_value = mock_service

            result = runner.invoke(review_group, ["list", "--limit", "50"])

            assert result.exit_code == 0
            mock_service.list_pending_assertions.assert_called_with(limit=50)

    def test_review_approve(self):
        """测试 review approve 命令"""
        runner = CliRunner()

        with patch("app.cli.commands.review.ReviewService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.approve_assertion.return_value = True
            mock_service_class.return_value = mock_service

            result = runner.invoke(review_group, ["approve", "assert-123"])

            assert result.exit_code == 0
            assert "Approving assertion" in result.output
            assert "Assertion approved" in result.output
            mock_service.approve_assertion.assert_called_with("assert-123", reviewer="cli")

    def test_review_approve_with_reviewer(self):
        """测试带 reviewer 选项的 review approve 命令"""
        runner = CliRunner()

        with patch("app.cli.commands.review.ReviewService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.approve_assertion.return_value = True
            mock_service_class.return_value = mock_service

            result = runner.invoke(review_group, ["approve", "assert-123", "--reviewer", "研究员A"])

            assert result.exit_code == 0
            mock_service.approve_assertion.assert_called_with("assert-123", reviewer="研究员A")

    def test_review_approve_failure(self):
        """测试 review approve 命令失败"""
        runner = CliRunner()

        with patch("app.cli.commands.review.ReviewService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.approve_assertion.return_value = False
            mock_service_class.return_value = mock_service

            result = runner.invoke(review_group, ["approve", "assert-123"])

            assert result.exit_code == 0
            assert "Failed to approve assertion" in result.output

    def test_review_reject(self):
        """测试 review reject 命令"""
        runner = CliRunner()

        with patch("app.cli.commands.review.ReviewService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.reject_assertion.return_value = True
            mock_service_class.return_value = mock_service

            result = runner.invoke(review_group, ["reject", "assert-123"])

            assert result.exit_code == 0
            assert "Rejecting assertion" in result.output
            assert "Assertion rejected" in result.output
            mock_service.reject_assertion.assert_called_with("assert-123", reviewer="cli")

    def test_review_reject_with_reviewer(self):
        """测试带 reviewer 选项的 review reject 命令"""
        runner = CliRunner()

        with patch("app.cli.commands.review.ReviewService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.reject_assertion.return_value = True
            mock_service_class.return_value = mock_service

            result = runner.invoke(review_group, ["reject", "assert-123", "--reviewer", "研究员A"])

            assert result.exit_code == 0
            mock_service.reject_assertion.assert_called_with("assert-123", reviewer="研究员A")

    def test_review_stats(self):
        """测试 review stats 命令"""
        runner = CliRunner()

        with patch("app.cli.commands.review.ReviewService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_statistics.return_value = {
                "pending_assertions": 5,
                "approved_assertions": 12,
                "rejected_assertions": 3,
                "pending_events": 0,
            }
            mock_service_class.return_value = mock_service

            result = runner.invoke(review_group, ["stats"])

            assert result.exit_code == 0
            assert "Review statistics" in result.output
            assert "Pending assertions: 5" in result.output
            assert "Approved assertions: 12" in result.output
            assert "Rejected assertions: 3" in result.output

    def test_review_error_handling(self):
        """测试错误处理"""
        runner = CliRunner()

        with patch("app.cli.commands.review.ReviewService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_statistics.side_effect = Exception("测试错误")
            mock_service_class.return_value = mock_service

            result = runner.invoke(review_group, ["stats"])

            assert result.exit_code != 0
            assert "Failed to get stats" in result.output
