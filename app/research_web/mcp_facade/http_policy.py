"""Bound entire SDK HTTP envelopes before disclosing any response bytes."""

from mcp.types import (
    ErrorData,
    InitializeRequest,
    JSONRPCError,
    JSONRPCRequest,
    jsonrpc_message_adapter,
)
from pydantic import ValidationError
from starlette.responses import JSONResponse

from core.observability import get_logger

from ..multiuser.accounts import AccountError
from .config import PROTOCOL, REQUEST_BYTES, RESPONSE_BYTES

log = get_logger(__name__)


class LimitExceeded(Exception):
    pass


class BoundedHTTP:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > REQUEST_BYTES:
                return await JSONResponse({"error": "request_too_large"}, status_code=413)(
                    scope, receive, send
                )
            if not message.get("more_body", False):
                break
        if scope["path"] == "/mcp" and scope["method"] == "POST":
            request_id = None
            try:
                parsed = jsonrpc_message_adapter.validate_json(bytes(body))
                if isinstance(parsed, JSONRPCRequest):
                    request_id = parsed.id
                versions = [v for k, v in scope["headers"] if k.lower() == b"mcp-protocol-version"]
                initialize = isinstance(parsed, JSONRPCRequest) and parsed.method == "initialize"
                if initialize:
                    request = InitializeRequest.model_validate(
                        parsed.model_dump(exclude_none=True), by_name=False
                    )
                    if request.params.protocol_version < PROTOCOL:
                        raise ValueError("unsupported_protocol")
                    if versions not in (
                        [],
                        [PROTOCOL.encode()],
                        [request.params.protocol_version.encode()],
                    ):
                        raise ValueError("unsupported_protocol")
                    # Let the SDK legacy runner counteroffer 2025 for newer typed
                    # offers. The JSON body remains exactly the client bytes.
                    scope = dict(scope)
                    scope["headers"] = [
                        (k, v) for k, v in scope["headers"] if k.lower() != b"mcp-protocol-version"
                    ] + [(b"mcp-protocol-version", PROTOCOL.encode())]
                else:
                    if versions != [PROTOCOL.encode()]:
                        raise ValueError("unsupported_protocol")
            except (ValidationError, ValueError):
                error = JSONRPCError(
                    jsonrpc="2.0",
                    id=request_id,
                    error=ErrorData(code=-32600, message="invalid_request_or_protocol"),
                )
                return await JSONResponse(
                    error.model_dump(by_alias=True, exclude_none=False), status_code=400
                )(scope, receive, send)
        replayed = False

        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        messages = []
        size = 0

        async def capture(message):
            nonlocal size
            size += len(message.get("body", b""))
            if size > RESPONSE_BYTES:
                raise LimitExceeded
            messages.append(message)

        try:
            await self.app(scope, replay, capture)
        except LimitExceeded:
            log.warning("mcp_response_limit_exceeded")
            return await JSONResponse({"error": "response_too_large"}, status_code=413)(
                scope, receive, send
            )
        except AccountError:
            log.warning("mcp_authorization_store_unavailable")
            return await JSONResponse({"error": "temporarily_unavailable"}, status_code=503)(
                scope, receive, send
            )
        for message in messages:
            await send(message)
