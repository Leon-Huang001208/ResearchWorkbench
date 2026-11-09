"""Framework-neutral OAuth records and additive AccountStore schema.

Only TokenPair carries raw bearer secrets, deliberately excluded from repr.
All other token/code records are metadata loaded by digest lookup.
"""

from dataclasses import dataclass, field

CLIENT_ID = "rwb-codex-native"
WEKNORA_CLIENT_ID = "rwb-weknora"
NATIVE_CALLBACK = "http://127.0.0.1/callback"
SCOPE = "rwb.read"
CODE_TTL = 60
ACCESS_TTL = 600
REFRESH_TTL = 604800
CONSENT_TTL = 600

SCHEMA = """
CREATE TABLE IF NOT EXISTS mcp_oauth_clients (
    issuer TEXT NOT NULL, client_id TEXT NOT NULL,
    redirect_uri TEXT NOT NULL, scope TEXT NOT NULL, auth_method TEXT NOT NULL,
    PRIMARY KEY (issuer, client_id)
);
CREATE TABLE IF NOT EXISTS mcp_oauth_requests (
    id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES accounts(id),
    client_id TEXT NOT NULL, issuer TEXT NOT NULL, resource TEXT NOT NULL,
    scope TEXT NOT NULL, redirect_uri TEXT NOT NULL, challenge TEXT NOT NULL,
    state TEXT, redirect_explicit INTEGER NOT NULL,
    created_at REAL NOT NULL, expires_at REAL NOT NULL, consumed INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS mcp_oauth_grants (
    id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES accounts(id),
    client_id TEXT NOT NULL, issuer TEXT NOT NULL, resource TEXT NOT NULL,
    scope TEXT NOT NULL, created_at REAL NOT NULL, expires_at REAL NOT NULL,
    revoked INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS mcp_oauth_codes (
    digest TEXT PRIMARY KEY, request_id TEXT NOT NULL REFERENCES mcp_oauth_requests(id),
    grant_id TEXT NOT NULL REFERENCES mcp_oauth_grants(id),
    created_at REAL NOT NULL, expires_at REAL NOT NULL, consumed INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS mcp_oauth_tokens (
    digest TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('access', 'refresh')),
    grant_id TEXT NOT NULL REFERENCES mcp_oauth_grants(id),
    created_at REAL NOT NULL, expires_at REAL NOT NULL, consumed INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS mcp_oauth_materials (
    id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES accounts(id),
    context_id TEXT NOT NULL, kind TEXT NOT NULL, object_id TEXT NOT NULL,
    sha256 TEXT NOT NULL, classification TEXT NOT NULL CHECK(classification IN ('public', 'synthetic')),
    revoked INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS mcp_oauth_grant_materials (
    grant_id TEXT NOT NULL REFERENCES mcp_oauth_grants(id),
    material_id TEXT NOT NULL REFERENCES mcp_oauth_materials(id),
    PRIMARY KEY (grant_id, material_id)
);
CREATE INDEX IF NOT EXISTS mcp_oauth_grants_user ON mcp_oauth_grants(user_id);
CREATE INDEX IF NOT EXISTS mcp_oauth_requests_user ON mcp_oauth_requests(user_id);
CREATE INDEX IF NOT EXISTS mcp_oauth_materials_user ON mcp_oauth_materials(user_id);
"""


@dataclass(frozen=True)
class FixedClient:
    client_id: str = CLIENT_ID
    redirect_uris: tuple[str, ...] = (NATIVE_CALLBACK,)
    scopes: tuple[str, ...] = (SCOPE,)
    token_endpoint_auth_method: str = "none"


@dataclass(frozen=True)
class ConsentRequest:
    id: str
    user_id: str
    client_id: str
    issuer: str
    resource: str
    scopes: tuple[str, ...]
    redirect_uri: str
    code_challenge: str
    state: str | None
    redirect_uri_provided_explicitly: bool
    expires_at: float


@dataclass(frozen=True)
class Grant:
    id: str
    user_id: str
    client_id: str
    issuer: str
    resource: str
    scopes: tuple[str, ...]
    expires_at: float
    revoked: bool


@dataclass(frozen=True)
class CodeRecord:
    grant_id: str
    request: ConsentRequest
    expires_at: float

    @property
    def code_challenge(self) -> str:
        return self.request.code_challenge


@dataclass(frozen=True)
class TokenRecord:
    grant_id: str
    user_id: str
    client_id: str
    issuer: str
    resource: str
    scopes: tuple[str, ...]
    expires_at: float


@dataclass(frozen=True)
class TokenPair:
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    expires_in: int
    scope: str
    resource: str


@dataclass(frozen=True)
class ApprovedMaterial:
    id: str
    user_id: str
    context_id: str
    kind: str
    object_id: str
    sha256: str
    classification: str
