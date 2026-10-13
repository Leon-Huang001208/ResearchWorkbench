"""Local project metadata and explicit, provenance-bound Claw file references."""

import copy
import hashlib
import os
import time
from pathlib import Path
from uuid import uuid4

from core.observability import get_logger

from .store import StoreError

log = get_logger(__name__)
REFERENCE_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".md",
    ".csv",
    ".xlsx",
    ".docx",
    ".pptx",
}
MAX_REFERENCE_BYTES = 30 * 1024 * 1024


class ClawProjects:
    def __init__(self, research):
        self.research = research
        self.store = research.store

    def _projects(self):
        return self.store.data.get("claw_projects", {})

    def get(self, project_id):
        if project_id == "default":
            return {"id": "default", "name": "我的研究", "archived": False}
        if project_id not in self._projects():
            raise StoreError("研究项目不存在", "project_not_found", 404)
        return dict(self._projects()[project_id])

    def members(self, project_id):
        self.get(project_id)
        return [
            row
            for row in self.store.data["sessions"].values()
            if row.get("mode") == "claw"
            and row.get("deleted_at") is None
            and row.get("project_id", "default") == project_id
        ]

    def list(self):
        items = [self.get("default"), *[dict(row) for row in self._projects().values()]]
        for item in items:
            item["session_count"] = len(self.members(item["id"]))
        return {"items": items}

    def _save_projects(self, rows):
        previous = self.store.data.get("claw_projects")
        self.store.data["claw_projects"] = rows
        try:
            self.store.save()
        except StoreError:
            if previous is None:
                self.store.data.pop("claw_projects", None)
            else:
                self.store.data["claw_projects"] = previous
            log.error("claw_project_save_failed")
            raise

    @staticmethod
    def _name(name):
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
            raise StoreError("项目名称应为 1 至 120 个字符")
        return name.strip()

    def create(self, name):
        row = {
            "id": f"project-{uuid4().hex}",
            "name": self._name(name),
            "archived": False,
            "created_at": time.time(),
        }
        rows = copy.deepcopy(self._projects())
        rows[row["id"]] = row
        self._save_projects(rows)
        log.info("claw_project_created", project_id=row["id"])
        return dict(row)

    def update(self, project_id, *, name=None, archived=None):
        row = self.get(project_id)
        if project_id == "default":
            raise StoreError("默认研究项目不能改名或归档", "default_project_locked", 409)
        if name is not None:
            row["name"] = self._name(name)
        if archived is not None:
            row["archived"] = archived
        rows = copy.deepcopy(self._projects())
        rows[project_id] = row
        self._save_projects(rows)
        log.info("claw_project_updated", project_id=project_id, archived=row["archived"])
        return row

    def move(self, sid, project_id):
        project = self.get(project_id)
        row = self.store.session(sid)
        if project["archived"]:
            raise StoreError("归档项目不能接收新会话", "project_archived", 409)
        if row["mode"] != "claw":
            raise StoreError("只有 Claw 会话可以移入研究项目")
        previous = row.get("project_id")
        row["project_id"] = project_id
        try:
            self.store.save()
        except StoreError:
            if previous is None:
                row.pop("project_id", None)
            else:
                row["project_id"] = previous
            log.error("claw_project_move_failed", session_id=sid)
            raise
        log.info("claw_session_moved", session_id=sid, project_id=project_id)
        return {"id": sid, "project_id": project_id}

    def detail(self, project_id):
        project = self.get(project_id)
        members = self.members(project_id)
        files, datasets = [], []
        for row in members:
            origin = {"session_id": row["id"], "session_title": row["title"]}
            for item in self.store.files(row["id"]):
                stream, _ = self.store.open_file(row["id"], item["id"])
                with stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                files.append({**item, **origin, "sha256": digest})
            datasets.extend(
                {**item, **origin} for item in self.research.datahub.summaries(row["id"])
            )
        return {
            **project,
            "sessions": [
                {
                    "id": row["id"],
                    "title": row["title"],
                    "mode": "claw",
                    "status": row["status"],
                    "project_id": project_id,
                }
                for row in members
            ],
            "files": files,
            "datasets": datasets,
        }

    def reference(self, target_sid, source_sid, file_id, expected_sha256):
        target, source = self.store.session(target_sid), self.store.session(source_sid)
        project_id = target.get("project_id", "default")
        if (
            source["mode"] != "claw"
            or target["mode"] != "claw"
            or source.get("project_id", "default") != project_id
        ):
            raise StoreError(
                "只能显式引用当前项目内的 Claw 文件", "reference_project_mismatch", 409
            )
        if self.get(project_id)["archived"]:
            raise StoreError("归档项目只允许查看", "project_archived", 409)
        if os.name == "nt":
            raise StoreError("当前平台尚未验证安全文件引用", "reference_platform_unverified", 409)
        stream, source_name = self.store.open_file(source_sid, file_id)
        suffix = Path(source_name).suffix.lower()
        if suffix not in REFERENCE_EXTENSIONS:
            stream.close()
            raise StoreError("此格式不能作为研究附件引用")
        destination_name = f"reference-{uuid4().hex}{suffix}"
        # Anchor all destination operations to owned directory FDs; no model paths.
        descriptors = []
        destination_fd = None
        created = False
        try:
            descriptors.append(
                os.open(self.store.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            )
            for component in ("sessions", target_sid, "inputs"):
                descriptors.append(
                    os.open(
                        component,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=descriptors[-1],
                    )
                )
            destination_fd = os.open(
                destination_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=descriptors[-1],
            )
            created = True
            digest, size = hashlib.sha256(), 0
            with stream, os.fdopen(destination_fd, "wb") as output:
                destination_fd = None
                while block := stream.read(65536):
                    size += len(block)
                    if size > MAX_REFERENCE_BYTES:
                        raise StoreError("单文件超过 30 MB")
                    digest.update(block)
                    output.write(block)
                output.flush()
                os.fsync(output.fileno())
            if digest.hexdigest() != expected_sha256:
                raise StoreError("来源文件已变化，请刷新项目后重新选择", "reference_changed", 409)
            # Ensure the FD still names this session's owned directory.
            current = os.stat(self.store.directory(target_sid) / "inputs", follow_symlinks=False)
            opened = os.fstat(descriptors[-1])
            if (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino):
                raise StoreError("当前会话文件目录已变化")
            reference = next(
                item for item in self.store.files(target_sid) if item["name"] == destination_name
            )
            reference.update(
                source_session_id=source_sid,
                source_file_id=file_id,
                sha256=digest.hexdigest(),
                source_name=source_name,
            )
            old = copy.deepcopy(target.get("file_references", {}))
            target.setdefault("file_references", {})[reference["id"]] = reference
            try:
                self.store.save()
            except StoreError:
                target["file_references"] = old
                raise
            log.info("claw_reference_created", session_id=target_sid, project_id=project_id)
            return reference
        except (OSError, StoreError, StopIteration) as exc:
            if created:
                os.unlink(destination_name, dir_fd=descriptors[-1])
            log.warning(
                "claw_reference_failed", session_id=target_sid, error_type=type(exc).__name__
            )
            if isinstance(exc, StoreError):
                raise
            raise StoreError("文件引用失败，请刷新后重试", "reference_failed", 409) from exc
        finally:
            stream.close()
            if destination_fd is not None:
                os.close(destination_fd)
            for descriptor in reversed(descriptors):
                os.close(descriptor)
