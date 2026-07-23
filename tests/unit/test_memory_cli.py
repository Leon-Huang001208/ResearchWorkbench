"""Memory CLI 测试"""

import pytest
from click.testing import CliRunner

from app.cli.main import cli


@pytest.fixture
def runner():
    """CLI runner fixture"""
    return CliRunner()


@pytest.fixture
def clean_journal():
    """Reset the journal singleton before each test"""
    from app.cli.commands.memory import get_journal

    if hasattr(get_journal, "_instance"):
        delattr(get_journal, "_instance")
    return get_journal()


def test_record_episode_cli(runner, clean_journal):
    """测试 CLI 记录事件记忆"""
    result = runner.invoke(
        cli,
        [
            "memory",
            "record-episode",
            "--episode-id",
            "test-cli-episode-001",
            "--event-id",
            "test-cli-event-001",
            "--event-type",
            "earnings",
            "--market-regime",
            "bullish",
            "--initial-reaction",
            "up",
            "--outcome-horizon",
            "20d",
            "--outcome-return",
            "0.05",
            "--outcome-excess-return",
            "0.03",
        ],
    )
    assert result.exit_code == 0
    assert "✓ Episode recorded: test-cli-episode-001" in result.output


def test_list_episodes_cli(runner, clean_journal):
    """测试 CLI 列出事件记忆"""
    # First record an episode
    runner.invoke(
        cli,
        [
            "memory",
            "record-episode",
            "--episode-id",
            "test-cli-episode-002",
            "--event-id",
            "test-cli-event-002",
            "--event-type",
            "policy",
            "--market-regime",
            "risk_off",
            "--initial-reaction",
            "down",
            "--outcome-horizon",
            "5d",
            "--outcome-return",
            "-0.02",
            "--outcome-excess-return",
            "-0.01",
        ],
    )

    result = runner.invoke(cli, ["memory", "list-episodes", "--event-type", "policy"])
    assert result.exit_code == 0
    assert "test-cli-episode-002" in result.output


def test_summarize_cli(runner, clean_journal):
    """测试 CLI 汇总事件类型"""
    # Record two episodes
    runner.invoke(
        cli,
        [
            "memory",
            "record-episode",
            "--episode-id",
            "test-cli-episode-003",
            "--event-id",
            "test-cli-event-003",
            "--event-type",
            "earnings",
            "--market-regime",
            "bullish",
            "--initial-reaction",
            "up",
            "--outcome-horizon",
            "20d",
            "--outcome-return",
            "0.05",
            "--outcome-excess-return",
            "0.03",
        ],
    )
    runner.invoke(
        cli,
        [
            "memory",
            "record-episode",
            "--episode-id",
            "test-cli-episode-004",
            "--event-id",
            "test-cli-event-004",
            "--event-type",
            "earnings",
            "--market-regime",
            "bullish",
            "--initial-reaction",
            "down",
            "--outcome-horizon",
            "20d",
            "--outcome-return",
            "-0.02",
            "--outcome-excess-return",
            "-0.01",
        ],
    )

    result = runner.invoke(cli, ["memory", "summarize", "earnings"])
    assert result.exit_code == 0
    assert "Sample Size: 2" in result.output
    assert "Win Rate: 50.00%" in result.output


def test_record_failure_cli(runner, clean_journal):
    """测试 CLI 记录失败记忆"""
    result = runner.invoke(
        cli,
        [
            "memory",
            "record-failure",
            "--failure-id",
            "test-cli-failure-001",
            "--source-id",
            "test-cli-signal-001",
            "--failure-type",
            "timing_error",
            "--root-cause",
            "Entered too early",
            "--corrective-action",
            "Wait for confirmation",
        ],
    )
    assert result.exit_code == 0
    assert "✓ Failure recorded: test-cli-failure-001" in result.output


def test_list_failures_cli(runner, clean_journal):
    """测试 CLI 列出失败记忆"""
    # First record a failure
    runner.invoke(
        cli,
        [
            "memory",
            "record-failure",
            "--failure-id",
            "test-cli-failure-002",
            "--source-id",
            "test-cli-signal-002",
            "--failure-type",
            "crowding_error",
            "--root-cause",
            "Too crowded",
            "--corrective-action",
            "Avoid crowded trades",
        ],
    )

    result = runner.invoke(cli, ["memory", "list-failures", "--failure-type", "crowding_error"])
    assert result.exit_code == 0
    assert "test-cli-failure-002" in result.output
