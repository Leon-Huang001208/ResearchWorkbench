"""Authenticated, fixed-target gateway for private per-user Research Web stacks."""

from __future__ import annotations

import asyncio
import re
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from core.observability import get_logger

from ..ai_news_routes import router as ai_news_router
from ..ai_news_service import create_ai_news_service
from ..aihot_routes import router as aihot_router
from .accounts import SESSION_TTL_SECONDS, AccountError, AccountStore
from .origin import validate_origin
from .runtime import RuntimeErrorSafe

log = get_logger(__name__)
UI = Path(__file__).resolve().parents[1] / "ui"
COOKIE = "rwb_session"
KEY_HEADER = "X-RWB-Tenant-Gateway-Key"
MAX_REQUEST_BYTES = 32 * 1024 * 1024
AI_PREFIXES = ("/api/research/ai-news", "/api/research/aihot")
AI_FEED = re.compile(
    r"/api/research/ai-news/feeds/(?:selected|selected-full|all|daily|weekly|monthly)\.xml\Z"
)
REQUEST_HEADERS = {
    "accept",
    "accept-encoding",
    "content-type",
    "range",
    "if-none-match",
    "idempotency-key",
}
RESPONSE_HEADERS = {
    "content-type",
    "content-length",
    "content-disposition",
    "content-encoding",
    "etag",
    "accept-ranges",
    "content-range",
    "last-modified",
    "content-security-policy",
    "x-frame-options",
}


def error(code: str, status: int) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": code}}, status_code=status)


def ai_path(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in AI_PREFIXES)


def page_matches(request: Request, user) -> bool:
    """Keep an old tab from submitting to a newly logged-in account."""
    values = (request.headers.get("X-RWB-Page-User"), request.query_params.get("rwb_user"))
    return not any(value is not None and value != user.id for value in values) and (
        request.method in {"GET", "HEAD"} or user.id in values
    )


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(StrictBody):
    username: str = Field(max_length=64)
    password: str = Field(max_length=1024)


class NewUser(Login):
    role: str = "user"


class UserStatus(StrictBody):
    enabled: bool = Field(strict=True)


class NewPassword(StrictBody):
    password: str = Field(max_length=1024)


