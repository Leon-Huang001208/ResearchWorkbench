"""Atomic single-process product ownership index. DSH owns all transcripts."""

import hashlib
import json
import mimetypes
import os
import re
import stat
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from core.observability import get_logger

log = get_logger(__name__)
PUBLIC_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".md",
    ".txt",
    ".csv",
    ".xlsx",
    ".docx",
    ".html",
    ".svg",
    ".json",
}


class StoreError(Exception):
    pass


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.index = self.root / "index.json"
        try:
            self.data = (
                json.loads(self.index.read_text())
                if self.index.exists()
                else {"sessions": {}, "receipts": {}}
            )
        except (OSError, ValueError) as exc:
            log.error("research_index_unreadable", error_type=type(exc).__name__)
            raise StoreError("会话索引不可读取；未覆盖原索引") from exc

    def save(self):
        fd, name = tempfile.mkstemp(prefix="index-", dir=self.root)
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(self.data, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.index)
        except OSError as exc:
            log.error("research_index_write_failed", error_type=type(exc).__name__)
            raise StoreError("会话索引保存失败") from exc
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def create(self, mode: str, title: str) -> dict:
        sid = str(uuid4())
        row: dict = {
            "id": sid,
            "mode": mode,
            "title": title,
            "workspace_id": "research",
            "status": "idle",
            "model": None,
            "updated_at": time.time(),
            "files": {},
            "created": False,
        }
        self.data["sessions"][sid] = row
        for folder in ("inputs", "outputs"):
            (self.directory(sid) / folder).mkdir(parents=True, mode=0o700)
        self.save()
        log.info("research_session_registered", session_id=sid, mode=mode)
        return row

    def session(self, sid: str) -> dict:
        if not re.fullmatch(r"[a-f0-9-]{36}", sid) or sid not in self.data["sessions"]:
            raise StoreError("研究会话不存在或不属于当前产品")
        return self.data["sessions"][sid]

    def directory(self, sid: str) -> Path:
        self.session(sid)
        path = self.root / "sessions" / sid
        if path.is_symlink() or not path.resolve().is_relative_to(self.root):
            raise StoreError("非法会话目录")
        return path

    def reserve(self, sid: str, key: str, digest: str, delivery: dict | None = None) -> bool:
        self.session(sid)
        name = f"{sid}:{key}"
        if name in self.data["receipts"]:
            if self.data["receipts"][name]["digest"] != digest:
                raise StoreError("幂等键不能用于不同问题")
            return False
        self.data["receipts"][name] = {"digest": digest, "status": "pending"}
        if delivery is not None:
            self.data["receipts"][name]["delivery"] = delivery
            self.session(sid)["delivery_key"] = key
        self.save()
        return True

    def receipt(self, sid, key, status=None):
        receipt = self.data["receipts"][f"{sid}:{key}"]
        if status:
            receipt["status"] = status
            self.save()
        return receipt

    def files(self, sid: str) -> list[dict]:
        row, root = self.session(sid), self.directory(sid)
        items = []
        changed = False
        for folder in ("inputs", "outputs"):
            base = root / folder
            if base.is_symlink():
                raise StoreError("文件目录不能为符号链接")
            for path in base.rglob("*"):
                relative = path.relative_to(root)
                if (
                    relative.parts[:2] == ("inputs", "datasets")
                    or not path.is_file()
                    or (
                        path.suffix.lower() not in PUBLIC_EXTENSIONS
                        and not (
                            path.suffix.lower() == ".zip"
                            and folder == "outputs"
                            and row.get("purpose") == "capability_creation"
                        )
                    )
                    or any(part.startswith(".") for part in relative.parts)
                    or any(p.is_symlink() for p in (path, *path.parents) if p != self.root)
                    or not path.resolve().is_relative_to(base.resolve())
                ):
                    continue
                fid = hashlib.sha256(str(relative).encode()).hexdigest()[:24]
                if row["files"].get(fid) != str(relative):
                    row["files"][fid] = str(relative)
                    changed = True
                url = f"/api/research/sessions/{sid}/files/{fid}"
                items.append(
                    {
                        "id": fid,
                        "name": path.name,
                        "size": path.stat().st_size,
                        "mime": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                        "url": url + "/download",
                        "preview_url": url + "/preview",
                        "kind": folder,
                    }
                )
        if changed:
            self.save()
        return items

    def file_path(self, sid: str, fid: str) -> Path:
        row = self.session(sid)
        if fid not in row["files"] or not re.fullmatch(r"[a-f0-9]{24}", fid):
            raise StoreError("文件不存在")
        root = self.directory(sid)
        path = root / row["files"][fid]
        if (
            not path.is_file()
            or any(p.is_symlink() for p in (path, *path.parents) if p != self.root)
            or not path.resolve().is_relative_to(root.resolve())
        ):
            raise StoreError("文件访问被拒绝")
        return path

    def open_file(self, sid: str, fid: str):
        """Open beneath directory descriptors so a concurrent symlink swap cannot escape."""
        row = self.session(sid)
        if not re.fullmatch(r"[a-f0-9]{24}", fid) or fid not in row["files"]:
            raise StoreError("文件不存在")
        relative = Path(row["files"][fid])
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.parts[0] not in {"inputs", "outputs"}
        ):
            raise StoreError("文件访问被拒绝")
        descriptor = None
        try:
            descriptor = os.open(self.directory(sid), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            for component in relative.parts[:-1]:
                child = os.open(
                    component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor
                )
                os.close(descriptor)
                descriptor = child
            fd = os.open(
                relative.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor
            )
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                os.close(fd)
                raise StoreError("仅允许下载独立普通文件")
            return os.fdopen(fd, "rb"), relative.name
        except OSError as exc:
            log.warning("research_download_denied", session_id=sid, error_type=type(exc).__name__)
            raise StoreError("文件访问被拒绝") from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)
