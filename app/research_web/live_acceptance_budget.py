"""Explicit, dated Docker text acceptance authorization and nonrefundable tickets.

Only manual init creates state. Runtime reads/reserves an existing installation;
same-UID trusted operators remain outside the private-file isolation boundary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import secrets
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager, redirect_stdout
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal, NoReturn, TypeAlias, TypedDict

# Isolated script execution imports only its fixed product root.
if __package__ in (None, ""):
    product_root = str(Path(__file__).resolve(strict=True).parents[2])
    if __name__ == "__main__":
        # Legacy logger imports ensure directories even for read-only commands.
        # Only this private process binds them to the existing managed root.
        os.environ["RESEARCH_RUN_MODE"] = "web-prod"
        os.environ.pop("RESEARCH_CONFIG_FILE", None)
        for key in ("LOG_DIR", "OBJECT_STORAGE_PATH", "PDF_MARKDOWN_DIR", "PDF_RAW_TEXT_DIR"):
            os.environ[key] = product_root
    sys.path.insert(0, product_root)

with redirect_stdout(sys.stderr):
    from app.research_web.credential_backend import (
        PrivateFileCredentialBackend,
        _file_state,
        _identity,
        _validate_file,
    )
    from app.research_web.runtime_state import _validate_directory, runtime_state_directory
    from research_workbench_entrypoint.runtime_mode import (
        _node_identity,
        _open_posix_directory,
        _pin_posix_parents,
        _validate_posix_private_directory,
    )

log = logging.getLogger(__name__)
INPUT_TOKENS = 1048576
POLICY_EXPIRY = datetime(2026, 10, 9, tzinfo=UTC)


class PolicyFields(TypedDict):
    policyId: str
    quoteDate: str
    policyExpires: str
    endpoint: str
    provider: str
    model: str
    inputMicroUsdPerMillion: int
    outputMicroUsdPerMillion: int
    inputReservation: int


class Authorization(PolicyFields):
    version: int
    modelCalls: int
    maxOutputTokens: int
    validUntil: str
    totalInputTokens: int
    totalOutputTokens: int
    totalMicroUsd: int


class Ledger(TypedDict):
    controlSha256: str
    tickets: int
    inputTokens: int
    outputTokens: int
    microUsd: int


class Reservation(TypedDict):
    ticket: int
    remainingMillis: int


class InitRequest(TypedDict):
    op: Literal["init"]
    authorization: object


class DescribeRequest(TypedDict):
    op: Literal["describe"]


class ReserveRequest(TypedDict):
    op: Literal["reserve"]
    outputTokens: object


Request: TypeAlias = InitRequest | DescribeRequest | ReserveRequest
PrivateRecord: TypeAlias = tuple[bytes, os.stat_result]
Clock: TypeAlias = Callable[[], datetime]

POLICY: PolicyFields = {
    "policyId": "deepseek-flash-20261008",
    "quoteDate": "2026-10-08",
    "policyExpires": "2026-10-09T00:00:00Z",
    "endpoint": "https://api.deepseek.com",
    "provider": "deepseek-official",
    "model": "deepseek-v4-flash",
    "inputMicroUsdPerMillion": 300000,
    "outputMicroUsdPerMillion": 1200000,
    "inputReservation": INPUT_TOKENS,
}
ERRORS = frozenset(
    {
        "acceptance_budget_unverified",
        "acceptance_budget_invalid",
        "acceptance_budget_exists",
        "acceptance_budget_expired",
        "acceptance_budget_exhausted",
        "acceptance_budget_unavailable",
        "acceptance_budget_commit_uncertain",
    }
)


class BudgetError(RuntimeError):
    """Fixed public error code; no request, credential or path details."""


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _date(value: object) -> datetime:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value) is None
    ):
        raise BudgetError("acceptance_budget_invalid")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def _number(value: object, maximum: int) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise BudgetError("acceptance_budget_invalid")
    return value


def request_cost(output: int) -> int:
    """Integral micro-USD, independently ceiling each worst-case component."""
    return (INPUT_TOKENS * 300000 + 999999) // 1000000 + (output * 1200000 + 999999) // 1000000


def authorization(tickets: object, output: object, valid_until: object) -> Authorization:
    """Build the exact reviewable nonsecret control; does not authorize/write."""
    ticket_count = _number(tickets, 3)
    output_cap = _number(output, 4096)
    if not isinstance(valid_until, str):
        raise BudgetError("acceptance_budget_invalid")
    _date(valid_until)
    return {
        **POLICY,
        "version": 1,
        "modelCalls": ticket_count,
        "maxOutputTokens": output_cap,
        "validUntil": valid_until,
        "totalInputTokens": ticket_count * INPUT_TOKENS,
        "totalOutputTokens": ticket_count * output_cap,
        "totalMicroUsd": ticket_count * request_cost(output_cap),
    }


def _encode(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise BudgetError("acceptance_budget_invalid")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise BudgetError("acceptance_budget_invalid")
        result[key] = item
    return result


def _decode(raw: bytes) -> dict[str, object]:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise BudgetError("acceptance_budget_invalid")
            result[key] = value
        return result

    value = _mapping(json.loads(raw, object_pairs_hook=unique))
    if _encode(value) != raw:
        raise BudgetError("acceptance_budget_invalid")
    return value


def _request(value: object) -> Request:
    mapping = _mapping(value)
    if set(mapping) == {"op", "authorization"} and mapping["op"] == "init":
        return {"op": "init", "authorization": mapping["authorization"]}
    if set(mapping) == {"op"} and mapping["op"] == "describe":
        return {"op": "describe"}
    if set(mapping) == {"op", "outputTokens"} and mapping["op"] == "reserve":
        return {"op": "reserve", "outputTokens": mapping["outputTokens"]}
    raise BudgetError("acceptance_budget_invalid")


class BudgetStore:
    """Pinned private leaf, existing permanent lock, fixed control and ledger."""

    def __init__(
        self, root: str | Path, installation_id: object, *, clock: Clock = _utcnow
    ) -> None:
        if (
            not isinstance(installation_id, str)
            or re.fullmatch(r"[a-f0-9]{32}", installation_id) is None
        ):
            raise BudgetError("acceptance_budget_invalid")
        self.root = Path(root)
        if (
            not self.root.is_absolute()
            or self.root.name != installation_id
            or ".." in self.root.parts
            or str(self.root).startswith("//")
        ):
            raise BudgetError("acceptance_budget_invalid")
        self.installation_id, self.clock = installation_id, clock

    def _control(self, value: object, *, initialize: bool = False) -> Authorization:
        mapping = _mapping(value)
        expected = authorization(
            mapping.get("modelCalls"), mapping.get("maxOutputTokens"), mapping.get("validUntil")
        )
        # Equality alone would accept bool as an integer in fixed numeric fields.
        if _encode(value) != _encode(expected):
            raise BudgetError("acceptance_budget_invalid")
        now, until = self.clock(), _date(expected["validUntil"])
        if now >= until or now >= POLICY_EXPIRY:
            raise BudgetError("acceptance_budget_expired")
        if until > POLICY_EXPIRY or (initialize and until > now + timedelta(hours=1)):
            raise BudgetError("acceptance_budget_invalid")
        return expected

    @contextmanager
    def _directory(self, *, locked: bool = False) -> Iterator[int]:
        import fcntl

        with (
            runtime_state_directory(self.root.parent, create=False),
            runtime_state_directory(self.root, create=False),
            _pin_posix_parents(self.root / "control.json", node_only=True) as directory,
        ):
            if not locked:
                yield directory
                return
            lock = os.open(
                "budget.lock", os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
            )
            try:
                opened = os.fstat(lock)
                _validate_file(opened)
                if opened.st_size != 0:
                    raise BudgetError("acceptance_budget_invalid")
                deadline = time.monotonic() + 5
                while True:
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        if time.monotonic() >= deadline:
                            raise BudgetError("acceptance_budget_unavailable") from None
                        time.sleep(0.01)

                def verify() -> None:
                    named = os.stat("budget.lock", dir_fd=directory, follow_symlinks=False)
                    _validate_file(named)
                    if named.st_size != 0 or _identity(named) != _identity(opened):
                        raise BudgetError("acceptance_budget_unavailable")

                verify()
                try:
                    yield directory
                finally:
                    verify()
                    fcntl.flock(lock, fcntl.LOCK_UN)
            finally:
                os.close(lock)

    def _read(self, directory: int) -> tuple[Authorization, Ledger, PrivateRecord]:
        control = PrivateFileCredentialBackend._read(directory, "control.json")
        ledger = PrivateFileCredentialBackend._read(directory, "ledger.json")
        if control is None or ledger is None:
            raise BudgetError("acceptance_budget_unverified")
        bound = _decode(control[0])
        if (
            set(bound) != {"installationId", "authorization"}
            or bound["installationId"] != self.installation_id
        ):
            raise BudgetError("acceptance_budget_invalid")
        value = self._control(bound["authorization"])
        spent = _decode(ledger[0])
        count = spent.get("tickets")
        if type(count) is not int or not 0 <= count <= value["modelCalls"]:
            raise BudgetError("acceptance_budget_invalid")
        expected: Ledger = {
            "controlSha256": hashlib.sha256(control[0]).hexdigest(),
            "tickets": count,
            "inputTokens": count * INPUT_TOKENS,
            "outputTokens": count * value["maxOutputTokens"],
            "microUsd": count * request_cost(value["maxOutputTokens"]),
        }
        if _encode(spent) != _encode(expected):
            raise BudgetError("acceptance_budget_invalid")
        return value, expected, ledger

    @staticmethod
    def _publish(
        directory: int, name: str, raw: bytes, previous: PrivateRecord | None, attempted: list[bool]
    ) -> None:
        temporary = ".budget." + secrets.token_hex(16) + ".tmp"
        descriptor = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory
        )
        try:
            identity = _identity(os.fstat(descriptor))
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(descriptor)
            current = PrivateFileCredentialBackend._read(directory, name)
            if (current is None) != (previous is None) or (
                current is not None
                and previous is not None
                and (
                    current[0] != previous[0] or _file_state(current[1]) != _file_state(previous[1])
                )
            ):
                raise BudgetError("acceptance_budget_unavailable")
            attempted[0] = True
            os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
            os.fsync(directory)
            persisted = PrivateFileCredentialBackend._read(directory, name)
            if persisted is None or persisted[0] != raw or _identity(persisted[1]) != identity:
                raise BudgetError("acceptance_budget_commit_uncertain")
        finally:
            os.close(descriptor)
            try:
                named = os.stat(temporary, dir_fd=directory, follow_symlinks=False)
                if _identity(named) == identity:
                    os.unlink(temporary, dir_fd=directory)
            except FileNotFoundError:
                pass

    def _failure(self, error: Exception, attempted: bool = False) -> NoReturn:
        code = (
            "acceptance_budget_commit_uncertain"
            if attempted
            else (
                str(error)
                if isinstance(error, BudgetError) and str(error) in ERRORS
                else "acceptance_budget_unavailable"
            )
        )
        try:
            log.warning("research_acceptance_budget_rejected code=%s", code)
        except Exception:  # noqa: BLE001, S110 - Logging cannot change commit semantics.
            pass
        raise BudgetError(code) from None

    @classmethod
    def initialize(
        cls, root: str | Path, installation_id: object, control: object, *, clock: Clock = _utcnow
    ) -> None:
        store = cls(root, installation_id, clock=clock)
        attempted = [False]
        try:
            authorized = store._control(control, initialize=True)
            # Only explicit init may create the shared acceptance parent; first
            # prove the already-managed private credential bind is private.
            if store.root.parent == Path("/run/rwb-secrets/private/live-acceptance"):
                with runtime_state_directory(store.root.parents[1], create=False):
                    info = store.root.parents[1].lstat()
                    if info.st_uid != os.getuid() or (info.st_mode & 0o777) != 0o700:
                        raise BudgetError("acceptance_budget_unavailable")
                    with runtime_state_directory(store.root.parent, create=True):
                        pass
            with (
                runtime_state_directory(store.root.parent, create=False),
                _pin_posix_parents(store.root, node_only=True) as parent,
            ):
                try:
                    os.mkdir(store.root.name, 0o700, dir_fd=parent)
                except FileExistsError:
                    raise BudgetError("acceptance_budget_exists") from None
                with store._directory() as directory:
                    lock = os.open(
                        "budget.lock",
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                        0o600,
                        dir_fd=directory,
                    )
                    try:
                        os.fsync(lock)
                    finally:
                        os.close(lock)
                    bound = _encode(
                        {"installationId": store.installation_id, "authorization": authorized}
                    )
                    store._publish(directory, "control.json", bound, None, attempted)
                    ledger: Ledger = {
                        "controlSha256": hashlib.sha256(bound).hexdigest(),
                        "tickets": 0,
                        "inputTokens": 0,
                        "outputTokens": 0,
                        "microUsd": 0,
                    }
                    store._publish(directory, "ledger.json", _encode(ledger), None, attempted)
                os.fsync(parent)
        except Exception as error:  # noqa: BLE001 - Expose only stable private boundary codes.
            store._failure(error, attempted[0])

    def describe(self) -> Authorization:
        try:
            with self._directory(locked=True) as directory:
                value, _, _ = self._read(directory)
                return value
        except Exception as error:  # noqa: BLE001 - Never disclose private file diagnostics.
            self._failure(error)

    def read_optional(self) -> Authorization | None:
        """Discover only fixed private ancestry; an existing leaf is never optional.

        Factory-supplied temporary roots are for deterministic unit fixtures.
        Production callers bind the fixed Docker installation path. Every
        existing directory stays pinned until even a missing-path return has
        independently rechecked its no-follow named identity and private mode.
        """
        records: list[tuple[int, int | None, str, os.stat_result, bool]] = []
        private_base = self.root.parents[1]
        try:
            with ExitStack() as stack:
                try:
                    parent: int | None = None
                    for component in (*reversed(self.root.parents), self.root):
                        name = str(component) if parent is None else component.name
                        private = component == private_base or component.is_relative_to(
                            private_base
                        )
                        if parent is None:
                            descriptor = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                            stack.callback(os.close, descriptor)
                            identity = os.fstat(descriptor)
                        else:
                            try:
                                descriptor, identity = _open_posix_directory(parent, name)
                            except FileNotFoundError:
                                # Missing the fixed base hierarchy or its
                                # namespace/installation leaf means no opt-in.
                                return None
                            stack.callback(os.close, descriptor)
                        _validate_directory(identity, leaf=private, platform_name=os.name)
                        if private:
                            _validate_posix_private_directory(identity)
                        records.append((descriptor, parent, name, identity, private))
                        parent = descriptor
                    # Once the installation directory exists, all three
                    # artifacts are mandatory, including after interrupted init.
                    return self.describe()
                finally:
                    for descriptor, ancestor, name, before, private in records:
                        opened = os.fstat(descriptor)
                        named = os.stat(name, dir_fd=ancestor, follow_symlinks=False)
                        for observed in (opened, named):
                            _validate_directory(observed, leaf=private, platform_name=os.name)
                            if private:
                                _validate_posix_private_directory(observed)
                            if _node_identity(observed) != _node_identity(before):
                                raise BudgetError("acceptance_budget_unavailable")
        # Optional absence never swallows unsafe ancestry.
        except Exception as error:  # noqa: BLE001
            self._failure(error)

    def reserve(self, output_tokens: object) -> Reservation:
        attempted = [False]
        try:
            with self._directory(locked=True) as directory:
                value, spent, previous = self._read(directory)
                _number(output_tokens, value["maxOutputTokens"])
                count = spent["tickets"] + 1
                if count > value["modelCalls"]:
                    raise BudgetError("acceptance_budget_exhausted")
                # Reserve configured output cap even when this dispatch is smaller.
                spent["tickets"] = count
                spent["inputTokens"] = count * INPUT_TOKENS
                spent["outputTokens"] = count * value["maxOutputTokens"]
                spent["microUsd"] = count * request_cost(value["maxOutputTokens"])
                self._publish(directory, "ledger.json", _encode(spent), previous, attempted)
                self._control(value)
                remaining = int((_date(value["validUntil"]) - self.clock()).total_seconds() * 1000)
                if not 1 <= remaining <= 3600000:
                    raise BudgetError("acceptance_budget_expired")
                result: Reservation = {"ticket": count, "remainingMillis": remaining}
            return result
        # Final FD/lock errors remain uncertain after commit.
        except Exception as error:  # noqa: BLE001
            self._failure(error, attempted[0])


def main() -> int:
    try:

        class PrivateParser(argparse.ArgumentParser):
            def error(self, message: str) -> NoReturn:
                raise BudgetError("acceptance_budget_invalid")

        parser = PrivateParser(add_help=False, exit_on_error=False)
        parser.add_argument("--installation-id", required=True)
        args = parser.parse_args()
        installation_id: object = args.installation_id
        if (
            sys.platform != "linux"
            or not isinstance(installation_id, str)
            or re.fullmatch(r"[a-f0-9]{32}", installation_id) is None
        ):
            raise BudgetError("acceptance_budget_invalid")
        root = Path("/run/rwb-secrets/private/live-acceptance") / installation_id
        raw = sys.stdin.buffer.read(8193)
        if len(raw) > 8192:
            raise BudgetError("acceptance_budget_invalid")
        request = _request(json.loads(raw))
        result: Authorization | Reservation | dict[str, object]
        with redirect_stdout(sys.stderr):
            if request["op"] == "init":
                BudgetStore.initialize(root, installation_id, request["authorization"])
                result = {}
            elif request["op"] == "describe":
                result = BudgetStore(root, installation_id).describe()
            else:
                result = BudgetStore(root, installation_id).reserve(request["outputTokens"])
        sys.stdout.write(json.dumps({"ok": True, **result}))
        return 0
    except Exception as error:  # noqa: BLE001 - Only fixed codes enter the private JSON pipe.
        code = (
            str(error)
            if isinstance(error, BudgetError) and str(error) in ERRORS
            else "acceptance_budget_unavailable"
        )
        sys.stdout.write(json.dumps({"ok": False, "error": code}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
