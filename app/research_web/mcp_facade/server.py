"""SDK resource server assembly. Created only after the explicit feature gate."""

from urllib.parse import urlsplit

import httpx
from mcp.server import MCPServer
from mcp.server.auth.settings import AuthSettings
from mcp.server.transport_security import TransportSecuritySettings
from mcp.shared.exceptions import MCPError
from mcp.types import (
    INVALID_PARAMS,
    METHOD_NOT_FOUND,
    CallToolRequestParams,
    InitializeResult,
    ListToolsResult,
    ServerCapabilities,
)
from pydantic import AnyHttpUrl
from starlette.routing import Route

from .authorization_store import AuthorizationStore
from .backend import FrozenBackend
from .http_policy import BoundedHTTP, BoundedMCPMethods
from .models import SCOPE
from .oauth import OAuthProvider, OAuthVerifier, create_oauth_routes
from .tools import TOOL_ARGUMENTS, register_tools


async def tools_only(ctx, call_next):
    """Use the SDK public middleware hook to narrow its default capabilities."""
    if ctx.method not in {
        "initialize",
        "ping",
        "tools/list",
        "tools/call",
        "notifications/initialized",
        "notifications/cancelled",
    }:
        raise MCPError(METHOD_NOT_FOUND, "method_not_found")
    if ctx.method == "tools/call":
        params = CallToolRequestParams.model_validate(ctx.params or {}, by_name=False)
        if params.name not in TOOL_ARGUMENTS:
            raise MCPError(METHOD_NOT_FOUND, "tool_not_found")
        if set(params.arguments or {}) - TOOL_ARGUMENTS[params.name]:
            raise MCPError(INVALID_PARAMS, "unsupported_tool_arguments")
    result = await call_next(ctx)
    # SDK 2.2's inner handler serializes before returning to public middleware.
    # Revalidate its wire result with SDK models before narrowing the policy.
    if ctx.method == "initialize":
        initialized = InitializeResult.model_validate(result, by_name=False)
        return initialized.model_copy(
            update={"capabilities": ServerCapabilities(tools=initialized.capabilities.tools)}
        )
    if ctx.method == "tools/list":
        listed = ListToolsResult.model_validate(result, by_name=False)
        return listed.model_copy(
            update={
                "tools": [
                    tool.model_copy(
                        update={
                            "input_schema": {**tool.input_schema, "additionalProperties": False}
                        }
                    )
                    for tool in listed.tools
                ]
            }
        )
    return result


class Facade:
    def __init__(self, accounts, pool, origin):
        self.store = AuthorizationStore(accounts, issuer=origin)
        self.client = httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=20)
        self.server = MCPServer(
            "Research Workbench readonly",
            token_verifier=OAuthVerifier(self.store),
            auth=AuthSettings(
                issuer_url=origin,
                resource_server_url=self.store.resource,
                required_scopes=[SCOPE],
                validate_token_resource=True,
            ),
        )
        self.server.middleware.append(tools_only)
        self.backend = FrozenBackend(pool, self.client)
        register_tools(self.server, self.store, self.backend)
        self.routes = create_oauth_routes(OAuthProvider(self.store))
        security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[urlsplit(origin).netloc],
            allowed_origins=[origin],
        )
        app = self.server.streamable_http_app(
            streamable_http_path="/mcp",
            stateless_http=True,
            json_response=True,
            transport_security=security,
        )
        # Compose the public Starlette route without changing SDK middleware,
        # POST dispatch, session management, or private SDK implementation.
        app.routes[:] = [
            (
                Route(
                    route.path,
                    BoundedMCPMethods(
                        route.app,
                        security,
                        required_scopes=[SCOPE],
                        resource_metadata_url=AnyHttpUrl(
                            origin + "/.well-known/oauth-protected-resource/mcp"
                        ),
                    ),
                    methods=route.methods,
                    name=route.name,
                )
                if isinstance(route, Route) and route.path == "/mcp"
                else route
            )
            for route in app.routes
        ]
        self.app = BoundedHTTP(app)
