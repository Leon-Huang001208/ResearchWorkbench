"""
Timing CLI 命令
"""
import json
from typing import Optional

import click

from core.observability import get_logger
from timing_engine import MetaTimingEngine

logger = get_logger(__name__)


@click.group(name="timing")
def timing_group():
    """
    Timing 管理命令

    示例:
        af timing evaluate --scores '[{"model_name": "regime", "score": 0.8, "confidence": 0.9, "rationale": "test"}]'
        af timing regime-weights --regime hot_money_theme
    """
    pass


@timing_group.command(name="evaluate")
@click.option("--scores", required=True, help="JSON 格式的 TimingModelScore 列表")
@click.option("--signal-id", help="信号 ID")
@click.option("--regime", default="unknown", help="市场 regime")
def evaluate(scores: str, signal_id: Optional[str], regime: str):
    """Evaluate timing decision from model scores"""
    click.echo("Evaluating timing decision")

    try:
        engine = MetaTimingEngine()
        scores_data = json.loads(scores)
        [
            # We'll just validate the data structure, proper parsing would use Pydantic
            type("TimingModelScore", (object,), s)
            for s in scores_data
        ]
        # Wait, better to use Pydantic to parse
        from timing_engine import TimingModelScore

        parsed_scores = [TimingModelScore(**s) for s in scores_data]
        decision = engine.evaluate(parsed_scores, signal_id=signal_id, market_regime=regime)
        click.echo("\n✓ Timing decision:")
        click.echo(f"  Action: {decision.action}")
        click.echo(f"  Readiness score: {decision.readiness_score:.3f}")
        click.echo(f"  Regime: {decision.market_regime}")
        if decision.blockers:
            click.echo(f"  Blockers: {', '.join(decision.blockers)}")
        if decision.rationale:
            click.echo(f"  Rationale: {'; '.join(decision.rationale)}")
    except Exception as e:
        click.echo(f"\n✗ Failed to evaluate timing: {e}", err=True)
        logger.error("Failed to evaluate timing", error=str(e), exc_info=True)
        raise click.Abort()


@timing_group.command(name="regime-weights")
@click.option("--regime", required=True, help="市场 regime (ai_growth/hot_money_theme/etc.)")
def regime_weights(regime: str):
    """Get model weights for a regime"""
    try:
        engine = MetaTimingEngine()
        weights = engine.weights_for_regime(regime)
        click.echo(f"\nRegime weights for '{regime}':")
        for model, weight in weights.items():
            click.echo(f"  {model}: {weight:.3f}")
    except Exception as e:
        click.echo(f"\n✗ Failed to get regime weights: {e}", err=True)
        logger.error("Failed to get regime weights", error=str(e), exc_info=True)
        raise click.Abort()


timing = timing_group
