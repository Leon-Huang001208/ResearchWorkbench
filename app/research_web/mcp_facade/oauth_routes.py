"""Thin SDK route adapters for fixed-client policy and known SDK 2.2 gaps."""

import json
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from mcp.server.auth.handlers.authorize import AuthorizationHandler
from mcp.server.auth.handlers.revoke import RevocationHandler
from mcp.server.auth.handlers.token import RefreshTokenRequest, TokenHandler, token_request_adapter
from mcp.server.auth.middleware.client_auth import ClientAuthenticator
from mcp.server.auth.routes import build_metadata, create_auth_routes
from mcp.server.auth.settings import ClientRegistrationOptions, RevocationOptions
from mcp.server.transport_security import RequestBodyLimitMiddleware
from pydantic import AnyHttpUrl, ConfigDict, TypeAdapter, ValidationError
from starlette.datastructures import FormData
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route, request_response

from app.research_web.multiuser.accounts import AccountError
from core.observability import get_logger

from .models import CLIENT_ID, SCOPE, WEKNORA_CLIENT_ID
from .oauth import OAuthProvider, browser_account, token_request
from .oauth_views import COOKIE, HEADERS, create_browser_routes

log = get_logger(__name__)
MAX_REQUEST_BYTES = 64 * 1024


def _error(code: str, status: int = 400) -> Response:
    return JSONResponse({"error": code}, status_code=status, headers=HEADERS)


def _safe_sdk_response(response: Response, provider: OAuthProvider) -> Response:
    """SDK validation descriptions can contain input values; never echo them."""
    if response.status_code >= 400:
        try:
            code = json.loads(bytes(response.body)).get("error", "invalid_request")
        except (ValueError, TypeError):
            code = "invalid_request"
        return _error(code, response.status_code)
    location = response.headers.get("location")
    if location:
        parsed = urlsplit(location)
        base = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
        if not provider.store.is_callback_destination(base):
            if base not in {"/auth", "/mcp/consent"} or parsed.fragment:
                return _error("invalid_request")
            response.headers.update(HEADERS)
            return response
        query = parse_qsl(parsed.query, keep_blank_values=True)
        if any(key in ("code", "error") for key, _ in query):
            query = [
                (key, value) for key, value in query if key not in ("iss", "error_description")
            ]
            query.append(("iss", provider.store.issuer))
            response.headers["location"] = base + "?" + urlencode(query)
    response.headers.update(HEADERS)
    return response


class _PublicRevocationRequest(Request):
    """SDK 2.2 requires a nullable client_secret field even for public clients.

    Supply only the missing None to the original SDK handler via Request's public
    form interface. No wire credential is requested, fabricated, or persisted.
    """

    async def form(self, **kwargs) -> FormData:  # type: ignore[override]
        form = await super().form(**kwargs)
        if "client_secret" not in form:
            # FormData's annotation excludes None; this SDK-required sentinel
            # exists only in the adapter and never represents uploaded content.
            return FormData([*form.multi_items(), ("client_secret", None)])  # type: ignore[list-item]
        return form


