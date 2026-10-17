"""Explicit private-server entry point; help and doctor use only the stdlib.

Run with ``python -m app.research_web.multiuser``. Neither inspection nor account
administration starts a research runtime or reads the legacy project .env file.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import importlib.util
import json
import logging
import os
import platform
import re
import sqlite3
import stat
import sys
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

from .. import RUNTIME_CONTRACT

PROJECT = Path(__file__).absolute().parents[3]
_SAFE_CODE = re.compile(r"[a-z][a-z0-9_]{0,79}\Z", re.ASCII)
_DATABASE = "accounts.sqlite3"
log = logging.getLogger("app.research_web.multiuser.command")


class ServerCommandError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Research Workbench 私网邀请制服务器")
    commands = result.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("init", "交互创建首个管理员"),
        ("serve", "仅在 macOS 回环启动私网登录网关"),
        ("doctor", "只读检查服务器配置，不启动研究"),
        ("reset-admin", "交互重置既有管理员密码并撤销登录态"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument(
            "--root", type=Path, default=Path.home() / ".research-workbench/server"
        )
        if name in {"init", "reset-admin"}:
            command.add_argument("--username", required=True)
        elif name == "serve":
            command.add_argument("--origin", required=True)
            command.add_argument("--source", type=Path, required=True)
            command.add_argument("--node", type=Path, required=True)
            command.add_argument("--port", type=int, default=8089)
            command.add_argument("--max-instances", type=int, choices=(1, 2, 3, 4), default=2)
        else:
            command.add_argument("--source", type=Path)
            command.add_argument("--json", action="store_true")
    return result


def _directory(root: Path, *, create: bool = False) -> bool:
    if not root.is_absolute() or ".." in root.parts:
        raise ServerCommandError("server_path_unsafe")
    for path in (*reversed(root.parents), root):
        try:
            info = path.lstat()
        except FileNotFoundError:
            if not create:
                return False
            path.mkdir(mode=0o700)
            info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise ServerCommandError("server_path_unsafe")
    info = root.lstat()
    if os.name == "posix" and (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700):
        raise ServerCommandError("server_path_unsafe")
    return True


def _private_file(path: Path) -> os.stat_result:
    info = path.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or os.name == "posix"
        and (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600)
    ):
        raise ServerCommandError("server_path_unsafe")
    return info


def _inspect_accounts(root: Path) -> dict:
    """Read DELETE-journal SQLite only; WAL/active journals remain unknown.

    A read-only SQLite WAL connection may create shared-memory sidecars. Refuse
    that mode instead of opening an immutable snapshot that ignores live WAL.
    """
    result = {"status": "not_configured", "exists": False, "active_admins": None}
    try:
        if not _directory(root):
            return result
        path = root / _DATABASE
        try:
            before = _private_file(path)
        except FileNotFoundError:
            return result
        result["exists"] = True
        sidecars = [root / (_DATABASE + suffix) for suffix in ("-journal", "-wal", "-shm")]
        if any(path.exists() or path.is_symlink() for path in sidecars):
            return {**result, "status": "unknown", "code": "database_busy"}
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            header = os.read(descriptor, 100)
        finally:
            os.close(descriptor)
        if not header.startswith(b"SQLite format 3\0"):
            return {**result, "status": "unknown", "code": "account_store_failed"}
        if header[18:20] != b"\x01\x01":
            return {**result, "status": "unknown", "code": "database_busy"}
        connection = sqlite3.connect(f"file:{quote(str(path))}?mode=ro", uri=True, timeout=0)
        try:
            connection.execute("PRAGMA query_only=ON")
            connection.execute("BEGIN")
            if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                return {**result, "status": "unknown", "code": "account_store_failed"}
            users, admins = connection.execute(
                "SELECT COUNT(*), COALESCE(SUM(role='admin' AND enabled=1),0) FROM accounts"
            ).fetchone()
        finally:
            connection.close()
        after = _private_file(path)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ) or any(path.exists() or path.is_symlink() for path in sidecars):
            return {**result, "status": "unknown", "code": "database_busy"}
        return {**result, "status": "configured", "active_admins": admins, "count": users}
    except ServerCommandError:
        return {**result, "status": "unsafe", "code": "server_path_unsafe"}
    except (OSError, sqlite3.Error, ValueError, TypeError):
        return {**result, "status": "unknown", "code": "account_store_failed"}


def _source_status(source: Path | None) -> dict:
    if source is None:
        return {"status": "not_configured", "pinned_revision": "not_verified"}
    try:
        if not source.is_absolute() or ".." in source.parts:
            raise ServerCommandError("runtime_source_invalid")
        entry = source / "apps/cli/lib/bin.js"
        for path in (*reversed(entry.parents), entry):
            if path.is_symlink():
                raise ServerCommandError("runtime_source_invalid")
        built = stat.S_ISREG(entry.stat().st_mode)
        return {
            "status": "build_present" if built else "not_configured",
            "pinned_revision": "not_verified",
        }
    except (OSError, ServerCommandError):
        return {"status": "not_configured", "pinned_revision": "not_verified"}


def _configured_capacity(config: dict) -> int:
    """Explicit private pair limit; older installations retain one extra pair."""
    value = config.get("max_additional_instances", 1)
    if type(value) is not int or not 1 <= value <= 4:
        log.warning("server_capacity_invalid")
        raise ServerCommandError("server_capacity_invalid")
    return value


def _inspect_capacity(root: Path) -> dict:
    """Inspect private configuration without importing or starting a runtime."""
    descriptor = None
    try:
        if not _directory(root):
            return {"status": "not_configured"}
        path = root / "resident.json"
        if not path.exists() and not path.is_symlink():
            return {"status": "not_configured"}
        before = _private_file(path)
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        actual = os.fstat(descriptor)
        if (
            (actual.st_dev, actual.st_ino) != (before.st_dev, before.st_ino)
            or actual.st_size > 65536
            or not stat.S_ISREG(actual.st_mode)
            or actual.st_nlink != 1
            or os.name == "posix"
            and (actual.st_uid != os.getuid() or stat.S_IMODE(actual.st_mode) != 0o600)
        ):
            raise ServerCommandError("server_path_unsafe")
        config = json.loads(os.read(descriptor, 65537))
        if not isinstance(config, dict):
            raise ServerCommandError("server_capacity_invalid")
        additional = _configured_capacity(config)
        return {
            "status": "configured",
            "additional_instances": additional,
            "total_instances": additional + 1,
        }
    except (OSError, ValueError, RecursionError, ServerCommandError):
        log.warning("server_capacity_inspection_failed")
        return {"status": "invalid"}
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _doctor(arguments: argparse.Namespace, root: Path) -> int:
    accounts = _inspect_accounts(root)
    source = _source_status(arguments.source)
    python_matches = sys.version_info[:2] == (
        RUNTIME_CONTRACT.python_major,
        RUNTIME_CONTRACT.python_minor,
    )
    modules = {
        name: importlib.util.find_spec(name) is not None for name in ("uvicorn", "fastapi", "httpx")
    }
    report = {
        "schema_version": 1,
        # Artifact presence does not establish pinned-source or model readiness.
        "status": "not_configured",
        "platform": "supported" if platform.system() == "Darwin" else "not_supported",
        "accounts": accounts,
        "capacity": _inspect_capacity(root),
        "source": source,
        "interpreter": {
            "status": "available" if python_matches and all(modules.values()) else "not_configured",
            "python_matches": python_matches,
            "modules": modules,
        },
        "runtime": "not_checked",
        "model": "not_checked",
    }
    if arguments.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(
            f"server: {report['status']}; accounts: {accounts['status']}; source: {source['status']}; runtime: not_checked"
        )
    return 0


def _confirmed_password() -> str:
    if not sys.stdin.isatty():
        raise ServerCommandError("password_tty_required")
    first = getpass.getpass("新密码（至少12字符）: ")
    second = getpass.getpass("再次输入密码: ")
    if first != second:
        raise ServerCommandError("password_confirmation_mismatch")
    return first


class _SafeFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        try:
            event = json.loads(record.getMessage())
        except (ValueError, TypeError):
            event = {"event": record.getMessage()}
        if not isinstance(event, dict):
            event = {}
        code = event.get("event", "")
        safe = {
            "at": time.time(),
            "level": record.levelname.lower(),
            "event": code if isinstance(code, str) and _SAFE_CODE.fullmatch(code) else "server_log",
        }
        for key in ("code", "error_type", "account_id", "user_id", "role", "enabled"):
            if key in event:
                safe[key] = event[key]
        return json.dumps(safe, ensure_ascii=False)


@contextmanager
def _server_context(root: Path) -> Iterator[None]:
    _directory(root, create=True)
    _directory(root / "logs", create=True)
    path = root / "logs/server.jsonl"
    descriptor = os.open(
        path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600
    )
    stream = None
    handler = None
    saved_environment = {}
    missing = object()
    structlog = None
    old_structlog = None
    logger = logging.getLogger("app.research_web.multiuser")
    old_logging = logger.handlers[:], logger.level, logger.propagate
    try:
        _private_file(path)
        stream = os.fdopen(descriptor, "a", encoding="utf-8")
        descriptor = -1
        handler = logging.StreamHandler(stream)
        handler.setFormatter(_SafeFormatter())
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False
        values = {
            "RESEARCH_RUN_MODE": "web-prod",
            "RESEARCH_PROJECT_ROOT": str(PROJECT),
            "RESEARCH_CONFIG_FILE": None,
            "LOG_DIR": str(root / "logs"),
            "OBJECT_STORAGE_PATH": str(root),
            "PDF_MARKDOWN_DIR": str(root),
            "PDF_RAW_TEXT_DIR": str(root),
        }
        for key, value in values.items():
            saved_environment[key] = os.environ.get(key, missing)
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        try:
            import structlog
        except ImportError:
            structlog = None
        if structlog is not None:
            old_structlog = structlog.get_config()
            structlog.configure(
                processors=[structlog.stdlib.filter_by_level, structlog.processors.JSONRenderer()],
                logger_factory=structlog.stdlib.LoggerFactory(),
                wrapper_class=structlog.stdlib.BoundLogger,
                cache_logger_on_first_use=False,
            )
        yield
    finally:
        if structlog is not None and old_structlog is not None:
            structlog.configure(**old_structlog)
        for key, value in saved_environment.items():
            if value is missing:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        logger.handlers, logger.level, logger.propagate = old_logging
        if handler is not None:
            handler.close()
        if stream is not None:
            stream.close()
        if descriptor != -1:
            os.close(descriptor)


def _require_accounts(root: Path) -> None:
    info = _inspect_accounts(root)
    if info["status"] != "configured" or not info.get("active_admins"):
        raise ServerCommandError(info.get("code", "server_not_initialized"))


@contextmanager
def _administration_lock(root: Path) -> Iterator[None]:
    """Serialize first-admin initialization without placing credentials on disk."""
    import fcntl

    path = root / "admin.lock"
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        _private_file(path)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ServerCommandError("server_admin_busy") from exc
        yield
    finally:
        os.close(descriptor)


def _origin(origin: str) -> str:
    # Keep invalid origins out of initialization/import paths as well as HTTP.
    from .origin import validate_origin

    try:
        return validate_origin(origin)
    except ValueError as exc:
        raise ServerCommandError("server_origin_invalid") from exc


def _serve(arguments: argparse.Namespace, root: Path) -> int:
    if platform.system() != "Darwin":
        raise ServerCommandError("server_platform_unsupported")
    if sys.version_info[:2] != (RUNTIME_CONTRACT.python_major, RUNTIME_CONTRACT.python_minor):
        raise ServerCommandError("server_python_invalid")
    origin = _origin(arguments.origin)
    if not 1 <= arguments.port <= 65535:
        raise ServerCommandError("server_port_invalid")
    if (
        not arguments.node.is_absolute()
        or not arguments.node.is_file()
        or not os.access(arguments.node, os.X_OK)
    ):
        raise ServerCommandError("server_node_invalid")
    if _source_status(arguments.source)["status"] != "build_present":
        raise ServerCommandError("runtime_source_invalid")
    _require_accounts(root)
    with _server_context(root):
        import uvicorn

        from .accounts import AccountStore
        from .gateway import create_gateway
        from .runtime import RuntimeConfig, RuntimePool

        config = RuntimeConfig(
            root=root,
            project=PROJECT,
            source=arguments.source,
            python=sys.executable,
            node=str(arguments.node),
            max_instances=arguments.max_instances,
        )
        pool = RuntimePool(config)
        try:
            app = create_gateway(AccountStore(root), pool, origin=origin)
            log.info(json.dumps({"event": "server_starting"}))
            uvicorn.run(
                app,
                host="127.0.0.1",
                port=arguments.port,
                access_log=False,
                proxy_headers=False,
                log_config=None,
            )
        finally:
            # The ASGI lifespan normally closes the pool. This also releases the
            # ownership lock when server startup fails before lifespan begins.
            if hasattr(pool, "close"):
                asyncio.run(pool.close())
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    root = arguments.root.expanduser().absolute()
    try:
        if arguments.command == "doctor":
            return _doctor(arguments, root)
        if arguments.command == "serve":
            return _serve(arguments, root)
        info = _inspect_accounts(root)
        if arguments.command == "init":
            if info.get("count", 0):
                raise ServerCommandError("server_already_initialized")
            if info["status"] not in {"not_configured", "configured"}:
                raise ServerCommandError(info.get("code", "account_store_failed"))
        else:
            _require_accounts(root)
        password = _confirmed_password()
        with _server_context(root), _administration_lock(root):
            from .accounts import AccountStore

            store = AccountStore(root)
            if arguments.command == "init":
                if store.list_users():
                    raise ServerCommandError("server_already_initialized")
                store.create_user(arguments.username, password, "admin")
                print("server_initialized")
            else:
                account = next(
                    (
                        item
                        for item in store.list_users()
                        if item.username == arguments.username.lower() and item.role == "admin"
                    ),
                    None,
                )
                if account is None:
                    raise ServerCommandError("admin_account_required")
                store.reset_password(account.id, password)
                print("admin_password_reset")
        return 0
    except (KeyboardInterrupt, EOFError):
        print("server_interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001 -- Final CLI boundary never exposes exception text.
        code = getattr(exc, "code", "server_command_failed")
        if not isinstance(code, str) or not _SAFE_CODE.fullmatch(code):
            code = "server_command_failed"
        print(code, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
