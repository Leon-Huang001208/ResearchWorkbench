"""Gateway-owned package approvals; identities come solely from AccountStore.

Shared and personal approval stores contain immutable bytes/review only. Tenant
backends project them using manager-provided paths, retaining personal credentials.
"""

import asyncio
import json
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Request, UploadFile
from fastapi.responses import JSONResponse, Response

from ..plugin_routes import Review
from ..plugins import PluginError, PluginService
from ..plugins.packages import MAX_ARCHIVE, safe_path
from ..plugins.proof import sign

router = APIRouter(prefix="/api/server/plugins")


def actor(request, *, admin=False):
    user = request.state.user
    if user is None:
        raise PluginError("login_required", 401)
    identities = (request.headers.get("X-RWB-Page-User"), request.query_params.get("rwb_user"))
    if any(value is not None and value != user.id for value in identities) or (
        request.method not in {"GET", "HEAD"} and user.id not in identities
    ):
        raise PluginError("account_changed", 401)
    if admin and user.role != "admin":
        raise PluginError("administrator_required", 403)
    return user


def source_root(root: Path, scope: str, owner: str):
    if scope == "shared":
        return root / "shared" / "plugin-approvals"
    if scope != "personal":
        raise PluginError("plugin_scope_invalid")
    try:
        if str(UUID(owner)) != owner:
            raise ValueError("canonical UUID required")
    except (ValueError, TypeError) as exc:
        raise PluginError("plugin_owner_invalid") from exc
    return root / "users" / owner / "plugin-approvals"


def configure(app, accounts, pool, client=None):
    """Attach lazy managers; importing or constructing a gateway starts no process."""
    app.state.plugin_lock = asyncio.Lock()
    app.state.plugin_accounts = accounts
    app.state.plugin_pool = pool
    app.state.plugin_client = client
    app.state.plugin_review_queue = {}
    app.state.plugin_root = getattr(getattr(pool, "config", None), "root", accounts.root)


async def native_request(request, user, digest, key, action, body, *, method="POST", reviewer=None):
    """Fixed user's pool backend and fixed plugin action; never a browser URL."""
    pool = request.app.state.plugin_pool
    backend = await pool.backend_for(user.id)
    path = f"/api/research/plugins/{digest}/mcp/{key}/{action}"
    actor = reviewer or user
    headers = sign(backend.key, method, path, body, actor.id, actor.role)
    headers.update(
        {
            "X-RWB-Tenant-Gateway-Key": backend.key,
            "Origin": backend.url,
            "Content-Type": "application/json",
        }
    )
    ticket = (
        await pool.request_started(user.id, backend) if hasattr(pool, "request_started") else None
    )
    try:
        response = await request.app.state.plugin_client.request(
            method, backend.url + path, content=body, headers=headers
        )
    finally:
        if ticket is not None:
            await pool.request_finished(user.id, ticket)
    if (
        len(response.content) > 1024 * 1024
        or response.headers.get("content-type", "").split(";")[0] != "application/json"
    ):
        raise PluginError("plugin_mcp_response_invalid", 503)
    result = JSONResponse(response.json(), status_code=response.status_code)
    result.plugin_backend = backend
    return result


@router.post("/mcp/{digest}/{key}/{action}")
async def mcp_action(digest: str, key: str, action: str, request: Request):
    if action not in {
        "preview",
        "install",
        "probe",
        "enable",
        "disable",
        "status",
        "classify",
        "authorize",
        "approvals",
        "decide",
        "credential-status",
        "credential-save",
        "credential-delete",
        "evaluation-candidate",
        "evaluation-preview",
        "evaluation-call",
        "evaluation-authorize",
    }:
        raise PluginError("plugin_mcp_action_invalid", 404)
    user = actor(request)
    if action == "classify" and user.role != "admin":
        raise PluginError("administrator_required", 403)
    body = await request.body()
    if len(body) > 65536:
        raise PluginError("plugin_request_limit", 413)
    response = await native_request(request, user, digest, key, action, body)
    if action in {"enable", "disable"} and response.status_code == 200:
        staged = json.loads(response.body)
        if staged.get("status") == "restart_required":
            pool = request.app.state.plugin_pool
            if not hasattr(pool, "restart_runtime"):
                return JSONResponse(
                    {
                        **staged,
                        "status": "restart_required",
                        "reason": "manager_restart_unavailable",
                    },
                    status_code=409,
                )
            result = await pool.restart_runtime(
                user.id, response.plugin_backend, staged["transaction_id"]
            )
            return JSONResponse(
                {**staged, **result}, status_code=200 if result["status"] == "ready" else 409
            )
    if action == "probe" and response.status_code == 200:
        status = await native_request(request, user, digest, key, "status", b"{}")
        if status.status_code != 200:
            return status
        snapshot = json.loads(status.body)
        async with request.app.state.plugin_lock:
            pending = request.app.state.plugin_review_queue
            if len(pending) >= 128:
                raise PluginError("plugin_mcp_review_queue_full", 409)
            rid = uuid4().hex
            pending[rid] = {
                "owner": user.id,
                "digest": digest,
                "component": key,
                "snapshot": snapshot,
            }
        return JSONResponse(
            {
                "capabilities": json.loads(response.body),
                "admin_review_id": rid,
                "status": "administrator_review_required",
            }
        )
    return response


