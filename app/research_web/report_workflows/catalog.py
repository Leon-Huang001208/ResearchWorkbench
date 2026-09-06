"""Immutable on-disk Report Workflow version packages."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from uuid import uuid4

import yaml
from pydantic import ValidationError

from core.observability import get_logger

from .models import (
    ReportWorkflowManifest,
    WorkbookFormulaProvider,
    WorkflowError,
    WorkflowResource,
    WorkflowResourceRole,
)
from .workbook import WorkbookRefreshService, scan_workbook_formulas

log = get_logger(__name__)
_WORKFLOW_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_RESOURCE_ROOTS = {"templates", "workbooks", "assets", "mappings"}
_RESOURCE_EXTENSIONS = {
    ".md",
    ".txt",
    ".csv",
    ".json",
    ".yaml",
    ".yml",
    ".html",
    ".css",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".svg",
    ".pdf",
    ".docx",
    ".xlsx",
    ".pptx",
}
_MAX_RESOURCE = 32 * 1024 * 1024


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _yaml_data(model) -> dict:
    return json.loads(model.model_dump_json())


def _atomic_json(path: Path, value: dict) -> None:
    fd, temporary = tempfile.mkstemp(prefix="catalog-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        log.error("report_workflow_catalog_write_failed", error_type=type(exc).__name__)
        raise WorkflowError("Report Workflow 索引无法保存", "catalog_unavailable", 503) from exc
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _validate_id(workflow_id: str) -> str:
    if not _WORKFLOW_ID.fullmatch(workflow_id):
        raise WorkflowError("Workflow 标识无效", "workflow_not_found", 404)
    return workflow_id


def _resource_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        not value
        or len(value) > 240
        or "\\" in value
        or ":" in value
        or "\x00" in value
        or path.is_absolute()
        or any(part in {"", ".", ".."} or part.startswith(".") for part in path.parts)
        or len(path.parts) < 2
        or path.parts[0] not in _RESOURCE_ROOTS
        or path.suffix.lower() not in _RESOURCE_EXTENSIONS
        or any(ord(character) < 32 for character in value)
    ):
        raise WorkflowError("资源路径或类型不允许", "unsafe_resource_path", 422)
    if path.parts[0] == "workbooks" and path.suffix.lower() != ".xlsx":
        raise WorkflowError("工作簿资源只支持 xlsx", "unsupported_workbook", 422)
    return path


def _ensure_tree_safe(base: Path) -> Path:
    if base.is_symlink():
        raise WorkflowError("Workflow 目录不能是符号链接", "unsafe_workflow_path", 409)
    try:
        resolved = base.resolve(strict=True)
    except OSError as exc:
        raise WorkflowError("Workflow 目录不可读取", "workflow_unavailable", 503) from exc
    for path in base.rglob("*"):
        if path.is_symlink():
            raise WorkflowError("Workflow 资源不能是符号链接", "unsafe_workflow_path", 409)
        if not path.resolve().is_relative_to(resolved):
            raise WorkflowError("Workflow 资源超出目录", "unsafe_workflow_path", 409)
    return resolved


def _safe_destination(base: Path, relative: PurePosixPath) -> Path:
    _ensure_tree_safe(base)
    current = base
    for part in relative.parts[:-1]:
        current = current / part
        if current.exists() and current.is_symlink():
            raise WorkflowError("资源目录不能是符号链接", "unsafe_workflow_path", 409)
    target = base.joinpath(*relative.parts)
    if target.exists() and target.is_symlink():
        raise WorkflowError("资源文件不能是符号链接", "unsafe_workflow_path", 409)
    if not target.resolve(strict=False).is_relative_to(base.resolve(strict=True)):
        raise WorkflowError("资源路径超出 Workflow 目录", "unsafe_workflow_path", 409)
    return target


def _role(path: str) -> WorkflowResourceRole:
    root = PurePosixPath(path).parts[0]
    return {
        "templates": WorkflowResourceRole.TEMPLATE,
        "workbooks": WorkflowResourceRole.WORKBOOK,
        "assets": WorkflowResourceRole.ASSET,
        "mappings": WorkflowResourceRole.MAPPING,
    }.get(root, WorkflowResourceRole.WORKFLOW)


class ReportWorkflowService:
    """Manage drafts, immutable versions and isolated runtime copies."""

    def __init__(self, data_root: Path) -> None:
        self.root = Path(data_root) / "report-workflows"
        if self.root.is_symlink():
            raise WorkflowError("Report Workflow 根目录不能是链接", "unsafe_workflow_root", 503)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        for folder in (self.root / "runs",):
            if folder.is_symlink():
                raise WorkflowError("Report Workflow 运行目录不能是链接", "unsafe_workflow_root", 503)
            folder.mkdir(exist_ok=True, mode=0o700)
        self.index = self.root / "catalog.json"
        try:
            self.data = (
                json.loads(self.index.read_text())
                if self.index.exists()
                else {"schema_version": 1, "workflows": {}, "runs": {}}
            )
            self.data.setdefault("workflows", {})
            self.data.setdefault("runs", {})
        except (OSError, ValueError, TypeError) as exc:
            log.error("report_workflow_catalog_unreadable", error_type=type(exc).__name__)
            raise WorkflowError(
                "Report Workflow 索引不可读取；未覆盖原索引", "catalog_unavailable", 503
            ) from exc

    def _save(self) -> None:
        _atomic_json(self.index, self.data)

    def _row(self, workflow_id: str) -> dict:
        _validate_id(workflow_id)
        try:
            return self.data["workflows"][workflow_id]
        except KeyError as exc:
            raise WorkflowError("Report Workflow 不存在", "workflow_not_found", 404) from exc

    def _draft(self, workflow_id: str) -> Path:
        row = self._row(workflow_id)
        path = self.root / workflow_id / "draft"
        if not path.is_dir() or path.is_symlink():
            raise WorkflowError("Workflow 草稿目录不可读取", "workflow_unavailable", 503)
        if row.get("draft_manifest", {}).get("workflow_id") != workflow_id:
            raise WorkflowError("Workflow 草稿归属不一致", "workflow_unavailable", 503)
        return path

    def create_draft(
        self,
        manifest: ReportWorkflowManifest | dict,
        *,
        workflow: dict | None = None,
        validation: dict | None = None,
    ) -> ReportWorkflowManifest:
        try:
            contract = (
                manifest
                if isinstance(manifest, ReportWorkflowManifest)
                else ReportWorkflowManifest.model_validate(manifest)
            )
        except ValidationError as exc:
            raise WorkflowError("Workflow manifest 不符合契约", "invalid_manifest", 422) from exc
        workflow_id = contract.workflow_id
        if workflow_id in self.data["workflows"]:
            raise WorkflowError("Report Workflow 已存在", "workflow_conflict", 409)
        base = self.root / workflow_id
        if base.exists() or base.is_symlink():
            raise WorkflowError("Report Workflow 目录冲突", "workflow_conflict", 409)
        draft = base / "draft"
        try:
            for folder in _RESOURCE_ROOTS:
                (draft / folder).mkdir(parents=True, exist_ok=False, mode=0o700)
            (draft / "workflow.yaml").write_text(
                yaml.safe_dump(workflow or {"steps": []}, allow_unicode=True, sort_keys=False)
            )
            (draft / "validation.yaml").write_text(
                yaml.safe_dump(
                    validation
                    or {
                        "workbooks": [
                            json.loads(policy.model_dump_json())
                            for policy in contract.workbook_policies
                        ]
                    },
                    allow_unicode=True,
                    sort_keys=False,
                )
            )
        except OSError as exc:
            log.error("report_workflow_draft_create_failed", error_type=type(exc).__name__)
            raise WorkflowError("Workflow 草稿无法创建", "workflow_unavailable", 503) from exc
        self.data["workflows"][workflow_id] = {
            "draft_manifest": _yaml_data(contract.model_copy(update={"resources": []})),
            "versions": {},
            "current_version": None,
        }
        self._save()
        log.info("report_workflow_draft_created", workflow_id=workflow_id)
        return contract

    def upload_resource(self, workflow_id: str, path: str, raw: bytes) -> WorkflowResource:
        if path.startswith("versions/"):
            raise WorkflowError("已发布版本不可变", "version_immutable", 409)
        relative = _resource_path(path)
        if not raw or len(raw) > _MAX_RESOURCE:
            raise WorkflowError("资源必须为 1 字节至 32 MiB", "resource_size", 413)
        draft = self._draft(workflow_id)
        target = _safe_destination(draft, relative)
        try:
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            target.write_bytes(raw)
            target.chmod(0o600)
        except OSError as exc:
            log.warning("report_workflow_resource_write_failed", error_type=type(exc).__name__)
            raise WorkflowError("Workflow 资源无法保存", "workflow_unavailable", 503) from exc
        resource = WorkflowResource(
            path=relative.as_posix(),
            role=_role(relative.as_posix()),
            sha256=hashlib.sha256(raw).hexdigest(),
            size=len(raw),
        )
        log.info(
            "report_workflow_resource_uploaded",
            workflow_id=workflow_id,
            role=resource.role.value,
        )
        return resource

    @staticmethod
    def _resources(package: Path) -> list[WorkflowResource]:
        resources: list[WorkflowResource] = []
        for path in sorted(package.rglob("*")):
            if not path.is_file() or path.name == "manifest.yaml":
                continue
            relative = path.relative_to(package).as_posix()
            role = (
                WorkflowResourceRole.WORKFLOW
                if relative == "workflow.yaml"
                else WorkflowResourceRole.VALIDATION
                if relative == "validation.yaml"
                else _role(relative)
            )
            resources.append(
                WorkflowResource(
                    path=relative,
                    role=role,
                    sha256=_sha256(path),
                    size=path.stat().st_size,
                )
            )
        return resources

    def create_version(self, workflow_id: str) -> ReportWorkflowManifest:
        row = self._row(workflow_id)
        draft = self._draft(workflow_id)
        _ensure_tree_safe(draft)
        number = max((int(value) for value in row["versions"]), default=0) + 1
        target = self.root / workflow_id / "versions" / str(number)
        if target.exists() or target.is_symlink():
            raise WorkflowError("Workflow 版本目录冲突", "version_conflict", 409)
        temporary = self.root / workflow_id / "versions" / f".building-{uuid4().hex}"
        try:
            temporary.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copytree(draft, temporary, symlinks=True)
            _ensure_tree_safe(temporary)
            manifest = ReportWorkflowManifest.model_validate(
                {
                    **row["draft_manifest"],
                    "version": number,
                    "resources": [
                        json.loads(item.model_dump_json()) for item in self._resources(temporary)
                    ],
                }
            )
            (temporary / "manifest.yaml").write_text(
                yaml.safe_dump(_yaml_data(manifest), allow_unicode=True, sort_keys=False)
            )
            os.replace(temporary, target)
            for path in target.rglob("*"):
                if path.is_file():
                    path.chmod(0o400)
            row["versions"][str(number)] = {"published": False}
            self._save()
            log.info(
                "report_workflow_version_created", workflow_id=workflow_id, version=number
            )
            return manifest
        except (OSError, ValidationError, WorkflowError) as exc:
            if temporary.exists() and not temporary.is_symlink():
                shutil.rmtree(temporary, ignore_errors=True)
            if isinstance(exc, WorkflowError):
                raise
            log.error("report_workflow_version_create_failed", error_type=type(exc).__name__)
            raise WorkflowError("Workflow 版本无法创建", "workflow_unavailable", 503) from exc

    def _version_path(self, workflow_id: str, version: int) -> Path:
        row = self._row(workflow_id)
        if str(version) not in row["versions"]:
            raise WorkflowError("Workflow 版本不存在", "version_not_found", 404)
        path = self.root / workflow_id / "versions" / str(version)
        _ensure_tree_safe(path)
        return path

    def manifest(self, workflow_id: str, version: int) -> ReportWorkflowManifest:
        package = self._version_path(workflow_id, version)
        try:
            raw = yaml.safe_load((package / "manifest.yaml").read_text())
            manifest = ReportWorkflowManifest.model_validate(raw)
        except (OSError, ValueError, TypeError, ValidationError, yaml.YAMLError) as exc:
            log.warning("report_workflow_manifest_read_failed", error_type=type(exc).__name__)
            raise WorkflowError("Workflow manifest 不可读取", "invalid_manifest", 409) from exc
        if manifest.workflow_id != workflow_id or manifest.version != version:
            raise WorkflowError("Workflow manifest 归属不一致", "invalid_manifest", 409)
        return manifest

    def list_resources(self, workflow_id: str, version: int) -> list[WorkflowResource]:
        return self.manifest(workflow_id, version).resources

    def resource_path(self, workflow_id: str, version: int, path: str) -> Path:
        relative = PurePosixPath(path)
        if relative.is_absolute() or ".." in relative.parts or "\\" in path:
            raise WorkflowError("资源路径不允许", "unsafe_resource_path", 422)
        manifest = self.manifest(workflow_id, version)
        expected = next((item for item in manifest.resources if item.path == path), None)
        if expected is None:
            raise WorkflowError("Workflow 资源不存在", "resource_not_found", 404)
        package = self._version_path(workflow_id, version)
        target = package.joinpath(*relative.parts)
        if target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(
            package.resolve()
        ):
            raise WorkflowError("Workflow 资源不可读取", "unsafe_workflow_path", 409)
        if target.stat().st_size != expected.size or _sha256(target) != expected.sha256:
            raise WorkflowError("Workflow 资源哈希不一致", "resource_hash_mismatch", 409)
        return target

    def preflight(self, workflow_id: str, version: int) -> dict:
        manifest = self.manifest(workflow_id, version)
        for resource in manifest.resources:
            self.resource_path(workflow_id, version, resource.path)
        for policy in manifest.workbook_policies:
            try:
                workbook = self.resource_path(workflow_id, version, policy.workbook)
            except WorkflowError as exc:
                return {"status": "blocked_data", "code": exc.code}
            scan = scan_workbook_formulas(workbook)
            required = (
                {"wind_excel", "ifind_excel"}
                if scan.provider is WorkbookFormulaProvider.MIXED
                else {scan.provider.value}
                if scan.provider is not WorkbookFormulaProvider.NONE
                else set()
            )
            declared = {item.provider.value for item in policy.providers}
            missing = sorted(required - declared)
            if missing:
                return {
                    "status": "blocked_data",
                    "code": "provider_declaration_missing",
                    "missing_providers": missing,
                }
            for requirement in policy.providers:
                mapping = requirement.equivalent_datahub_mapping
                if mapping and not any(item.path == mapping for item in manifest.resources):
                    return {
                        "status": "blocked_data",
                        "code": "fallback_mapping_missing",
                        "path": mapping,
                    }
        return {"status": "ready", "code": None}

    def publish_version(self, workflow_id: str, version: int) -> dict:
        result = self.preflight(workflow_id, version)
        if result["status"] != "ready":
            raise WorkflowError("Workflow 预检未通过", result["code"], 409)
        row = self._row(workflow_id)
        row["versions"][str(version)]["published"] = True
        row["current_version"] = version
        self._save()
        log.info("report_workflow_version_published", workflow_id=workflow_id, version=version)
        return {"workflow_id": workflow_id, "current_version": version, "status": "published"}

    def rollback_version(self, workflow_id: str, version: int) -> dict:
        row = self._row(workflow_id)
        target = row["versions"].get(str(version))
        if target is None or not target.get("published"):
            raise WorkflowError("只能回滚到已发布版本", "version_not_published", 409)
        self.preflight(workflow_id, version)
        row["current_version"] = version
        self._save()
        log.info("report_workflow_version_rolled_back", workflow_id=workflow_id, version=version)
        return {"workflow_id": workflow_id, "current_version": version, "status": "published"}

    def create_run_workspace(self, workflow_id: str, version: int | None = None) -> dict:
        row = self._row(workflow_id)
        selected = version or row.get("current_version")
        if selected is None:
            raise WorkflowError("Workflow 尚未发布", "version_required", 409)
        preflight = self.preflight(workflow_id, selected)
        if preflight["status"] != "ready":
            raise WorkflowError("Workflow 预检未通过", preflight["code"], 409)
        source = self._version_path(workflow_id, selected)
        run_id = uuid4().hex
        target = self.root / "runs" / run_id
        try:
            shutil.copytree(source, target, symlinks=True)
            _ensure_tree_safe(target)
        except (OSError, WorkflowError) as exc:
            if target.exists() and not target.is_symlink():
                shutil.rmtree(target, ignore_errors=True)
            log.error("report_workflow_run_copy_failed", error_type=type(exc).__name__)
            raise WorkflowError("Workflow 运行空间无法创建", "run_workspace_failed", 503) from exc
        self.data["runs"][run_id] = {
            "workflow_id": workflow_id,
            "version": selected,
            "path": str(target),
        }
        self._save()
        log.info(
            "report_workflow_run_workspace_created",
            workflow_id=workflow_id,
            version=selected,
            report_run_id=run_id,
        )
        return {"run_id": run_id, "workflow_id": workflow_id, "version": selected, "path": str(target)}

    def read_refresh_manifest(self, run_id: str) -> dict:
        if not re.fullmatch(r"[a-f0-9]{32}", run_id) or run_id not in self.data["runs"]:
            raise WorkflowError("Workflow 运行不存在", "run_not_found", 404)
        root = self.root / "runs" / run_id
        _ensure_tree_safe(root)
        path = root / "refresh-manifest.json"
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(
            root.resolve()
        ):
            raise WorkflowError("刷新清单不存在", "refresh_manifest_not_found", 404)
        try:
            value = json.loads(path.read_text())
        except (OSError, ValueError, TypeError) as exc:
            raise WorkflowError("刷新清单不可读取", "refresh_manifest_invalid", 409) from exc
        if value.get("status") != "ready" or not re.fullmatch(
            r"[a-f0-9]{64}", str(value.get("output_sha256", ""))
        ):
            raise WorkflowError("刷新清单无效", "refresh_manifest_invalid", 409)
        return value

    def refresh_workbook(
        self,
        run_id: str,
        workbook: str,
        *,
        refresh_service: WorkbookRefreshService | None = None,
    ):
        if run_id not in self.data["runs"]:
            raise WorkflowError("Workflow 运行不存在", "run_not_found", 404)
        row = self.data["runs"][run_id]
        manifest = self.manifest(row["workflow_id"], row["version"])
        policy = next((item for item in manifest.workbook_policies if item.workbook == workbook), None)
        if policy is None:
            raise WorkflowError("工作簿没有刷新策略", "refresh_policy_not_found", 404)
        source = self.resource_path(row["workflow_id"], row["version"], workbook)
        run_root = self.root / "runs" / run_id
        return (refresh_service or WorkbookRefreshService()).refresh(source, run_root, policy)
