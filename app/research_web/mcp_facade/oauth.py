"""SDK OAuth provider and bearer verifier over the reviewed durable store.

Request contexts exist only while SDK HTTP handlers run. They never cross a
background task or become credentials; the store rechecks all durable bindings.
"""

from contextvars import ContextVar
from urllib.parse import urlencode

from mcp.server.auth.handlers.token import (
    AuthorizationCodeRequest,
    RefreshTokenRequest,
    TokenRequest,
)
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    RegistrationError,
    TokenError,
    TokenVerifier,
)
from mcp.shared.auth import InvalidRedirectUriError, OAuthClientInformationFull, OAuthToken
from pydantic import AnyUrl

from app.research_web.multiuser.accounts import Account, AccountError
from core.observability import get_logger

from .authorization_store import AuthorizationStore
from .models import CLIENT_ID, NATIVE_CALLBACK, SCOPE, TokenPair, TokenRecord

log = get_logger(__name__)
token_request: ContextVar[TokenRequest | None] = ContextVar("rwb_oauth_token_request", default=None)
browser_account: ContextVar[Account | None] = ContextVar("rwb_oauth_browser_account", default=None)


class NativeClient(OAuthClientInformationFull):
    """RFC 8252 loopback port variation, with exactly one approved host/path."""

    def validate_redirect_uri(self, redirect_uri: AnyUrl | None) -> AnyUrl:
        uri = redirect_uri or AnyUrl(NATIVE_CALLBACK)
        try:
            AuthorizationStore.validate_native_redirect(str(uri))
        except AccountError as exc:
            raise InvalidRedirectUriError("Unregistered callback") from exc
        return uri


def _access(raw: str, record: TokenRecord) -> AccessToken:
    return AccessToken(
        token=raw,
        client_id=record.client_id,
        scopes=list(record.scopes),
        expires_at=int(record.expires_at),
        resource=record.resource,
        subject=record.user_id,
        claims={"iss": record.issuer, "grant_id": record.grant_id},
    )


def _pair(pair: TokenPair) -> OAuthToken:
    return OAuthToken(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        token_type="Bearer",
        expires_in=pair.expires_in,
        scope=pair.scope,
    )


def _token_error(exc: AccountError) -> TokenError:
    if exc.status < 500 and exc.code == "invalid_target":
        return TokenError("invalid_target")
    if exc.status < 500 and exc.code == "invalid_scope":
        return TokenError("invalid_scope")
    if _definitely_invalid_token(exc):
        return TokenError("invalid_grant")
    # A failed transaction does not prove an invalid credential. The HTTP
    # storage guard logs a stable event and emits 503 without redirect/retry.
    raise exc


def _definitely_invalid_token(exc: AccountError) -> bool:
    """Storage/security failures do not prove absence or successful revocation."""
    return exc.status < 500 and exc.code in {
        "invalid_grant",
        "access_denied",
        "account_not_found",
    }


