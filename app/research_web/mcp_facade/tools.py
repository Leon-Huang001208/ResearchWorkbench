"""Four account-bound readonly tools. Identity comes exclusively from SDK bearer context."""

import inspect
import json
from typing import Annotated, Literal

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from core.observability import get_logger

from ..multiuser.accounts import AccountError
from .backend import ReadError, canonical_id
from .config import RESPONSE_BYTES
from .models import DATA_SCOPE, SCOPE
from .task_contracts import TASKS

log = get_logger(__name__)
TOOL_ARGUMENTS = {
    "rwb_capabilities_list": frozenset(),
    "rwb_datasets_list": frozenset({"context_id"}),
    "rwb_dataset_read": frozenset({"context_id", "dataset_id", "view", "offset", "limit"}),
    "rwb_source_read": frozenset({"context_id", "file_id", "offset", "limit"}),
}
DATA_TOOL_ARGUMENTS = {
    "rwb_datahub_query": frozenset({"request_id", "source", "series_id", "start_date", "end_date"}),
    "rwb_datahub_status": frozenset({"query_id", "offset", "limit"}),
    "rwb_datahub_cancel": frozenset({"query_id"}),
}
TOOL_ARGUMENTS.update(DATA_TOOL_ARGUMENTS)
CONFIGURED_TOOL_ARGUMENTS = {
    "rwb_datahub_catalog": frozenset(),
    "rwb_datahub_business_query": frozenset({"request_id", "query"}),
}
TOOL_ARGUMENTS.update(CONFIGURED_TOOL_ARGUMENTS)
TASK_TOOL_ARGUMENTS = {
    name: frozenset(schema.model_fields) for name, (_, _, schema, _) in TASKS.items()
}
CONFIGURED_TOOL_ARGUMENTS.update(TASK_TOOL_ARGUMENTS)
TOOL_ARGUMENTS.update(TASK_TOOL_ARGUMENTS)
UUIDArg = Annotated[
    str, Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
]
FileArg = Annotated[str, Field(pattern=r"^[0-9a-f]{24}$")]
Offset = Annotated[int, Field(ge=0, le=100000000, strict=True)]
RowsLimit = Annotated[int, Field(ge=1, le=500, strict=True)]
TextLimit = Annotated[int, Field(ge=1, le=12000, strict=True)]


