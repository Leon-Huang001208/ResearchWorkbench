"""Read-only public projection of privately bound pack execution receipts."""

import hashlib
import json

from core.observability import get_logger

from .store import StoreError

log = get_logger(__name__)


def project(service, sid, receipt, context, files):
    """Called only after detail's current-owner and ancestor authority checks.

    Never trust filenames, stdout or declared runtime flags. Saved executions are
    reopened with the same full schema/hash/input checks as the quality boundary.
    Public references must already be in the ordinary authenticated file index.
    """
    if not context or not context.get("pack_seal"):
        return None
    from .capabilities.pack_native import read_regular
    from .scenario_handoffs import fingerprint
    from .scenario_pack_execution import read_artifacts

    task_id = receipt.get("research_contract", {}).get("task_id")
    result = {
        "schema": "research_pack_ui_v1",
        "pack_id": context["scenario"]["contract"]["pack_id"],
        "qualification_status": context["pack_qualification"]["status"],
        "executions": [],
    }
    for execution in receipt.get("pack_executions", []):
        binding = execution.get("binding", {})
        if (
            binding.get("task_id") != task_id
            or binding.get("context_sha256") != fingerprint(context)
            or binding.get("call_id") != execution.get("call_id")
            or binding.get("pack_id") != result["pack_id"]
            or binding.get("input_sha256") != context["pack_seal"]["input_sha256"]
        ):
            log.warning("research_pack_ui_binding_unavailable")
            result["executions"].append({"state": "unavailable", "files": []})
            continue
        view = {"state": "unknown", "files": []}
        if execution.get("state") != "saved":
            view["state"] = "cancelled" if execution.get("state") == "cancelled" else "unknown"
            result["executions"].append(view)
            continue
        try:
            observed = read_artifacts(service.store.root / "sessions" / sid, execution)
            if observed != {key: execution.get(key) for key in observed}:
                raise StoreError("组合包产物变化", "pack_output_changed", 409)
            receipt_file = observed["artifacts"]["receipt"]
            raw = read_regular(service.store.root / "sessions" / sid / receipt_file["path"], 65536)
            if hashlib.sha256(raw).hexdigest() != receipt_file["sha256"]:
                raise StoreError("组合包产物变化", "pack_output_changed", 409)
            checked_receipt = json.loads(raw)
            public = []
            registered = service.store.session(sid)["files"]
            for name, artifact in observed["artifacts"].items():
                matches = [file for file in files if registered.get(file["id"]) == artifact["path"]]
                if len(matches) != 1:
                    raise StoreError("组合包产物索引不可核验", "pack_output_unindexed", 409)
                file = matches[0]
                public.append(
                    {
                        "name": name + ".json",
                        "id": file["id"],
                        "url": file["url"],
                        "preview_url": file["preview_url"],
                        "sha256": artifact["sha256"],
                        "bytes": artifact["bytes"],
                    }
                )
            view.update(
                state="saved",
                computation_status=observed["computation_status"],
                counts=observed["counts"],
                row_delivery={
                    "root": checked_receipt["row_delivery"],
                    "components": {
                        item["method"]: item["result"]["row_delivery"]
                        for item in checked_receipt["rows"]
                    },
                },
                missing=[{"code": gap["code"]} for gap in observed["missing"]],
                files=public,
            )
        except (StoreError, OSError, ValueError, KeyError, TypeError):
            log.warning("research_pack_ui_artifacts_unavailable")
            view.update(state="invalid", files=[])
        result["executions"].append(view)
    return result