def create_routes(provider: OAuthProvider) -> list[Route]:
    issuer = TypeAdapter(
        AnyHttpUrl, config=ConfigDict(url_preserve_empty_path=True)
    ).validate_python(provider.store.issuer)
    registration = ClientRegistrationOptions(
        enabled=False, valid_scopes=[SCOPE], default_scopes=[SCOPE]
    )
    revocation = RevocationOptions(enabled=True)
    routes = create_auth_routes(
        provider,
        issuer,
        client_registration_options=registration,
        revocation_options=revocation,
        identity_assertion_enabled=False,
    )
    metadata = build_metadata(issuer, None, registration, revocation)
    metadata.token_endpoint_auth_methods_supported = ["none"]
    metadata.revocation_endpoint_auth_methods_supported = ["none"]
    metadata.client_id_metadata_document_supported = False
    metadata.authorization_response_iss_parameter_supported = True
    authenticator = ClientAuthenticator(provider)
    authorize_handler = AuthorizationHandler(provider)
    token_handler = TokenHandler(provider, authenticator)
    revoke_handler = RevocationHandler(provider, authenticator)

    async def metadata_endpoint(request: Request) -> Response:
        return JSONResponse(metadata.model_dump(mode="json", exclude_none=True), headers=HEADERS)

    async def authorize_endpoint(request: Request) -> Response:
        if request.method == "POST" and request.headers.get("origin") != provider.store.issuer:
            return _error("csrf_rejected", 403)
        data = request.query_params if request.method == "GET" else await request.form()
        # Check raw callback spelling before AnyUrl normalizes it.
        client_id = str(data.get("client_id", CLIENT_ID))
        if client_id == WEKNORA_CLIENT_ID and "redirect_uri" not in data:
            return _error("invalid_request")
        if "redirect_uri" in data:
            try:
                provider.store.validate_redirect(str(data["redirect_uri"]), client_id=client_id)
            except AccountError:
                return _error("invalid_request")
        user = provider.store.accounts.authenticate(request.cookies.get(COOKIE, ""))
        marker = browser_account.set(user)
        try:
            return _safe_sdk_response(await authorize_handler.handle(request), provider)
        finally:
            browser_account.reset(marker)

    async def token_endpoint(request: Request) -> Response:
        data = dict(await request.form())
        if (
            data.get("client_id") == WEKNORA_CLIENT_ID
            and data.get("grant_type") == "authorization_code"
        ):
            try:
                provider.store.validate_redirect(
                    str(data.get("redirect_uri", "")), client_id=WEKNORA_CLIENT_ID
                )
            except AccountError:
                return _error("invalid_grant")
        try:
            parsed = token_request_adapter.validate_python(data)
        except ValidationError:
            return _safe_sdk_response(await token_handler.handle(request), provider)
        if parsed.resource not in (None, provider.store.resource):
            return _error("invalid_target")
        if (
            isinstance(parsed, RefreshTokenRequest)
            and parsed.scope is not None
            and parsed.scope != SCOPE
        ):
            return _error("invalid_scope")
        marker = token_request.set(parsed)
        try:
            return _safe_sdk_response(await token_handler.handle(request), provider)
        finally:
            token_request.reset(marker)

    async def revoke_endpoint(request: Request) -> Response:
        # The guard below has consumed/cached the form. Use a bounded public
        # receive replay so the SDK adapter reads the same original wire bytes.
        body = await request.body()
        sent = False

        async def receive():
            nonlocal sent
            if sent:
                return {"type": "http.disconnect"}
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        adapted = _PublicRevocationRequest(request.scope, receive)
        return _safe_sdk_response(await revoke_handler.handle(adapted), provider)

    endpoints = {
        "/.well-known/oauth-authorization-server": metadata_endpoint,
        "/authorize": authorize_endpoint,
        "/token": token_endpoint,
        "/revoke": revoke_endpoint,
    }

    def guarded(endpoint, *, browser: bool = False):
        async def handle(request: Request) -> Response:
            if request.headers.get("host") != urlsplit(provider.store.issuer).netloc:
                return _error("invalid_request", 400)
            origin = request.headers.get("origin")
            if origin is not None and origin != provider.store.issuer:
                return _error("invalid_request", 403)
            try:
                if not browser:
                    if request.method == "POST":
                        await request.body()  # bounded by the outer SDK middleware
                    data = request.query_params if request.method == "GET" else await request.form()
                    if len(data.multi_items()) != len(data):
                        return _error("invalid_request")
                    if "client_secret" in data or request.headers.get("authorization"):
                        return _error("invalid_client")
                response = await endpoint(request)
                if len(response.body) > 256 * 1024:
                    log.warning("mcp_oauth_response_limit_exceeded")
                    return _error("response_limit_exceeded", 503)
                return response
            except AccountError:
                log.warning("mcp_oauth_storage_unavailable")
                return _error("temporarily_unavailable", 503)
            except HTTPException:
                log.info("mcp_oauth_form_rejected")
                return _error("invalid_request")

        return handle

    result = []
    for route in routes:
        endpoint = guarded(endpoints[route.path])
        app = RequestBodyLimitMiddleware(request_response(endpoint), MAX_REQUEST_BYTES)
        if route.path != "/authorize":
            app = CORSMiddleware(
                app,
                allow_origins=[provider.store.issuer],
                allow_methods=sorted(route.methods or []),
                allow_headers=["MCP-Protocol-Version"],
            )
        result.append(Route(route.path, app, methods=route.methods))
    for route in create_browser_routes(provider.store):
        result.append(
            Route(
                route.path,
                RequestBodyLimitMiddleware(
                    request_response(guarded(route.endpoint, browser=True)), MAX_REQUEST_BYTES
                ),
                methods=route.methods,
            )
        )
    return result
