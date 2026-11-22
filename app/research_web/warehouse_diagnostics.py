"""Read-only, credential-free optional warehouse installation diagnostics."""

import importlib.util
import json
import re
from pathlib import Path

from core.observability import get_logger
from research_workbench_entrypoint.web_contract import read_private_json

from .datahub.security import directory, read_file
from .store import StoreError

log = get_logger(__name__)
PROFILE_LIMIT = 16384


def warehouse_diagnostic(data_root: Path) -> dict:
    """Inspect only this instance's profile; never instantiate backend/keyring."""
    try:
        dependency = "installed" if importlib.util.find_spec("psycopg") else "missing"
    except (ImportError, OSError, ValueError, AttributeError):
        dependency = "unknown"
        log.warning("warehouse_doctor_dependency_unknown")
    report = {
        "optional": True,
        "state": "unconfigured",
        "enabled": False,
        "driver": dependency,
        "connectivity": "unknown",
        "readiness": "not_verified",
        "code": "warehouse_unconfigured",
    }
    root = Path(data_root)
    fact = read_private_json(
        root / "warehouse.json", trusted_root=root.parent, max_bytes=PROFILE_LIMIT
    )
    if fact.state == "missing":
        return report
    try:
        if fact.state != "valid":
            raise ValueError("unsafe_profile")
        # The shared reader rejects alias/size/type changes. The DataHub reader
        # additionally enforces owner and private directory/file permission bits.
        with directory(root.parent, (root.name,), private=True) as descriptor:
            value = json.loads(
                read_file(descriptor, "warehouse.json", private=True, limit=PROFILE_LIMIT)
            )
        if (
            not isinstance(value, dict)
            or set(value) != {"id", "owner", "enabled", "configuration"}
            or not isinstance(value["id"], str)
            or re.fullmatch(r"[0-9a-f]{32}", value["id"]) is None
            or not isinstance(value["owner"], str)
            or re.fullmatch(r"warehouse-[0-9a-f]{32}", value["owner"]) is None
            or type(value["enabled"]) is not bool
            or not isinstance(value["configuration"], dict)
            or set(value["configuration"]) - {"host", "port", "database", "username", "sslmode"}
        ):
            raise ValueError("invalid_profile")
        # Reuse the current profile contract, without constructing a warehouse,
        # loading psycopg, looking up credentials or calling a database factory.
        from .datahub.research_warehouse import WarehouseConfiguration

        WarehouseConfiguration.model_validate(value["configuration"])
    except (StoreError, OSError, ValueError, TypeError, KeyError, RecursionError):
        log.warning("warehouse_doctor_profile_invalid")
        return {**report, "state": "invalid", "enabled": None, "code": "warehouse_profile_invalid"}
    log.info("warehouse_doctor_profile_checked", enabled=value["enabled"])
    return {
        **report,
        "state": "configured",
        "enabled": value["enabled"],
        "code": "warehouse_explicit_validation_required",
    }
