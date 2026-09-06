"""Product facade for report Workflow packages, runs, schedules, and migration."""

from __future__ import annotations

import builtins
import json
import os
import tempfile
import time
from contextlib import suppress
from pathlib import Path

import yaml
from pydantic import ValidationError

from core.observability import get_logger

from .catalog import ReportWorkflowService
from .migration import ReportWorkflowMigration
from .models import ReportWorkflowManifest, WorkflowError
from .runtime import ReportWorkflowRuntime, _public_metadata
from .workbook import WorkbookRefreshService

log = get_logger(__name__)
_SAFE_READINESS_CODES = {"unsupported_platform", "xlwings_missing"}


class ReportWorkflowManager:
    """Expose stable product operations without weakening the package boundary."""

    def __init__(self, service) -> None:
        self.service = service
        self.catalog = ReportWorkflowService(service.store.root)
        self.refresh = WorkbookRefreshService()
        self.runtime = ReportWorkflowRuntime(service, self.catalog, self.refresh)
        self.migration = ReportWorkflowMigration(self.catalog)
        self._probes: dict[str, dict] = {}

    async def start(self) -> None:
        await self.runtime.start()

    async def close(self) -> None:
        await self.runtime.close()

    def _row(self, workflow_id: str) -> dict:
        return self.catalog._row(workflow_id)

    @staticmethod
    def _public_artifact(item: dict) -> dict:
        return _public_metadata(item)

    def summary(self, workflow_id: str) -> dict:
        row = self._row(workflow_id)
        draft = row["draft_manifest"]
        return {
            "id": workflow_id,
            "name": draft["name"],
            "description": draft.get("description", ""),
            "status": row.get("status", "draft"),
            "current_version": row.get("current_version"),
            "version_count": len(row.get("versions", {})),
            "delivery_formats": draft.get("delivery", {}).get("formats", []),
            "providers": [item["provider"] for item in draft.get("providers", [])],
            "next_run_at": row.get("schedule", {}).get("next_run_at"),
            "latest_run": row.get("latest_run"),
            "updated_at": row.get("updated_at"),
        }

    def list(self) -> list[dict]:
        with self.catalog._exclusive():
            items = [self.summary(workflow_id) for workflow_id in self.catalog.data["workflows"]]
        return sorted(items, key=lambda item: (item["name"], item["id"]))

    def detail(self, workflow_id: str) -> dict:
        row = self._row(workflow_id)
        return {
            **self.summary(workflow_id),
            "draft": row["draft_manifest"],
            "versions": self.versions(workflow_id),
            "schedule": self.runtime.schedule(workflow_id),
            "migration": row.get("migration"),
            "migration_conflict": row.get("migration_conflict"),
            "historical_artifacts": [
                self._public_artifact(item) for item in row.get("historical_artifacts", [])
            ],
        }

    def create_draft(self, body: dict) -> dict:
        with self.catalog._exclusive():
            manifest = self.catalog.create_draft(body)
            row = self._row(manifest.workflow_id)
            row.update(status="draft", created_at=time.time(), updated_at=time.time())
            self.catalog._save()
        return self.detail(manifest.workflow_id)

    @staticmethod
    def _atomic_yaml(path: Path, value: dict) -> None:
        fd, temporary = tempfile.mkstemp(prefix="draft-", dir=path.parent)
        try:
            try:
                with os.fdopen(fd, "w") as stream:
                    yaml.safe_dump(value, stream, allow_unicode=True, sort_keys=False)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
            except (OSError, yaml.YAMLError) as exc:
                raise WorkflowError("Workflow 草稿无法保存", "workflow_unavailable", 503) from exc
        finally:
            if os.path.exists(temporary):
                with suppress(OSError):
                    os.unlink(temporary)

    def update_draft(
        self,
        workflow_id: str,
        *,
        manifest: dict | None = None,
        workflow: dict | None = None,
        validation: dict | None = None,
    ) -> dict:
        with self.catalog._exclusive():
            self.runtime.assert_not_active(workflow_id)
            row = self._row(workflow_id)
            draft = self.catalog._draft(workflow_id)
            if manifest is not None:
                try:
                    value = ReportWorkflowManifest.model_validate(manifest)
                except ValidationError as exc:
                    raise WorkflowError(
                        "Workflow manifest 不符合契约", "invalid_manifest", 422
                    ) from exc
                if value.workflow_id != workflow_id:
                    raise WorkflowError("Workflow 草稿归属不一致", "invalid_manifest", 422)
                row["draft_manifest"] = json.loads(
                    value.model_copy(update={"resources": []}).model_dump_json()
                )
            if workflow is not None:
                if not isinstance(workflow.get("steps", []), list):
                    raise WorkflowError("Workflow 步骤必须是列表", "invalid_workflow", 422)
                self._atomic_yaml(draft / "workflow.yaml", workflow)
            if validation is not None:
                self._atomic_yaml(draft / "validation.yaml", validation)
            row["updated_at"] = time.time()
            self.catalog._save()
        return self.detail(workflow_id)

    def copy(self, workflow_id: str, new_id: str, name: str, version: int | None = None) -> dict:
        with self.catalog._exclusive():
            source = self._row(workflow_id)
            selected = version or source.get("current_version")
            if selected is None:
                raise WorkflowError("Workflow 尚无可复制版本", "version_required", 409)
            manifest = self.catalog.manifest(workflow_id, selected)
            copied = json.loads(manifest.model_dump_json())
            copied.update(workflow_id=new_id, name=name, version=1, resources=[])
            self.catalog.create_draft(copied)
            source_root = self.catalog._version_path(workflow_id, selected)
            draft = self.catalog._draft(new_id)
            for filename in ("workflow.yaml", "validation.yaml"):
                self._atomic_yaml(
                    draft / filename,
                    yaml.safe_load((source_root / filename).read_text()),
                )
            for resource in manifest.resources:
                if resource.path in {"workflow.yaml", "validation.yaml"}:
                    continue
                self.catalog.upload_resource(
                    new_id,
                    resource.path,
                    self.catalog.resource_path(workflow_id, selected, resource.path).read_bytes(),
                )
            row = self._row(new_id)
            row.update(status="draft", created_at=time.time(), updated_at=time.time())
            self.catalog._save()
        return self.detail(new_id)

    def versions(self, workflow_id: str) -> builtins.list[dict]:
        row = self._row(workflow_id)
        items = []
        for value in sorted(row.get("versions", {}), key=int):
            version = int(value)
            manifest = self.catalog.manifest(workflow_id, version)
            items.append(
                {
                    "version": version,
                    "published": bool(row["versions"][value].get("published")),
                    "current": row.get("current_version") == version,
                    "manifest": json.loads(manifest.model_dump_json()),
                }
            )
        return items

    def create_version(self, workflow_id: str) -> dict:
        with self.catalog._exclusive():
            self.runtime.assert_not_active(workflow_id)
            manifest = self.catalog.create_version(workflow_id)
            row = self._row(workflow_id)
            row["updated_at"] = time.time()
            self.catalog._save()
        return json.loads(manifest.model_dump_json())

    def publish(self, workflow_id: str, version: int) -> dict:
        with self.catalog._exclusive():
            self.runtime.assert_not_active(workflow_id)
            self.catalog.publish_version(workflow_id, version)
            row = self._row(workflow_id)
            row.update(status="enabled", updated_at=time.time())
            self.catalog._save()
        return self.detail(workflow_id)

    def rollback(self, workflow_id: str, version: int) -> dict:
        with self.catalog._exclusive():
            self.runtime.assert_not_active(workflow_id)
            self.catalog.rollback_version(workflow_id, version)
            row = self._row(workflow_id)
            row.update(status="enabled", updated_at=time.time())
            self.catalog._save()
        return self.detail(workflow_id)

    def disable(self, workflow_id: str) -> dict:
        with self.catalog._exclusive():
            self.runtime.assert_not_active(workflow_id)
            row = self._row(workflow_id)
            row.update(status="disabled", updated_at=time.time())
            self.catalog._save()
        return self.detail(workflow_id)

    def resource(self, workflow_id: str, version: int, path: str) -> Path:
        return self.catalog.resource_path(workflow_id, version, path)

    def upload_resource(self, workflow_id: str, path: str, raw: bytes) -> dict:
        with self.catalog._exclusive():
            self.runtime.assert_not_active(workflow_id)
            resource = self.catalog.upload_resource(workflow_id, path, raw)
            row = self._row(workflow_id)
            row["updated_at"] = time.time()
            self.catalog._save()
        return resource.model_dump(mode="json")

    def provider_status(self) -> builtins.list[dict]:
        items = []
        for provider_id, provider in sorted(self.refresh.providers.items()):
            if provider_id == "datahub":
                continue
            readiness = self._dependency_readiness(provider_id, provider)
            dependency_ready = readiness["ready"]
            items.append(
                {
                    "id": provider_id,
                    "ready": False,
                    "integration_state": "ready" if dependency_ready else "blocked_dependency",
                    "health": "untested",
                    "code": "needs_probe" if dependency_ready else readiness["code"],
                }
            )
        return items

    @staticmethod
    def _dependency_readiness(provider_id: str, provider) -> dict:
        try:
            readiness = provider.readiness()
        except Exception as exc:  # noqa: BLE001 - provider errors must stay content-free.
            log.warning(
                "report_provider_dependency_check_failed",
                provider=provider_id,
                error_type=type(exc).__name__,
            )
            return {"ready": False, "code": "provider_dependency_check_failed"}
        ready = bool(readiness.get("ready"))
        if ready:
            return {"ready": True, "code": None}
        code = str(readiness.get("code") or "provider_dependency_unavailable")
        if code not in _SAFE_READINESS_CODES:
            code = "provider_dependency_unavailable"
        return {"ready": False, "code": code}

    def probe(self, provider_id: str, key: str) -> dict:
        name = f"{provider_id}:{key}"
        if name in self._probes:
            return self._probes[name]
        provider = self.refresh.providers.get(provider_id)
        if provider is None or provider_id == "datahub":
            raise WorkflowError("Excel Provider 不存在", "provider_not_found", 404)
        readiness = self._dependency_readiness(provider_id, provider)
        dependency_ready = readiness["ready"]
        result = {
            "id": name,
            "provider": provider_id,
            "ready": False,
            "integration_state": "ready" if dependency_ready else "blocked_dependency",
            "health": "unverified" if dependency_ready else "unavailable",
            "code": "provider_health_unverified" if dependency_ready else readiness["code"],
            "checked_at": time.time(),
        }
        self._probes[name] = result
        return result

    def migrate_legacy(self, *, dry_run: bool = True) -> dict:
        """Import only from the configured project asset root.

        The HTTP API intentionally does not accept a filesystem path. This keeps
        a local migration action from becoming an arbitrary host-file reader.
        """

        configured = os.environ.get("RESEARCH_REPORT_MIGRATION_SOURCE")
        if configured:
            source = Path(configured)
        else:
            project_root = Path(
                os.environ.get("RESEARCH_PROJECT_ROOT", str(Path(__file__).resolve().parents[3]))
            )
            source = project_root / "report_projects"
        return self.migration.migrate(source, dry_run=dry_run)
