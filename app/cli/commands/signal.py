"""
信号 CLI 命令
"""

from typing import Optional

import click

from core.observability import get_logger
from services.signal_service import SignalService

logger = get_logger(__name__)


@click.group(name="signal")
def signal_group():
    """
    信号管理命令

    示例:
        rwb signal create --subject 600519.SH --thesis "看好白酒股"
        rwb signal list
        rwb signal validate --id <signal_id>
        rwb signal promote --id <signal_id> --status candidate
    """
    pass


@signal_group.command(name="create")
@click.option("--subject", "-s", required=True, help="主体ID")
@click.option("--thesis", "-t", required=True, help="研究论点")
@click.option("--horizon", "-h", default="20d", help="预测期 (1d/5d/20d/60d)")
@click.option("--score", default=0.5, type=float, help="信号分数 (0-1)")
@click.option("--confidence", default=0.5, type=float, help="置信度 (0-1)")
@click.option("--scenario", multiple=True, help="情景引用（可多次指定）")
@click.option("--evidence", multiple=True, help="证据引用（可多次指定）")
@click.option("--status", default="research_only", help="状态")
def create_signal(
    subject: str,
    thesis: str,
    horizon: str,
    score: float,
    confidence: float,
    scenario: tuple,
    evidence: tuple,
    status: str,
):
    """创建信号"""
    click.echo(f"Creating signal for: {subject}")

    try:
        service = SignalService()

        signal = service.create_signal(
            subject_id=subject,
            thesis=thesis,
            horizon=horizon,
            score=score,
            confidence=confidence,
            scenario_refs=list(scenario),
            evidence_refs=list(evidence),
            status=status,
        )

        click.echo(f"\n✓ Signal created: {signal.signal_id}")
        click.echo(f"  Subject: {signal.subject_id}")
        click.echo(f"  Thesis: {signal.thesis}")
        click.echo(f"  Horizon: {signal.horizon}")
        click.echo(f"  Score: {signal.score:.2f}")
        click.echo(f"  Confidence: {signal.confidence:.2f}")
        click.echo(f"  Status: {signal.status}")

    except Exception as e:
        click.echo(f"\n✗ Failed to create signal: {e}", err=True)
        logger.error("Failed to create signal", error=str(e), exc_info=True)
        raise click.Abort()


@signal_group.command(name="list")
@click.option("--status", help="状态过滤")
@click.option("--subject", "-s", help="主体过滤")
@click.option("--limit", "-l", default=20, type=int, help="返回数量限制")
def list_signals(status: Optional[str], subject: Optional[str], limit: int):
    """列出信号"""
    try:
        service = SignalService()
        signals = service.list_signals(status=status, subject_id=subject, limit=limit)

        if not signals:
            click.echo("No signals found")
            return

        click.echo(f"\nFound {len(signals)} signal(s):")
        click.echo("-" * 80)

        for i, signal in enumerate(signals, 1):
            click.echo(f"{i}. [{signal.status}] {signal.signal_id} - {signal.subject_id}")
            click.echo(f"   Thesis: {signal.thesis}")
            click.echo(f"   Score: {signal.score:.2f}, Confidence: {signal.confidence:.2f}")
            if signal.scenario_refs:
                click.echo(f"   Scenarios: {', '.join(signal.scenario_refs)}")
            if signal.evidence_refs:
                click.echo(f"   Evidences: {len(signal.evidence_refs)}")
            click.echo()

    except Exception as e:
        click.echo(f"\n✗ Failed to list signals: {e}", err=True)
        logger.error("Failed to list signals", error=str(e), exc_info=True)
        raise click.Abort()


@signal_group.command(name="validate")
@click.option("--id", "signal_id", required=True, help="信号ID")
def validate_signal(signal_id: str):
    """验证信号"""
    click.echo(f"Validating signal: {signal_id}")

    try:
        service = SignalService()
        signal = service.get_signal(signal_id)

        if not signal:
            click.echo(f"\n✗ Signal not found: {signal_id}", err=True)
            raise click.Abort()

        result = service.validate_signal(signal)

        click.echo("\n✓ Validation results:")
        click.echo(f"  Composite Score: {result['composite_score']:.3f}")

        if result["features"]:
            click.echo(f"  Features: {len(result['features'])}")

        click.echo(f"  Validated at: {result['validated_at']}")

    except Exception as e:
        click.echo(f"\n✗ Failed to validate signal: {e}", err=True)
        logger.error("Failed to validate signal", error=str(e), exc_info=True)
        raise click.Abort()


@signal_group.command(name="promote")
@click.option("--id", "signal_id", required=True, help="信号ID")
@click.option("--status", required=True, help="新状态 (research_only/candidate/paper_trade)")
def promote_signal(signal_id: str, status: str):
    """升级信号状态"""
    click.echo(f"Promoting signal: {signal_id} to {status}")

    try:
        service = SignalService()
        updated = service.promote_signal(signal_id, status)

        if not updated:
            click.echo("\n✗ Failed to promote signal", err=True)
            raise click.Abort()

        click.echo("\n✓ Signal promoted successfully!")
        click.echo(f"  New status: {updated.status}")

    except Exception as e:
        click.echo(f"\n✗ Failed to promote signal: {e}", err=True)
        logger.error("Failed to promote signal", error=str(e), exc_info=True)
        raise click.Abort()


@signal_group.command(name="candidate")
@click.option("--id", "signal_id", required=True, help="信号ID")
def generate_candidate(signal_id: str):
    """生成交易候选"""
    click.echo(f"Generating trade candidate for: {signal_id}")

    try:
        service = SignalService()
        signal = service.get_signal(signal_id)

        if not signal:
            click.echo(f"\n✗ Signal not found: {signal_id}", err=True)
            raise click.Abort()

        candidate = service.generate_trade_candidate(signal)

        click.echo(f"\n✓ Trade candidate generated: {candidate.candidate_id}")
        click.echo(f"  Action: {candidate.action}")
        click.echo(f"  Sizing: {candidate.sizing_hint:.2%}")
        if candidate.risk_notes:
            click.echo(f"  Risk notes: {', '.join(candidate.risk_notes)}")

    except Exception as e:
        click.echo(f"\n✗ Failed to generate candidate: {e}", err=True)
        logger.error("Failed to generate candidate", error=str(e), exc_info=True)
        raise click.Abort()


signal = signal_group
