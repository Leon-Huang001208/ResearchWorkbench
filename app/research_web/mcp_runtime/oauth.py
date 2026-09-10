"""OAuth 2.1 discovery and authorization-code state for remote MCP servers."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit

import httpx

from .credentials import RuntimeCredentialError, RuntimeCredentialStore
from .transport import validate_remote_endpoint

FetchJSON = Callable[[str], Awaitable[dict[str, Any]]]
TokenExchange = Callable[[str, dict[str, str]], Awaitable[dict[str, Any]]]


class OAuthError(RuntimeError):
    """Stable OAuth failure without token or third-party response content."""


@dataclass(frozen=True)
class OAuthMetadata:
    resource: str
    issuer: str
    authorization_endpoint: str
    token_endpoint: str


@dataclass(frozen=True)
class OAuthStartResult:
    attempt_id: str
    authorization_url: str
    expires_at: float


@dataclass(frozen=True)
class OAuthCompletion:
    credential_ref: dict[str, str]
    resource: str
    status: str = "stored"


@dataclass(frozen=True)
class _OAuthAttempt:
    installation_id: str
    state: str
    code_verifier: str
    resource: str
    issuer: str
    token_endpoint: str
    expires_at: float


def _well_known(origin: str, name: str, path: str = "") -> str:
    parsed = urlsplit(origin)
    suffix = path if path.startswith("/") else f"/{path}" if path else ""
    return urlunsplit((parsed.scheme, parsed.netloc, f"/.well-known/{name}{suffix}", "", ""))


def _https_metadata_url(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise OAuthError(f"oauth_{field}_invalid")
    try:
        normalized = validate_remote_endpoint(value)
    except ValueError as exc:
        raise OAuthError(f"oauth_{field}_invalid") from exc
    if urlsplit(normalized).scheme != "https":
        raise OAuthError(f"oauth_{field}_insecure")
    return normalized


class OAuthDiscovery:
    def __init__(self, fetch_json: FetchJSON | None = None) -> None:
        self._fetch = fetch_json or self._safe_fetch_json

    @staticmethod
    async def _safe_fetch_json(url: str) -> dict[str, Any]:
        try:
            async with (
                httpx.AsyncClient(
                    trust_env=False,
                    follow_redirects=False,
                    timeout=httpx.Timeout(10, connect=5),
                    headers={"Accept": "application/json"},
                ) as client,
                client.stream("GET", url) as response,
            ):
                if response.is_redirect:
                    raise OAuthError("oauth_metadata_redirect_forbidden")
                response.raise_for_status()
                if int(response.headers.get("content-length", "0") or 0) > 1024 * 1024:
                    raise OAuthError("oauth_metadata_too_large")
                chunks = bytearray()
                async for chunk in response.aiter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > 1024 * 1024:
                        raise OAuthError("oauth_metadata_too_large")
                raw = bytes(chunks)
            value = json.loads(raw)
        except OAuthError:
            raise
        except (httpx.HTTPError, UnicodeDecodeError, ValueError) as exc:
            raise OAuthError("oauth_metadata_unavailable") from exc
        if not isinstance(value, dict):
            raise OAuthError("oauth_metadata_invalid")
        return value

    async def discover(self, resource: str) -> OAuthMetadata:
        resource = validate_remote_endpoint(resource)
        parsed = urlsplit(resource)
        resource_metadata_url = _well_known(
            urlunsplit((parsed.scheme, parsed.netloc, "", "", "")),
            "oauth-protected-resource",
            parsed.path,
        )
        protected = await self._fetch(resource_metadata_url)
        if protected.get("resource") != resource:
            raise OAuthError("oauth_resource_mismatch")
        servers = protected.get("authorization_servers")
        if not isinstance(servers, list) or len(servers) != 1:
            raise OAuthError("oauth_authorization_server_ambiguous")
        issuer = _https_metadata_url(servers[0], "issuer")
        issuer_path = urlsplit(issuer).path
        authorization = await self._fetch(
            _well_known(issuer, "oauth-authorization-server", issuer_path)
        )
        if authorization.get("issuer") != issuer:
            raise OAuthError("oauth_issuer_mismatch")
        methods = authorization.get("code_challenge_methods_supported")
        if not isinstance(methods, list) or "S256" not in methods:
            raise OAuthError("oauth_pkce_s256_required")
        return OAuthMetadata(  # type: ignore[call-arg]
            resource,
            issuer,
            _https_metadata_url(
                authorization.get("authorization_endpoint"), "authorization_endpoint"
            ),
            _https_metadata_url(authorization.get("token_endpoint"), "token_endpoint"),
        )


class OAuthCoordinator:
    def __init__(
        self,
        discovery: OAuthDiscovery,
        credentials: RuntimeCredentialStore,
        *,
        redirect_uri: str,
        client_id: str,
        clock: Callable[[], float] = time.time,
        token_transport: httpx.AsyncBaseTransport | None = None,
        max_token_response_bytes: int = 1024 * 1024,
        max_attempts: int = 64,
    ) -> None:
        parsed = urlsplit(redirect_uri)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"127.0.0.1", "::1"}
            or not parsed.port
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise OAuthError("oauth_redirect_invalid")
        if not isinstance(client_id, str) or not client_id or len(client_id) > 512:
            raise OAuthError("oauth_client_invalid")
        self.discovery = discovery
        self.credentials = credentials
        self.redirect_uri = redirect_uri
        self.client_id = client_id
        self.clock = clock
        if max_token_response_bytes < 1 or max_attempts < 1:
            raise OAuthError("oauth_configuration_invalid")
        self.token_transport = token_transport
        self.max_token_response_bytes = max_token_response_bytes
        self.max_attempts = max_attempts
        self._attempts: dict[str, _OAuthAttempt] = {}

    def _prune_attempts(self) -> None:
        now = self.clock()
        self._attempts = {
            attempt_id: attempt
            for attempt_id, attempt in self._attempts.items()
            if attempt.expires_at >= now
        }

    async def start(self, installation_id: str, resource: str) -> OAuthStartResult:
        # Validate the durable installation identity before any network request.
        try:
            self.credentials.reference(installation_id, "oauth")
        except RuntimeCredentialError as exc:
            raise OAuthError("oauth_installation_invalid") from exc
        self._prune_attempts()
        if len(self._attempts) >= self.max_attempts:
            raise OAuthError("oauth_attempt_capacity_reached")
        metadata = await self.discovery.discover(resource)
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "state": state,
                "resource": metadata.resource,
            }
        )
        attempt = _OAuthAttempt(  # type: ignore[call-arg]
            installation_id,
            state,
            verifier,
            metadata.resource,
            metadata.issuer,
            metadata.token_endpoint,
            self.clock() + 600,
        )
        # The loopback callback receives OAuth state but no application-specific attempt ID.
        # Use the same opaque, one-use nonce for both so callback completion is possible
        # without asking the browser or authorization server to echo extra secrets.
        attempt_id = state
        self._attempts[state] = attempt
        return OAuthStartResult(  # type: ignore[call-arg]
            attempt_id,
            f"{metadata.authorization_endpoint}?{query}",
            attempt.expires_at,
        )

    async def complete(
        self,
        attempt_id: str,
        state: str,
        code: str,
        exchange: TokenExchange | None = None,
        *,
        issuer: str | None = None,
    ) -> OAuthCompletion:
        self._prune_attempts()
        attempt = self._attempts.get(attempt_id)
        if (
            attempt is None
            or not secrets.compare_digest(attempt.state, state)
            or self.clock() > attempt.expires_at
        ):
            raise OAuthError("oauth_state_invalid")
        if issuer is not None and issuer != attempt.issuer:
            raise OAuthError("oauth_issuer_mismatch")
        if not isinstance(code, str) or not code or len(code) > 8192:
            raise OAuthError("oauth_code_invalid")
        # Consume before exchange so an authorization code cannot be replayed.
        del self._attempts[attempt_id]
        body = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "code_verifier": attempt.code_verifier,
            "resource": attempt.resource,
        }
        response = (
            await exchange(attempt.token_endpoint, body)
            if exchange is not None
            else await self._safe_token_exchange(attempt.token_endpoint, body)
        )
        asserted_resources = [response[key] for key in ("resource", "audience") if key in response]
        # Opaque access tokens cannot be inspected cryptographically by this client. Fail closed
        # unless the authorization server explicitly echoes the target resource, then bind the
        # stored credential to that exact resource; the resource server remains the final verifier.
        if not asserted_resources or any(value != attempt.resource for value in asserted_resources):
            raise OAuthError("oauth_token_audience_mismatch")
        access_token = response.get("access_token")
        if (
            response.get("token_type", "").lower() != "bearer"
            or not isinstance(access_token, str)
            or not access_token
            or len(access_token.encode("utf-8")) > 64 * 1024
            or any(ord(char) < 32 for char in access_token)
        ):
            raise OAuthError("oauth_token_invalid")
        token: dict[str, Any] = {
            key: response[key]
            for key in ("access_token", "refresh_token", "token_type", "expires_in", "scope")
            if key in response
        }
        token["resource"] = attempt.resource
        self.credentials.write(attempt.installation_id, "oauth", token)
        return OAuthCompletion(  # type: ignore[call-arg]
            self.credentials.reference(attempt.installation_id, "oauth"),
            attempt.resource,
        )

    async def _safe_token_exchange(
        self,
        endpoint: str,
        body: dict[str, str],
    ) -> dict[str, Any]:
        try:
            endpoint = _https_metadata_url(endpoint, "token_endpoint")
            async with (
                httpx.AsyncClient(
                    trust_env=False,
                    follow_redirects=False,
                    timeout=httpx.Timeout(15, connect=5),
                    transport=self.token_transport,
                    headers={"Accept": "application/json"},
                ) as client,
                client.stream("POST", endpoint, data=body) as response,
            ):
                if response.is_redirect:
                    raise OAuthError("oauth_token_redirect_forbidden")
                response.raise_for_status()
                declared = int(response.headers.get("content-length", "0") or 0)
                if declared > self.max_token_response_bytes:
                    raise OAuthError("oauth_token_response_too_large")
                chunks = bytearray()
                async for chunk in response.aiter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > self.max_token_response_bytes:
                        raise OAuthError("oauth_token_response_too_large")
            value = json.loads(bytes(chunks))
        except OAuthError:
            raise
        except (httpx.HTTPError, UnicodeDecodeError, ValueError) as exc:
            raise OAuthError("oauth_token_exchange_failed") from exc
        if not isinstance(value, dict):
            raise OAuthError("oauth_token_invalid")
        return value
