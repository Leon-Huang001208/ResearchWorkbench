"""Durable OAuth policy in the existing private account SQLite transaction.

No HTTP, SDK, browser cookies, runtime allocation, or research reads live here.
approve_material/revoke_material are TRUSTED OPERATOR APIs, never OAuth/tool input.
The gateway must authenticate consent/revocation owners and reverify access plus
authorize_material immediately before returning bytes. Record IDs are not auth.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import sqlite3
import uuid
from collections.abc import Sequence
from typing import NoReturn
from urllib.parse import urlsplit

from core.observability import get_logger

from ..multiuser.accounts import AccountError, AccountStore
from ..multiuser.origin import validate_origin
from .models import (
    ACCESS_TTL,
    CLIENT_ID,
    CODE_TTL,
    CONSENT_TTL,
    REFRESH_TTL,
    SCHEMA,
    SCOPE,
    ApprovedMaterial,
    CodeRecord,
    ConsentRequest,
    FixedClient,
    Grant,
    TokenPair,
    TokenRecord,
)

log = get_logger(__name__)
_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}\Z", re.ASCII)
_VERIFIER = re.compile(r"[A-Za-z0-9._~-]{43,128}\Z", re.ASCII)
_SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)


def _reject(code: str = "invalid_grant") -> NoReturn:
    raise AccountError(code, 400)


def _digest(raw: str) -> str:
    if not isinstance(raw, str) or not _TOKEN.fullmatch(raw):
        _reject()
    return hashlib.sha256(raw.encode("ascii")).hexdigest()


def _label(value: str) -> None:
    if not isinstance(value, str) or not 1 <= len(value) <= 256 or any(ord(c) < 32 for c in value):
        _reject("invalid_material")


def _consent(row: sqlite3.Row) -> ConsentRequest:
    return ConsentRequest(
        row["id"],
        row["user_id"],
        row["client_id"],
        row["issuer"],
        row["resource"],
        (row["scope"],),
        row["redirect_uri"],
        row["challenge"],
        row["state"],
        bool(row["redirect_explicit"]),
        row["expires_at"],
    )


def _material(row: sqlite3.Row) -> ApprovedMaterial:
    return ApprovedMaterial(
        *(
            row[key]
            for key in (
                "id",
                "user_id",
                "context_id",
                "kind",
                "object_id",
                "sha256",
                "classification",
            )
        )
    )


def _grant_record(row: sqlite3.Row) -> Grant:
    return Grant(
        row["id"],
        row["user_id"],
        row["client_id"],
        row["issuer"],
        row["resource"],
        (row["scope"],),
        row["expires_at"],
        bool(row["revoked"]),
    )


class AuthorizationStore:
    """All writes use AccountStore's identity-checked BEGIN IMMEDIATE connection."""

    def __init__(self, accounts: AccountStore, *, issuer: str):
        try:
            self.issuer = validate_origin(issuer)
        except ValueError as exc:
            raise AccountError("invalid_issuer") from exc
        self.resource = self.issuer + "/mcp"
        self.accounts = accounts
        with accounts._connection() as db:
            for statement in SCHEMA.split(";"):
                if statement.strip():
                    db.execute(statement)
            db.execute(
                "INSERT OR IGNORE INTO mcp_oauth_clients VALUES (?,?,?,?,?)",
                (self.issuer, CLIENT_ID, "http://127.0.0.1/callback", SCOPE, "none"),
            )
        self.load_client(CLIENT_ID)

    def load_client(self, client_id: str) -> FixedClient:
        if client_id != CLIENT_ID:
            _reject("invalid_client")
        with self.accounts._connection() as db:
            row = db.execute(
                "SELECT * FROM mcp_oauth_clients WHERE issuer=? AND client_id=?",
                (self.issuer, client_id),
            ).fetchone()
            if row is None or (row["redirect_uri"], row["scope"], row["auth_method"]) != (
                "http://127.0.0.1/callback",
                SCOPE,
                "none",
            ):
                _reject("invalid_client")
        return FixedClient()

    @staticmethod
    def validate_redirect(redirect_uri: str) -> None:
        try:
            url = urlsplit(redirect_uri)
            port = url.port
            valid = (
                url.scheme == "http"
                and url.hostname == "127.0.0.1"
                and url.path == "/callback"
                and not url.query
                and not url.fragment
                and not url.username
                and not url.password
                and port != 0
                and redirect_uri == "http://127.0.0.1" + (f":{port}" if port else "") + "/callback"
            )
        except (TypeError, ValueError):
            valid = False
        if not valid:
            _reject("invalid_redirect_uri")

    def _resource(self, value: str | None) -> None:
        if value is not None and value != self.resource:
            _reject("invalid_target")

    @staticmethod
    def _scopes(scopes: Sequence[str]) -> None:
        if list(scopes) != [SCOPE]:
            _reject("invalid_scope")

    def _account(self, db: sqlite3.Connection, user_id: str) -> None:
        if not self.accounts._find(db, user_id)["enabled"]:
            _reject("access_denied")

    def _bound(self, row: sqlite3.Row) -> None:
        if (row["client_id"], row["issuer"], row["resource"], row["scope"]) != (
            CLIENT_ID,
            self.issuer,
            self.resource,
            SCOPE,
        ):
            _reject()

    def _current(self, row: sqlite3.Row | None) -> None:
        now = self.accounts._now()
        if row is None or not row["created_at"] <= now < row["expires_at"]:
            _reject()

    def _grant(self, db: sqlite3.Connection, grant_id: str) -> sqlite3.Row:
        row = db.execute("SELECT * FROM mcp_oauth_grants WHERE id=?", (grant_id,)).fetchone()
        self._current(row)
        assert row is not None
        self._bound(row)
        self._account(db, row["user_id"])
        if row["revoked"]:
            _reject()
        return row

    def create_request(
        self,
        *,
        user_id: str,
        client_id: str,
        redirect_uri: str,
        scopes: Sequence[str],
        code_challenge: str,
        code_challenge_method: str,
        resource: str | None = None,
        state: str | None = None,
        redirect_uri_provided_explicitly: bool = True,
    ) -> ConsentRequest:
        self.load_client(client_id)
        self.validate_redirect(redirect_uri)
        self._resource(resource)
        self._scopes(scopes)
        if (
            code_challenge_method != "S256"
            or not isinstance(code_challenge, str)
            or not _TOKEN.fullmatch(code_challenge)
        ):
            _reject("invalid_request")
        if state is not None and (not isinstance(state, str) or len(state) > 2048):
            _reject("invalid_request")
        now = self.accounts._now()
        request_id = str(uuid.uuid4())
        with self.accounts._connection() as db:
            self._account(db, user_id)
            db.execute(
                "INSERT INTO mcp_oauth_requests VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0)",
                (
                    request_id,
                    user_id,
                    client_id,
                    self.issuer,
                    self.resource,
                    SCOPE,
                    redirect_uri,
                    code_challenge,
                    state,
                    int(redirect_uri_provided_explicitly),
                    now,
                    now + CONSENT_TTL,
                ),
            )
            row = db.execute(
                "SELECT * FROM mcp_oauth_requests WHERE id=?", (request_id,)
            ).fetchone()
        log.info("mcp_oauth_consent_created", account_id=user_id)
        return _consent(row)

    def _request(self, db: sqlite3.Connection, request_id: str, user_id: str) -> sqlite3.Row:
        row = db.execute("SELECT * FROM mcp_oauth_requests WHERE id=?", (request_id,)).fetchone()
        self._current(row)
        assert row is not None
        self._bound(row)
        self._account(db, user_id)
        if row["user_id"] != user_id or row["consumed"]:
            _reject()
        return row

    def load_request(self, request_id: str, *, user_id: str) -> ConsentRequest:
        with self.accounts._connection() as db:
            return _consent(self._request(db, request_id, user_id))

    def issue_code(self, request_id: str, *, user_id: str, material_ids: Sequence[str]) -> str:
        if len(material_ids) > 256 or len(set(material_ids)) != len(material_ids):
            _reject("invalid_material")
        code, grant_id = secrets.token_urlsafe(32), str(uuid.uuid4())
        now = self.accounts._now()
        with self.accounts._connection() as db:
            request = self._request(db, request_id, user_id)
            for material_id in material_ids:
                row = db.execute(
                    "SELECT * FROM mcp_oauth_materials WHERE id=? AND user_id=? " "AND revoked=0",
                    (material_id, user_id),
                ).fetchone()
                if row is None:
                    _reject("invalid_material")
            db.execute(
                "INSERT INTO mcp_oauth_grants VALUES (?,?,?,?,?,?,?,?,0)",
                (
                    grant_id,
                    user_id,
                    request["client_id"],
                    self.issuer,
                    self.resource,
                    SCOPE,
                    now,
                    now + REFRESH_TTL,
                ),
            )
            db.executemany(
                "INSERT INTO mcp_oauth_grant_materials VALUES (?,?)",
                [(grant_id, material_id) for material_id in material_ids],
            )
            db.execute(
                "INSERT INTO mcp_oauth_codes VALUES (?,?,?,?,?,0)",
                (_digest(code), request_id, grant_id, now, now + CODE_TTL),
            )
            db.execute("UPDATE mcp_oauth_requests SET consumed=1 WHERE id=?", (request_id,))
        log.info("mcp_oauth_grant_created", account_id=user_id, grant_id=grant_id)
        return code

    def _code(self, db: sqlite3.Connection, code: str, client_id: str) -> CodeRecord:
        row = db.execute(
            "SELECT * FROM mcp_oauth_codes WHERE digest=?", (_digest(code),)
        ).fetchone()
        self._current(row)
        assert row is not None
        grant = self._grant(db, row["grant_id"])
        if row["consumed"] or grant["client_id"] != client_id:
            _reject()
        request = db.execute(
            "SELECT * FROM mcp_oauth_requests WHERE id=?", (row["request_id"],)
        ).fetchone()
        self._bound(request)
        return CodeRecord(grant["id"], _consent(request), row["expires_at"])

    def load_code(self, code: str, *, client_id: str) -> CodeRecord:
        with self.accounts._connection() as db:
            return self._code(db, code, client_id)

    def exchange_code(
        self,
        code: str,
        *,
        client_id: str,
        redirect_uri: str,
        code_verifier: str,
        resource: str | None = None,
    ) -> TokenPair:
        self._resource(resource)
        if not isinstance(code_verifier, str) or not _VERIFIER.fullmatch(code_verifier):
            _reject()
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode("ascii")).digest())
            .rstrip(b"=")
            .decode("ascii")
        )
        with self.accounts._connection() as db:
            record = self._code(db, code, client_id)
            if redirect_uri != record.request.redirect_uri or not hmac.compare_digest(
                challenge, record.code_challenge
            ):
                _reject()
            db.execute("UPDATE mcp_oauth_codes SET consumed=1 WHERE digest=?", (_digest(code),))
            tokens = self._issue_tokens(db, self._grant(db, record.grant_id))
        log.info("mcp_oauth_code_exchanged", grant_id=record.grant_id)
        return tokens

    def _issue_tokens(self, db: sqlite3.Connection, grant: sqlite3.Row) -> TokenPair:
        now = self.accounts._now()
        access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        access_expiry = min(now + ACCESS_TTL, grant["expires_at"])
        for raw, kind, expiry in (
            (access, "access", access_expiry),
            (refresh, "refresh", min(now + REFRESH_TTL, grant["expires_at"])),
        ):
            db.execute(
                "INSERT INTO mcp_oauth_tokens VALUES (?,?,?,?,?,0)",
                (_digest(raw), kind, grant["id"], now, expiry),
            )
        return TokenPair(access, refresh, int(access_expiry - now), SCOPE, self.resource)

    def _token(self, db: sqlite3.Connection, raw: str, kind: str) -> TokenRecord:
        row = db.execute(
            "SELECT * FROM mcp_oauth_tokens WHERE digest=? AND kind=?", (_digest(raw), kind)
        ).fetchone()
        self._current(row)
        assert row is not None
        grant = self._grant(db, row["grant_id"])
        if row["consumed"]:
            _reject()
        return TokenRecord(
            grant["id"],
            grant["user_id"],
            grant["client_id"],
            grant["issuer"],
            grant["resource"],
            (grant["scope"],),
            row["expires_at"],
        )

    def verify_access(self, token: str, *, resource: str) -> TokenRecord:
        self._resource(resource)
        with self.accounts._connection() as db:
            return self._token(db, token, "access")

    def load_refresh(self, token: str, *, client_id: str) -> TokenRecord:
        """SDK lookup also detects replay; revocation commits before rejection."""
        with self.accounts._connection() as db:
            record, replay = self._refresh(db, token, client_id)
        if replay:
            log.info("mcp_oauth_refresh_replay_revoked", grant_id=record.grant_id)
            _reject()
        return record

    def _refresh(
        self, db: sqlite3.Connection, token: str, client_id: str
    ) -> tuple[TokenRecord, bool]:
        row = db.execute(
            "SELECT * FROM mcp_oauth_tokens WHERE digest=? AND kind='refresh'", (_digest(token),)
        ).fetchone()
        self._current(row)
        assert row is not None
        grant = self._grant(db, row["grant_id"])
        if grant["client_id"] != client_id:
            _reject()
        replay = bool(row["consumed"])
        if replay:
            db.execute("UPDATE mcp_oauth_grants SET revoked=1 WHERE id=?", (grant["id"],))
        return (
            TokenRecord(
                grant["id"],
                grant["user_id"],
                grant["client_id"],
                grant["issuer"],
                grant["resource"],
                (grant["scope"],),
                row["expires_at"],
            ),
            replay,
        )

    def rotate_refresh(
        self,
        token: str,
        *,
        client_id: str,
        resource: str | None = None,
        scopes: Sequence[str] | None = None,
    ) -> TokenPair:
        self._resource(resource)
        if scopes is not None:
            self._scopes(scopes)
        with self.accounts._connection() as db:
            record, replay = self._refresh(db, token, client_id)
            if not replay:
                db.execute(
                    "UPDATE mcp_oauth_tokens SET consumed=1 WHERE digest=?", (_digest(token),)
                )
                tokens = self._issue_tokens(db, self._grant(db, record.grant_id))
        if replay:
            log.info("mcp_oauth_refresh_replay_revoked", grant_id=record.grant_id)
            _reject()
        log.info("mcp_oauth_refresh_rotated", grant_id=record.grant_id)
        return tokens

    def revoke_grant(self, grant_id: str, *, user_id: str) -> None:
        with self.accounts._connection() as db:
            row = db.execute(
                "SELECT user_id FROM mcp_oauth_grants WHERE id=? AND issuer=?",
                (grant_id, self.issuer),
            ).fetchone()
            if row is None or row["user_id"] != user_id:
                _reject("access_denied")
            db.execute("UPDATE mcp_oauth_grants SET revoked=1 WHERE id=?", (grant_id,))
        log.info("mcp_oauth_grant_revoked", grant_id=grant_id)

    def list_grants(self, user_id: str) -> list[Grant]:
        with self.accounts._connection() as db:
            self._account(db, user_id)
            return [
                _grant_record(row)
                for row in db.execute(
                    "SELECT * FROM mcp_oauth_grants WHERE user_id=? AND issuer=? ORDER BY created_at,id",
                    (user_id, self.issuer),
                )
            ]

    def approve_material(
        self,
        *,
        user_id: str,
        context_id: str,
        kind: str,
        object_id: str,
        sha256: str,
        classification: str,
    ) -> ApprovedMaterial:
        """Trusted operator assertion about exact frozen bytes; never expose as a tool."""
        for value in (context_id, kind, object_id):
            _label(value)
        if (
            classification not in {"public", "synthetic"}
            or not isinstance(sha256, str)
            or not _SHA.fullmatch(sha256)
        ):
            _reject("invalid_material")
        result = ApprovedMaterial(
            str(uuid.uuid4()), user_id, context_id, kind, object_id, sha256, classification
        )
        with self.accounts._connection() as db:
            self._account(db, user_id)
            db.execute(
                "UPDATE mcp_oauth_materials SET revoked=1 WHERE user_id=? AND context_id=? "
                "AND kind=? AND object_id=?",
                (user_id, context_id, kind, object_id),
            )
            db.execute(
                "INSERT INTO mcp_oauth_materials VALUES (?,?,?,?,?,?,?,0)",
                (result.id, user_id, context_id, kind, object_id, sha256, classification),
            )
        log.info("mcp_oauth_material_approved", account_id=user_id, material_id=result.id)
        return result

    def revoke_material(self, material_id: str) -> None:
        """Trusted operator revocation; grant selections can never revive this ID."""
        with self.accounts._connection() as db:
            db.execute("UPDATE mcp_oauth_materials SET revoked=1 WHERE id=?", (material_id,))
        log.info("mcp_oauth_material_revoked", material_id=material_id)

    def list_materials(self, user_id: str) -> list[ApprovedMaterial]:
        with self.accounts._connection() as db:
            self._account(db, user_id)
            return [
                _material(row)
                for row in db.execute(
                    "SELECT * FROM mcp_oauth_materials WHERE user_id=? AND revoked=0 ORDER BY id",
                    (user_id,),
                )
            ]

    def list_grant_materials(self, grant_id: str, *, user_id: str) -> list[ApprovedMaterial]:
        with self.accounts._connection() as db:
            if self._grant(db, grant_id)["user_id"] != user_id:
                _reject("access_denied")
            return [
                _material(row)
                for row in db.execute(
                    "SELECT m.* FROM mcp_oauth_materials m JOIN mcp_oauth_grant_materials g "
                    "ON g.material_id=m.id WHERE g.grant_id=? AND m.user_id=? AND m.revoked=0 ORDER BY m.id",
                    (grant_id, user_id),
                )
            ]

    def authorize_material(
        self,
        grant_id: str,
        *,
        user_id: str,
        context_id: str,
        kind: str,
        object_id: str,
        sha256: str,
    ) -> ApprovedMaterial:
        for material in self.list_grant_materials(grant_id, user_id=user_id):
            if (material.context_id, material.kind, material.object_id, material.sha256) == (
                context_id,
                kind,
                object_id,
                sha256,
            ):
                return material
        _reject("access_denied")
