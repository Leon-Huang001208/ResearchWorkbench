"""Desktop first-run database readiness status endpoint."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.configuration_security import require_configuration_origin_only
from core.observability import get_logger
from core.settings.config import RUNTIME_CONTEXT, settings
from services.database_readiness import (
    DatabaseReadiness,
    DatabaseReadinessCode,
    probe_postgresql,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/setup", tags=["setup"])


def _uninitialized_readiness() -> DatabaseReadiness:
    """Return a safe fallback when tests or an interrupted startup lack state."""
    return DatabaseReadiness(
        ready=False,
        code=DatabaseReadinessCode.UNEXPECTED_ERROR,
        message="数据库状态尚未完成初始化。",
        remediation=("请重启应用后重试。",),
    )


def _startup_readiness(request: Request) -> DatabaseReadiness:
    """Read only the readiness captured during startup, never an engine/session."""
    readiness = getattr(request.app.state, "database_readiness", None)
    return readiness if isinstance(readiness, DatabaseReadiness) else _uninitialized_readiness()


def _current_readiness() -> DatabaseReadiness:
    """Re-probe the configured URL without altering the process-wide SQLAlchemy engine."""
    try:
        return probe_postgresql(settings.DATABASE_URL)
    except Exception as exc:  # pragma: no cover - probe normally converts all failures.
        logger.warning(
            "Setup readiness probe failed unexpectedly",
            extra={"error_type": type(exc).__name__},
        )
        return _uninitialized_readiness()


@router.get("/readiness", dependencies=[Depends(require_configuration_origin_only)])
def get_setup_readiness(request: Request) -> dict[str, Any]:
    """Expose the desktop-only, safe readiness state needed by first-run configuration."""
    if RUNTIME_CONTEXT.mode != "desktop":
        raise HTTPException(status_code=404, detail="Not Found")

    startup_readiness = _startup_readiness(request)
    current_readiness = _current_readiness()
    runtime_status = "ready" if startup_readiness.ready else "setup_required"
    return {
        "runtime_status": runtime_status,
        "database": {
            "ready": current_readiness.ready,
            "code": current_readiness.code.value,
            "message": current_readiness.message,
            "remediation": list(current_readiness.remediation),
        },
        "restart_required": runtime_status == "setup_required",
    }
