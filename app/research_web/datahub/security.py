"""Private control and descriptor-relative IO; never reuse model credentials."""

import json
import os
import re
import secrets
import stat
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from core.observability import get_logger

from ..store import StoreError

log = get_logger(__name__)


@contextmanager
def directory(root: Path, parts=(), *, create=False, private=False):
    """All descendants opened with NOFOLLOW; trusted root is canonical."""
    fd = None
    try:
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        for component in parts:
            if not component or component in {".", ".."} or "/" in component:
                raise StoreError("资料目录非法")
            if create:
                try:
                    os.mkdir(component, mode=0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
            info = os.fstat(fd)
            if private and (info.st_mode & 0o077 or info.st_uid != os.getuid()):
                raise StoreError("私有资料目录权限异常")
        yield fd
    except OSError as exc:
        log.warning("datahub_directory_denied", error_type=type(exc).__name__)
        raise StoreError("资料目录访问被拒绝") from exc
    finally:
        if fd is not None:
            os.close(fd)


def read_file(fd, name, *, private=False, limit=17 * 1024 * 1024):
    handle = None
    try:
        handle = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        info = os.fstat(handle)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
            raise StoreError("资料文件类型、链接或大小非法")
        if private and (info.st_mode & 0o077 or info.st_uid != os.getuid()):
            raise StoreError("私有控制文件权限异常")
        with os.fdopen(handle, "rb") as stream:
            handle = None
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise StoreError("资料文件超过读取上限")
        return data
    except OSError as exc:
        log.warning("datahub_file_denied", error_type=type(exc).__name__)
        raise StoreError("资料文件访问被拒绝") from exc
    finally:
        if handle is not None:
            os.close(handle)


def write_new(fd, name, content):
    try:
        handle = os.open(
            name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd
        )
        with os.fdopen(handle, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        log.error("datahub_file_write_failed", error_type=type(exc).__name__)
        raise StoreError("资料文件保存失败") from exc


def atomic_json(fd, name, value):
    temporary = f".pending-{uuid4().hex}"
    try:
        write_new(fd, temporary, json_bytes(value))
        os.replace(temporary, name, src_dir_fd=fd, dst_dir_fd=fd)
        os.fsync(fd)
    except OSError as exc:
        raise StoreError("资料记录保存失败") from exc
    finally:
        try:
            os.unlink(temporary, dir_fd=fd)
        except FileNotFoundError:
            pass


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2).encode()


def checked_url(value):
    if not isinstance(value, str):
        raise StoreError("DataHub 地址必须为字符串")
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"127.0.0.1", "::1"}
            or parsed.username is not None
            or parsed.password is not None
            or "?" in value
            or "#" in value
            or parsed.path not in {"", "/"}
            or not parsed.port
        ):
            raise ValueError("not a loopback origin")
    except (TypeError, ValueError) as exc:
        raise StoreError("DataHub 只接受可信回环服务地址") from exc
    return value.rstrip("/")


def load_control(root: Path, url: str | None = None):
    """Startup/service-owned fixed file. Existing abnormal permissions fail closed."""
    if url is not None:
        url = checked_url(url)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    with directory(root, (".control",), create=True, private=True) as fd:
        if "datahub.json" not in os.listdir(fd):
            config = {"token": secrets.token_urlsafe(32), "url": url or "http://127.0.0.1:8088"}
            try:
                write_new(fd, "datahub.json", json_bytes(config))
            except StoreError:
                # Another trusted startup may have won O_EXCL; read and validate it.
                if "datahub.json" not in os.listdir(fd):
                    raise
        try:
            config = json.loads(read_file(fd, "datahub.json", private=True, limit=4096))
            if (
                not isinstance(config, dict)
                or not isinstance(config.get("token"), str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", config["token"])
            ):
                raise ValueError("invalid token")
            checked_url(config["url"])
            if url is not None and config["url"] != url:
                raise StoreError("DataHub 回环地址与已有可信配置不符；未覆盖")
            return config
        except (ValueError, KeyError, TypeError) as exc:
            raise StoreError("DataHub 私有配置无效") from exc