def register_tools(server, store, backend, datahub=None):
    annotations = ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
    )

    def principal(*, query=False):
        token = get_access_token()
        if token is None:
            raise ReadError("access_denied")
        try:
            record = store.verify_access(token.token, resource=store.resource)
        except AccountError as exc:
            log.warning("mcp_tool_authorization_denied")
            raise ToolError(
                "authorization_unavailable" if exc.status >= 500 else "access_denied"
            ) from None
        if (
            (record.user_id, record.client_id, record.issuer, record.scopes)
            != (
                token.subject,
                token.client_id,
                (token.claims or {}).get("iss"),
                tuple(token.scopes),
            )
            or SCOPE not in record.scopes
            or (query and DATA_SCOPE not in record.scopes)
        ):
            raise ReadError("access_denied")
        return record

    def materials(record):
        try:
            return store.list_grant_materials(record.grant_id, user_id=record.user_id)
        except AccountError as exc:
            log.warning("mcp_material_authorization_denied")
            raise ToolError(
                "authorization_unavailable" if exc.status >= 500 else "access_denied"
            ) from None

    def bounded(value):
        # The HTTP gate additionally bounds the actual SDK response envelope.
        if len(json.dumps(value, ensure_ascii=False).encode()) > RESPONSE_BYTES // 2:
            raise ToolError("response_too_large")
        return value

    def describe(material):
        return {
            "context_id": material.context_id,
            "kind": material.kind,
            "object_id": material.object_id,
            "sha256": material.sha256,
            "digest_status": "approved_expected_original",
            "availability": "not_checked",
            "physical_verification": "not_checked",
            "classification": material.classification,
            "metadata": {
                "status": "missing",
                "title": None,
                "provider": None,
                "as_of": None,
                "url": None,
                "pit": "unknown",
            },
        }

    def checked_listing(context_id=None, kind=None):
        record = principal()
        selected = materials(record)
        usable = [m for m in selected if m.kind in {"dataset", "source"}]
        try:
            for material in usable:
                canonical_id(material.context_id)
                canonical_id(material.object_id, file=material.kind == "source")
            if context_id is not None:
                canonical_id(context_id)
        except ReadError:
            raise ToolError("unsupported_material_identifier") from None
        if context_id is not None and not any(m.context_id == context_id for m in usable):
            raise ToolError("access_denied")
        result = [
            describe(m)
            for m in usable
            if (context_id is None or m.context_id == context_id)
            and (kind is None or m.kind == kind)
        ]
        current = principal()
        if current != record or selected != materials(current):
            raise ToolError("access_denied")
        return result

    async def read(kind, context_id, object_id, offset, limit, view="rows"):
        try:
            canonical_id(context_id)
            canonical_id(object_id, file=kind == "source")
            record = principal()
            material = next(
                (
                    item
                    for item in materials(record)
                    if (item.context_id, item.kind, item.object_id) == (context_id, kind, object_id)
                ),
                None,
            )
            if material is None:
                raise ReadError("access_denied")
            result = await backend.read(
                record.user_id, material, offset=offset, limit=limit, view=view
            )
            current = principal()
            if current != record or material not in materials(current):
                raise ReadError("access_denied")
            log.info("mcp_frozen_read_completed", kind=kind)
            return bounded(
                {
                    "context_id": context_id,
                    "object_id": object_id,
                    "classification": material.classification,
                    **result,
                }
            )
        except (ReadError, AccountError) as exc:
            code = (
                str(exc)
                if isinstance(exc, ReadError)
                else "authorization_unavailable" if exc.status >= 500 else "access_denied"
            )
            log.warning("mcp_frozen_read_denied", code=code)
            raise ToolError(code) from None

    @server.tool(annotations=annotations)
    def rwb_capabilities_list() -> dict:
        """Discover approved frozen data capabilities and usable grant contexts without backend allocation."""
        approved = checked_listing()
        context_ids = sorted({m["context_id"] for m in approved})
        return bounded(
            {
                "tools": [
                    "rwb_capabilities_list",
                    "rwb_datasets_list",
                    "rwb_dataset_read",
                    "rwb_source_read",
                ],
                "scope": SCOPE,
                "execution": False,
                "rows_limit": 500,
                "text_limit": 12000,
                "materials": "explicit_grant_only",
                "contexts": [
                    {
                        "context_id": sid,
                        "metadata": {"status": "missing", "title": None},
                        "materials": [m for m in approved if m["context_id"] == sid],
                    }
                    for sid in context_ids
                ],
                "data_capabilities": [
                    {
                        "kind": kind,
                        "context_ids": sorted(
                            {m["context_id"] for m in approved if m["kind"] == kind}
                        ),
                        "views": (
                            ["manifest", "rows"] if kind == "dataset" else ["references", "text"]
                        ),
                        "source": "approved_material_registry",
                        "execution": False,
                    }
                    for kind in sorted({m["kind"] for m in approved})
                ],
            }
        )

    @server.tool(annotations=annotations)
    def rwb_datasets_list(context_id: UUIDArg) -> dict:
        """List only approved frozen datasets in one authorized grant context."""
        return bounded({"context_id": context_id, "items": checked_listing(context_id, "dataset")})

    @server.tool(annotations=annotations)
    async def rwb_dataset_read(
        context_id: UUIDArg,
        dataset_id: UUIDArg,
        offset: Offset = 0,
        limit: RowsLimit = 100,
        view: Literal["manifest", "rows"] = "rows",
    ) -> dict:
        """Read the original approved manifest or a page from fully hash-verified frozen rows."""
        return await read("dataset", context_id, dataset_id, offset, limit, view)

    @server.tool(annotations=annotations)
    async def rwb_source_read(
        context_id: UUIDArg,
        file_id: FileArg | None = None,
        offset: Offset = 0,
        limit: TextLimit = 12000,
    ) -> dict:
        """Omit file_id to list approved context sources; otherwise read verified frozen UTF8 text."""
        if file_id is None:
            return bounded(
                {"context_id": context_id, "items": checked_listing(context_id, "source")}
            )
        return await read("source", context_id, file_id, offset, limit)

    if datahub is None:
        return

    async def data_operation(operation, *args, **kwargs):
        try:
            record = principal(query=True)
            result = await operation(record, *args, **kwargs)
            if principal(query=True) != record:
                raise ReadError("access_denied")
            return bounded(result)
        except (ReadError, AccountError, ValueError) as exc:
            code = (
                str(exc)
                if isinstance(exc, ReadError)
                else "invalid_data_query" if isinstance(exc, ValueError) else "access_denied"
            )
            log.warning("mcp_public_data_operation_rejected", code=code)
            raise ToolError(code) from None

    execution = ToolAnnotations(
        readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True
    )

    @server.tool(annotations=execution)
    async def rwb_datahub_query(
        request_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9_.:-]{1,64}$")],
        source: Literal["ext_fred", "ext_bls"],
        series_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9_]{1,64}$")],
        start_date: str,
        end_date: str,
    ) -> dict:
        """Submit a FRED/BLS public series query (at most 366 days), creating a frozen DataHub snapshot. Pass the returned id to rwb_datahub_status; reuse request_id only for identical inputs. No model or script execution."""
        return await data_operation(
            datahub.query, request_id, source, series_id, start_date, end_date
        )

    @server.tool(annotations=annotations)
    async def rwb_datahub_status(
        query_id: UUIDArg, offset: Offset = 0, limit: RowsLimit = 100
    ) -> dict:
        """Read this grant's query status and verified frozen result, preserving source/units/missing/as_of/PIT and pagination. status=completed only means execution ended; check data_success separately."""
        return await data_operation(datahub.status, query_id, offset=offset, limit=limit)

    @server.tool(annotations=execution)
    async def rwb_datahub_cancel(query_id: UUIDArg) -> dict:
        """Cancel this grant's exact pending public-data query; completed data is retained and never refetched."""
        return await data_operation(datahub.cancel, query_id)

    @server.tool(annotations=annotations)
    async def rwb_datahub_catalog() -> dict:
        """List this account's callable DataHub sources, implemented bindings and business parameters. Reuses existing configuration and permissions; does not call suppliers or return credentials."""
        return await data_operation(datahub.configured_catalog)

    @server.tool(annotations=execution)
    async def rwb_datahub_business_query(
        request_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9_.:-]{1,64}$")],
        query: dict,
    ) -> dict:
        """Submit a DataHub BusinessQuery for an explicit source/capability returned by rwb_datahub_catalog. query contains capability, source, parameters and optional purpose/quality/refresh; no credentials or arbitrary endpoints. Uses that account's configured provider without fallback. Read the returned id with rwb_datahub_status; check data_success, provenance, units, missing values and PIT separately."""
        return await data_operation(datahub.configured_query, request_id, query)

    if callable(getattr(datahub, "task_query", None)):
        for name, (domain, _, schema, description) in TASKS.items():

            def build_task(tool_name, argument_model, business_domain, text):
                async def operation(**arguments) -> dict:
                    return await data_operation(datahub.task_query, tool_name, arguments)

                operation.__name__ = tool_name
                operation.__doc__ = (
                    f"[{business_domain}] {text} "
                    "返回原查询 id；使用 rwb_datahub_status(query_id=id)读取冻结结果与分页，"
                    "核对 data_success、单位、缺失与 PIT。request_id 同键同参复用。"
                )
                annotations_map = {"return": dict}
                parameters = []
                for key, field in argument_model.model_fields.items():
                    annotations_map[key] = field.rebuild_annotation()
                    if field.description:
                        annotations_map[key] = Annotated[
                            annotations_map[key], Field(description=field.description)
                        ]
                    default = inspect.Parameter.empty
                    if not field.is_required():
                        default = field.get_default(call_default_factory=True)
                    parameters.append(
                        inspect.Parameter(
                            key,
                            inspect.Parameter.KEYWORD_ONLY,
                            default=default,
                            annotation=annotations_map[key],
                        )
                    )
                operation.__annotations__ = annotations_map
                operation.__signature__ = inspect.Signature(parameters, return_annotation=dict)
                return operation

            server.tool(annotations=execution)(build_task(name, schema, domain, description))
