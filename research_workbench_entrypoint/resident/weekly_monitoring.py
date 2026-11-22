"""Read-only legacy monitoring preview; mutation awaits the reviewed operator.

No resident service, Native client or upgrade operations are initialized here.
An apply flag is parsed solely to reject premature use explicitly.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from app.research_web.report_workflows.catalog import ReportWorkflowService
from app.research_web.report_workflows.legacy_monitoring import PROFILE, LegacyMonitoringExpectation
from app.research_web.report_workflows.models import WorkflowError
from app.research_web.report_workflows.owner import resolve_primary_owner
from core.observability import get_logger

log = get_logger(__name__)


def preview(data_root, expected, *, operation_id, owner_check):
    """No idle assertion: complete three-lock resident admission remains required."""
    catalog = ReportWorkflowService.open_for_maintenance(data_root)
    result = catalog.end_legacy_monitoring(
        expected,
        operation_id=operation_id,
        owner_check=owner_check,
    )
    return {
        "profile": PROFILE,
        "status": "dry_run",
        "domain_preview": result,
        "apply_available": False,
        "resident_admission": "NOT_RUN",
        "native_idle": "NOT_RUN",
        "host_refresh": "NOT_RUN",
        "operations_idle": "NOT_RUN",
        "upgrade": "NOT_RUN",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--reviewed-profile", choices=[PROFILE], required=True)
    parser.add_argument("--operation-id", required=True)
    parser.add_argument("--apply", action="store_true")
    for name in LegacyMonitoringExpectation.__dataclass_fields__:
        parser.add_argument(
            "--expected-" + name.replace("_", "-"),
            required=True,
            type=int if name == "version" else str,
        )
    args = parser.parse_args(argv)
    if args.apply:
        log.warning("weekly_monitoring_apply_unavailable")
        print(json.dumps({"status": "blocked", "code": "weekly_monitoring_operator_required"}))
        return 2
    expected = LegacyMonitoringExpectation(
        **{
            name: getattr(args, "expected_" + name)
            for name in LegacyMonitoringExpectation.__dataclass_fields__
        }
    )
    owner_service = SimpleNamespace(store=SimpleNamespace(root=args.data_root))
    try:
        result = preview(
            args.data_root,
            expected,
            operation_id=args.operation_id,
            owner_check=lambda owner_id: resolve_primary_owner(owner_service, owner_id),
        )
    except (WorkflowError, OSError, ValueError, TypeError) as exc:
        log.warning("weekly_monitoring_preview_failed", error_type=type(exc).__name__)
        print(
            json.dumps(
                {"status": "blocked", "code": getattr(exc, "code", "weekly_monitoring_unavailable")}
            )
        )
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
