"""Single-client identity handoff to WeKnora's native OIDC/userinfo client.

The existing account cookie authenticates the user. Neither knowledge tokens nor
RWB passwords cross the browser bridge. This does not authorize DataHub access.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse

from core.observability import get_logger

from ..knowledge_backend.storage import KnowledgeStore
from .accounts import AccountError
from .fingpt_config import FinGPTConfig as FinGPTConfig

log = get_logger(__name__)
PREFIX = "/api/server/fingpt"
CLIENT = "rwb-fingpt"
MACHINE = {PREFIX + "/token", PREFIX + "/userinfo", "/.well-known/openid-configuration"}
HEADERS = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}


def account_root(pool, user_id):
    """Same attached-primary and private-account directories as the Host pool."""
    if user_id == getattr(pool, "primary_user_id", None):
        return pool.binding.data_root
    private = getattr(pool, "private_pool", pool)
    return private.config.root / "users" / user_id / "research-web"


def bound_identity(pool, config, user_id):
    root = account_root(pool, user_id)
    if not root.is_dir():
        raise AccountError("fingpt_account_not_bound", 409)
    binding = KnowledgeStore(root).binding()
    if not binding or binding.get("origin") != config.origin:
        raise AccountError("fingpt_account_not_bound", 409)
    email = binding.get("sso_email")
    if not isinstance(email, str) or "@" not in email or len(email) > 254:
        raise AccountError("fingpt_identity_link_required", 409)
    # Email is captured only from authenticated /auth/me, never an RWB username
    # or request parameter. Native WeKnora resolves its original user by email.
    return {"sub": user_id, "email": email, "name": email.split("@")[0]}, (
        binding["user_id"],
        binding["workspace_id"],
        email,
    )


class FinGPTIdentity:
    def __init__(self, accounts, pool, config, issuer):
        self.accounts, self.pool, self.config = accounts, pool, config
        self.issuer = issuer
        with accounts._connection() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS fingpt_login_tokens ("
                "digest TEXT PRIMARY KEY, kind TEXT NOT NULL, session_hash TEXT NOT NULL, "
                "user_id TEXT NOT NULL, identity TEXT NOT NULL, expires REAL NOT NULL)"
            )

    @staticmethod
    def digest(value):
        return hashlib.sha256(value.encode()).hexdigest()

    def issue(self, session, kind, ttl):
        user = self.accounts.authenticate(session)
        if user is None:
            raise AccountError("login_required", 401)
        _, identity = bound_identity(self.pool, self.config, user.id)
        token = secrets.token_urlsafe(32)
        with self.accounts._connection() as db:
            now = self.accounts._now()
            db.execute("DELETE FROM fingpt_login_tokens WHERE expires <= ?", (now,))
            db.execute(
                "INSERT INTO fingpt_login_tokens VALUES (?,?,?,?,?,?)",
                (
                    self.digest(token),
                    kind,
                    self.digest(session),
                    user.id,
                    json.dumps(identity),
                    now + ttl,
                ),
            )
        return token

    def resolve(self, token, kind, *, consume=False):
        with self.accounts._connection() as db:
            row = db.execute(
                "SELECT t.* FROM fingpt_login_tokens t JOIN sessions s "
                "ON s.token_hash=t.session_hash JOIN accounts a ON a.id=t.user_id "
                "WHERE t.digest=? AND t.kind=? AND t.expires>? "
                "AND s.user_id=t.user_id AND s.expires_at>? AND a.enabled=1",
                (self.digest(token), kind, self.accounts._now(), self.accounts._now()),
            ).fetchone()
            if row is None:
                raise AccountError("invalid_grant", 401)
            claims, identity = bound_identity(self.pool, self.config, row["user_id"])
            if json.loads(row["identity"]) != list(identity):
                raise AccountError("fingpt_identity_changed", 401)
            if consume:
                db.execute("DELETE FROM fingpt_login_tokens WHERE digest=?", (self.digest(token),))
            return claims, row["session_hash"], row["user_id"], row["identity"]

    def exchange(self, code):
        claims, session_hash, user_id, identity = self.resolve(code, "code", consume=True)
        token = secrets.token_urlsafe(32)
        with self.accounts._connection() as db:
            db.execute(
                "INSERT INTO fingpt_login_tokens VALUES (?,?,?,?,?,?)",
                (
                    self.digest(token),
                    "access",
                    session_hash,
                    user_id,
                    identity,
                    self.accounts._now() + 60,
                ),
            )
        log.info("fingpt_identity_exchanged", user_id=claims["sub"])
        return token

    def navigation(self, request):
        q = request.query_params
        return (
            request.method == "GET"
            and request.url.path == PREFIX + "/authorize"
            and q.getlist("client_id") == [CLIENT]
            and q.getlist("redirect_uri") == [self.config.callback]
        )

    async def discovery(self):
        # Native WeKnora explicitly supports authenticated userinfo without
        # id_token. No JWT signing/discovery service is introduced here.
        return JSONResponse(
            {
                "issuer": self.issuer,
                "authorization_endpoint": self.issuer + PREFIX + "/authorize",
                "token_endpoint": self.issuer + PREFIX + "/token",
                "userinfo_endpoint": self.issuer + PREFIX + "/userinfo",
                "response_types_supported": ["code"],
                "grant_types_supported": ["authorization_code"],
                "token_endpoint_auth_methods_supported": ["client_secret_post"],
                "scopes_supported": ["openid", "email", "profile"],
            },
            headers=HEADERS,
        )

    async def workspace(self, request: Request):
        bound_identity(self.pool, self.config, request.state.user.id)
        return {"enabled": True, "entry": self.config.origin + "/rwb-fingpt.html"}

    async def authorize(self, request: Request):
        q = request.query_params
        if (
            not self.navigation(request)
            or q.getlist("response_type") != ["code"]
            or len(q.getlist("state")) != 1
            or not 1 <= len(q["state"]) <= 8192
            or q.getlist("scope") != ["openid email profile"]
        ):
            raise AccountError("invalid_request")
        code = self.issue(request.cookies.get("rwb_session", ""), "code", 60)
        return RedirectResponse(
            self.config.callback + "?" + urlencode({"code": code, "state": q["state"]}),
            status_code=302,
            headers=HEADERS,
        )

    async def token(self, request: Request):
        form = await request.form()
        expected = {
            "client_id": CLIENT,
            "redirect_uri": self.config.callback,
            "grant_type": "authorization_code",
        }
        if (
            any(form.getlist(k) != [v] for k, v in expected.items())
            or len(form.getlist("client_secret")) != 1
            or not hmac.compare_digest(str(form["client_secret"]), self.config.client_secret)
            or len(form.getlist("code")) != 1
        ):
            raise AccountError("invalid_client", 401)
        return JSONResponse(
            {
                "access_token": self.exchange(str(form["code"])),
                "token_type": "Bearer",
                "expires_in": 60,
            },
            headers=HEADERS,
        )

    async def userinfo(self, request: Request):
        bearer = request.headers.get("authorization", "")
        if not bearer.startswith("Bearer ") or len(bearer) > 256:
            raise AccountError("invalid_token", 401)
        claims, *_ = self.resolve(bearer[7:], "access")
        return JSONResponse(claims, headers=HEADERS)
