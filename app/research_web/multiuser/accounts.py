"""Private SQLite accounts and revocable opaque browser sessions.

Only password derivations and token digests are persisted. Each operation owns a
short-lived SQLite connection; account changes and session revocation commit in
the same transaction. The gateway supplies authorization for administration.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import os
import re
import secrets
import sqlite3
import stat
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from core.observability import get_logger

log = get_logger(__name__)
SESSION_TTL_SECONDS = 43200
MAX_ACCOUNTS = 128
MAX_SESSIONS_PER_USER = 16
LOGIN_WINDOW_SECONDS = 900
LOGIN_USERNAME_FAILURE_LIMIT = 5
LOGIN_GLOBAL_FAILURE_LIMIT = 100
SCRYPT_N = 32768
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_BYTES = 32
SCRYPT_SALT_BYTES = 16
_USERNAME = re.compile(r"[a-z][a-z0-9_.-]{2,63}\Z", re.ASCII)
_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}\Z", re.ASCII)
_DUMMY_SALT = b"rwb-login-dummy!!"
_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'user')),
    enabled INTEGER NOT NULL CHECK(enabled IN (0, 1)),
    salt BLOB NOT NULL,
    password_hash BLOB NOT NULL,
    scrypt_n INTEGER NOT NULL,
    scrypt_r INTEGER NOT NULL,
    scrypt_p INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id, created_at);
CREATE TABLE IF NOT EXISTS login_failures (
    bucket TEXT PRIMARY KEY,
    window_start REAL NOT NULL,
    failures INTEGER NOT NULL
);
"""


class AccountError(Exception):
    """An API-safe error without database paths or submitted credentials."""

    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


@dataclass(frozen=True)
class Account:
    id: str
    username: str
    role: str
    enabled: bool

    def public(self) -> dict[str, str | bool]:
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "enabled": self.enabled,
        }


def _username(value: str) -> str:
    if not isinstance(value, str) or len(value) > 64:
        raise AccountError("invalid_username")
    result = value.lower()
    if not value.isascii() or not _USERNAME.fullmatch(result):
        raise AccountError("invalid_username")
    return result


def _password(value: str) -> bytes:
    if not isinstance(value, str) or not 12 <= len(value) <= 1024:
        raise AccountError("invalid_password")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise AccountError("invalid_password") from exc
    if len(encoded) > 1024:
        raise AccountError("invalid_password")
    return encoded


def _derive(password: bytes, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password,
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_BYTES,
        maxmem=64 * 1024 * 1024,
    )


def _account(row: sqlite3.Row) -> Account:
    return Account(row["id"], row["username"], row["role"], bool(row["enabled"]))


