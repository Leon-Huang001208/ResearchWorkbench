"""Tests for analyze CLI command."""
from unittest.mock import Mock, patch

from click.testing import CliRunner

from app.cli.commands.analyze import analyze_command


class TestAnalyzeCommand:
    """Test suite for analyze CLI command."""

    def test_analyze_basic(self):
        """Test basic analyze command execution."""
        runner = CliRunner()

        with patch("app.cli.commands.analyze.get_db") as mock_get_db, patch(
            "app.cli.commands.analyze.AssetAnalysisService"
        ) as mock_service, patch(
            "app.cli.commands.analyze.AssetSnapshotRepositoryImpl"
        ) as mock_repo:
            # Setup mocks
            mock_session = Mock()
            mock_get_db.return_value.__enter__.return_value = mock_session

            mock_snapshot = Mock()
            mock_snapshot.canonical_id = "600000.SH"
            mock_snapshot.valuation = {"pe_ttm": 24.9}
            mock_snapshot.price_volume = {"close_price": 58.5}

            mock_service_instance = Mock()
            mock_service_instance.generate_snapshot.return_value = mock_snapshot
            mock_service.return_value = mock_service_instance

            result = runner.invoke(
                analyze_command,
                ["--asset", "600000.SH"],
            )

            assert result.exit_code == 0
            assert "600000.SH" in result.output

    def test_analyze_with_output_file(self, tmp_path):
        """Test analyze with output to file."""
        runner = CliRunner()
        output_file = tmp_path / "report.md"

        with patch("app.cli.commands.analyze.get_db"), patch(
            "app.cli.commands.analyze.AssetAnalysisService"
        ) as mock_service, patch("app.cli.commands.analyze.AssetSnapshotRepositoryImpl"), patch(
            "app.cli.commands.analyze.MarkdownProjection"
        ) as mock_md:
            mock_snapshot = Mock()
            mock_snapshot.canonical_id = "600000.SH"
            mock_snapshot.valuation = {}
            mock_snapshot.price_volume = {}
            mock_snapshot.evidence_refs = []
            mock_snapshot.event_impact = []
            mock_snapshot.as_of = "2026-05-05"

            mock_service_instance = Mock()
            mock_service_instance.generate_snapshot.return_value = mock_snapshot
            mock_service.return_value = mock_service_instance

            mock_projection = Mock()
            mock_md.return_value = mock_projection

            result = runner.invoke(
                analyze_command,
                ["--asset", "600000.SH", "--output", str(output_file)],
            )

            assert result.exit_code == 0
            mock_projection.save.assert_called_once()

    def test_analyze_without_mock(self):
        """Test analyze with --no-mock flag."""
        runner = CliRunner()

        with patch("app.cli.commands.analyze.get_db"), patch(
            "app.cli.commands.analyze.AssetAnalysisService"
        ) as mock_service, patch("app.cli.commands.analyze.AssetSnapshotRepositoryImpl"):
            mock_snapshot = Mock()
            mock_snapshot.canonical_id = "600000.SH"
            mock_snapshot.valuation = {}
            mock_snapshot.price_volume = {}

            mock_service_instance = Mock()
            mock_service_instance.generate_snapshot.return_value = mock_snapshot
            mock_service.return_value = mock_service_instance

            result = runner.invoke(
                analyze_command,
                ["--asset", "600000.SH", "--no-mock"],
            )

            assert result.exit_code == 0
            # Verify use_mock=False was passed
            call_kwargs = mock_service_instance.generate_snapshot.call_args
            assert call_kwargs.kwargs["use_mock"] is False

    def test_analyze_with_as_of(self):
        """Test analyze with --as-of flag."""
        runner = CliRunner()

        with patch("app.cli.commands.analyze.get_db"), patch(
            "app.cli.commands.analyze.AssetAnalysisService"
        ) as mock_service, patch("app.cli.commands.analyze.AssetSnapshotRepositoryImpl"):
            mock_snapshot = Mock()
            mock_snapshot.canonical_id = "600000.SH"
            mock_snapshot.valuation = {}
            mock_snapshot.price_volume = {}

            mock_service_instance = Mock()
            mock_service_instance.generate_snapshot.return_value = mock_snapshot
            mock_service.return_value = mock_service_instance

            result = runner.invoke(
                analyze_command,
                ["--asset", "600000.SH", "--as-of", "2026-05-03T12:00:00"],
            )

            assert result.exit_code == 0

    def test_analyze_invalid_date(self):
        """Test analyze with invalid date format."""
        runner = CliRunner()

        result = runner.invoke(
            analyze_command,
            ["--asset", "600000.SH", "--as-of", "invalid-date"],
        )

        assert result.exit_code != 0
        assert "Invalid date format" in result.output

    def test_analyze_handles_service_error(self):
        """Test that analyze handles service errors gracefully."""
        runner = CliRunner()

        with patch("app.cli.commands.analyze.get_db"), patch(
            "app.cli.commands.analyze.AssetAnalysisService"
        ) as mock_service, patch("app.cli.commands.analyze.AssetSnapshotRepositoryImpl"):
            mock_service_instance = Mock()
            mock_service_instance.generate_snapshot.side_effect = Exception("API Error")
            mock_service.return_value = mock_service_instance

            result = runner.invoke(
                analyze_command,
                ["--asset", "600000.SH"],
            )

            assert result.exit_code != 0
            assert "Failed to generate snapshot" in result.output
