"""
Memory & Learning CLI 命令
"""
from typing import Optional

import click

from core.observability import get_logger
from memory_learning.journal import LearningJournal
from memory_learning.contracts import (
    MarketEpisode,
    FailureMemory,
)

logger = get_logger(__name__)


def get_journal() -> LearningJournal:
    """获取 LearningJournal 实例（单例）"""
    if not hasattr(get_journal, "_instance"):
        get_journal._instance = LearningJournal()
    return get_journal._instance


@click.group(name="memory")
def memory_group():
    """
    Memory & Learning 管理命令

    示例:
        af memory record-episode --episode-id test-001 --event-id evt-001 --event-type earnings --market-regime bullish --initial-reaction up --outcome-horizon 20d --outcome-return 0.05 --outcome-excess-return 0.03
        af memory list-episodes
        af memory summarize earnings
        af memory record-failure --failure-id fail-001 --source-id test-001 --failure-type timing_error --root-cause "Bad timing" --corrective-action "Adjust timing model"
        af memory list-failures
    """
    pass


# ─── Episode Commands ──────────────────────────────────────────────────


@memory_group.command(name="record-episode")
@click.option("--episode-id", required=True, help="Episode ID")
@click.option("--event-id", required=True, help="Event ID")
@click.option("--event-type", required=True, help="Event type (e.g., earnings, policy)")
@click.option("--market-regime", required=True, help="Market regime (e.g., bullish, risk_off)")
@click.option("--initial-reaction", required=True, help="Initial market reaction (e.g., up, down)")
@click.option("--outcome-horizon", type=click.Choice(["1d", "5d", "20d", "30d", "60d"]), required=True, help="Outcome horizon")
@click.option("--outcome-return", type=float, required=True, help="Outcome return (e.g., 0.05 for 5%)")
@click.option("--outcome-excess-return", type=float, required=True, help="Outcome excess return (e.g., 0.03 for 3%)")
@click.option("--timing-action", type=click.Choice(["enter", "wait", "reduce", "exit", "block"]), help="Timing action taken")
@click.option("--signal-id", help="Signal ID")
@click.option("--timing-decision-id", help="Timing decision ID")
@click.option("--failed-reason", help="Failed reason")
@click.option("--lesson", help="Lesson learned")
def record_episode(
    episode_id: str,
    event_id: str,
    event_type: str,
    market_regime: str,
    initial_reaction: str,
    outcome_horizon: str,
    outcome_return: float,
    outcome_excess_return: float,
    timing_action: Optional[str],
    signal_id: Optional[str],
    timing_decision_id: Optional[str],
    failed_reason: Optional[str],
    lesson: Optional[str],
):
    """记录事件记忆"""
    click.echo(f"Recording episode: {episode_id}")

    try:
        journal = get_journal()
        episode = MarketEpisode(
            episode_id=episode_id,
            event_id=event_id,
            event_type=event_type,
            market_regime=market_regime,
            initial_reaction=initial_reaction,
            outcome_horizon=outcome_horizon,  # type: ignore[arg-type]
            outcome_return=outcome_return,
            outcome_excess_return=outcome_excess_return,
            timing_action=timing_action,  # type: ignore[arg-type]
            signal_id=signal_id,
            timing_decision_id=timing_decision_id,
            failed_reason=failed_reason,
            lesson=lesson,
        )
        journal.record_episode(episode)
        click.echo(f"\n✓ Episode recorded: {episode_id}")
    except Exception as e:
        click.echo(f"\n✗ Failed to record episode: {e}", err=True)
        logger.error("Failed to record episode", error=str(e), exc_info=True)
        raise click.Abort()