class OAuthProvider(OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]):
    def __init__(self, store: AuthorizationStore):
        self.store = store

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        if not self.store.client_enabled(client_id):
            return None
        registered = self.store.load_client(client_id)
        model = NativeClient if client_id == CLIENT_ID else OAuthClientInformationFull
        return model(
            client_id=client_id,
            client_name="RWB readonly native client" if client_id == CLIENT_ID else "WeKnora",
            redirect_uris=[AnyUrl(uri) for uri in registered.redirect_uris],
            token_endpoint_auth_method="none",
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            scope=SCOPE,
        )

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        raise RegistrationError("invalid_client_metadata", "Registration disabled")

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        try:
            self.store.validate_redirect(str(params.redirect_uri), client_id=client.client_id)
            if params.resource not in (None, self.store.resource):
                raise AccountError("invalid_target")
            if params.scopes != [SCOPE]:
                raise AccountError("invalid_scope")
            user = browser_account.get()
            if user is None:
                # Re-enter the SDK after the existing login. Never store an unbound
                # consent request or let login redirect directly to a client URL.
                query = {
                    "client_id": client.client_id,
                    "response_type": "code",
                    "scope": SCOPE,
                    "code_challenge": params.code_challenge,
                    "code_challenge_method": "S256",
                }
                if params.redirect_uri_provided_explicitly:
                    query["redirect_uri"] = str(params.redirect_uri)
                if params.state is not None:
                    query["state"] = params.state
                if params.resource is not None:
                    query["resource"] = params.resource
                return "/auth?" + urlencode({"return_to": "/authorize?" + urlencode(query)})
            pending = self.store.create_request(
                user_id=user.id,
                client_id=client.client_id,
                redirect_uri=str(params.redirect_uri),
                scopes=params.scopes,
                code_challenge=params.code_challenge,
                code_challenge_method="S256",
                resource=params.resource,
                state=params.state,
                redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            )
            return "/mcp/consent?" + urlencode({"request_id": pending.id})
        except AccountError as exc:
            if exc.status < 500 and exc.code == "invalid_target":
                raise AuthorizeError("invalid_target") from exc
            if exc.status < 500 and exc.code == "invalid_scope":
                raise AuthorizeError("invalid_scope") from exc
            if _definitely_invalid_token(exc):
                raise AuthorizeError("access_denied") from exc
            if exc.status < 500 and exc.code == "invalid_request":
                raise AuthorizeError("invalid_request") from exc
            log.warning("mcp_oauth_authorization_storage_unavailable")
            raise AuthorizeError("temporarily_unavailable") from exc

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, raw: str
    ) -> AuthorizationCode | None:
        try:
            record = self.store.load_code(raw, client_id=client.client_id)
        except AccountError as exc:
            if not _definitely_invalid_token(exc):
                raise
            return None
        req = record.request
        return AuthorizationCode(
            code=raw,
            scopes=list(req.scopes),
            expires_at=record.expires_at,
            client_id=req.client_id,
            code_challenge=req.code_challenge,
            redirect_uri=AnyUrl(req.redirect_uri),
            redirect_uri_provided_explicitly=req.redirect_uri_provided_explicitly,
            resource=req.resource,
            subject=req.user_id,
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, code: AuthorizationCode
    ) -> OAuthToken:
        request = token_request.get()
        if (
            not isinstance(request, AuthorizationCodeRequest)
            or request.code != code.code
            or request.client_id != client.client_id
        ):
            raise TokenError("invalid_request")
        try:
            return _pair(
                self.store.exchange_code(
                    code.code,
                    client_id=client.client_id,
                    redirect_uri=(
                        str(request.redirect_uri)
                        if request.redirect_uri
                        else str(code.redirect_uri)
                    ),
                    code_verifier=request.code_verifier,
                    resource=request.resource,
                )
            )
        except AccountError as exc:
            raise _token_error(exc) from exc

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, raw: str
    ) -> RefreshToken | None:
        request = token_request.get()
        # This guard is before load_refresh: a replay lookup has a durable side
        # effect (family revocation). Revocation handler has no token context.
        if request is not None and (
            not isinstance(request, RefreshTokenRequest)
            or request.refresh_token != raw
            or request.client_id != client.client_id
            or request.resource not in (None, self.store.resource)
        ):
            return None
        try:
            record = self.store.load_refresh(raw, client_id=client.client_id)
        except AccountError as exc:
            if not _definitely_invalid_token(exc):
                raise
            return None
        return RefreshToken(
            token=raw,
            client_id=record.client_id,
            scopes=list(record.scopes),
            expires_at=int(record.expires_at),
            resource=record.resource,
            subject=record.user_id,
        )

    async def exchange_refresh_token(
        self, client: OAuthClientInformationFull, refresh: RefreshToken, scopes: list[str]
    ) -> OAuthToken:
        request = token_request.get()
        if (
            not isinstance(request, RefreshTokenRequest)
            or request.refresh_token != refresh.token
            or request.client_id != client.client_id
        ):
            raise TokenError("invalid_request")
        try:
            return _pair(
                self.store.rotate_refresh(
                    refresh.token,
                    client_id=client.client_id,
                    resource=request.resource,
                    scopes=scopes,
                )
            )
        except AccountError as exc:
            raise _token_error(exc) from exc

    async def load_access_token(self, token: str) -> AccessToken | None:
        return await OAuthVerifier(self.store).verify_token(token)

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        try:
            record = (
                self.store.verify_access(token.token, resource=self.store.resource)
                if isinstance(token, AccessToken)
                else self.store.load_refresh(token.token, client_id=token.client_id)
            )
            self.store.revoke_grant(record.grant_id, user_id=record.user_id)
        except AccountError as exc:
            if not _definitely_invalid_token(exc):
                raise
            # RFC 7009 success for an already invalid/revoked token.
            log.info("mcp_oauth_revoke_already_invalid")


class OAuthVerifier(TokenVerifier):
    def __init__(self, store: AuthorizationStore):
        self.store = store

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            record = self.store.verify_access(token, resource=self.store.resource)
        except AccountError as exc:
            if not _definitely_invalid_token(exc):
                raise
            return None
        if (record.issuer, record.resource, record.scopes) != (
            self.store.issuer,
            self.store.resource,
            (SCOPE,),
        ):
            return None
        return _access(token, record)


def create_oauth_routes(provider: OAuthProvider):
    """AS and browser routes only; mount before MCP's root app. No lifespan."""
    from .oauth_routes import create_routes

    return create_routes(provider)
