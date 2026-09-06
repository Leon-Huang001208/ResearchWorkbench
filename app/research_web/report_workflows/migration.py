"""Idempotent import of legacy report assets into versioned Workflow packages."""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path
from uuid import uuid4

import yaml

from core.observability import get_logger

from .models import WorkflowError
from .workbook import scan_workbook_formulas

log = get_logger(__name__)
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        config = {}
        for filename in ("project.yaml", "report_config.yaml"):
            candidate = folder / filename
            if candidate.is_file() and not candidate.is_symlink():
                try:
                    loaded = yaml.safe_load(candidate.read_text())
                    if isinstance(loaded, dict):
                        config.update(loaded)
                except (OSError, yaml.YAMLError):
                    pass
        report_config = {}
        configured_report = str(config.get("report_config") or "config/report_config.yaml")
        configured_path = Path(configured_report)
        if not configured_path.is_absolute() and ".." not in configured_path.parts:
            candidate = folder / configured_path
            if (
                candidate.is_file()
                and not candidate.is_symlink()
                and candidate.resolve().is_relative_to(folder.resolve())
            ):
                try:
                    loaded = yaml.safe_load(candidate.read_text())
                    if isinstance(loaded, dict):
                        report_config = loaded
                except (OSError, yaml.YAMLError):
                    pass
        resources = []
        history = []
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.is_symlink() or path.name == ".DS_Store":
                continue
            relative = path.relative_to(folder)
            if ".preview-cache" in relative.parts:
                continue
            item = {
                "path": relative.as_posix(),
                "logical_path": self._logical_path(relative),
                "sha256": _sha256(path),
                "size": path.stat().st_size,
                "source_path": str(path),
            }
            if any(part in {"generated", "runs", "jobs", "outputs"} for part in relative.parts):
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
            "source": str(folder),
            "resources": resources,
            "history": history,
            "config": config,
            "report_config": report_config,
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
            raise WorkflowError("迁移源目录不可读取", "migration_source_invalid", 422) from exc
        if root.is_symlink() or not root.is_dir():
            raise WorkflowError("迁移源目录不可读取", "migration_source_invalid", 422)
        projects = []
        rejected = []
        quarantined = []
        for folder in sorted(root.iterdir()):
            if not folder.is_dir() or folder.name == "华安ETF周报 2":
                continue
            spec = KNOWN.get(folder.name)
            if not spec:
                rejected.append({"path": folder.name, "reason": "unknown_project"})
                continue
            projects.append(self._scan(folder, *spec))
        duplicate = root / "华安ETF周报 2"
        primary = next((item for item in projects if item["id"] == "huaan-etf-weekly"), None)
        if duplicate.is_dir() and primary:
            existing = {item["logical_path"]: item["sha256"] for item in primary["resources"]}
            hashes = set(existing.values())
            for path in sorted(duplicate.rglob("*")):
                if not path.is_file() or path.is_symlink() or path.suffix.lower() not in ALLOWED:
                    continue
                logical = self._logical_path(path.relative_to(duplicate))
                digest = _sha256(path)
                if digest in hashes:
                    continue
                if logical in existing:
                    quarantined.append(
                        {
                            "path": logical,
                            "sha256": digest,
                            "reason": "path_content_conflict",
                        }
                    )
                    continue
                primary["resources"].append(
                    {
                        "path": path.relative_to(duplicate).as_posix(),
                        "logical_path": logical,
                        "sha256": digest,
                        "size": path.stat().st_size,
                        "source_path": str(path),
                    }
                )
        accepted = [
            {key: value for key, value in resource.items() if key != "source_path"}
            for project in projects
            for resource in project["resources"]
        ]
        if not dry_run:
            for project in projects:
                self._apply(project)
        report = {
            "id": uuid4().hex,
            "dry_run": dry_run,
            "source": str(root),
            "source_sha256": hashlib.sha256(
                json.dumps(
                    sorted(
                        (item["logical_path"], item["sha256"])
                        for project in projects
                        for item in project["resources"]
                    )
                ).encode()
            ).hexdigest(),
            "project_count": len(projects),
            "projects": [
                {"id": item["id"], "name": item["name"], "status": item["status"]}
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

    def _apply(self, project: dict) -> None:
        with self.catalog._exclusive():
            self._apply_locked(project)

    def _apply_locked(self, project: dict) -> None:
        if project["id"] in self.catalog.data["workflows"]:
            return
        workbook_policies = []
        providers = {}
        refresh = project["config"].get("excel_refresh") or {}
        active_workbook = Path(str(project["config"].get("active_excel_workbook", ""))).name
        for item in project["resources"]:
            if not item["logical_path"].startswith("workbooks/"):
                continue
            try:
                formula_provider = scan_workbook_formulas(Path(item["source_path"])).provider.value
            except WorkflowError:
                project["status"] = "needs_attention"
                continue
            required = (
                ["wind_excel", "ifind_excel"]
                if formula_provider == "mixed"
                else [formula_provider] if formula_provider in {"wind_excel", "ifind_excel"} else []
            )
            declared = str(refresh.get("provider", ""))
            if item["logical_path"].endswith(active_workbook) and declared in {
                "wind_excel",
                "ifind_excel",
            }:
                required = sorted({*required, declared})
            if required or item["logical_path"].endswith(active_workbook):
                requirements = [{"provider": provider, "required": True} for provider in required]
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
                if item["logical_path"].endswith(active_workbook) and refresh.get("date_cell"):
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
                    Path(logical).parent / f"{resource['sha256'][:12]}-{Path(logical).name}"
                ).as_posix()
            seen[logical] = resource["sha256"]
            self.catalog.upload_resource(
                project["id"], logical, Path(resource["source_path"]).read_bytes()
            )
        row = self.catalog._row(project["id"])
        row.update(
            status=project["status"],
            migration={"source": project["source"], "applied_at": time.time()},
        )
        if project["status"] != "needs_attention":
            version = self.catalog.create_version(project["id"])
            self.catalog.publish_version(project["id"], version.version)
            row["status"] = "enabled"
        history_root = self.catalog.root / project["id"] / "history"
        history_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        history = []
        for item in project["history"]:
            target = history_root / f"{item['sha256'][:12]}-{Path(item['path']).name}"
            if not target.exists():
                shutil.copy2(item["source_path"], target)
                target.chmod(0o400)
            history.append(
                {
                    "id": item["sha256"],
                    "path": item["path"],
                    "sha256": item["sha256"],
                    "size": item["size"],
                    "stored_path": str(target),
                    "historical": True,
                }
            )
        row["historical_artifacts"] = history
        self.catalog._save()
