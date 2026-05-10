"""
审核 CLI 命令
"""

import click

from core.observability import get_logger
from core.services.review_service import ReviewService

logger = get_logger(__name__)


@click.group(name="review")
def review_group():
    """审核队列管理"""
    pass


@review_group.command(name="list")
@click.option("--limit", "-n", default=20, help="显示数量")
def review_list(limit: int):
    """列出待审核的项目"""
    click.echo("Pending review items:")
    click.echo("-" * 60)

    try:
        service = ReviewService()
        assertions = service.list_pending_assertions(limit=limit)

        if not assertions:
            click.echo("No pending assertions.")
            return

        for i, assertion in enumerate(assertions, 1):
            click.echo(f"\n[{i}] ID: {assertion.assertion_id}")
            click.echo(f"    Subject: {assertion.subject_entity_id or 'N/A'}")
            click.echo(f"    Predicate: {assertion.predicate}")
            click.echo(
                f"    Object: {assertion.object_entity_id or assertion.object_value or 'N/A'}"
            )
            click.echo(f"    Confidence: {assertion.confidence:.2f}")
            click.echo(f"    Source: {assertion.source_doc_id}")

    except Exception as e:
        click.echo(f"\n✗ Failed to list pending items: {e}", err=True)
        logger.error("Failed to list pending review items", error=str(e))
        raise click.Abort()


@review_group.command(name="approve")
@click.argument("assertion_id")
@click.option("--reviewer", "-r", default="cli", help="审核人")
def review_approve(assertion_id: str, reviewer: str):
    """批准断言"""
    click.echo(f"Approving assertion: {assertion_id}")

    try:
        service = ReviewService()
        success = service.approve_assertion(assertion_id, reviewer=reviewer)

        if success:
            click.echo(f"\n✓ Assertion approved: {assertion_id}")
        else:
            click.echo(f"\n✗ Failed to approve assertion: {assertion_id}", err=True)

    except Exception as e:
        click.echo(f"\n✗ Failed to approve: {e}", err=True)
        logger.error("Failed to approve assertion", error=str(e), assertion_id=assertion_id)
        raise click.Abort()


@review_group.command(name="reject")
@click.argument("assertion_id")
@click.option("--reviewer", "-r", default="cli", help="审核人")
def review_reject(assertion_id: str, reviewer: str):
    """拒绝断言"""
    click.echo(f"Rejecting assertion: {assertion_id}")

    try:
        service = ReviewService()
        success = service.reject_assertion(assertion_id, reviewer=reviewer)

        if success:
            click.echo(f"\n✓ Assertion rejected: {assertion_id}")
        else:
            click.echo(f"\n✗ Failed to reject assertion: {assertion_id}", err=True)

    except Exception as e:
        click.echo(f"\n✗ Failed to reject: {e}", err=True)
        logger.error("Failed to reject assertion", error=str(e), assertion_id=assertion_id)
        raise click.Abort()


@review_group.command(name="stats")
def review_stats():
    """显示审核统计"""
    try:
        service = ReviewService()
        stats = service.get_statistics()

        click.echo("Review statistics:")
        click.echo("-" * 60)
        click.echo(f"Pending assertions: {stats['pending_assertions']}")
        click.echo(f"Approved assertions: {stats['approved_assertions']}")
        click.echo(f"Rejected assertions: {stats['rejected_assertions']}")

    except Exception as e:
        click.echo(f"\n✗ Failed to get stats: {e}", err=True)
        logger.error("Failed to get review statistics", error=str(e))
        raise click.Abort()


review = review_group
