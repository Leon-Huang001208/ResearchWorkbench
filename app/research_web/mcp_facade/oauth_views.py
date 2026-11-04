"""Account-bound consent and app revocation, using existing browser sessions."""

from html import escape
from urllib.parse import urlencode, urlsplit

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route

from app.research_web.multiuser.accounts import AccountError
from core.observability import get_logger

from .authorization_store import AuthorizationStore

log = get_logger(__name__)
COOKIE = "rwb_session"
HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
    "X-Content-Type-Options": "nosniff",
}


def validated_login_return(value: str | None) -> str | None:
    """Narrow existing /auth UI handoff; SDK revalidates all OAuth parameters."""
    if not value or len(value) > 8192 or any(ord(char) < 32 for char in value) or "\\" in value:
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.fragment
        or parsed.path != "/authorize"
        or not parsed.query
    ):
        return None
    return value


def callback_response(
    store: AuthorizationStore, uri: str, *, state: str | None, **result: str
) -> RedirectResponse:
    store.validate_redirect(uri)
    query = {**result, "iss": store.issuer}
    if state is not None:
        query["state"] = state
    return RedirectResponse(uri + "?" + urlencode(query), status_code=302, headers=HEADERS)


def create_browser_routes(store: AuthorizationStore) -> list[Route]:
    def user_for(request: Request):
        user = store.accounts.authenticate(request.cookies.get(COOKIE, ""))
        if user is None:
            raise AccountError("authentication_required", 401)
        if request.method == "POST" and (
            request.headers.get("origin") != store.issuer
            or request.headers.get("sec-fetch-site", "same-origin") not in ("same-origin", "none")
        ):
            raise AccountError("csrf_rejected", 403)
        return user

    def error(exc: AccountError) -> JSONResponse:
        log.info("mcp_oauth_browser_rejected", code=exc.code)
        return JSONResponse({"error": exc.code}, status_code=exc.status, headers=HEADERS)

    async def consent(request: Request) -> Response:
        try:
            user = user_for(request)
            data = request.query_params if request.method == "GET" else await request.form()
            if len(data.getlist("request_id")) != 1:
                raise AccountError("invalid_request")
            pending = store.load_request(str(data["request_id"]), user_id=user.id)
            if request.method == "POST":
                if len(data.getlist("decision")) != 1:
                    raise AccountError("invalid_request")
                if data["decision"] == "deny":
                    return callback_response(
                        store, pending.redirect_uri, state=pending.state, error="access_denied"
                    )
                if data["decision"] != "allow":
                    raise AccountError("invalid_request")
                code = store.issue_code(
                    pending.id,
                    user_id=user.id,
                    material_ids=[str(item) for item in data.getlist("material_id")],
                )
                return callback_response(
                    store, pending.redirect_uri, state=pending.state, code=code
                )
            materials = store.list_materials(user.id)
            choices = "".join(
                '<label><input type="checkbox" name="material_id" value="'
                + escape(item.id, quote=True)
                + '">'
                + escape(item.kind + " / " + item.context_id + " / " + item.object_id)
                + "</label><br>"
                for item in materials
            )
            return HTMLResponse(
                '<!doctype html><html lang="zh"><meta charset="utf-8"><title>RWB 授权</title>'
                "<h1>授权 RWB 只读应用</h1><p>当前账号："
                + escape(user.username)
                + "</p><p>仅允许读取下列已批准的公开或合成资料。未勾选资料不可读取；不允许运行研究或调用模型。</p>"
                '<form method="post" action="/mcp/consent"><input type="hidden" name="request_id" value="'
                + escape(pending.id, quote=True)
                + '">'
                + choices
                + '<button name="decision" value="allow">允许所选资料</button>'
                '<button name="decision" value="deny">拒绝</button></form></html>',
                headers=HEADERS,
            )
        except AccountError as exc:
            return error(exc)

    async def applications(request: Request) -> Response:
        try:
            user = user_for(request)
            if request.method == "POST":
                data = await request.form()
                if len(data.getlist("grant_id")) != 1:
                    raise AccountError("invalid_request")
                store.revoke_grant(str(data["grant_id"]), user_id=user.id)
                return RedirectResponse("/mcp/applications", status_code=303, headers=HEADERS)
            rows = "".join(
                "<li>RWB readonly — "
                + (
                    "已撤销"
                    if grant.revoked
                    else "已过期" if grant.expires_at <= store.accounts.clock() else "已授权"
                )
                + '<form method="post" action="/mcp/applications"><input type="hidden" name="grant_id" value="'
                + escape(grant.id, quote=True)
                + '"><button>撤销授权</button></form></li>'
                for grant in store.list_grants(user.id)
            )
            return HTMLResponse(
                '<!doctype html><html lang="zh"><meta charset="utf-8"><title>已授权应用</title>'
                "<h1>已授权应用</h1><p>"
                + escape(user.username)
                + "</p><ul>"
                + rows
                + "</ul></html>",
                headers=HEADERS,
            )
        except AccountError as exc:
            return error(exc)

    return [
        Route("/mcp/consent", consent, methods=["GET", "POST"]),
        Route("/mcp/applications", applications, methods=["GET", "POST"]),
    ]
