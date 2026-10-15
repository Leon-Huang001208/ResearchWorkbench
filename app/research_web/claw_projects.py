"""Mode-scoped local projects and explicit, provenance-bound file references."""

import copy
import hashlib
import mimetypes
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
    def __init__(self, research, mode="claw"):
        if mode not in {"claw", "fingpt"}:
            raise StoreError("不支持的研究模式", "invalid_mode", 422)
        self.research = research
        self.store = research.store
        self.mode = mode
        self.key = f"{mode}_projects"

    def _projects(self):
        return self.store.data.get(self.key, {})

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
            if row.get("mode") == self.mode
            and row.get("deleted_at") is None
            and row.get("project_id", "default") == project_id
        ]

    def list(self):
        items = [self.get("default"), *[dict(row) for row in self._projects().values()]]
        for item in items:
            item["session_count"] = len(self.members(item["id"]))
        return {"items": items}

    def _save_projects(self, rows):
        previous = self.store.data.get(self.key)
        self.store.data[self.key] = rows
        try:
            self.store.save()
        except (OSError, StoreError) as exc:
            if previous is None:
                self.store.data.pop(self.key, None)
            else:
                self.store.data[self.key] = previous
            log.error("claw_project_save_failed", mode=self.mode)
            if isinstance(exc, StoreError):
                raise
            raise StoreError("项目保存失败", "project_save_failed", 500) from exc

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
        log.info("claw_project_created", project_id=row["id"], mode=self.mode)
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
        log.info(
            "claw_project_updated", project_id=project_id, archived=row["archived"], mode=self.mode
        )
        return row

    def move(self, sid, project_id):
        project = self.get(project_id)
        row = self.store.session(sid)
        if project["archived"]:
            raise StoreError("归档项目不能接收新会话", "project_archived", 409)
        if row["mode"] != self.mode:
            raise StoreError("只能移入相同研究模式的项目", "project_mode_mismatch", 409)
        previous = row.get("project_id")
        row["project_id"] = project_id
        try:
            self.store.save()
        except (OSError, StoreError) as exc:
            if previous is None:
                row.pop("project_id", None)
            else:
                row["project_id"] = previous
            log.error("claw_project_move_failed", session_id=sid, mode=self.mode)
            if isinstance(exc, StoreError):
                raise
            raise StoreError("会话移组保存失败", "project_move_failed", 500) from exc
        log.info("claw_session_moved", session_id=sid, project_id=project_id, mode=self.mode)
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
                    "mode": self.mode,
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
            source["mode"] != self.mode
            or target["mode"] != self.mode
            or source.get("project_id", "default") != project_id
        ):
            raise StoreError(
                "只能显式引用当前模式、当前项目内的文件", "reference_project_mismatch", 409
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
            # Publish the new file index and provenance in one save. Store.files()
            # discovers files by saving, so cannot be called inside this transaction.
            # Keep its existing relative-path SHA-256 ID and public URL contract.
            relative = f"inputs/{destination_name}"
            reference_id = hashlib.sha256(relative.encode()).hexdigest()[:24]
            url = f"/api/research/sessions/{target_sid}/files/{reference_id}"
            reference = {
                "id": reference_id,
                "name": destination_name,
                "size": size,
                "mime": mimetypes.guess_type(destination_name)[0] or "application/octet-stream",
                "url": url + "/download",
                "preview_url": url + "/preview",
                "kind": "inputs",
                "source_session_id": source_sid,
                "source_file_id": file_id,
                "sha256": digest.hexdigest(),
                "source_name": source_name,
            }
            old_references = target.get("file_references")
            old_files = target["files"]
            target["file_references"] = {
                **(old_references or {}),
                reference_id: reference,
            }
            target["files"] = {**old_files, reference_id: relative}
            try:
                self.store.save()
            except (OSError, StoreError):
                target["files"] = old_files
                if old_references is None:
                    target.pop("file_references", None)
                else:
                    target["file_references"] = old_references
                raise
            log.info(
                "claw_reference_created",
                session_id=target_sid,
                project_id=project_id,
                mode=self.mode,
            )
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