class AccountStore:
    """One server's private account database; never stores research transcripts."""

    def __init__(self, root: Path, *, clock: Callable[[], float] = time.time):
        self.root = Path(root).absolute()
        self.path = self.root / "accounts.sqlite3"
        self.clock = clock
        self._root_identity: tuple[int, int] | None = None
        self._db_identity: tuple[int, int] | None = None
        try:
            self._prepare_root()
            try:
                descriptor = os.open(
                    self.path,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                    0o600,
                )
            except FileExistsError:
                self._validate_paths()
            else:
                os.close(descriptor)
            self._validate_paths()
            self._db_identity = self._identity(self.path.lstat())
            with self._connection() as db:
                for statement in _SCHEMA.split(";"):
                    if statement.strip():
                        db.execute(statement)
                if (
                    db.execute("PRAGMA quick_check").fetchone()[0] != "ok"
                    or db.execute("PRAGMA foreign_key_check").fetchone() is not None
                ):
                    raise AccountError("account_store_failed", 503)
        except AccountError:
            raise
        except (OSError, sqlite3.Error, ValueError) as exc:
            self._failed(exc)

    @staticmethod
    def _identity(info: os.stat_result) -> tuple[int, int]:
        return info.st_dev, info.st_ino

    @staticmethod
    def _failed(exc: Exception) -> None:
        log.error("multiuser_account_store_failed", error_type=type(exc).__name__)
        raise AccountError("account_store_failed", 503) from exc

    def _prepare_root(self) -> None:
        if ".." in self.root.parts:
            raise AccountError("account_store_unsafe", 503)
        # Check ancestors before creating any child: mkdir(parents=True) alone
        # would follow an ancestor symlink and write outside the chosen root.
        for path in (*reversed(self.root.parents), self.root):
            try:
                info = path.lstat()
            except FileNotFoundError:
                path.mkdir(mode=0o700)
                info = path.lstat()
            if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
                raise AccountError("account_store_unsafe", 503)
        self._validate_paths()
        self._root_identity = self._identity(self.root.lstat())

    def _validate_paths(self) -> None:
        for path in (*reversed(self.root.parents), self.root):
            info = path.lstat()
            if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
                raise AccountError("account_store_unsafe", 503)
        root_info = self.root.lstat()
        if os.name == "posix" and (
            root_info.st_uid != os.getuid() or stat.S_IMODE(root_info.st_mode) != 0o700
        ):
            raise AccountError("account_store_unsafe", 503)
        if self._root_identity is not None and self._identity(root_info) != self._root_identity:
            raise AccountError("account_store_unsafe", 503)
        for name in (
            "accounts.sqlite3",
            "accounts.sqlite3-journal",
            "accounts.sqlite3-wal",
            "accounts.sqlite3-shm",
        ):
            path = self.root / name
            try:
                info = path.lstat()
            except FileNotFoundError:
                if name == "accounts.sqlite3" and self._db_identity is not None:
                    raise AccountError("account_store_unsafe", 503) from None
                continue
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise AccountError("account_store_unsafe", 503)
            if os.name == "posix" and (
                info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600
            ):
                raise AccountError("account_store_unsafe", 503)
            if (
                name == "accounts.sqlite3"
                and self._db_identity is not None
                and self._identity(info) != self._db_identity
            ):
                raise AccountError("account_store_unsafe", 503)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        db = None
        try:
            self._validate_paths()
            db = sqlite3.connect(f"file:{quote(str(self.path))}?mode=rw", uri=True, timeout=5)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA trusted_schema=OFF")
            db.execute("PRAGMA secure_delete=ON")
            db.execute("PRAGMA busy_timeout=5000")
            self._validate_paths()
            db.execute("BEGIN IMMEDIATE")
            yield db
            self._validate_paths()
            db.commit()
        except AccountError:
            if db is not None:
                self._rollback(db)
            raise
        except (OSError, sqlite3.Error, ValueError, OverflowError) as exc:
            if db is not None:
                self._rollback(db)
            self._failed(exc)
        finally:
            if db is not None:
                try:
                    db.close()
                except (OSError, sqlite3.Error) as exc:
                    self._failed(exc)

    @staticmethod
    def _rollback(db: sqlite3.Connection) -> None:
        try:
            db.rollback()
        except (OSError, sqlite3.Error) as exc:
            # Closing below still releases the connection. Preserve the original
            # safe failure while recording that rollback could not be confirmed.
            log.error("multiuser_account_rollback_failed", error_type=type(exc).__name__)

    def _now(self) -> float:
        try:
            now = float(self.clock())
        except (OSError, TypeError, ValueError, OverflowError) as exc:
            self._failed(exc)
        if not math.isfinite(now):
            raise AccountError("account_store_failed", 503)
        return now

    @staticmethod
    def _find(db: sqlite3.Connection, user_id: str) -> sqlite3.Row:
        if not isinstance(user_id, str) or len(user_id) != 36:
            raise AccountError("account_not_found", 404)
        row = db.execute("SELECT * FROM accounts WHERE id=?", (user_id,)).fetchone()
        if row is None:
            raise AccountError("account_not_found", 404)
        return row

    def create_user(self, username: str, password: str, role: str = "user") -> Account:
        normalized = _username(username)
        encoded = _password(password)
        if role not in ("admin", "user"):
            raise AccountError("invalid_role")
        try:
            salt = secrets.token_bytes(SCRYPT_SALT_BYTES)
            derived = _derive(encoded, salt)
            account = Account(str(uuid.uuid4()), normalized, role, True)
            with self._connection() as db:
                if db.execute("SELECT 1 FROM accounts WHERE username=?", (normalized,)).fetchone():
                    raise AccountError("username_exists", 409)
                if db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] >= MAX_ACCOUNTS:
                    raise AccountError("account_limit_reached", 409)
                db.execute(
                    "INSERT INTO accounts VALUES (?,?,?,?,?,?,?,?,?)",
                    (account.id, normalized, role, 1, salt, derived, SCRYPT_N, SCRYPT_R, SCRYPT_P),
                )
        except AccountError:
            raise
        except (OSError, ValueError) as exc:
            self._failed(exc)
        log.info("multiuser_account_created", account_id=account.id, role=role)
        return account

    def list_users(self) -> list[Account]:
        with self._connection() as db:
            return [_account(row) for row in db.execute("SELECT * FROM accounts ORDER BY username")]

    def get_user(self, user_id: str) -> Account:
        with self._connection() as db:
            return _account(self._find(db, user_id))

    def set_enabled(self, user_id: str, enabled: bool) -> Account:
        if not isinstance(enabled, bool):
            raise AccountError("invalid_enabled")
        with self._connection() as db:
            row = self._find(db, user_id)
            if not enabled and row["role"] == "admin" and row["enabled"]:
                count = db.execute(
                    "SELECT COUNT(*) FROM accounts WHERE role='admin' AND enabled=1"
                ).fetchone()[0]
                if count <= 1:
                    raise AccountError("last_active_admin", 409)
            db.execute("UPDATE accounts SET enabled=? WHERE id=?", (int(enabled), user_id))
            if not enabled:
                db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
            account = _account(self._find(db, user_id))
        log.info("multiuser_account_enabled_changed", account_id=user_id, enabled=enabled)
        return account

    def reset_password(self, user_id: str, password: str) -> None:
        encoded = _password(password)
        try:
            salt = secrets.token_bytes(SCRYPT_SALT_BYTES)
            derived = _derive(encoded, salt)
            with self._connection() as db:
                row = self._find(db, user_id)
                db.execute(
                    "UPDATE accounts SET salt=?,password_hash=?,scrypt_n=?,scrypt_r=?,scrypt_p=? WHERE id=?",
                    (salt, derived, SCRYPT_N, SCRYPT_R, SCRYPT_P, user_id),
                )
                db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
                db.execute(
                    "DELETE FROM login_failures WHERE bucket=?", (self._bucket(row["username"]),)
                )
        except AccountError:
            raise
        except (OSError, ValueError) as exc:
            self._failed(exc)
        log.info("multiuser_account_password_reset", account_id=user_id)

    @staticmethod
    def _bucket(username: str) -> str:
        return "user:" + hashlib.sha256(username.encode("utf-8")).hexdigest()

    @staticmethod
    def _token_hash(token: str) -> str | None:
        if not isinstance(token, str) or not _TOKEN.fullmatch(token):
            return None
        return hashlib.sha256(token.encode("ascii")).hexdigest()

    @staticmethod
    def _verify(row: sqlite3.Row | None, password: bytes) -> bool:
        if row is None:
            _derive(password, _DUMMY_SALT)
            return False
        if (
            (row["scrypt_n"], row["scrypt_r"], row["scrypt_p"]) != (SCRYPT_N, SCRYPT_R, SCRYPT_P)
            or not isinstance(row["salt"], bytes)
            or len(row["salt"]) != SCRYPT_SALT_BYTES
            or not isinstance(row["password_hash"], bytes)
            or len(row["password_hash"]) != SCRYPT_BYTES
        ):
            raise AccountError("account_store_failed", 503)
        return hmac.compare_digest(_derive(password, row["salt"]), row["password_hash"])

    def login(self, username: str, password: str) -> tuple[str, Account]:
        try:
            normalized = _username(username)
        except AccountError:
            normalized = "!invalid"
        try:
            encoded = _password(password)
        except AccountError:
            encoded = b""
        bucket = self._bucket(normalized)
        now = self._now()
        result = None
        with self._connection() as db:
            # Future-dated buckets remain limiting if the system clock moves
            # backwards. Expired rows are removed so arbitrary names stay bounded.
            db.execute(
                "DELETE FROM login_failures WHERE window_start <= ?", (now - LOGIN_WINDOW_SECONDS,)
            )
            for name, limit in (
                ("global", LOGIN_GLOBAL_FAILURE_LIMIT),
                (bucket, LOGIN_USERNAME_FAILURE_LIMIT),
            ):
                failure = db.execute(
                    "SELECT failures FROM login_failures WHERE bucket=?", (name,)
                ).fetchone()
                if failure is not None and failure[0] >= limit:
                    raise AccountError("login_rate_limited", 429)
            row = db.execute("SELECT * FROM accounts WHERE username=?", (normalized,)).fetchone()
            verified = self._verify(row, encoded) if encoded else False
            if verified and row is not None and row["enabled"]:
                token = secrets.token_urlsafe(32)
                db.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
                # Keep the newest 15 before inserting the sixteenth session.
                db.execute(
                    "DELETE FROM sessions WHERE token_hash IN (SELECT token_hash FROM sessions "
                    "WHERE user_id=? ORDER BY created_at DESC, rowid DESC LIMIT -1 OFFSET ?)",
                    (row["id"], MAX_SESSIONS_PER_USER - 1),
                )
                db.execute(
                    "INSERT INTO sessions VALUES (?,?,?,?)",
                    (self._token_hash(token), row["id"], now, now + SESSION_TTL_SECONDS),
                )
                db.execute("DELETE FROM login_failures WHERE bucket=?", (bucket,))
                result = (token, _account(row))
            else:
                for name in ("global", bucket):
                    db.execute(
                        "INSERT INTO login_failures VALUES (?,?,1) ON CONFLICT(bucket) "
                        "DO UPDATE SET failures=failures+1",
                        (name, now),
                    )
        if result is None:
            log.info("multiuser_login_rejected")
            raise AccountError("invalid_credentials", 401)
        log.info("multiuser_login_accepted", account_id=result[1].id)
        return result

    def authenticate(self, token: str) -> Account | None:
        token_hash = self._token_hash(token)
        if token_hash is None:
            return None
        now = self._now()
        with self._connection() as db:
            row = db.execute(
                "SELECT accounts.* FROM sessions JOIN accounts ON accounts.id=sessions.user_id "
                "WHERE token_hash=? AND expires_at>? AND created_at<=? AND enabled=1",
                (token_hash, now, now),
            ).fetchone()
            return _account(row) if row is not None else None

    def logout(self, token: str) -> None:
        token_hash = self._token_hash(token)
        if token_hash is None:
            return
        with self._connection() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))
        log.info("multiuser_logout")