@router.post("/runtime/refresh")
async def refresh_runtime(request: Request):
    user = actor(request)
    pool = request.app.state.plugin_pool
    if not hasattr(pool, "restart_runtime"):
        raise PluginError("plugin_runtime_restart_unavailable", 409)
    backend = await pool.backend_for(user.id)
    result = await pool.restart_runtime(user.id, backend)
    return JSONResponse(result, status_code=200 if result["status"] == "ready" else 409)


@router.get("/reviews/pending")
async def pending_reviews(request: Request):
    actor(request, admin=True)
    async with request.app.state.plugin_lock:
        return {
            "items": [
                {"id": rid, **item} for rid, item in request.app.state.plugin_review_queue.items()
            ]
        }


@router.post("/reviews/{review_id}/approve")
async def approve_native_review(review_id: str, request: Request):
    admin = actor(request, admin=True)
    async with request.app.state.plugin_lock:
        pending = request.app.state.plugin_review_queue.get(review_id)
        if pending is None:
            raise PluginError("plugin_mcp_review_not_found", 404)
        # The owner and native snapshot were captured by the server from the
        # original authenticated request, never an approval body/header/URL.
        owner = next(
            (
                user
                for user in request.app.state.plugin_accounts.list_users()
                if user.id == pending["owner"] and user.enabled
            ),
            None,
        )
        if owner is None:
            raise PluginError("plugin_owner_not_found", 404)
        body = json.dumps({"expected": pending["snapshot"]["fingerprint"]}).encode()
        response = await native_request(
            request, owner, pending["digest"], pending["component"], "review", body, reviewer=admin
        )
        if response.status_code == 200:
            request.app.state.plugin_review_queue.pop(review_id)
        return response


def _service(request, scope, owner=None, *, admin=False):
    user = actor(request, admin=admin)
    target = owner or user.id
    if target != user.id and user.role != "admin":
        raise PluginError("plugin_owner_denied", 403)
    if scope == "personal" and not any(
        account.id == target for account in request.app.state.plugin_accounts.list_users()
    ):
        raise PluginError("plugin_owner_not_found", 404)
    return PluginService(
        source_root(request.app.state.plugin_root, scope, target), idle_gate=lambda: True
    )


@router.get("/{scope}")
async def catalog(scope: str, request: Request, owner: str | None = None):
    async with request.app.state.plugin_lock:
        return _service(request, scope, owner).list()


@router.get("/{scope}/{digest}/files/{name:path}")
async def source_file(
    scope: str, digest: str, name: str, request: Request, owner: str | None = None
):
    async with request.app.state.plugin_lock:
        package = _service(request, scope, owner)._archive(digest)
        name = safe_path(name)
        if name not in package["files"]:
            raise PluginError("plugin_file_not_found", 404)
        return Response(
            package["files"][name],
            media_type="application/octet-stream",
            headers={"Content-Disposition": "attachment", "X-Content-Type-Options": "nosniff"},
        )


@router.post("/{scope}/preview", status_code=201)
async def preview(scope: str, request: Request, file: UploadFile, owner: str | None = None):
    try:
        raw = await file.read(MAX_ARCHIVE + 1)
        async with request.app.state.plugin_lock:
            return _service(request, scope, owner, admin=True).preview(raw)
    finally:
        await file.close()


@router.post("/{scope}/{digest}/review")
async def review(scope: str, digest: str, body: Review, request: Request, owner: str | None = None):
    async with request.app.state.plugin_lock:
        return _service(request, scope, owner, admin=True).review(
            digest, body.permissions, request.state.user.id
        )


@router.post("/{scope}/{digest}/enable")
async def enable(scope: str, digest: str, request: Request, owner: str | None = None):
    async with request.app.state.plugin_lock:
        # This enables approval distribution only. Each tenant checks actual
        # runtime idleness before native activation, and reports readiness there.
        return await _service(request, scope, owner, admin=True).enable(digest)


@router.post("/{scope}/{digest}/disable")
async def disable(scope: str, digest: str, request: Request, owner: str | None = None):
    async with request.app.state.plugin_lock:
        return await _service(request, scope, owner, admin=True).disable(digest)


@router.delete("/{scope}/{digest}")
async def uninstall(scope: str, digest: str, request: Request, owner: str | None = None):
    async with request.app.state.plugin_lock:
        return await _service(request, scope, owner, admin=True).uninstall(digest)


@router.get("/candidate/seek-alpha")
def seek_alpha_candidate(request: Request):
    from ..plugins.seek_alpha_candidate import candidate_archive

    actor(request)
    return Response(
        candidate_archive(),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="seek-alpha-candidate-0.1.0.zip"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )
