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


def _is_reparse_point(path: Path) -> bool:
    """Reject links and Windows reparse points before path-based fallback IO."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return path.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & reparse_flag)


def _safe_component(component: str) -> bool:
    return (
        bool(component)
        and component not in {".", ".."}
        and not any(separator in component for separator in ("/", "\\"))
    )


@contextmanager
def _windows_directory(root: Path, parts=(), *, create=False, private=False):
    """Path-based Windows fallback guarded by canonical and reparse-point checks."""
    del private  # Windows ACLs are not represented by portable POSIX mode bits.
    try:
        if _is_reparse_point(root) or not root.is_dir():
            raise StoreError("资料目录访问被拒绝")
        trusted_root = root.resolve(strict=True)
        folder = root
        for component in parts:
            if not _safe_component(component):
                raise StoreError("资料目录非法")
            folder = folder / component
            if create:
                folder.mkdir(mode=0o700, exist_ok=True)
            if (
                _is_reparse_point(folder)
                or not folder.is_dir()
                or not folder.resolve(strict=True).is_relative_to(trusted_root)
            ):
                raise StoreError("私有资料目录权限异常")
        yield folder
    except StoreError:
        raise
    except OSError as exc:
        log.warning("datahub_windows_directory_denied", error_type=type(exc).__name__)
        raise StoreError("资料目录访问被拒绝") from exc


def _windows_read_file(folder: Path, name: str, *, limit: int) -> bytes:
    if not _safe_component(name):
        raise StoreError("资料文件访问被拒绝")
    path = folder / name
    try:
        before = path.lstat()
        if (
            _is_reparse_point(path)
            or not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size > limit
        ):
            raise StoreError("资料文件类型、链接或大小非法")
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise StoreError("资料文件类型、链接或大小非法")
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise StoreError("资料文件超过读取上限")
        return data
    except StoreError:
        raise
    except OSError as exc:
        log.warning("datahub_windows_file_denied", error_type=type(exc).__name__)
        raise StoreError("资料文件访问被拒绝") from exc


def _windows_write_new(folder: Path, name: str, content: bytes) -> None:
    if not _safe_component(name):
        raise StoreError("资料文件保存失败")
    path = folder / name
    handle = None
    try:
        if _is_reparse_point(path):
            raise StoreError("资料文件保存失败")
        handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(handle, "wb") as stream:
            handle = None
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise StoreError("资料文件保存失败")
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
    except StoreError:
        raise
    except OSError as exc:
        log.error("datahub_windows_file_write_failed", error_type=type(exc).__name__)
        raise StoreError("资料文件保存失败") from exc
    finally:
        if handle is not None:
            os.close(handle)


def _windows_atomic_json(folder: Path, name: str, value) -> None:
    if not _safe_component(name):
        raise StoreError("资料记录保存失败")
    temporary = f".pending-{uuid4().hex}"
    temp_path = folder / temporary
    try:
        destination = folder / name
        if destination.exists() or _is_reparse_point(destination):
            before = destination.lstat()
            if (
                _is_reparse_point(destination)
                or not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
            ):
                raise StoreError("资料记录保存失败")
        _windows_write_new(folder, temporary, json_bytes(value))
        os.replace(temp_path, destination)
    except StoreError:
        raise
    except OSError as exc:
        log.error("datahub_windows_record_write_failed", error_type=type(exc).__name__)
        raise StoreError("资料记录保存失败") from exc
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            log.warning("datahub_windows_temporary_cleanup_failed", error_type=type(exc).__name__)


def _parse_control(raw: bytes, url: str | None) -> dict:
    try:
        config = json.loads(raw)
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


def _windows_control(root: Path, url: str | None) -> dict:
    """Windows fallback for startup control IO without unsupported dir_fd flags."""
    try:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if _is_reparse_point(root) or not root.is_dir():
            raise StoreError("资料目录访问被拒绝")
        trusted_root = root.resolve(strict=True)
        folder = root / ".control"
        folder.mkdir(mode=0o700, exist_ok=True)
        if (
            _is_reparse_point(folder)
            or not folder.is_dir()
            or not folder.resolve(strict=True).is_relative_to(trusted_root)
        ):
            raise StoreError("私有资料目录权限异常")

        path = folder / "datahub.json"
        if _is_reparse_point(path):
            raise StoreError("私有控制文件权限异常")
        if not path.exists():
            config = {
                "token": secrets.token_urlsafe(32),
                "url": url or "http://127.0.0.1:8088",
            }
            try:
                handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(handle, "wb") as stream:
                    stream.write(json_bytes(config))
                    stream.flush()
                    os.fsync(stream.fileno())
            except FileExistsError:
                pass

        before = path.lstat()
        if (
            _is_reparse_point(path)
            or not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size > 4096
        ):
            raise StoreError("私有控制文件权限异常")
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise StoreError("私有控制文件权限异常")
            raw = stream.read(4097)
        if len(raw) > 4096:
            raise StoreError("资料文件超过读取上限")
        return _parse_control(raw, url)
    except StoreError:
        raise
    except OSError as exc:
        log.warning("datahub_windows_control_denied", error_type=type(exc).__name__)
        raise StoreError("资料目录访问被拒绝") from exc


@contextmanager
def directory(root: Path, parts=(), *, create=False, private=False):
    """All descendants opened with NOFOLLOW; trusted root is canonical."""
    if os.name == "nt":
        with _windows_directory(root, parts, create=create, private=private) as folder:
            yield folder
        return
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
    if isinstance(fd, Path):
        return _windows_read_file(fd, name, limit=limit)
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
    if isinstance(fd, Path):
        _windows_write_new(fd, name, content)
        return
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
    if isinstance(fd, Path):
        _windows_atomic_json(fd, name, value)
        return
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


def make_directory(fd, name: str) -> None:
    if not _safe_component(name):
        raise StoreError("资料目录非法")
    try:
        if isinstance(fd, Path):
            path = fd / name
            if _is_reparse_point(path):
                raise StoreError("资料目录访问被拒绝")
            path.mkdir(mode=0o700)
            return
        os.mkdir(name, mode=0o700, dir_fd=fd)
    except StoreError:
        raise
    except OSError as exc:
        log.warning("datahub_directory_create_failed", error_type=type(exc).__name__)
        raise StoreError("资料目录创建失败") from exc


def rename_directory(fd, source: str, destination: str) -> None:
    if not _safe_component(source) or not _safe_component(destination):
        raise StoreError("资料目录非法")
    try:
        if isinstance(fd, Path):
            source_path = fd / source
            destination_path = fd / destination
            if (
                _is_reparse_point(source_path)
                or not source_path.is_dir()
                or destination_path.exists()
                or _is_reparse_point(destination_path)
            ):
                raise StoreError("资料目录发布失败")
            os.rename(source_path, destination_path)
            return
        os.rename(source, destination, src_dir_fd=fd, dst_dir_fd=fd)
    except StoreError:
        raise
    except OSError as exc:
        log.warning("datahub_directory_rename_failed", error_type=type(exc).__name__)
        raise StoreError("资料目录发布失败") from exc


def unlink_file(fd, name: str) -> None:
    if not _safe_component(name):
        raise StoreError("资料文件访问被拒绝")
    try:
        if isinstance(fd, Path):
            path = fd / name
            before = path.lstat()
            if _is_reparse_point(path) or not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                raise StoreError("资料文件访问被拒绝")
            path.unlink()
            return
        os.unlink(name, dir_fd=fd)
    except StoreError:
        raise
    except OSError as exc:
        log.warning("datahub_file_remove_failed", error_type=type(exc).__name__)
        raise StoreError("资料文件删除失败") from exc


def remove_directory(fd, name: str) -> None:
    if not _safe_component(name):
        raise StoreError("资料目录非法")
    try:
        if isinstance(fd, Path):
            path = fd / name
            if _is_reparse_point(path) or not path.is_dir():
                raise StoreError("资料目录访问被拒绝")
            path.rmdir()
            return
        os.rmdir(name, dir_fd=fd)
    except StoreError:
        raise
    except OSError as exc:
        log.warning("datahub_directory_remove_failed", error_type=type(exc).__name__)
        raise StoreError("资料目录删除失败") from exc


def sync_directory(fd) -> None:
    """Flush a POSIX directory; Windows has no portable directory fsync."""
    if isinstance(fd, Path):
        return
    os.fsync(fd)


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2).encode("utf-8")


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
    if os.name == "nt":
        return _windows_control(root, url)
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
        return _parse_control(read_file(fd, "datahub.json", private=True, limit=4096), url)
