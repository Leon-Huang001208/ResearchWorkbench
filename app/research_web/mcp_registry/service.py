"""Read-only MCP Registry orchestration and safe response projection."""

from __future__ import annotations

import copy
import os
import re
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from core.observability import get_logger

from .catalog import CatalogError, RegistryCatalog, timestamp
from .credentials import CredentialError, RegistryCredentialStore
from .models import (
    SERVER_NAME_PATTERN,
    AuthBearer,
    AuthNone,
    AuthOAuth2,
    RegistryCreate,
    RegistryUpdate,
    UpstreamList,
    normalize_upstream_server,
    validate_registry_transport,
)
from .publisher import PublisherMetadata
from .sync import RegistryHTTPClient, SyncError

log = get_logger(__name__)


class RegistryError(RuntimeError):
    def __init__(self, message: str, code: str = "mcp_registry_error", status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def registry_feature_enabled() -> bool:
    return os.environ.get("RESEARCH_MCP_REGISTRY_ENABLED", "1").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


class MCPRegistryService:
    def __init__(
        self,
        data_root: Path,
        *,
        enabled: bool | None = None,
        keyring_backend=None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.enabled = registry_feature_enabled() if enabled is None else enabled
        self._data_root = Path(data_root)
        self._keyring_backend = keyring_backend
        self._http_client = http_client
        self._catalog: RegistryCatalog | None = None
        self._credentials: RegistryCredentialStore | None = None
        self._http: RegistryHTTPClient | None = None
        self._publisher: PublisherMetadata | None = None
        self._volatile_status: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        if self.enabled:
            self._initialize()

    def _initialize(self) -> None:
        if self._catalog is not None:
            return
        self._catalog = RegistryCatalog(self._data_root)
        self._credentials = RegistryCredentialStore(self._keyring_backend)
        self._http = RegistryHTTPClient(self._http_client)
        self._publisher = PublisherMetadata()

    @property
    def catalog(self) -> RegistryCatalog:
        self._ensure_enabled()
        self._initialize()
        assert self._catalog is not None
        return self._catalog

    @property
    def credentials(self) -> RegistryCredentialStore:
        self._ensure_enabled()
        self._initialize()
        assert self._credentials is not None
        return self._credentials

    @credentials.setter
    def credentials(self, value: RegistryCredentialStore) -> None:
        self._credentials = value

    @property
    def http(self) -> RegistryHTTPClient:
        self._ensure_enabled()
        self._initialize()
        assert self._http is not None
        return self._http

    @property
    def publisher(self) -> PublisherMetadata:
        self._ensure_enabled()
        self._initialize()
        assert self._publisher is not None
        return self._publisher

    async def start(self) -> None:
        """Lifecycle hook kept intentionally network-free."""

        log.info("mcp_registry_service_started", enabled=self.enabled)

    async def close(self) -> None:
        if self._http is not None:
            await self._http.close()

    def _ensure_enabled(self) -> None:
        if not self.enabled:
            raise RegistryError(
                "MCP Registry 功能未启用",
                "mcp_registry_disabled",
                404,
            )

    @staticmethod
    def _catalog_error(exc: CatalogError) -> RegistryError:
        code = str(exc)
        if code == "registry_not_found":
            return RegistryError("Registry 不存在", code, 404)
        if code == "official_registry_immutable":
            return RegistryError("official registry is immutable", code, 409)
        if code == "registry_source_changed":
            return RegistryError("Registry 来源已在同步期间变更", code, 409)
        return RegistryError("Registry 本地目录不可用", code, 503)

    @staticmethod
    def _secret_payload(auth) -> dict[str, str]:
        if isinstance(auth, AuthBearer):
            return {"token": auth.token.get_secret_value()} if auth.token else {}
        if isinstance(auth, AuthOAuth2):
            result = {}
            if auth.access_token:
                result["access_token"] = auth.access_token.get_secret_value()
            if auth.client_secret:
                result["client_secret"] = auth.client_secret.get_secret_value()
            return result
        return {}

    @staticmethod
    def _stored_auth(auth) -> dict[str, Any]:
        if isinstance(auth, AuthNone):
            return {"type": "none"}
        if isinstance(auth, AuthBearer):
            return {"type": "bearer"}
        return auth.model_dump(exclude={"access_token", "client_secret"})

    def _project(self, row: dict[str, Any]) -> dict[str, Any]:
        auth = copy.deepcopy(row["auth"])
        auth["secret_configured"] = self.credentials.configured(row["id"], auth["type"])
        return {**copy.deepcopy(row), "auth": auth}

    @staticmethod
    def _validate_transport(base_url: str, auth_type: str, auth: Any | None = None) -> None:
        try:
            validate_registry_transport(base_url, auth_type)
            if auth_type == "oauth2" and not isinstance(auth, AuthOAuth2):
                stored_auth = {
                    key: value for key, value in (auth or {}).items() if key != "secret_configured"
                }
                AuthOAuth2.model_validate(stored_auth)
        except (TypeError, ValidationError, ValueError) as exc:
            raise RegistryError(
                "Registry 传输配置不安全",
                "registry_transport_insecure",
                422,
            ) from exc

    def list_registries(self) -> dict[str, Any]:
        self._ensure_enabled()
        rows = sorted(
            self.catalog.rows(),
            key=lambda row: (not row["official"], row["name"].casefold(), row["id"]),
        )
        return {"items": [self._project(row) for row in rows]}

    def registry(self, registry_id: str) -> dict[str, Any]:
        self._ensure_enabled()
        try:
            return self._project(self.catalog.row(registry_id))
        except CatalogError as exc:
            raise self._catalog_error(exc) from exc

    def create_registry(self, request: RegistryCreate) -> dict[str, Any]:
        self._ensure_enabled()
        self._validate_transport(request.base_url, request.auth.type, request.auth)
        secret = self._secret_payload(request.auth)
        if isinstance(request.auth, AuthBearer) and not secret:
            raise RegistryError("Bearer Registry 必须提供 token", "registry_secret_required", 422)
        stored_auth = self._stored_auth(request.auth)
        try:
            row = self.catalog.create(request.name, request.base_url, stored_auth)
            try:
                if secret:
                    self.credentials.write(row["id"], stored_auth["type"], secret)
            except CredentialError:
                self.catalog.delete(row["id"])
                raise
        except CatalogError as exc:
            raise self._catalog_error(exc) from exc
        except CredentialError as exc:
            raise RegistryError("系统凭据库不可用", str(exc), 503) from exc
        log.info("mcp_registry_created", registry_id=row["id"], auth_type=stored_auth["type"])
        return self._project(row)

    def update_registry(self, registry_id: str, request: RegistryUpdate) -> dict[str, Any]:
        self._ensure_enabled()
        try:
            current = self.catalog.row(registry_id)
        except CatalogError as exc:
            raise self._catalog_error(exc) from exc
        if current["immutable"]:
            raise RegistryError(
                "official registry is immutable", "official_registry_immutable", 409
            )
        effective_base_url = request.base_url or current["base_url"]
        effective_auth = request.auth if request.auth is not None else current["auth"]
        effective_auth_type = (
            effective_auth.type if request.auth is not None else effective_auth["type"]
        )
        self._validate_transport(effective_base_url, effective_auth_type, effective_auth)
        changes = request.model_dump(exclude_none=True, exclude={"auth"})
        old_type = current["auth"]["type"]
        if request.auth is not None:
            new_type = request.auth.type
            secret = self._secret_payload(request.auth)
            if isinstance(request.auth, AuthBearer) and not secret and old_type != "bearer":
                raise RegistryError(
                    "Bearer Registry 必须提供 token", "registry_secret_required", 422
                )
            try:
                old_snapshot = self.credentials.snapshot(registry_id, old_type)
                new_snapshot = (
                    old_snapshot
                    if old_type == new_type
                    else self.credentials.snapshot(registry_id, new_type)
                )
                old_secret = old_snapshot or {}
                if not secret and old_type == new_type:
                    secret = old_secret
                self.credentials.replace(registry_id, old_type, new_type, secret)
            except CredentialError as exc:
                raise RegistryError("系统凭据库不可用", str(exc), 503) from exc
            changes["auth"] = self._stored_auth(request.auth)
            try:
                row = self.catalog.update(registry_id, changes)
            except CatalogError as exc:
                try:
                    if old_type == new_type:
                        self.credentials.restore(registry_id, old_type, old_snapshot)
                    else:
                        self.credentials.restore(registry_id, old_type, old_snapshot)
                        self.credentials.restore(registry_id, new_type, new_snapshot)
                except CredentialError as rollback_exc:
                    log.error("mcp_registry_auth_rollback_failed", registry_id=registry_id)
                    raise RegistryError(
                        "Registry 凭据补偿失败", "credential_compensation_failed", 503
                    ) from rollback_exc
                raise self._catalog_error(exc) from exc
        else:
            try:
                row = self.catalog.update(registry_id, changes)
            except CatalogError as exc:
                raise self._catalog_error(exc) from exc
        log.info("mcp_registry_updated", registry_id=registry_id)
        return self._project(row)

    def delete_registry(self, registry_id: str) -> dict[str, Any]:
        self._ensure_enabled()
        try:
            current = self.catalog.row(registry_id)
        except CatalogError as exc:
            raise self._catalog_error(exc) from exc
        if current["immutable"]:
            raise RegistryError(
                "official registry is immutable", "official_registry_immutable", 409
            )
        auth_type = current["auth"]["type"]
        try:
            secret = self.credentials.read(registry_id, auth_type)
            self.credentials.delete(registry_id, auth_type)
            try:
                self.catalog.delete(registry_id)
            except CatalogError:
                if secret:
                    self.credentials.write(registry_id, auth_type, secret)
                raise
        except CredentialError as exc:
            raise RegistryError("系统凭据库不可用", str(exc), 503) from exc
        except CatalogError as exc:
            raise self._catalog_error(exc) from exc
        log.info("mcp_registry_deleted", registry_id=registry_id)
        return {"id": registry_id, "deleted": True}

    @staticmethod
    def _page_result(record: dict[str, Any], **changes: Any) -> dict[str, Any]:
        result = {
            key: copy.deepcopy(value)
            for key, value in record.items()
            if key not in {"etag", "source_url"}
        }
        result.update(changes)
        return result

    @staticmethod
    def _matches_source(record: dict[str, Any] | None, source_url: str) -> bool:
        return record is not None and record.get("source_url") == source_url

    def _sync_status(
        self, registry_id: str, kind: str, source_url: str, **values: Any
    ) -> dict[str, Any]:
        key = (registry_id, kind, source_url, self.catalog.query_key(kind, **values))
        if key in self._volatile_status:
            status = self._volatile_status[key]
        else:
            try:
                status = self.catalog.sync_status(registry_id, kind, **values)
            except CatalogError as exc:
                log.warning(
                    "mcp_registry_status_projection_failed",
                    registry_id=registry_id,
                    failure_code=str(exc),
                )
                return {"stale": True, "failure_code": str(exc)}
        if status is None or status.get("source_url") != source_url:
            return {"stale": False, "failure_code": None}
        return {
            "stale": status.get("stale") is True,
            "failure_code": status.get("failure_code"),
        }

    def _set_sync_status(
        self,
        registry_id: str,
        kind: str,
        source_url: str,
        value: dict[str, Any] | None,
        **values: Any,
    ) -> None:
        key = (registry_id, kind, source_url, self.catalog.query_key(kind, **values))
        fallback = value or {
            "source_url": source_url,
            "stale": False,
            "failure_code": None,
        }
        try:
            self.catalog.set_sync_status(registry_id, kind, value, **values)
        except CatalogError as exc:
            self._volatile_status[key] = copy.deepcopy(fallback)
            log.warning(
                "mcp_registry_status_persist_failed",
                registry_id=registry_id,
                failure_code=str(exc),
            )
        else:
            self._volatile_status.pop(key, None)

    def list_servers(
        self,
        registry_id: str,
        *,
        cursor: str | None = None,
        search: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        row = self.registry(registry_id)
        self._validate_transport(row["base_url"], row["auth"]["type"], row["auth"])
        cached: dict[str, Any] | None = None
        try:
            cached = self.catalog.cached_page(
                registry_id, cursor=cursor, search=search, limit=limit
            )
            if not self._matches_source(cached, row["base_url"]):
                cached = None
        except CatalogError as exc:
            raise self._catalog_error(exc) from exc
        if cached is None:
            return {
                "registry_id": registry_id,
                "items": [],
                "cursor": cursor,
                "next_cursor": None,
                "count": 0,
                "fetched_at": None,
                "stale": False,
                "failure_code": None,
            }
        status = self._sync_status(
            registry_id,
            "page",
            row["base_url"],
            cursor=cursor,
            search=search,
            limit=limit,
        )
        return self._page_result(cached, **status)

    async def sync_registry(
        self,
        registry_id: str,
        *,
        cursor: str | None = None,
        search: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        row = self.registry(registry_id)
        self._validate_transport(row["base_url"], row["auth"]["type"], row["auth"])
        cached: dict[str, Any] | None = None
        try:
            cached = self.catalog.cached_page(
                registry_id, cursor=cursor, search=search, limit=limit
            )
            if not self._matches_source(cached, row["base_url"]):
                cached = None
            authorization = self.credentials.authorization(registry_id, row["auth"]["type"])
            status, payload, etag = await self.http.page(
                row["base_url"],
                cursor=cursor,
                search=search,
                limit=limit,
                etag=cached.get("etag") if cached else None,
                authorization=authorization,
            )
            if status == 304:
                if cached is None:
                    raise SyncError("registry_invalid_not_modified", 502)
                if self.catalog.row(registry_id)["base_url"] != row["base_url"]:
                    raise SyncError("registry_source_changed", 409)
                self._set_sync_status(
                    registry_id,
                    "page",
                    row["base_url"],
                    None,
                    cursor=cursor,
                    search=search,
                    limit=limit,
                )
                return self._page_result(cached, stale=False, failure_code=None, not_modified=True)
            try:
                upstream = UpstreamList.model_validate(payload)
                items = [normalize_upstream_server(registry_id, item) for item in upstream.servers]
            except (ValidationError, TypeError, ValueError) as exc:
                raise SyncError("registry_invalid_response", 502) from exc
            if not items:
                raise SyncError("registry_empty_response", 502)
            if upstream.metadata.count != len(items):
                raise SyncError("registry_invalid_response", 502)
            record = {
                "registry_id": registry_id,
                "items": items,
                "cursor": cursor,
                "next_cursor": upstream.metadata.next_cursor,
                "count": upstream.metadata.count,
                "fetched_at": timestamp(),
                "etag": etag,
                "source_url": row["base_url"],
            }
            self.catalog.save_page(
                registry_id,
                cursor=cursor,
                search=search,
                limit=limit,
                value=record,
                expected_source_url=row["base_url"],
            )
            self._set_sync_status(
                registry_id,
                "page",
                row["base_url"],
                None,
                cursor=cursor,
                search=search,
                limit=limit,
            )
            log.info("mcp_registry_sync_succeeded", registry_id=registry_id, count=len(items))
            return self._page_result(record, stale=False, failure_code=None, not_modified=False)
        except CredentialError as exc:
            error = SyncError(str(exc), 503)
        except CatalogError as exc:
            error = SyncError(str(exc), 409 if str(exc) == "registry_source_changed" else 503)
        except SyncError as exc:
            error = exc
        log.warning("mcp_registry_sync_failed", registry_id=registry_id, failure_code=error.code)
        try:
            if self.catalog.row(registry_id)["base_url"] != row["base_url"]:
                cached = None
                error = SyncError("registry_source_changed", 409)
        except CatalogError as exc:
            raise self._catalog_error(exc) from exc
        if cached is not None:
            self._set_sync_status(
                registry_id,
                "page",
                row["base_url"],
                {
                    "source_url": row["base_url"],
                    "stale": True,
                    "failure_code": error.code,
                    "updated_at": timestamp(),
                },
                cursor=cursor,
                search=search,
                limit=limit,
            )
            return self._page_result(
                cached, stale=True, failure_code=error.code, not_modified=False
            )
        raise RegistryError("Registry 同步失败", error.code, error.status) from error

    @staticmethod
    def _validate_identity(server_name: str, version: str) -> None:
        namespace, server_part = (
            server_name.split("/", 1)
            if isinstance(server_name, str) and "/" in server_name
            else ("", "")
        )
        if (
            not isinstance(server_name, str)
            or not re.fullmatch(SERVER_NAME_PATTERN, server_name)
            or any(not label or label in {".", ".."} for label in namespace.split("."))
            or server_part in {".", ".."}
            or not isinstance(version, str)
            or not version
            or len(version) > 255
            or "/" in version
            or version == "latest"
            or any(ord(char) < 32 for char in version)
        ):
            raise RegistryError("Server identity 格式非法", "registry_identity_invalid", 422)

    async def version_detail(
        self,
        registry_id: str,
        server_name: str,
        version: str,
        *,
        refresh: bool = True,
    ) -> dict[str, Any]:
        self._validate_identity(server_name, version)
        row = self.registry(registry_id)
        self._validate_transport(row["base_url"], row["auth"]["type"], row["auth"])
        cached: dict[str, Any] | None = None
        try:
            cached = self.catalog.cached_detail(registry_id, server_name, version)
            if not self._matches_source(cached, row["base_url"]):
                cached = None
            if not refresh and cached is not None:
                status = self._sync_status(
                    registry_id,
                    "detail",
                    row["base_url"],
                    server_name=server_name,
                    version=version,
                )
                return self._page_result(cached, **status)
            authorization = self.credentials.authorization(registry_id, row["auth"]["type"])
            status, payload, etag = await self.http.detail(
                row["base_url"],
                server_name,
                version,
                etag=cached.get("etag") if cached else None,
                authorization=authorization,
            )
            if status == 304:
                if cached is None:
                    raise SyncError("registry_invalid_not_modified", 502)
                if self.catalog.row(registry_id)["base_url"] != row["base_url"]:
                    raise SyncError("registry_source_changed", 409)
                self._set_sync_status(
                    registry_id,
                    "detail",
                    row["base_url"],
                    None,
                    server_name=server_name,
                    version=version,
                )
                return self._page_result(cached, stale=False, failure_code=None)
            try:
                item = normalize_upstream_server(registry_id, payload or {})
            except (TypeError, ValueError) as exc:
                raise SyncError("registry_invalid_response", 502) from exc
            if item["name"] != server_name or item["version"] != version:
                raise SyncError("registry_identity_mismatch", 502)
            record = {
                **item,
                "fetched_at": timestamp(),
                "etag": etag,
                "source_url": row["base_url"],
            }
            self.catalog.save_detail(
                registry_id,
                server_name,
                version,
                record,
                expected_source_url=row["base_url"],
            )
            self._set_sync_status(
                registry_id,
                "detail",
                row["base_url"],
                None,
                server_name=server_name,
                version=version,
            )
            return self._page_result(record, stale=False, failure_code=None)
        except CredentialError as exc:
            error = SyncError(str(exc), 503)
        except CatalogError as exc:
            error = SyncError(str(exc), 409 if str(exc) == "registry_source_changed" else 503)
        except SyncError as exc:
            error = exc
        log.warning("mcp_registry_detail_failed", registry_id=registry_id, failure_code=error.code)
        try:
            if self.catalog.row(registry_id)["base_url"] != row["base_url"]:
                cached = None
                error = SyncError("registry_source_changed", 409)
        except CatalogError as exc:
            raise self._catalog_error(exc) from exc
        if cached is not None:
            self._set_sync_status(
                registry_id,
                "detail",
                row["base_url"],
                {
                    "source_url": row["base_url"],
                    "stale": True,
                    "failure_code": error.code,
                    "updated_at": timestamp(),
                },
                server_name=server_name,
                version=version,
            )
            return self._page_result(cached, stale=True, failure_code=error.code)
        raise RegistryError("Registry 版本详情读取失败", error.code, error.status) from error

    def publisher_preview(self, value: dict[str, Any]) -> dict[str, Any]:
        self._ensure_enabled()
        try:
            return self.publisher.preview(value)
        except (ValidationError, TypeError, ValueError) as exc:
            raise RegistryError("server.json 格式非法", "publisher_metadata_invalid", 422) from exc

    def publisher_validate(self, value: dict[str, Any]) -> dict[str, Any]:
        self._ensure_enabled()
        return self.publisher.validate(value)
