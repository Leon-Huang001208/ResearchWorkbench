"""Delete old FinGPT chat data during the explicitly authorized stopped cutover.

Call only after the account Host and DSH have stopped. No backup is created.
DataHub datasets and files actually referenced by other business records stay
in their original directories; a data-only context keeps their handles valid.
"""

import json
from pathlib import Path
from uuid import UUID

from core.observability import get_logger

from .dossiers.storage import DossierStore
from .store import StoreError

log = get_logger(__name__)


def retire_fingpt_history(store):
    targets = {
        sid: row
        for sid, row in store.data["sessions"].items()
        if row.get("mode") == "fingpt"
        and not row.get("mcp_data_grant_id")
        and not row.get("data_only")
    }
    # Shared references are read before any index/file removal. This includes
    # formal reports, Claw materials and DataHub query records, not chat receipts.
    shared = json.dumps(
        {
            k: (
                {sid: row for sid, row in v.items() if sid not in targets} if k == "sessions" else v
            )
            for k, v in store.data.items()
            if k not in {"receipts", "operation_audit"}
        },
        ensure_ascii=False,
    )
    result = {"deleted_chats": 0, "retained_data_contexts": 0}
    for sid, row in targets.items():
        if str(UUID(sid)) != sid:
            raise StoreError("旧会话标识无效", "fingpt_retirement_invalid", 409)
        root = store.directory(sid)
        datasets = root / "inputs" / "datasets"
        has_data = datasets.is_dir() and any(datasets.iterdir())
        referenced = sid in shared or bool(DossierStore(store.root).retained_by(sid))
        keep = {}
        for fid, item in row.get("files", {}).items():
            path = item.get("path", "")
            if fid in shared or (path and f"sessions/{sid}/{path}" in shared):
                keep[fid] = item
        # Session-level references can resolve a file through its original id.
        # Preserve the referenced material set; remove its chat ledger regardless.
        if referenced:
            keep = dict(row.get("files", {}))
        retained = {Path(item["path"]) for item in keep.values()}
        if has_data:
            retained.add(Path("inputs/datasets"))
        # Remove only exclusive chat files. Shared material remains in place.
        if root.exists():
            for child in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
                relative = child.relative_to(root)
                if any(relative == p or p in relative.parents for p in retained):
                    continue
                if child.is_dir() and not child.is_symlink():
                    if not any(child.iterdir()):
                        child.rmdir()
                else:
                    child.unlink()
            if not any(root.iterdir()):
                root.rmdir()
        # Native DSH generations for this exact former chat workspace.
        native = store.root / "runtime/home/sessions"
        if native.is_dir():
            for project in native.iterdir():
                if project.is_dir() and not project.is_symlink():
                    own = project / sid
                    if own.exists():
                        store._remove_owned_tree(own)
                        if not any(project.iterdir()):
                            project.rmdir()
        for folder in ("calls", "snapshots", "source-captures"):
            if folder in {"snapshots", "source-captures"} and (has_data or referenced):
                continue
            store._remove_owned_tree(store.root / ".control" / folder / sid)
        store.data["receipts"] = {
            key: value
            for key, value in store.data["receipts"].items()
            if not key.startswith(sid + ":")
        }
        store.data["operation_audit"] = [
            event for event in store.data["operation_audit"] if event.get("session_id") != sid
        ]
        if has_data or keep or referenced:
            store.data["sessions"][sid] = {
                "id": sid,
                "mode": "fingpt",
                "title": "保留的数据资料",
                "data_only": True,
                "status": "idle",
                "created": False,
                "files": keep,
                "workspace_id": row.get("workspace_id", "research"),
                "updated_at": row.get("updated_at", 0),
            }
            result["retained_data_contexts"] += 1
        else:
            store.data["sessions"].pop(sid)
        result["deleted_chats"] += 1
    store.save()
    log.info("fingpt_history_retired", **result)
    return result
