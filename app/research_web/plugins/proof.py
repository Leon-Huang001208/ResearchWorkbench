"""One-use, short-lived gateway proof restricted to plugin MCP routes."""

import hashlib
import hmac
import re
import secrets
import time

from .packages import PluginError

ACTOR = "X-RWB-Plugin-Actor"
PROOF = "X-RWB-Plugin-Proof"
ROLE = "X-RWB-Plugin-Role"
PATH = re.compile(
    r"^/api/research/plugins/[a-f0-9]{64}/mcp/[a-z0-9]+(?:-[a-z0-9]+)*/(?:preview|install|probe|review|enable|disable|status|classify|authorize|approvals|decide|credential-status|credential-save|credential-delete|evaluation-candidate|evaluation-preview|evaluation-authorize|evaluation-call)$"
)
MANAGER_PATH = re.compile(
    r"^/api/research/internal/plugin-runtime/(?:freeze|unfreeze|commit|rollback)$"
)


def _message(method, path, body, actor, role, expiry, nonce):
    if (
        method not in {"POST", "GET"}
        or not (PATH.fullmatch(path) or MANAGER_PATH.fullmatch(path))
        or len(body) > 65536
        or not re.fullmatch(r"[a-f0-9-]{36}", actor)
        or (role != "manager" if MANAGER_PATH.fullmatch(path) else role not in {"admin", "user"})
    ):
        raise PluginError("plugin_proof_scope_invalid", 403)
    return "\n".join(
        (method, path, hashlib.sha256(body).hexdigest(), actor, role, str(expiry), nonce)
    ).encode()


def sign(key, method, path, body, actor, role, *, now=None):
    expiry = int(time.time() if now is None else now) + 30
    nonce = secrets.token_hex(16)
    message = _message(method, path, body, actor, role, expiry, nonce)
    signature = hmac.digest(key.encode(), message, "sha256").hex()
    return {ACTOR: actor, ROLE: role, PROOF: f"{expiry}.{nonce}.{signature}"}


def verify(key, method, path, body, headers, consumed, *, now=None):
    try:
        expiry, nonce, signature = headers.get(PROOF, "").split(".")
        expiry = int(expiry)
        current = time.time() if now is None else now
        if not current <= expiry <= current + 30 or not re.fullmatch(r"[a-f0-9]{32}", nonce):
            raise ValueError("expired")
        actor, role = headers.get(ACTOR, ""), headers.get(ROLE, "")
        expected = hmac.digest(
            key.encode(), _message(method, path, body, actor, role, expiry, nonce), "sha256"
        ).hex()
        if not hmac.compare_digest(signature, expected) or nonce in consumed:
            raise ValueError("invalid or replayed")
        # Keep requests in this process once only. Restart invalidates pending
        # native confirmation tokens, so unknown install is never auto-retried.
        for prior, deadline in list(consumed.items()):
            if deadline < current:
                consumed.pop(prior)
        if len(consumed) >= 4096:
            raise ValueError("proof capacity")
        consumed[nonce] = expiry
        return actor, role
    except (ValueError, TypeError, AttributeError) as exc:
        raise PluginError("plugin_gateway_proof_denied", 403) from exc
