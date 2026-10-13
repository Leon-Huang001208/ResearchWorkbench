"""Durable release maintenance and task admission; private Unix control only.

The manager enters maintenance through the owned container, never a public route.
Existing admissions drain; queued Automation tasks wait without cancellation.
"""

from __future__ import annotations

import asyncio
import contextvars
import functools
import json
import logging
import os
import re
import socket
import sys
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.research_web.client import RuntimeFailure

LOG = logging.getLogger("rwb.release.maintenance")
ADMITTED: contextvars.ContextVar[frozenset[tuple[int, object]]] = contextvars.ContextVar(
    "rwb_release_admitted", default=frozenset()
)
SOCKET_PATH = "/state/release-control.sock"


class MaintenanceGate:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self.active = 0
        self.admitted_tokens: set[object] = set()
        self.lock = asyncio.Condition()
        self.transaction: str | None = None
        self.server: asyncio.AbstractServer | None = None
        if path:
            try:
                if path.is_symlink():
                    raise ValueError("alias")
                if (
                    path.with_suffix(".pending").exists()
                    or path.with_suffix(".pending").is_symlink()
                ):
                    raise ValueError("unfinished")
                if path.exists():
                    value = json.loads(path.read_text())
                    if value.get("schema") != 1 or not re.fullmatch(
                        r"[a-f0-9]{32}", value.get("transaction", "")
                    ):
                        raise ValueError("invalid")
                    self.transaction = value["transaction"]
                    # Even a released tombstone requires the accepted controller
                    # to confirm the restarted process before it admits tasks.
            except (OSError, ValueError, TypeError):
                raise RuntimeFailure("维护记录不可确认", "maintenance_state_unknown") from None

    @asynccontextmanager
    async def admit(self, *, background: bool = False, fresh: bool = False) -> AsyncIterator[None]:
        if not fresh and any(
            identity == id(self) and token in self.admitted_tokens
            for identity, token in ADMITTED.get()
        ):
            yield
            return
        async with self.lock:
            while self.transaction:
                if not background:
                    raise RuntimeFailure("实例维护中，暂不受理新任务", "release_maintenance")
                await self.lock.wait()
            self.active += 1
            admission = object()
            self.admitted_tokens.add(admission)
        token = ADMITTED.set(ADMITTED.get() | {(id(self), admission)})
        try:
            yield
        finally:
            ADMITTED.reset(token)
            async with self.lock:
                self.active -= 1
                self.admitted_tokens.remove(admission)
                self.lock.notify_all()

    async def begin(self, transaction: str) -> None:
        if not re.fullmatch(r"[a-f0-9]{32}", transaction):
            raise RuntimeFailure("维护事务无效", "maintenance_state_unknown")
        async with self.lock:
            if self.transaction and self.transaction != transaction:
                raise RuntimeFailure("其他维护事务未完成", "maintenance_transaction_conflict")
            if not self.transaction:
                if self.path:
                    temporary = self.path.with_suffix(".pending")
                    try:
                        if self.path.is_symlink() or temporary.is_symlink():
                            raise OSError("alias")
                        with temporary.open("x", encoding="utf-8") as stream:
                            os.chmod(temporary, 0o600)
                            json.dump(
                                {"schema": 1, "transaction": transaction, "state": "maintenance"},
                                stream,
                            )
                            stream.flush()
                            os.fsync(stream.fileno())
                        temporary.replace(self.path)
                        self._sync_root()
                    except OSError:
                        # Fail closed even when persistence has an ambiguous result.
                        self.transaction = transaction
                        LOG.error("release_maintenance_persistence_failed")
                        raise RuntimeFailure(
                            "维护记录保存失败", "maintenance_state_unknown"
                        ) from None
                self.transaction = transaction
                LOG.info("release_maintenance_entered")

    def _sync_root(self) -> None:
        if self.path:
            descriptor = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)

    async def end(self, transaction: str) -> None:
        async with self.lock:
            if self.transaction != transaction:
                raise RuntimeFailure("维护事务不匹配", "maintenance_transaction_conflict")
            try:
                if self.path:
                    if self.path.is_symlink():
                        raise OSError("alias")
                    temporary = self.path.with_suffix(".pending")
                    with temporary.open("x", encoding="utf-8") as stream:
                        os.chmod(temporary, 0o600)
                        json.dump(
                            {"schema": 1, "transaction": transaction, "state": "released"}, stream
                        )
                        stream.flush()
                        os.fsync(stream.fileno())
                    temporary.replace(self.path)
                    self._sync_root()
            except OSError:
                LOG.error("release_maintenance_resume_failed")
                raise RuntimeFailure("维护恢复未确认", "maintenance_state_unknown") from None
            self.transaction = None
            self.lock.notify_all()
            LOG.info("release_maintenance_resumed")

    async def start_control(self, service: Any) -> None:
        if not self.path:
            return

        async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            try:
                raw = await asyncio.wait_for(reader.readline(), 5)
                if len(raw) > 512:
                    raise ValueError("bounded")
                request = json.loads(raw)
                action, transaction = request["action"], request["transaction"]
                if set(request) != {"action", "transaction"}:
                    raise ValueError("invalid")
                if action == "begin":
                    await self.begin(transaction)
                elif action == "end":
                    await self.end(transaction)
                elif action != "status":
                    raise ValueError("invalid")
                if self.transaction and self.transaction != transaction:
                    raise RuntimeFailure("维护事务不匹配", "maintenance_transaction_conflict")
                idle = False
                state = "busy"
                if self.active == 0:
                    try:
                        idle = await asyncio.wait_for(service.release_idle(), 15) is True
                        state = "idle" if idle else "busy"
                    except Exception:
                        state = "unknown"
                        LOG.warning("release_idle_unconfirmed")
                reply = {
                    "ok": True,
                    "maintenance": bool(self.transaction),
                    "transaction": self.transaction,
                    "idle": idle,
                    "state": state,
                    "admissions": self.active,
                }
            except Exception:
                reply = {"ok": False, "state": "unknown"}
                LOG.warning("release_control_refused")
            writer.write(json.dumps(reply).encode() + b"\n")
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        self.server = await asyncio.start_unix_server(handle, SOCKET_PATH, limit=1024)
        os.chmod(SOCKET_PATH, 0o600)

    async def close(self) -> None:
        if self.server:
            self.server.close()
            await self.server.wait_closed()


def task_admission(*, background: bool = False) -> Callable:
    def decorate(function: Callable) -> Callable:
        @functools.wraps(function)
        async def call(self: Any, *args: Any, **kwargs: Any) -> Any:
            gate = (
                getattr(self, "maintenance", None)
                or getattr(getattr(self, "research", None), "maintenance", None)
                or getattr(getattr(self, "service", None), "maintenance", None)
            )
            if gate is None:
                return await function(self, *args, **kwargs)
            async with gate.admit(background=background, fresh=background):
                return await function(self, *args, **kwargs)

        return call

    return decorate


def control_main() -> int:
    try:
        action, transaction = sys.argv[1:]
        if action not in {"begin", "status", "end"} or not re.fullmatch(
            r"[a-f0-9]{32}", transaction
        ):
            raise ValueError("invalid")
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(25)
            connection.connect(SOCKET_PATH)
            connection.sendall(
                json.dumps({"action": action, "transaction": transaction}).encode() + b"\n"
            )
            response = connection.makefile("rb").readline(1024)
        value = json.loads(response)
        if value.get("ok") is not True:
            raise ValueError("unconfirmed")
        print(json.dumps(value))
        return 0
    except Exception:
        print("release_control_unconfirmed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(control_main())
