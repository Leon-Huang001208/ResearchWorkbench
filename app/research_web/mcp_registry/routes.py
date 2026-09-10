"""FastAPI routes for the read-only MCP Registry and publisher handoff."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request

from .models import RegistryCreate, RegistryUpdate, SyncRequest

router = APIRouter(prefix="/api/research/mcp")


def service(request: Request):
    return request.app.state.research.mcp_registry


@router.get("/registries")
def registries(request: Request):
    return service(request).list_registries()


@router.post("/registries", status_code=201)
def create_registry(body: RegistryCreate, request: Request):
    return service(request).create_registry(body)


@router.get("/registries/{registry_id}")
def registry_detail(registry_id: str, request: Request):
    return service(request).registry(registry_id)


@router.patch("/registries/{registry_id}")
def update_registry(registry_id: str, body: RegistryUpdate, request: Request):
    return service(request).update_registry(registry_id, body)


@router.delete("/registries/{registry_id}")
def delete_registry(registry_id: str, request: Request):
    return service(request).delete_registry(registry_id)


@router.post("/registries/{registry_id}/sync")
async def sync_registry(
    registry_id: str,
    request: Request,
    body: SyncRequest | None = None,
):
    request_body = body or SyncRequest()
    return await service(request).sync_registry(
        registry_id,
        cursor=request_body.cursor,
        search=request_body.search,
        limit=request_body.limit,
    )


@router.get("/servers")
def servers(
    request: Request,
    registry_id: str,
    search: str | None = Query(default=None, max_length=200),
    cursor: str | None = Query(default=None, max_length=4096),
    limit: int = Query(default=100, ge=1, le=100),
):
    return service(request).list_servers(
        registry_id,
        cursor=cursor,
        search=search,
        limit=limit,
    )


@router.get("/servers/{registry_id}/{server_name:path}/versions/{version}")
async def server_version(
    registry_id: str,
    server_name: str,
    version: str,
    request: Request,
    refresh: bool = True,
):
    return await service(request).version_detail(registry_id, server_name, version, refresh=refresh)


@router.post("/publisher/preview")
def publisher_preview(body: dict[str, Any], request: Request):
    return service(request).publisher_preview(body)


@router.post("/publisher/validate")
def publisher_validate(body: dict[str, Any], request: Request):
    return service(request).publisher_validate(body)
