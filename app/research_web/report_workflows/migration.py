"""Idempotent import of legacy report assets into versioned Workflow packages."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import tempfile
import time
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

import yaml

from core.observability import get_logger

from .models import WorkflowError
from .workbook import read_cached_workbook, scan_workbook_formulas

log = get_logger(__name__)
SOURCE_REF = "legacy-report-projects"
KNOWN = {
    "华安ETF周报": ("huaan-etf-weekly", ["docx", "html", "xlsx"]),
    "创业板50周报": ("chinext-50-weekly", ["docx", "html", "xlsx"]),
    "华安ETF投资风向标": ("huaan-etf-compass", ["pptx"]),
    "AI周报": ("ai-weekly", ["docx", "html", "xlsx"]),
}
ALLOWED = {
    ".docx",
    ".xlsx",
    ".pptx",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".md",
    ".txt",
    ".csv",
    ".json",
    ".yaml",
    ".yml",
    ".html",
}
HISTORY_PARTS = {"generated", "runs", "jobs", "outputs"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _items_sha256(items: list[dict], path_key: str) -> str:
    payload = sorted((item[path_key], item["sha256"]) for item in items)
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def _set_project_identity(project: dict) -> None:
    project["resource_sha256"] = _items_sha256(project["resources"], "logical_path")
    project["history_sha256"] = _items_sha256(project["history"], "path")
    project["source_sha256"] = hashlib.sha256(
        json.dumps(
            {
                "resources": project["resource_sha256"],
                "history": project["history_sha256"],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


class ReportWorkflowMigration:
    def __init__(self, catalog) -> None:
        self.catalog = catalog

    @staticmethod
    def _logical_path(relative: Path) -> str:
        if relative.suffix.lower() == ".xlsx":
            return (Path("workbooks") / relative.name).as_posix()
        if relative.suffix.lower() in {".docx", ".pptx"}:
            return (Path("templates") / relative.name).as_posix()
        return (Path("assets") / relative).as_posix()

    def _scan(self, folder: Path, workflow_id: str, formats: list[str]) -> dict:
        root = folder.resolve(strict=True)
        config = {}
        for filename in ("project.yaml", "report_config.yaml"):
            candidate = folder / filename
            if candidate.is_file() and not candidate.is_symlink():
                try:
                    loaded = yaml.safe_load(candidate.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        config.update(loaded)
                except (OSError, yaml.YAMLError):
                    pass
        report_config = {}
        configured_report = str(
            config.get("report_config") or "config/report_config.yaml"
        )
        configured_path = Path(configured_report)
        if not configured_path.is_absolute() and ".." not in configured_path.parts:
            candidate = folder / configured_path
            if (
                candidate.is_file()
                and not candidate.is_symlink()
                and candidate.resolve().is_relative_to(root)
            ):
                try:
                    loaded = yaml.safe_load(candidate.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        report_config = loaded
                except (OSError, yaml.YAMLError):
                    pass
        resources = []
        history = []
        scan_issues = []
        for path in sorted(folder.rglob("*")):
            if path.is_symlink():
                scan_issues.append(
                    {
                        "path": path.relative_to(folder).as_posix(),
                        "reason": "unsafe_symlink",
                    }
                )
                continue
            try:
                resolved = path.resolve(strict=True)
            except OSError:
                scan_issues.append(
                    {
                        "path": path.relative_to(folder).as_posix(),
                        "reason": "source_unreadable",
                    }
                )
                continue
            if not resolved.is_relative_to(root):
                scan_issues.append(
                    {
                        "path": path.relative_to(folder).as_posix(),
                        "reason": "source_outside_project",
                    }
                )
                continue
            if not resolved.is_file() or path.name == ".DS_Store":
                continue
            relative = path.relative_to(folder)
            if ".preview-cache" in relative.parts:
                continue
            item = {
                "path": relative.as_posix(),
                "logical_path": self._logical_path(relative),
                "sha256": _sha256(resolved),
                "size": resolved.stat().st_size,
                "source_path": str(resolved),
                "source_root": str(root),
            }
            if any(part in HISTORY_PARTS for part in relative.parts):
                history.append(item)
            elif path.suffix.lower() in ALLOWED:
                resources.append(item)
        complete = bool(config) and any(
            item["logical_path"].startswith("templates/") for item in resources
        )
        if workflow_id == "ai-weekly":
            complete = False
        return {
            "id": workflow_id,
            "name": str(config.get("name") or folder.name),
            "status": "enabled" if complete else "needs_attention",
            "formats": formats,
            "source_ref": f"{SOURCE_REF}/{folder.name}",
            "resources": resources,
            "history": history,
            "config": config,
            "report_config": report_config,
            "scan_issues": scan_issues,
        }

    @staticmethod
    def _blocks(project: dict) -> tuple[list[dict], list[dict]]:
        blocks: list[dict] = []
        steps: list[dict] = []
        report_config = project.get("report_config") or {}
        groups = (
            ("placeholders", None),
            ("charts", "chart"),
            ("tables", "table"),
        )
        for group, fixed_kind in groups:
            values = report_config.get(group) or {}
            if not isinstance(values, dict):
                project["status"] = "needs_attention"
                continue
            for key, value in values.items():
                if len(blocks) >= 128:
                    project["status"] = "needs_attention"
                    break
                item = value if isinstance(value, dict) else {}
                source_type = str(item.get("type") or "").casefold()
                kind = fixed_kind or {
                    "chart": "chart",
                    "table": "table",
                    "workbook": "workbook",
                    "appendix": "appendix",
                }.get(source_type, "narrative")
                block_id = f"block_{len(blocks) + 1:03d}"
                block = {
                    "id": block_id,
                    "title": str(item.get("title") or key)[:160],
                    "kind": kind,
                    "required": bool(item.get("required", True)),
                    "source_refs": ["assets/config/report_config.yaml"],
                }
                blocks.append(block)
                steps.append(
                    {
                        "id": f"compose_{block_id}",
                        "type": kind,
                        "block_id": block_id,
                        "source_refs": block["source_refs"],
                    }
                )
        return blocks, steps

    def migrate(self, source: Path, *, dry_run: bool = True) -> dict:
        source = Path(source)
        if source.is_symlink():
            raise WorkflowError("迁移源目录不可读取", "migration_source_invalid", 422)
        try:
            root = source.resolve(strict=True)
        except OSError as exc:
            raise WorkflowError(
                "迁移源目录不可读取", "migration_source_invalid", 422
            ) from exc
        if root.is_symlink() or not root.is_dir():
            raise WorkflowError("迁移源目录不可读取", "migration_source_invalid", 422)
        projects: list[dict] = []
        rejected: list[dict] = []
        quarantined: list[dict] = []
        for folder in sorted(root.iterdir()):
            if folder.name == "华安ETF周报 2":
                continue
            spec = KNOWN.get(folder.name)
            if folder.is_symlink():
                if spec:
                    rejected.append(
                        {"path": folder.name, "reason": "unsafe_project_directory"}
                    )
                continue
            try:
                resolved = folder.resolve(strict=True)
            except OSError:
                if spec:
                    rejected.append(
                        {"path": folder.name, "reason": "source_unreadable"}
                    )
                continue
            if not resolved.is_dir() or not resolved.is_relative_to(root):
                if spec:
                    rejected.append(
                        {"path": folder.name, "reason": "unsafe_project_directory"}
                    )
                continue
            if not spec:
                rejected.append({"path": folder.name, "reason": "unknown_project"})
                continue
            project = self._scan(resolved, *spec)
            projects.append(project)
            quarantined.extend(
                {**issue, "workflow_id": project["id"]}
                for issue in project.get("scan_issues", [])
            )
        duplicate = root / "华安ETF周报 2"
        primary = next(
            (item for item in projects if item["id"] == "huaan-etf-weekly"), None
        )
        duplicate_root = None
        if duplicate.is_symlink():
            quarantined.append(
                {"path": duplicate.name, "reason": "unsafe_duplicate_directory"}
            )
        elif duplicate.exists():
            try:
                resolved = duplicate.resolve(strict=True)
                if resolved.is_dir() and resolved.is_relative_to(root):
                    duplicate_root = resolved
                else:
                    quarantined.append(
                        {"path": duplicate.name, "reason": "unsafe_duplicate_directory"}
                    )
            except OSError:
                quarantined.append(
                    {"path": duplicate.name, "reason": "unsafe_duplicate_directory"}
                )
        if duplicate_root is not None and primary:
            resource_paths = {
                item["logical_path"]: item["sha256"] for item in primary["resources"]
            }
            history_paths = {
                item["path"]: item["sha256"] for item in primary["history"]
            }
            hashes = {
                item["sha256"] for item in [*primary["resources"], *primary["history"]]
            }
            for path in sorted(duplicate_root.rglob("*")):
                if path.is_symlink():
                    quarantined.append(
                        {
                            "path": path.relative_to(duplicate_root).as_posix(),
                            "reason": "unsafe_symlink",
                        }
                    )
                    continue
                try:
                    resolved = path.resolve(strict=True)
                except OSError:
                    quarantined.append(
                        {
                            "path": path.relative_to(duplicate_root).as_posix(),
                            "reason": "source_unreadable",
                        }
                    )
                    continue
                if not resolved.is_relative_to(duplicate_root):
                    quarantined.append(
                        {
                            "path": path.relative_to(duplicate_root).as_posix(),
                            "reason": "source_outside_project",
                        }
                    )
                    continue
                if not resolved.is_file():
                    continue
                relative = resolved.relative_to(duplicate_root)
                if ".preview-cache" in relative.parts:
                    continue
                historical = any(part in HISTORY_PARTS for part in relative.parts)
                if not historical and resolved.suffix.lower() not in ALLOWED:
                    continue
                digest = _sha256(resolved)
                if digest in hashes:
                    continue
                item: dict = {
                    "path": relative.as_posix(),
                    "logical_path": self._logical_path(relative),
                    "sha256": digest,
                    "size": resolved.stat().st_size,
                    "source_path": str(resolved),
                    "source_root": str(duplicate_root),
                }
                if historical:
                    if item["path"] in history_paths:
                        quarantined.append(
                            {
                                "path": item["path"],
                                "sha256": digest,
                                "reason": "historical_path_content_conflict",
                            }
                        )
                        continue
                    primary["history"].append(item)
                    history_paths[item["path"]] = digest
                    hashes.add(digest)
                    continue
                logical = item["logical_path"]
                if logical in resource_paths:
                    quarantined.append(
                        {
                            "path": logical,
                            "sha256": digest,
                            "reason": "path_content_conflict",
                        }
                    )
                    continue
                primary["resources"].append(item)
                resource_paths[logical] = digest
                hashes.add(digest)
        for project in projects:
            _set_project_identity(project)

        outcomes: dict[str, str] = {}
        for project in projects:
            outcome = self._classify(project) if dry_run else self._apply(project)
            outcomes[project["id"]] = outcome
            if outcome == "conflict":
                project["status"] = "needs_attention"
                quarantined.append(
                    {
                        "workflow_id": project["id"],
                        "reason": "source_hash_conflict",
                        "incoming_source_sha256": project["source_sha256"],
                    }
                )
        accepted = [
            {
                **{
                    key: value
                    for key, value in resource.items()
                    if key not in {"source_path", "source_root"}
                },
                "workflow_id": project["id"],
                "migration_status": outcomes[project["id"]],
            }
            for project in projects
            if outcomes[project["id"]] != "conflict"
            for resource in project["resources"]
        ]
        report = {
            "id": uuid4().hex,
            "dry_run": dry_run,
            "source": SOURCE_REF,
            "source_sha256": hashlib.sha256(
                json.dumps(
                    sorted(
                        (project["id"], kind, item[path_key], item["sha256"])
                        for project in projects
                        for kind, values, path_key in (
                            ("resource", project["resources"], "logical_path"),
                            ("history", project["history"], "path"),
                        )
                        for item in values
                    ),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest(),
            "project_count": len(projects),
            "resource_count": sum(len(item["resources"]) for item in projects),
            "resource_bytes": sum(
                resource["size"] for item in projects for resource in item["resources"]
            ),
            "history_count": sum(len(item["history"]) for item in projects),
            "history_bytes": sum(
                artifact["size"] for item in projects for artifact in item["history"]
            ),
            "accepted_count": len(accepted),
            "accepted_bytes": sum(item["size"] for item in accepted),
            "projects": [
                {
                    "id": item["id"],
                    "name": item["name"],
                    "status": item["status"],
                    "source_sha256": item["source_sha256"],
                    "resource_sha256": item["resource_sha256"],
                    "history_sha256": item["history_sha256"],
                    "migration_status": outcomes[item["id"]],
                    "resource_count": len(item["resources"]),
                    "resource_bytes": sum(
                        resource["size"] for resource in item["resources"]
                    ),
                    "history_count": len(item["history"]),
                    "history_bytes": sum(
                        artifact["size"] for artifact in item["history"]
                    ),
                }
                for item in projects
            ],
            "accepted": accepted,
            "quarantined": quarantined,
            "rejected": rejected,
        }
        log.info(
            "report_workflow_migration_checked",
            dry_run=dry_run,
            project_count=len(projects),
        )
        return report

    def _classify(self, project: dict) -> str:
        with self.catalog._exclusive():
            row = self.catalog.data["workflows"].get(project["id"])
            if row is None:
                return "pending"
            return self._migration_state(row, project)

    @staticmethod
    def _migration_state(row: dict, project: dict) -> str:
        migration = row.get("migration") or {}
        # Before split identities were introduced, source_sha256 represented only
        # the immutable resource package. Preserve idempotency for those records.
        existing_resources = migration.get("resource_sha256") or migration.get(
            "source_sha256"
        )
        if existing_resources != project["resource_sha256"]:
            return "conflict"
        if migration.get("history_sha256") == project["history_sha256"]:
            return "already_present"
        return "history_updated"

    @staticmethod
    def _verified_bytes(item: dict) -> bytes:
        try:
            source = Path(item["source_path"])
            root = Path(item["source_root"]).resolve(strict=True)
            if source.is_symlink():
                raise OSError("symlink")
            resolved = source.resolve(strict=True)
            if not resolved.is_file() or not resolved.is_relative_to(root):
                raise OSError("outside source root")
            raw = resolved.read_bytes()
        except (KeyError, OSError) as exc:
            raise WorkflowError(
                "迁移源文件在导入前发生变化", "migration_source_changed", 409
            ) from exc
        digest = hashlib.sha256(raw).hexdigest()
        if digest != item["sha256"] or len(raw) != item["size"]:
            raise WorkflowError(
                "迁移源文件在导入前发生变化", "migration_source_changed", 409
            )
        return raw

    def _verify_project(self, project: dict) -> dict[str, bytes]:
        return {
            item["source_path"]: self._verified_bytes(item)
            for item in [*project["resources"], *project["history"]]
        }

    @staticmethod
    def _atomic_history_file(target: Path, raw: bytes, expected_sha256: str) -> bool:
        if target.exists():
            if (
                target.is_symlink()
                or not target.is_file()
                or _sha256(target) != expected_sha256
            ):
                raise WorkflowError(
                    "历史产物存储冲突", "migration_history_conflict", 409
                )
            return False
        fd, temporary = tempfile.mkstemp(prefix="history-", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o400)
            os.replace(temporary, target)
            return True
        except OSError as exc:
            raise WorkflowError(
                "历史产物无法安全保存", "migration_history_unavailable", 503
            ) from exc
        finally:
            if os.path.exists(temporary):
                with suppress(OSError):
                    os.unlink(temporary)

    def _append_history_locked(
        self, row: dict, project: dict, payloads: dict[str, bytes]
    ) -> None:
        history_root = self.catalog.root / project["id"] / "history"
        history_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        existing = list(row.get("historical_artifacts", []))
        existing_hashes = {item.get("sha256") for item in existing}
        for item in project["history"]:
            if item["sha256"] in existing_hashes:
                continue
            target = history_root / f"{item['sha256'][:12]}-{Path(item['path']).name}"
            self._atomic_history_file(
                target, payloads[item["source_path"]], item["sha256"]
            )
            existing.append(
                {
                    "id": item["sha256"],
                    "path": item["path"],
                    "sha256": item["sha256"],
                    "size": item["size"],
                    "stored_ref": f"history/{target.name}",
                    "historical": True,
                }
            )
            existing_hashes.add(item["sha256"])
        row["historical_artifacts"] = existing
        migration = row.setdefault("migration", {})
        migration.update(
            source_ref=project["source_ref"],
            source_sha256=project["source_sha256"],
            resource_sha256=project["resource_sha256"],
            history_sha256=project["history_sha256"],
            applied_at=time.time(),
        )

    def _apply(self, project: dict) -> str:
        # Capture and revalidate every byte before the first catalog mutation.
        # All later writes consume this immutable snapshot, closing scan/read TOCTOU.
        payloads = self._verify_project(project)
        with self.catalog._exclusive():
            row = self.catalog.data["workflows"].get(project["id"])
            if row is not None:
                state = self._migration_state(row, project)
                if state == "already_present":
                    return "already_present"
                if state == "history_updated":
                    self._append_history_locked(row, project, payloads)
                    self.catalog._save()
                    return "history_updated"
                row["status"] = "needs_attention"
                row["migration_conflict"] = {
                    "source_ref": project["source_ref"],
                    "incoming_source_sha256": project["source_sha256"],
                    "detected_at": time.time(),
                }
                self.catalog._save()
                return "conflict"
            before = copy.deepcopy(self.catalog.data)
            try:
                self._apply_locked(project, payloads)
            except Exception:
                self.catalog.data = before
                self.catalog._save()
                target = self.catalog.root / project["id"]
                if target.is_dir() and not target.is_symlink():
                    shutil.rmtree(target, ignore_errors=True)
                raise
            return "created"

    def _apply_locked(self, project: dict, payloads: dict[str, bytes]) -> None:
        workbook_policies = []
        providers = {}
        refresh = project["config"].get("excel_refresh") or {}
        active_workbook = Path(
            str(project["config"].get("active_excel_workbook", ""))
        ).name
        for item in project["resources"]:
            if not item["logical_path"].startswith("workbooks/"):
                continue
            try:
                with tempfile.NamedTemporaryFile(suffix=".xlsx") as workbook:
                    workbook.write(payloads[item["source_path"]])
                    workbook.flush()
                    formula_provider = scan_workbook_formulas(
                        Path(workbook.name)
                    ).provider.value
            except WorkflowError:
                project["status"] = "needs_attention"
                continue
            required = (
                ["wind_excel", "ifind_excel"]
                if formula_provider == "mixed"
                else [formula_provider]
                if formula_provider in {"wind_excel", "ifind_excel"}
                else []
            )
            declared = str(refresh.get("provider", ""))
            if item["logical_path"].endswith(active_workbook) and declared in {
                "wind_excel",
                "ifind_excel",
            }:
                required = sorted({*required, declared})
            if required or item["logical_path"].endswith(active_workbook):
                requirements = [
                    {"provider": provider, "required": True} for provider in required
                ]
                for requirement in requirements:
                    providers[requirement["provider"]] = requirement
                policy = {
                    "workbook": item["logical_path"],
                    "providers": requirements,
                    "required_cells": (
                        list(refresh.get("required_cells") or [])
                        if item["logical_path"].endswith(active_workbook)
                        else []
                    ),
                    "stability_checks": int(refresh.get("stable_polls", 2)),
                    "poll_interval_seconds": float(refresh.get("poll_seconds", 0.25)),
                    "timeout_seconds": float(refresh.get("timeout_seconds", 30)),
                }
                if item["logical_path"].endswith(active_workbook) and refresh.get(
                    "date_cell"
                ):
                    policy["required_date_cell"] = refresh["date_cell"]
                    policy["max_age_days"] = 7
                workbook_policies.append(policy)
        blocks, composition_steps = self._blocks(project)
        manifest = {
            "workflow_id": project["id"],
            "name": project["name"],
            "description": "迁移的报告 Workflow；模板、Excel 底稿和品牌素材随版本锁定。",
            "version": 1,
            "providers": list(providers.values()),
            "workbook_policies": workbook_policies,
            "blocks": blocks,
            "delivery": {"formats": project["formats"], "required_artifacts": []},
        }
        refresh_steps = [
            {
                "id": f"refresh_{index:03d}",
                "type": "workbook_refresh",
                "tool": "workbook_refresh",
                "workbook": policy["workbook"],
            }
            for index, policy in enumerate(workbook_policies, start=1)
        ]
        self.catalog.create_draft(
            manifest,
            workflow={"steps": [*refresh_steps, *composition_steps]},
            validation={"workbooks": workbook_policies},
        )
        seen = {}
        for resource in project["resources"]:
            logical = resource["logical_path"]
            if logical in seen:
                logical = (
                    Path(logical).parent
                    / f"{resource['sha256'][:12]}-{Path(logical).name}"
                ).as_posix()
            seen[logical] = resource["sha256"]
            self.catalog.upload_resource(
                project["id"], logical, payloads[resource["source_path"]]
            )
        row = self.catalog._row(project["id"])
        row.update(
            status=project["status"],
            migration={
                "source_ref": project["source_ref"],
                "source_sha256": project["source_sha256"],
                "resource_sha256": project["resource_sha256"],
                "history_sha256": project["history_sha256"],
                "applied_at": time.time(),
            },
        )
        if project["status"] != "needs_attention":
            version = self.catalog.create_version(project["id"])
            self.catalog.publish_version(project["id"], version.version)
            row["status"] = "enabled"
        self._append_history_locked(row, project, payloads)
        self.catalog._save()

    @staticmethod
    def _v2_primary_workbook(workflow_id: str) -> str | None:
        if workflow_id == "chinext-50-weekly":
            return "workbooks/创业板50周报（iFind版）.xlsx"
        if workflow_id == "huaan-etf-weekly":
            return "workbooks/周报数据.xlsx"
        return None

    @staticmethod
    def _v2_validation(workflow_id: str, workbook: str) -> dict:
        if workflow_id == "chinext-50-weekly" and workbook.endswith(
            "创业板50周报（iFind版）.xlsx"
        ):
            return {
                "required_cells": [
                    "基本信息!C3",
                    "基本信息!D3",
                    "基本信息!E3",
                    "基本信息!F3",
                    "基本信息!G3",
                    "基本信息!I3",
                    "基本信息!J3",
                ],
                "required_date_cell": "基本信息!B3",
                "max_age_days": 7,
                "reject_zero_cells": [
                    "基本信息!E3",
                    "基本信息!F3",
                    "基本信息!G3",
                    "基本信息!I3",
                    "基本信息!J3",
                ],
            }
        return {}

    @staticmethod
    def _write_yaml(path: Path, value: dict) -> None:
        fd, temporary = tempfile.mkstemp(prefix="workflow-v2-", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                yaml.safe_dump(value, stream, allow_unicode=True, sort_keys=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
        except (OSError, yaml.YAMLError) as exc:
            raise WorkflowError(
                "Workflow v2 无法保存", "workflow_unavailable", 503
            ) from exc
        finally:
            if os.path.exists(temporary):
                with suppress(OSError):
                    os.unlink(temporary)

    def upgrade_all_v2(self) -> dict[str, list[str]]:
        """Upgrade only source-owned migrated packages while preserving published v1."""

        upgraded: list[str] = []
        unchanged: list[str] = []
        with self.catalog._exclusive():
            workflow_ids = sorted(self.catalog.data.get("workflows", {}))
        for workflow_id in workflow_ids:
            with self.catalog._exclusive():
                row = self.catalog._row(workflow_id)
                migration = row.get("migration")
                if not isinstance(migration, dict) or workflow_id == "ai-weekly":
                    continue
                current = row.get("current_version")
                if current is None:
                    continue
                manifest = self.catalog.manifest(workflow_id, int(current))
                needs_backup_fix = workflow_id == "huaan-etf-weekly" and any(
                    ".before_excel_update" in item.workbook
                    for item in manifest.workbook_policies
                )
                needs_timeout_fix = any(
                    item.providers and item.timeout_seconds < 180
                    for item in manifest.workbook_policies
                )
                needs_subagent_fix = manifest.minimum_subagents < 2
                migration_schema = int(migration.get("schema_version") or 1)
                if (
                    migration_schema >= 2
                    and not needs_backup_fix
                    and not needs_timeout_fix
                    and not needs_subagent_fix
                ):
                    unchanged.append(workflow_id)
                    continue
                previous = {item.workbook: item for item in manifest.workbook_policies}
                draft = self.catalog._draft(workflow_id)
                policies: list[dict] = []
                providers: dict[str, dict] = {}
                legacy_resources: list[dict] = []
                for resource in manifest.resources:
                    if resource.role.value != "workbook":
                        continue
                    workbook = resource.path
                    if (
                        workflow_id == "chinext-50-weekly"
                        and "Wind版" in Path(workbook).name
                    ) or (
                        workflow_id == "huaan-etf-weekly"
                        and ".before_excel_update" in Path(workbook).name
                    ):
                        legacy_resources.append(
                            {
                                "path": workbook,
                                "status": (
                                    "legacy_mislabeled"
                                    if workflow_id == "chinext-50-weekly"
                                    else "static_backup"
                                ),
                                "detected_provider": (
                                    "ifind_excel"
                                    if workflow_id == "chinext-50-weekly"
                                    else "wind_excel"
                                ),
                                "runtime_enabled": False,
                            }
                        )
                        continue
                    formula_provider = scan_workbook_formulas(
                        draft / workbook
                    ).provider.value
                    required = (
                        ["wind_excel", "ifind_excel"]
                        if formula_provider == "mixed"
                        else (
                            [formula_provider]
                            if formula_provider in {"wind_excel", "ifind_excel"}
                            else []
                        )
                    )
                    if not required:
                        continue
                    base = (
                        json.loads(previous[workbook].model_dump_json())
                        if workbook in previous
                        else {"workbook": workbook}
                    )
                    requirements = [
                        {"provider": provider, "required": True}
                        for provider in required
                    ]
                    base["providers"] = requirements
                    # Financial add-ins may need more than 30 seconds to load,
                    # authenticate and refresh a workbook.  The worker remains
                    # bounded and killable, but the immutable workflow version
                    # must allow a realistic Excel refresh window.
                    base["timeout_seconds"] = max(
                        180.0, float(base.get("timeout_seconds") or 0)
                    )
                    validation = self._v2_validation(workflow_id, workbook)
                    if validation:
                        try:
                            cached, _, _ = read_cached_workbook(draft / workbook)
                        except WorkflowError:
                            cached = {}
                        references = [
                            *validation.get("required_cells", []),
                            *validation.get("reject_zero_cells", []),
                            validation.get("required_date_cell"),
                        ]
                        if cached and all(
                            reference in cached for reference in references if reference
                        ):
                            base.update(validation)
                    policies.append(base)
                    for requirement in requirements:
                        providers[requirement["provider"]] = requirement
                primary = self._v2_primary_workbook(workflow_id)
                if primary and not any(
                    item["workbook"] == primary for item in policies
                ):
                    row["status"] = "needs_attention"
                    self.catalog._save()
                    log.warning(
                        "report_workflow_v2_primary_workbook_missing",
                        workflow_id=workflow_id,
                    )
                    continue
                delivery = json.loads(manifest.delivery.model_dump_json())
                delivery.update(
                    primary_workbook=primary,
                    required_artifacts=[
                        f"report.{item.value}" for item in manifest.delivery.formats
                    ],
                )
                draft_manifest = json.loads(manifest.model_dump_json())
                draft_manifest.update(
                    version=int(current),
                    resources=[],
                    providers=list(providers.values()),
                    workbook_policies=policies,
                    excluded_workbooks=[item["path"] for item in legacy_resources],
                    minimum_subagents=2,
                    delivery=delivery,
                )
                row["draft_manifest"] = draft_manifest
                steps = [
                    {
                        "id": f"refresh_{index:03d}",
                        "type": "workbook_refresh",
                        "tool": "report_workbook_refresh",
                        "workbook": item["workbook"],
                    }
                    for index, item in enumerate(policies, start=1)
                ]
                steps.extend(
                    [
                        {
                            "id": "extract",
                            "type": "data_snapshot",
                            "tool": "report_workbook_extract",
                        },
                        {
                            "id": "research",
                            "type": "claw_research",
                            "minimum_subagents": draft_manifest["minimum_subagents"],
                        },
                        {
                            "id": "assemble",
                            "type": "file_assembly",
                            "tool": "report_template_assemble",
                        },
                        {
                            "id": "validate",
                            "type": "delivery_check",
                            "tool": "report_delivery_validate",
                        },
                    ]
                )
                self._write_yaml(draft / "workflow.yaml", {"steps": steps})
                self._write_yaml(
                    draft / "validation.yaml",
                    {"workbooks": policies, "legacy_resources": legacy_resources},
                )
                if legacy_resources:
                    self.catalog.upload_resource(
                        workflow_id,
                        "mappings/resource-status.yaml",
                        yaml.safe_dump(
                            {"resources": legacy_resources},
                            allow_unicode=True,
                            sort_keys=False,
                        ).encode(),
                    )
                version = self.catalog.create_version(workflow_id)
                self.catalog.publish_version(workflow_id, version.version)
                row = self.catalog._row(workflow_id)
                row.update(status="enabled", updated_at=time.time())
                row.setdefault("migration", {})["schema_version"] = max(
                    4, migration_schema + 1
                )
                self.catalog._save()
                upgraded.append(workflow_id)
                log.info(
                    "report_workflow_migrated_v2",
                    workflow_id=workflow_id,
                    version=version.version,
                )
        return {"upgraded": upgraded, "unchanged": unchanged}
