"""Versioned report projects orchestrated by the one native DSH/Claw runtime."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import shutil
import time
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4
from zoneinfo import ZoneInfo

import yaml

from core.observability import get_logger

from .datahub import BusinessQuery
from .delivery import FINAL
from .store import StoreError

if TYPE_CHECKING:
    from .service import ResearchService

log = get_logger(__name__)
SHANGHAI = ZoneInfo("Asia/Shanghai")
ACTIVE_RUNS = {
    "queued",
    "preparing_data",
    "blocked_approval",
    "running",
    "validating",
}
PROJECT_STATES = {"draft", "needs_attention", "ready", "enabled", "disabled"}
OUTPUT_FORMATS = {"docx", "html", "xlsx", "pptx", "png", "md"}
REPORT_ARTIFACT_EXTENSIONS = OUTPUT_FORMATS | {"pdf", "jpg", "jpeg", "csv", "json"}
REPORT_INPUT_EXTENSIONS = {
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
}
MIGRATION_NAMES = {
    "华安ETF周报": ("huaan-etf-weekly", "weekly"),
    "创业板50周报": ("chinext-50-weekly", "weekly"),
    "华安ETF投资风向标": ("huaan-etf-compass", "presentation"),
    "AI周报": ("ai-weekly", "weekly"),
}


class ReportStudioError(StoreError):
    def __init__(
        self, message: str, code: str = "report_studio_error", status: int = 400
    ):
        super().__init__(message)
        self.code = code
        self.status = status


def _now() -> float:
    return time.time()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _public_file(item: dict) -> dict:
    return {
        key: value
        for key, value in item.items()
        if key not in {"stored_path", "source_path"}
    }


class ReportStudio:
    """Own project metadata and schedules; delegate every report turn to Claw."""

    def __init__(self, service: ResearchService):
        self.service = service
        self.store = service.store
        self.root = self.store.root / "report-projects"
        if self.root.is_symlink():
            raise ReportStudioError("报告项目目录不能为链接", "unsafe_report_root", 503)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.tasks: dict[str, asyncio.Task] = {}
        self.scheduler_task: asyncio.Task | None = None
        self.lock = asyncio.Lock()

    async def start(self) -> None:
        self.scheduler_task = asyncio.create_task(
            self._scheduler(), name="report-scheduler"
        )

    async def close(self) -> None:
        if self.scheduler_task:
            self.scheduler_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.scheduler_task
        for task in self.tasks.values():
            task.cancel()
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)

    def _project(self, project_id: str) -> dict:
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", project_id):
            raise ReportStudioError("报告项目标识无效", "project_not_found", 404)
        try:
            return self.store.data["report_projects"][project_id]
        except KeyError as exc:
            raise ReportStudioError("报告项目不存在", "project_not_found", 404) from exc

    def _run(self, run_id: str) -> dict:
        try:
            return self.store.data["report_runs"][run_id]
        except KeyError as exc:
            raise ReportStudioError("报告运行不存在", "run_not_found", 404) from exc

    @staticmethod
    def _summary(project: dict) -> dict:
        version = project.get("versions", {}).get(str(project.get("current_version")))
        return {
            key: project.get(key)
            for key in (
                "id",
                "name",
                "project_type",
                "status",
                "current_version",
                "created_at",
                "updated_at",
            )
        } | {
            "workflow": version.get("workflow") if version else None,
            "output_formats": version.get("output_formats", []) if version else [],
            "next_run_at": project.get("schedule", {}).get("next_run_at"),
            "latest_run": project.get("latest_run"),
        }

    def list_projects(self) -> list[dict]:
        rows = sorted(
            self.store.data["report_projects"].values(),
            key=lambda item: (item.get("display_order", 99), item["name"]),
        )
        return [self._summary(row) for row in rows]

    def project(self, project_id: str) -> dict:
        row = self._project(project_id)
        return {
            **self._summary(row),
            "draft": row.get("draft", {}),
            "versions": [
                self._public_version(v) for v in row.get("versions", {}).values()
            ],
            "schedule": row.get("schedule", self._default_schedule()),
            "migration": row.get("migration"),
        }

    @staticmethod
    def _public_version(version: dict) -> dict:
        return {
            **{key: value for key, value in version.items() if key != "files"},
            "files": [_public_file(item) for item in version.get("files", [])],
        }

    @staticmethod
    def _default_schedule() -> dict:
        return {
            "kind": "off",
            "enabled": False,
            "timezone": "Asia/Shanghai",
            "once_at": None,
            "weekday": None,
            "hour": None,
            "minute": None,
            "next_run_at": None,
            "last_triggered_at": None,
        }

    def create_project(self, body: dict) -> dict:
        project_id = body["id"]
        if project_id in self.store.data["report_projects"]:
            raise ReportStudioError("报告项目已存在", "project_conflict", 409)
        now = _now()
        row = {
            "id": project_id,
            "name": body["name"].strip(),
            "project_type": body.get("project_type", "report"),
            "status": "draft",
            "draft": body.get("draft", {}),
            "current_version": None,
            "versions": {},
            "schedule": self._default_schedule(),
            "latest_run": None,
            "display_order": 99,
            "created_at": now,
            "updated_at": now,
        }
        self.store.data["report_projects"][project_id] = row
        self.store.save()
        log.info("report_project_created", project_id=project_id)
        return self.project(project_id)

    def patch_project(self, project_id: str, changes: dict) -> dict:
        row = self._project(project_id)
        if "name" in changes:
            row["name"] = changes["name"].strip()
        if "draft" in changes:
            row["draft"] = changes["draft"]
        if "status" in changes:
            requested = changes["status"]
            if requested not in PROJECT_STATES:
                raise ReportStudioError("报告项目状态无效")
            if requested in {"ready", "enabled"} and not row.get("current_version"):
                raise ReportStudioError(
                    "没有已发布版本，不能启用", "version_required", 409
                )
            row["status"] = requested
        row["updated_at"] = _now()
        self.store.save()
        return self.project(project_id)

    def create_version(self, project_id: str, body: dict) -> dict:
        row = self._project(project_id)
        active = any(
            run["project_id"] == project_id and run["status"] in ACTIVE_RUNS
            for run in self.store.data["report_runs"].values()
        )
        if active:
            raise ReportStudioError(
                "项目正在运行；草稿已保留，请结束后再发布", "project_busy", 409
            )
        formats = list(dict.fromkeys(body.get("output_formats") or []))
        if not formats or any(item not in OUTPUT_FORMATS for item in formats):
            raise ReportStudioError(
                "必须声明支持的输出格式", "invalid_output_formats", 422
            )
        number = max((int(value) for value in row["versions"]), default=0) + 1
        version_files = []
        logical_paths: dict[str, str] = {}
        for item in row.get("draft", {}).get("files", []):
            stored = Path(item.get("stored_path", ""))
            if (
                stored.is_symlink()
                or not stored.is_file()
                or not stored.resolve().is_relative_to(
                    (self.root / project_id).resolve()
                )
                or _sha256(stored) != item.get("sha256")
            ):
                raise ReportStudioError(
                    "项目草稿文件无法安全读取", "unsafe_project_file", 409
                )
            if (
                item["path"] in logical_paths
                and logical_paths[item["path"]] != item["sha256"]
            ):
                raise ReportStudioError(
                    "同名项目文件存在不同内容，请先处理冲突",
                    "project_file_conflict",
                    409,
                )
            logical_paths[item["path"]] = item["sha256"]
            version_files.append(dict(item))
        data_recipe = self._validated_data_recipe(body.get("data_recipe", []))
        version = {
            "version": number,
            "created_at": _now(),
            "workflow": body.get("workflow")
            or {"id": "report-production-workflow", "version": None},
            "output_formats": formats,
            "sections": body.get("sections", []),
            "data_recipe": data_recipe,
            "instructions": body.get("instructions", ""),
            "files": version_files,
        }
        row["versions"][str(number)] = version
        row["current_version"] = number
        row["status"] = "ready"
        row["updated_at"] = _now()
        self.store.save()
        log.info(
            "report_project_version_created", project_id=project_id, version=number
        )
        return self._public_version(version)

    def _validated_data_recipe(self, recipe: list[dict]) -> list[dict]:
        catalog = self.service.datahub.catalog()
        capabilities = {row["id"] for row in catalog["capabilities"]}
        sources = {row["id"] for row in catalog["sources"]}
        bindings = {
            (row["capability_id"], row["source_id"]) for row in catalog["bindings"]
        }
        normalized = []
        for index, item in enumerate(recipe):
            if not isinstance(item, dict):
                raise ReportStudioError(
                    "数据配方条目必须是对象", "invalid_data_recipe", 422
                )
            capability = item.get("capability")
            source = item.get("source")
            if (
                capability not in capabilities
                or source not in sources
                or source == "auto"
            ):
                raise ReportStudioError(
                    "数据配方必须固定已登记的能力和来源",
                    "invalid_data_recipe",
                    422,
                )
            if (capability, source) not in bindings:
                raise ReportStudioError(
                    "数据来源不支持配方中的能力", "invalid_data_recipe", 422
                )
            try:
                query = BusinessQuery(
                    capability=capability,
                    source=source,
                    allow_fallback=False,
                    parameters=item.get("parameters", {}),
                    refresh=bool(item.get("refresh", True)),
                )
            except ValueError as exc:
                raise ReportStudioError(
                    "数据配方参数无效", "invalid_data_recipe", 422
                ) from exc
            normalized.append(
                {
                    "id": item.get("id") or f"dataset-{index + 1}",
                    **query.model_dump(),
                    "required": item.get("required", True) is not False,
                    "allow_partial": item.get("allow_partial", False) is True,
                }
            )
        return normalized

    def _preauthorization(self, item: dict) -> tuple[str, str | None]:
        detail = self.service.datahub.catalog_source(item["source"])
        if detail is None:
            return "blocked_approval", "source_not_registered"
        binding = next(
            (
                row
                for row in detail["bindings"]
                if row["capability_id"] == item["capability"]
            ),
            None,
        )
        if binding is None or not binding["implemented"]:
            return "blocked_approval", "capability_not_integrated"
        if detail["fee"] != "free" or detail["auth_type"] != "none":
            return "blocked_approval", "source_requires_approval"
        readiness = detail["readiness"]
        if not readiness["callable"]:
            return "blocked_data", readiness["integration_state"]
        return "allowed", None

    async def _prepare_data(
        self, run: dict, session_id: str, recipe: list[dict]
    ) -> bool:
        missing = []
        for index, item in enumerate(recipe):
            decision, reason = self._preauthorization(item)
            if decision != "allowed":
                run.update(
                    status=decision,
                    failure_code=reason,
                    missing=[item["id"]],
                    updated_at=_now(),
                )
                self.store.save()
                return False
            try:
                result = await self.service.datahub.query(
                    session_id,
                    f"report-{run['id']}-dataset-{index + 1}",
                    BusinessQuery(
                        capability=item["capability"],
                        source=item["source"],
                        allow_fallback=False,
                        parameters=item["parameters"],
                        refresh=item["refresh"],
                    ),
                )
            except (StoreError, OSError, ValueError, TypeError) as exc:
                log.warning(
                    "report_data_preparation_failed",
                    report_run_id=run["id"],
                    capability=item["capability"],
                    error_type=type(exc).__name__,
                )
                if item["required"]:
                    run.update(
                        status="blocked_data",
                        failure_code="data_query_failed",
                        missing=[item["id"]],
                        updated_at=_now(),
                    )
                    self.store.save()
                    return False
                missing.append(item["id"])
                continue
            run["dataset_ids"].append(result["dataset_id"])
            incomplete = result.get("status") in {"failed", "empty"} or (
                result.get("status") == "partial" and not item["allow_partial"]
            )
            if item["required"] and incomplete:
                run.update(
                    status="blocked_data",
                    failure_code=f"data_{result.get('status', 'incomplete')}",
                    missing=[item["id"]],
                    updated_at=_now(),
                )
                self.store.save()
                return False
            if incomplete:
                missing.append(item["id"])
        run["missing"] = missing
        self.store.save()
        return True

    def add_project_file(self, project_id: str, filename: str, raw: bytes) -> dict:
        row = self._project(project_id)
        safe_name = Path(filename).name
        extension = Path(safe_name).suffix.lower()
        if (
            not safe_name
            or safe_name != filename
            or "/" in filename
            or "\\" in filename
            or any(ord(character) < 32 for character in filename)
            or extension not in REPORT_INPUT_EXTENSIONS
        ):
            raise ReportStudioError(
                "报告项目文件类型不支持", "unsupported_project_file", 422
            )
        if not raw or len(raw) > 32 * 1024 * 1024:
            raise ReportStudioError(
                "报告项目文件必须为 1 字节至 32 MiB", "project_file_size", 413
            )
        digest = hashlib.sha256(raw).hexdigest()
        target = (
            self.root / project_id / "drafts" / "uploads" / f"{digest[:12]}-{safe_name}"
        )
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not target.exists():
            target.write_bytes(raw)
            target.chmod(0o600)
        item = {
            "id": digest,
            "path": f"uploads/{safe_name}",
            "sha256": digest,
            "size": len(raw),
            "role": "upload",
            "stored_path": str(target),
        }
        files = row.setdefault("draft", {}).setdefault("files", [])
        if not any(existing["sha256"] == digest for existing in files):
            files.append(item)
            row["updated_at"] = _now()
            self.store.save()
        log.info(
            "report_project_file_added", project_id=project_id, extension=extension
        )
        return _public_file(item)

    def versions(self, project_id: str) -> list[dict]:
        versions = self._project(project_id).get("versions", {}).values()
        return [
            self._public_version(row)
            for row in sorted(versions, key=lambda row: row["version"])
        ]

    def rollback(self, project_id: str, version: int) -> dict:
        row = self._project(project_id)
        if str(version) not in row["versions"]:
            raise ReportStudioError("报告版本不存在", "version_not_found", 404)
        row["current_version"] = version
        row["updated_at"] = _now()
        self.store.save()
        return self.project(project_id)

    def migration(self, source: Path, *, dry_run: bool = True) -> dict:
        source = source.resolve(strict=True)
        if source.is_symlink() or not source.is_dir():
            raise ReportStudioError("迁移源目录不可用", "migration_source_invalid", 422)
        projects: dict[str, dict] = {}
        accepted: list[dict] = []
        quarantined: list[dict] = []
        rejected: list[dict] = []
        for folder in sorted(source.iterdir()):
            if not folder.is_dir() or folder.name == "华安ETF周报 2":
                continue
            spec = MIGRATION_NAMES.get(folder.name)
            if not spec:
                rejected.append({"path": folder.name, "reason": "unknown_project"})
                continue
            project_id, project_type = spec
            projects[project_id] = self._scan_migration_project(
                folder, project_id, project_type
            )
        duplicate = source / "华安ETF周报 2"
        if duplicate.is_dir() and "huaan-etf-weekly" in projects:
            self._merge_duplicate(projects["huaan-etf-weekly"], duplicate, quarantined)
        for item in projects.values():
            accepted.extend(_public_file(file) for file in item["version"]["files"])
            if not dry_run:
                self._apply_migration(item)
        report = {
            "id": str(uuid4()),
            "dry_run": dry_run,
            "source": str(source),
            "project_count": len(projects),
            "projects": [
                {
                    "id": item["id"],
                    "name": item["name"],
                    "status": item["status"],
                    "file_count": len(item["version"]["files"]),
                    "size": sum(file["size"] for file in item["version"]["files"]),
                }
                for item in projects.values()
            ],
            "accepted": accepted,
            "quarantined": quarantined,
            "rejected": rejected,
            "created_at": _now(),
        }
        if not dry_run:
            self.store.data["report_migrations"].append(report)
            self.store.save()
        return report

    def _scan_migration_project(
        self, folder: Path, project_id: str, project_type: str
    ) -> dict:
        config = {}
        project_file = folder / "project.yaml"
        if project_file.is_file() and not project_file.is_symlink():
            loaded = yaml.safe_load(project_file.read_text())
            if isinstance(loaded, dict):
                config = loaded
        report_config = {}
        report_config_file = folder / "config" / "report_config.yaml"
        if report_config_file.is_file() and not report_config_file.is_symlink():
            loaded = yaml.safe_load(report_config_file.read_text())
            if isinstance(loaded, dict):
                report_config = loaded
        files = []
        artifacts = []
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.is_symlink() or path.name == ".DS_Store":
                continue
            relative = path.relative_to(folder).as_posix()
            item = {
                "path": relative,
                "sha256": _sha256(path),
                "size": path.stat().st_size,
                "source_path": str(path),
                "role": relative.split("/", 1)[0],
            }
            if item["role"] in {"generated", "runs", "jobs"}:
                artifacts.append(item)
            else:
                files.append(item)
        template = next((item for item in files if item["role"] == "templates"), None)
        status = "ready" if config and template else "needs_attention"
        formats = (
            ["pptx"] if project_type == "presentation" else ["docx", "html", "xlsx"]
        )
        sections = []
        for section_id, section in report_config.get("placeholders", {}).items():
            if not isinstance(section, dict):
                continue
            sections.append(
                {
                    "id": str(section_id),
                    "title": str(section.get("title") or section_id),
                    "type": str(section.get("type") or "content"),
                    "target_words": section.get("target_words"),
                }
            )
        data_recipe = []
        if status == "ready":
            data_recipe = [
                {
                    "id": "current-public-news",
                    "capability": "search_news",
                    "source": "cls",
                    "allow_fallback": False,
                    "parameters": {
                        "query": config.get("name", folder.name),
                        "limit": 30,
                    },
                    "refresh": True,
                    "required": False,
                    "allow_partial": True,
                }
            ]
        return {
            "id": project_id,
            "name": config.get("name", folder.name),
            "project_type": project_type,
            "status": status,
            "display_order": config.get("display_order", 99),
            "source": str(folder),
            "version": {
                "version": 1,
                "created_at": _now(),
                "workflow": {"id": "report-production-workflow", "version": None},
                "output_formats": formats,
                "sections": sections,
                "data_recipe": data_recipe,
                "instructions": (
                    "迁移自旧报告项目。读取已锁定的模板、底稿、prompt_templates.md "
                    "和 report_config.yaml 作为章节及写作约束；忽略其中旧 Evidence、检索器和旧 LLM "
                    "执行字段，不调用旧执行链。"
                ),
                "files": files,
            },
            "artifacts": artifacts,
        }

    @staticmethod
    def _merge_duplicate(
        project: dict, duplicate: Path, quarantined: list[dict]
    ) -> None:
        by_path = {item["path"]: item for item in project["version"]["files"]}
        by_hash = {item["sha256"] for item in project["version"]["files"]}
        for path in sorted(duplicate.rglob("*")):
            if not path.is_file() or path.is_symlink() or path.name == ".DS_Store":
                continue
            relative = path.relative_to(duplicate).as_posix()
            role = relative.split("/", 1)[0]
            if role in {"generated", "runs", "jobs"}:
                continue
            digest = _sha256(path)
            if digest in by_hash:
                continue
            item = {
                "path": relative,
                "sha256": digest,
                "size": path.stat().st_size,
                "source_path": str(path),
                "role": role,
            }
            if relative in by_path:
                quarantined.append(
                    {
                        "path": relative,
                        "sha256": digest,
                        "reason": "path_content_conflict",
                    }
                )
                continue
            project["version"]["files"].append(item)
            by_hash.add(digest)

    def _apply_migration(self, item: dict) -> None:
        if item["id"] in self.store.data["report_projects"]:
            return
        target = self.root / item["id"] / "versions" / "1" / "assets"
        target.mkdir(parents=True, exist_ok=True, mode=0o700)
        stored_files = []
        for source in item["version"]["files"]:
            relative = Path(source["path"])
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copy2(source["source_path"], destination)
            if _sha256(destination) != source["sha256"]:
                raise ReportStudioError(
                    "报告文件复制后校验失败", "migration_hash_mismatch", 500
                )
            stored_files.append({**source, "stored_path": str(destination)})
        history_root = self.root / item["id"] / "history"
        history_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        artifact_index = []
        seen = set()
        for source in item["artifacts"]:
            if source["sha256"] in seen:
                continue
            seen.add(source["sha256"])
            destination = (
                history_root / f"{source['sha256'][:12]}-{Path(source['path']).name}"
            )
            shutil.copy2(source["source_path"], destination)
            artifact_index.append(
                {**source, "stored_path": str(destination), "historical": True}
            )
        now = _now()
        version = {**item["version"], "files": stored_files}
        row = {
            "id": item["id"],
            "name": item["name"],
            "project_type": item["project_type"],
            "status": item["status"],
            "draft": {},
            "current_version": 1,
            "versions": {"1": version},
            "schedule": self._default_schedule(),
            "latest_run": None,
            "historical_artifacts": artifact_index,
            "migration": {"source": item["source"], "applied_at": now},
            "display_order": item["display_order"],
            "created_at": now,
            "updated_at": now,
        }
        self.store.data["report_projects"][item["id"]] = row
        self.store.save()
        log.info(
            "report_project_migrated", project_id=item["id"], status=item["status"]
        )

    def schedule(self, project_id: str) -> dict:
        return self._project(project_id).get("schedule", self._default_schedule())

    def put_schedule(
        self, project_id: str, body: dict, *, now: datetime | None = None
    ) -> dict:
        project = self._project(project_id)
        kind = body.get("kind", "off")
        if kind not in {"off", "once", "weekly"}:
            raise ReportStudioError("日程只支持关闭、一次性或每周")
        schedule = self._default_schedule()
        schedule.update(
            kind=kind,
            enabled=bool(body.get("enabled", kind != "off")) and kind != "off",
            once_at=body.get("once_at"),
            weekday=body.get("weekday"),
            hour=body.get("hour"),
            minute=body.get("minute"),
        )
        schedule["next_run_at"] = self._next_run(schedule, now or datetime.now(UTC))
        project["schedule"] = schedule
        project["updated_at"] = _now()
        self.store.save()
        return schedule

    @staticmethod
    def _next_run(schedule: dict, now: datetime) -> str | None:
        if not schedule["enabled"]:
            return None
        if schedule["kind"] == "once":
            try:
                value = datetime.fromisoformat(schedule["once_at"])
            except (TypeError, ValueError) as exc:
                raise ReportStudioError("一次性日程需要有效时间") from exc
            if value.tzinfo is None:
                value = value.replace(tzinfo=SHANGHAI)
            return value.astimezone(UTC).isoformat()
        if schedule["kind"] == "weekly":
            weekday, hour, minute = (
                schedule.get("weekday"),
                schedule.get("hour"),
                schedule.get("minute"),
            )
            if not isinstance(weekday, int) or weekday not in range(7):
                raise ReportStudioError("每周日程需要 0–6 的星期")
            if (
                not isinstance(hour, int)
                or hour not in range(24)
                or not isinstance(minute, int)
                or minute not in range(60)
            ):
                raise ReportStudioError("每周日程需要有效时分")
            local = now.astimezone(SHANGHAI)
            target = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
            target += timedelta(days=(weekday - target.weekday()) % 7)
            if target <= local:
                target += timedelta(days=7)
            return target.astimezone(UTC).isoformat()
        return None

    async def _scheduler(self) -> None:
        while True:
            try:
                await self.tick()
            except (OSError, StoreError, ValueError, TypeError) as exc:
                log.error("report_scheduler_tick_failed", error_type=type(exc).__name__)
            await asyncio.sleep(15)

    async def tick(self, now: datetime | None = None) -> None:
        now = now or datetime.now(UTC)
        for project in list(self.store.data["report_projects"].values()):
            schedule = project.get("schedule", {})
            due = schedule.get("next_run_at")
            if not schedule.get("enabled") or not due:
                continue
            if datetime.fromisoformat(due).astimezone(UTC) > now:
                continue
            await self.start_run(project["id"], trigger="schedule")
            schedule["last_triggered_at"] = now.isoformat()
            if schedule["kind"] == "once":
                schedule.update(enabled=False, next_run_at=None)
            else:
                schedule["next_run_at"] = self._next_run(schedule, now)
            self.store.save()

    async def start_run(self, project_id: str, *, trigger: str = "manual") -> dict:
        async with self.lock:
            project = self._project(project_id)
            active = next(
                (
                    item
                    for item in self.store.data["report_runs"].values()
                    if item["project_id"] == project_id
                    and item["status"] in ACTIVE_RUNS
                ),
                None,
            )
            run_id = str(uuid4())
            if active:
                skipped = self._new_run(run_id, project, trigger, "skipped_overlap")
                self.store.data["report_runs"][run_id] = skipped
                self.store.save()
                return self.public_run(skipped)
            if project["status"] not in {"ready", "enabled"} or not project.get(
                "current_version"
            ):
                raise ReportStudioError(
                    "项目资料或版本尚未补全", "project_not_ready", 409
                )
            run = self._new_run(run_id, project, trigger, "queued")
            self.store.data["report_runs"][run_id] = run
            project["latest_run"] = run_id
            self.store.save()
            self.tasks[run_id] = asyncio.create_task(
                self._execute(run_id), name=f"report-{run_id}"
            )
            return self.public_run(run)

    @staticmethod
    def _new_run(run_id: str, project: dict, trigger: str, status: str) -> dict:
        return {
            "id": run_id,
            "project_id": project["id"],
            "trigger": trigger,
            "version": project.get("current_version"),
            "workflow": project.get("versions", {})
            .get(str(project.get("current_version")), {})
            .get("workflow"),
            "session_id": None,
            "dataset_ids": [],
            "status": status,
            "delivery_status": "pending",
            "missing": [],
            "artifacts": [],
            "failure_code": None,
            "created_at": _now(),
            "updated_at": _now(),
        }

    async def _execute(self, run_id: str) -> None:
        run = self._run(run_id)
        try:
            run.update(status="preparing_data", updated_at=_now())
            self.store.save()
            project = self._project(run["project_id"])
            version = project["versions"][str(run["version"])]
            missing = [
                item["path"]
                for item in version["files"]
                if not Path(item.get("stored_path", "")).is_file()
            ]
            if missing:
                run.update(
                    status="blocked_data",
                    missing=missing,
                    failure_code="project_files_missing",
                    updated_at=_now(),
                )
                self.store.save()
                return
            session = await self.service.create("claw", f"{project['name']} · 报告运行")
            run["session_id"] = session["id"]
            if not await self._prepare_data(run, session["id"], version["data_recipe"]):
                return
            target = self.store.directory(session["id"]) / "inputs" / "report-project"
            target.mkdir(parents=True, exist_ok=True, mode=0o700)
            for item in version["files"]:
                destination = target / item["path"]
                destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                shutil.copy2(item["stored_path"], destination)
            manifest = {
                "project": project["name"],
                "project_id": project["id"],
                "version": run["version"],
                "workflow": version["workflow"],
                "output_formats": version["output_formats"],
                "sections": version["sections"],
                "data_recipe": version["data_recipe"],
                "dataset_ids": run["dataset_ids"],
                "files": [_public_file(item) for item in version["files"]],
            }
            (target / "report-project-manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2)
            )
            prompt = (
                f"执行报告项目《{project['name']}》的锁定版本 v{run['version']}。"
                "先核对 inputs/report-project/report-project-manifest.json 及模板、底稿和数据要求；"
                "复杂报告至少委派两个原生子 Agent，并让它们读取同一份资料。"
                "不要调用旧报告服务。生成结构化 report_payload.json，并在 outputs 下交付要求的实际文件。"
                "明确数据截止时间、来源、缺失项和未映射模板占位符。"
            )
            workflow = version["workflow"] or {}
            await self.service.send(
                session["id"],
                prompt,
                f"report-{run_id}",
                formats=version["output_formats"],
                capability_id=workflow.get("id", "report-production-workflow"),
                capability_version=workflow.get("version"),
            )
            run.update(status="running", updated_at=_now())
            self.store.audit(
                "report",
                "started",
                session_id=session["id"],
                project_id=project["id"],
                report_run_id=run_id,
            )
            self.store.save()
            for _ in range(7200):
                await asyncio.sleep(1)
                detail = await self.service.detail(session["id"])
                if detail.get("approvals"):
                    run["status"] = "blocked_approval"
                elif detail.get("can_cancel") or detail.get("status") == "running":
                    run["status"] = "running"
                else:
                    delivery = detail.get("delivery") or {}
                    if delivery.get("status") not in FINAL:
                        continue
                    run["delivery_status"] = (
                        "complete"
                        if delivery.get("status") == "completed"
                        else "incomplete"
                    )
                    run["artifacts"] = delivery.get("files", [])
                    run["missing"] = delivery.get("missing_formats", [])
                    run["status"] = (
                        "completed"
                        if delivery.get("status") == "completed"
                        else "delivery_incomplete"
                    )
                    break
                run["updated_at"] = _now()
                self.store.save()
            else:
                run.update(status="failed", failure_code="report_timeout")
        except asyncio.CancelledError:
            if run.get("session_id"):
                with suppress(Exception):
                    await self.service.cancel(run["session_id"])
            run.update(status="cancelled", delivery_status="incomplete")
            raise
        except Exception as exc:  # noqa: BLE001 - background boundary is fail-closed
            log.error("report_run_failed", run_id=run_id, error_type=type(exc).__name__)
            run.update(status="failed", failure_code=type(exc).__name__)
        finally:
            run["updated_at"] = _now()
            self.store.audit(
                "report",
                run["status"],
                session_id=run.get("session_id"),
                project_id=run["project_id"],
                report_run_id=run_id,
            )
            self.store.save()
            self.tasks.pop(run_id, None)

    def public_run(self, run: dict) -> dict:
        return {
            **run,
            "artifacts": [_public_file(item) for item in run.get("artifacts", [])],
        }

    def runs(self, project_id: str) -> list[dict]:
        self._project(project_id)
        rows = [
            item
            for item in self.store.data["report_runs"].values()
            if item["project_id"] == project_id
        ]
        return [
            self.public_run(item)
            for item in sorted(rows, key=lambda item: item["created_at"], reverse=True)
        ]

    async def cancel(self, run_id: str) -> dict:
        run = self._run(run_id)
        if run["status"] not in ACTIVE_RUNS:
            raise ReportStudioError("报告运行已结束", "run_not_active", 409)
        if run.get("session_id"):
            await self.service.cancel(run["session_id"])
        task = self.tasks.get(run_id)
        if task:
            task.cancel()
        run.update(status="cancelled", delivery_status="incomplete", updated_at=_now())
        self.store.save()
        return self.public_run(run)

    def artifacts(self, project_id: str) -> list[dict]:
        project = self._project(project_id)
        historical = [
            {
                **_public_file(item),
                "id": item["sha256"],
                "name": item.get("name") or Path(item["path"]).name,
                "run_id": None,
                "url": f"/api/research/report-projects/{project_id}/artifacts/{item['sha256']}",
                "preview_url": f"/api/research/report-projects/{project_id}/artifacts/{item['sha256']}?preview=true",
            }
            for item in project.get("historical_artifacts", [])
            if self._visible_historical_artifact(item)
        ]
        generated = []
        for run in self.runs(project_id):
            generated.extend(
                {**item, "run_id": run["id"]} for item in run.get("artifacts", [])
            )
        return generated + historical

    @staticmethod
    def _visible_historical_artifact(item: dict) -> bool:
        """Keep deliverables visible while hiding preview caches and job state."""
        relative = Path(item.get("path", ""))
        if ".preview-cache" in relative.parts:
            return False
        suffix = relative.suffix.lower().lstrip(".")
        if suffix not in REPORT_ARTIFACT_EXTENSIONS:
            return False
        return suffix != "json" or any(
            part in {"logs", "log"} for part in relative.parts
        )

    def artifact_path(self, project_id: str, artifact_id: str) -> Path:
        project = self._project(project_id)
        if not re.fullmatch(r"[a-f0-9]{64}", artifact_id):
            raise ReportStudioError("报告产物不存在", "artifact_not_found", 404)
        item = next(
            (
                row
                for row in project.get("historical_artifacts", [])
                if row["sha256"] == artifact_id
            ),
            None,
        )
        if not item:
            raise ReportStudioError("报告产物不存在", "artifact_not_found", 404)
        path = Path(item["stored_path"])
        if (
            path.is_symlink()
            or not path.is_file()
            or not path.resolve().is_relative_to(self.root)
        ):
            raise ReportStudioError("报告产物不可安全读取", "unsafe_artifact", 409)
        return path