def create_gateway(
    accounts: AccountStore,
    pool,
    *,
    origin: str,
    upstream: httpx.AsyncClient | None = None,
    ai_news_factory=None,
) -> FastAPI:
    """Build one gateway without starting tenant processes or reading model secrets."""
    origin = validate_origin(origin)
    authority = urlsplit(origin).netloc
    secure = origin.startswith("https:")
    client = upstream or httpx.AsyncClient(
        timeout=httpx.Timeout(30, read=None), follow_redirects=False, trust_env=False
    )

    @asynccontextmanager
    async def lifespan(app):
        try:
            if hasattr(pool, "start"):
                await pool.start()
            yield
        finally:
            await pool.close()
            await client.aclose()

    app = FastAPI(title="Research Workbench Private Server", lifespan=lifespan)
    app.state.accounts = accounts
    app.state.pool = pool
    # One server-owned news store, outside every user's DSH/data/credential namespace.
    # Constructing the default bridge does no I/O and never starts a runtime or DB.
    app.state.ai_news = (ai_news_factory or create_ai_news_service)(
        Path(__file__).resolve().parents[3], accounts.root / "shared"
    )
    app.state.aihot = app.state.ai_news.reader
    app.include_router(aihot_router)
    app.include_router(ai_news_router)

    def original_reading(request: Request) -> bool:
        user = request.state.user
        return (
            user is not None
            and user.id == getattr(pool, "primary_user_id", None)
            and request.url.path.startswith("/api/research/aihot/")
        )

    @app.exception_handler(AccountError)
    async def account_error(request, exc):
        return error(exc.code, exc.status)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return error("invalid_request", 422)

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        log.error("multiuser_request_failed", error_type=type(exc).__name__)
        return error("server_request_failed", 503)

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        maintenance = getattr(pool, "maintenance_path", None)
        if (
            maintenance is not None
            and (maintenance.exists() or maintenance.is_symlink())
            and request.method not in {"GET", "HEAD"}
            and request.url.path not in {"/api/server/login", "/api/server/logout"}
        ):
            return error("server_maintenance", 503)
        if request.headers.get("host", "").lower() != authority:
            return error("server_host_denied", 403)
        supplied_origin = request.headers.get("origin")
        if (
            (supplied_origin is not None and supplied_origin != origin)
            or request.headers.get("sec-fetch-site") == "cross-site"
            or (request.method not in {"GET", "HEAD"} and supplied_origin != origin)
        ):
            return error("server_origin_denied", 403)
        raw_path = request.scope.get("raw_path", b"").split(b"?", 1)[0].lower()
        if any(value in raw_path for value in (b"%2f", b"%5c", b"%00", b"%2e", b"\\")):
            return error("server_path_denied", 403)
        if request.url.path.startswith("/static/") and request.url.path.endswith(".html"):
            return error("server_entry_required", 403)
        try:
            length = int(request.headers.get("content-length", "0"))
        except ValueError:
            return error("invalid_request", 400)
        if length < 0 or length > MAX_REQUEST_BYTES:
            return error("request_too_large", 413)
        public = request.url.path in {
            "/auth",
            "/api/server/login",
            "/api/server/logout",
            "/api/server/health",
        } or request.url.path.startswith(("/static/", "/server-static/"))
        try:
            user = await asyncio.to_thread(accounts.authenticate, request.cookies.get(COOKIE, ""))
            request.state.user = user
            if user is None and not public:
                if request.url.path in {"/", "/account"}:
                    return RedirectResponse("/auth", status_code=303)
                return error("login_required", 401)
            news = ai_path(request.url.path)
            news_admin = request.url.path in {
                "/api/research/ai-news/status",
                "/api/research/ai-news/control",
            }
            if news:
                if user is None:
                    return error("login_required", 401)
                # Tailscale terminates HTTPS before this loopback HTTP gateway. RSS links
                # use the operator-validated origin scheme, never forwarded browser headers.
                request.scope["scheme"] = urlsplit(origin).scheme
                if "//" in request.url.path or "\\" in request.url.path:
                    return error("server_path_denied", 403)
                if not page_matches(request, user):
                    return error("account_changed", 401)
                if news_admin:
                    if user.role != "admin":
                        log.warning("multiuser_ai_news_admin_denied", user_id=user.id)
                        return error("administrator_required", 403)
                    expected = "POST" if request.url.path.endswith("/control") else "GET"
                    if request.method != expected:
                        return error("method_not_allowed", 405)
                elif not (
                    request.method in {"GET", "HEAD"}
                    and (
                        request.url.path.startswith("/api/research/aihot/")
                        or AI_FEED.fullmatch(request.url.path)
                    )
                ):
                    return error("not_found", 404)
            if (request.url.path.startswith("/api/server/") or news) and request.method not in {
                "GET",
                "HEAD",
            }:
                maximum = 65536 if news else 16384
                if length > maximum:
                    return error("request_too_large", 413)
                parts = []
                size = 0
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > maximum:
                        return error("request_too_large", 413)
                    parts.append(chunk)
                # Starlette's cached request replays this bounded body to the route.
                request._body = b"".join(parts)
                if user is not None:
                    fresh = await asyncio.to_thread(
                        accounts.authenticate, request.cookies.get(COOKIE, "")
                    )
                    if fresh is None or fresh.id != user.id:
                        return error("login_required", 401)
                    request.state.user = fresh
                    if news_admin and fresh.role != "admin":
                        return error("administrator_required", 403)
                    if news_admin:
                        log.info("multiuser_ai_news_control_admitted", user_id=fresh.id)
            # Preserve the attached owner's original UI/API version pair. Shared
            # news rollout remains independent from this authentication cutover.
            response = (
                await proxy(request.url.path.lstrip("/"), request)
                if original_reading(request)
                else await call_next(request)
            )
            if news:
                # AI responses are bounded complete JSON/XML/image reads, not tenant SSE.
                fresh = await asyncio.to_thread(
                    accounts.authenticate, request.cookies.get(COOKIE, "")
                )
                if fresh is None or user is None or fresh.id != user.id:
                    return error("login_required", 401)
                if news_admin and fresh.role != "admin":
                    return error("administrator_required", 403)
        except AccountError as exc:
            response = error(exc.code, exc.status)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
            }
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self'; frame-src 'self'; object-src 'none'; frame-ancestors 'none'",
        )
        return response

    def admin(request: Request):
        user = request.state.user
        if user is None or user.role != "admin":
            raise AccountError("administrator_required", 403)
        return user

    @app.post("/api/server/login")
    async def login(body: Login):
        token, user = await asyncio.to_thread(accounts.login, body.username, body.password)
        response = JSONResponse({"user": user.public()})
        response.set_cookie(
            COOKIE,
            token,
            max_age=SESSION_TTL_SECONDS,
            httponly=True,
            secure=secure,
            samesite="strict",
            path="/",
        )
        log.info("multiuser_login", user_id=user.id)
        return response

    @app.post("/api/server/logout")
    async def logout(request: Request):
        await asyncio.to_thread(accounts.logout, request.cookies.get(COOKIE, ""))
        response = JSONResponse({"ok": True})
        response.delete_cookie(COOKIE, path="/", secure=secure, httponly=True, samesite="strict")
        return response

    @app.get("/api/server/me")
    async def me(request: Request):
        return {
            "user": request.state.user.public(),
            "primary": request.state.user.id == getattr(pool, "primary_user_id", None),
        }

    @app.get("/api/server/health")
    async def health():
        if hasattr(pool, "health"):
            try:
                return await pool.health()
            except RuntimeErrorSafe as exc:
                return error(exc.code, exc.status)
        return {"status": "ready", "runtime": "not_started_by_health"}

    @app.get("/api/server/users")
    async def users(request: Request):
        admin(request)
        return {
            "items": [u.public() for u in await asyncio.to_thread(accounts.list_users)],
            "primary_user_id": getattr(pool, "primary_user_id", None),
        }

    @app.post("/api/server/users", status_code=201)
    async def create_user(body: NewUser, request: Request):
        admin(request)
        user = await asyncio.to_thread(
            accounts.create_user, body.username, body.password, body.role
        )
        return {"user": user.public()}

    @app.patch("/api/server/users/{user_id}")
    async def set_enabled(user_id: str, body: UserStatus, request: Request):
        admin(request)
        if not body.enabled and user_id == getattr(pool, "primary_user_id", None):
            raise AccountError("primary_account_protected", 409)
        user = await asyncio.to_thread(accounts.set_enabled, user_id, body.enabled)
        if not user.enabled:
            await pool.stop(user.id)
        return {"user": user.public()}

    @app.post("/api/server/users/{user_id}/password")
    async def reset_password(user_id: str, body: NewPassword, request: Request):
        admin(request)
        await asyncio.to_thread(accounts.reset_password, user_id, body.password)
        return {"ok": True}

    @app.post("/api/server/users/{user_id}/stop")
    async def stop_user(user_id: str, request: Request):
        admin(request)
        user = await asyncio.to_thread(accounts.get_user, user_id)
        await pool.stop(user.id)
        return {"ok": True}

    @app.get("/auth")
    async def auth_page(request: Request):
        if request.state.user is not None:
            return RedirectResponse("/", status_code=303)
        return HTMLResponse((UI / "server-accounts.html").read_text(encoding="utf-8"))

    @app.get("/account")
    async def account_page():
        return HTMLResponse((UI / "server-accounts.html").read_text(encoding="utf-8"))

    @app.get("/")
    async def research_page(request: Request):
        ui = (
            getattr(pool, "primary_ui", UI)
            if request.state.user.id == getattr(pool, "primary_user_id", None)
            else UI
        )
        source = (ui / "index.html").read_text(encoding="utf-8")
        return HTMLResponse(
            source.replace('src="/static/app.mjs"', 'src="/server-static/session.mjs"')
        )

    current_static = StaticFiles(directory=UI)
    primary_static = StaticFiles(directory=getattr(pool, "primary_ui", UI))

    async def user_static(scope, receive, send):
        user = scope.get("state", {}).get("user")
        target = (
            primary_static
            if user is not None and user.id == getattr(pool, "primary_user_id", None)
            else current_static
        )
        await target(scope, receive, send)

    app.mount("/static", user_static, name="research-static")
    app.mount("/server-static", StaticFiles(directory=UI / "server"), name="server-static")

    @app.get("/{path:path}")
    @app.post("/{path:path}")
    @app.put("/{path:path}")
    @app.patch("/{path:path}")
    @app.delete("/{path:path}")
    @app.head("/{path:path}")
    async def proxy(path: str, request: Request):
        if ai_path(request.url.path) and not original_reading(request):
            # Unknown shared-news routes never allocate a per-user Web/DSH instance.
            return error("not_found", 404)
        if not path.startswith("api/research/") and not path.startswith("frameworks-embed/"):
            return error("not_found", 404)
        if path.startswith("api/research/internal/") or "//" in path or "\\" in path:
            return error("server_internal_route_denied", 403)
        user = request.state.user
        token = request.cookies.get(COOKIE, "")
        if not page_matches(request, user):
            return error("account_changed", 401)
        try:
            backend = await pool.backend_for(user.id)
        except RuntimeErrorSafe as exc:
            log.warning(
                "multiuser_backend_unavailable", error_type=type(exc).__name__, code=exc.code
            )
            return error(getattr(exc, "code", "runtime_unavailable"), getattr(exc, "status", 503))
        # Never forward browser cookies, Authorization, proxy headers or a chosen tenant key.
        headers = {k: v for k, v in request.headers.items() if k.lower() in REQUEST_HEADERS}
        if backend.key:
            headers[KEY_HEADER] = backend.key
        headers["Origin"] = backend.url
        parts = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > MAX_REQUEST_BYTES:
                return error("request_too_large", 413)
            parts.append(chunk)
        current = await asyncio.to_thread(accounts.authenticate, token)
        if current is None or current.id != user.id:
            return error("login_required", 401)
        query = httpx.QueryParams(request.url.query).remove("rwb_user")
        target = httpx.URL(backend.url + "/" + path).copy_with(query=str(query).encode())
        outbound = client.build_request(
            request.method, target, headers=headers, content=b"".join(parts)
        )
        # httpx's shared cookie jar may have learned a backend Set-Cookie.
        # Backend authentication is exclusively the per-instance header.
        outbound.headers.pop("cookie", None)
        try:
            response = await client.send(outbound, stream=True, follow_redirects=False)
        except httpx.HTTPError as exc:
            log.warning("multiuser_proxy_failed", error_type=type(exc).__name__)
            return error("runtime_unavailable", 503)
        if 300 <= response.status_code < 400:
            await response.aclose()
            return error("runtime_redirect_denied", 502)

        async def content():
            pending = None
            try:
                iterator = (
                    response.aiter_bytes() if response.is_stream_consumed else response.aiter_raw()
                ).__aiter__()
                while True:
                    if await asyncio.to_thread(accounts.authenticate, token) is None:
                        break
                    if pending is None:
                        pending = asyncio.create_task(anext(iterator))
                    done, _ = await asyncio.wait({pending}, timeout=1)
                    if not done:
                        continue
                    try:
                        chunk = pending.result()
                    except StopAsyncIteration:
                        break
                    pending = None
                    if await asyncio.to_thread(accounts.authenticate, token) is None:
                        break
                    yield chunk
            except httpx.HTTPError as exc:
                log.warning("multiuser_stream_failed", error_type=type(exc).__name__)
            finally:
                if pending is not None:
                    pending.cancel()
                    await asyncio.gather(pending, return_exceptions=True)
                await response.aclose()

        return StreamingResponse(
            content(),
            status_code=response.status_code,
            headers={k: v for k, v in response.headers.items() if k.lower() in RESPONSE_HEADERS},
        )

    return app