@memory_group.command(name="list-episodes")
@click.option("--event-type", help="Filter by event type")
@click.option("--market-regime", help="Filter by market regime")
def list_episodes(event_type: Optional[str], market_regime: Optional[str]):
    """列出事件记忆"""
    try:
        journal = get_journal()
        episodes = journal.list_episodes(event_type=event_type, market_regime=market_regime)

        if not episodes:
            click.echo("No episodes found")
            return

        click.echo(f"\nFound {len(episodes)} episode(s):")
        click.echo("-" * 80)

        for i, episode in enumerate(episodes, 1):
            click.echo(f"{i}. [{episode.event_type}] {episode.episode_id} - {episode.market_regime}")
            click.echo(f"   Event ID: {episode.event_id}")
            click.echo(f"   Initial Reaction: {episode.initial_reaction}")
            click.echo(f"   Outcome Return: {episode.outcome_return:.2%}, Excess: {episode.outcome_excess_return:.2%}")
            if episode.timing_action:
                click.echo(f"   Timing Action: {episode.timing_action}")
            if episode.lesson:
                click.echo(f"   Lesson: {episode.lesson}")
            click.echo()

    except Exception as e:
        click.echo(f"\n✗ Failed to list episodes: {e}", err=True)
        logger.error("Failed to list episodes", error=str(e), exc_info=True)
        raise click.Abort()


@memory_group.command(name="summarize")
@click.argument("event_type")
def summarize_event_type(event_type: str):
    """汇总事件类型统计"""
    try:
        journal = get_journal()
        summary = journal.summarize_event_type(event_type)

        click.echo(f"\nSummary for event type: {event_type}")
        click.echo("-" * 80)
        click.echo(f"Sample Size: {summary['sample_size']}")
        click.echo(f"Win Rate: {summary['win_rate']:.2%}")
        click.echo(f"Average Excess Return: {summary['average_excess_return']:.2%}")

    except Exception as e:
        click.echo(f"\n✗ Failed to summarize event type: {e}", err=True)
        logger.error("Failed to summarize event type", error=str(e), exc_info=True)
        raise click.Abort()


# ─── Failure Commands ─────────────────────────────────────────────────


@memory_group.command(name="record-failure")
@click.option("--failure-id", required=True, help="Failure ID")
@click.option("--source-id", required=True, help="Source ID (episode, signal, etc.)")
@click.option("--failure-type", type=click.Choice(["wrong_thesis", "timing_error", "crowding_error", "regime_misread", "data_quality", "execution_error", "risk_error", "unknown"]), required=True, help="Failure type")
@click.option("--root-cause", required=True, help="Root cause of failure")
@click.option("--corrective-action", required=True, help="Corrective action to take")
@click.option("--evidence-ref", multiple=True, help="Evidence references (can specify multiple)")
def record_failure(
    failure_id: str,
    source_id: str,
    failure_type: str,
    root_cause: str,
    corrective_action: str,
    evidence_ref: tuple,
):
    """记录失败记忆"""
    click.echo(f"Recording failure: {failure_id}")

    try:
        journal = get_journal()
        failure = FailureMemory(
            failure_id=failure_id,
            source_id=source_id,
            failure_type=failure_type,  # type: ignore[arg-type]
            root_cause=root_cause,
            corrective_action=corrective_action,
            evidence_refs=list(evidence_ref),
        )
        journal.record_failure(failure)
        click.echo(f"\n✓ Failure recorded: {failure_id}")
    except Exception as e:
        click.echo(f"\n✗ Failed to record failure: {e}", err=True)
        logger.error("Failed to record failure", error=str(e), exc_info=True)
        raise click.Abort()


@memory_group.command(name="list-failures")
@click.option("--failure-type", help="Filter by failure type")
@click.option("--source-id", help="Filter by source ID")
def list_failures(failure_type: Optional[str], source_id: Optional[str]):
    """列出失败记忆"""
    try:
        journal = get_journal()
        failures = journal.list_failures(failure_type=failure_type, source_id=source_id)

        if not failures:
            click.echo("No failures found")
            return

        click.echo(f"\nFound {len(failures)} failure(s):")
        click.echo("-" * 80)

        for i, failure in enumerate(failures, 1):
            click.echo(f"{i}. [{failure.failure_type}] {failure.failure_id} - {failure.source_id}")
            click.echo(f"   Root Cause: {failure.root_cause}")
            click.echo(f"   Corrective Action: {failure.corrective_action}")
            if failure.evidence_refs:
                click.echo(f"   Evidence Refs: {', '.join(failure.evidence_refs)}")
            click.echo()

    except Exception as e:
        click.echo(f"\n✗ Failed to list failures: {e}", err=True)
        logger.error("Failed to list failures", error=str(e), exc_info=True)
        raise click.Abort()


memory = memory_group
