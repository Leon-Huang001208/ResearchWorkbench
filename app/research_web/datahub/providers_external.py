"""Bounded, cancellable reads of named endpoints from the external-source inventory."""

import asyncio
import csv
import hashlib
import hmac
import io
import json
import re
import time
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote, urlsplit
from xml.etree import ElementTree

import httpx

from core.observability import get_logger

from .contracts import BusinessQuery
from .external_sources import (
    EXTERNAL_SOURCES,
    credential_transport_blocked,
    inventory_rows,
    readable_endpoints,
)
from .providers import DEADLINE, MAX_RESPONSE_BYTES, MAX_ROWS, ProviderError, Result

log = get_logger(__name__)
_PRIVATE_KEYS = re.compile(
    r"(?:password|secret|token|api_?key|authorization|cookie|headers?|url|host|proxy|redirect|callback|path|module|sql)",
    re.IGNORECASE,
)


def arguments(value: str | None) -> dict[str, Any]:
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, ValueError):
        raise ProviderError("external_arguments_invalid") from None
    if not isinstance(parsed, dict) or set(parsed) - {"params", "query", "body"}:
        raise ProviderError("external_arguments_invalid")

    def validate(item: Any, depth: int = 0) -> None:
        if depth > 8:
            raise ProviderError("external_arguments_invalid")
        if isinstance(item, dict):
            if len(item) > 50 or any(_PRIVATE_KEYS.search(key) for key in item):
                raise ProviderError("external_arguments_forbidden")
            for child in item.values():
                validate(child, depth + 1)
        elif isinstance(item, list):
            if len(item) > 100:
                raise ProviderError("external_arguments_invalid")
            for child in item:
                validate(child, depth + 1)
        elif item is not None and not isinstance(item, (str, int, float, bool)):
            raise ProviderError("external_arguments_invalid")

    validate(parsed)
    for key in ("params", "query", "body"):
        if key in parsed and not isinstance(parsed[key], dict):
            raise ProviderError("external_arguments_invalid")
    return parsed


def endpoint_request(
    source_id: str, dataset: str, args: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    endpoint = next((ep for ep in readable_endpoints(source_id) if ep["id"] == dataset), None)
    if endpoint is None:
        raise ProviderError("external_dataset_unknown")
    params = args.get("params", {})
    names = set(re.findall(r"\{(\w+)\}", endpoint["url"]))
    if set(params) != names:
        raise ProviderError("external_parameters_mismatch")
    url = endpoint["url"]
    for name, value in params.items():
        if not isinstance(value, (str, int)) or isinstance(value, bool):
            raise ProviderError("external_parameters_invalid")
        text = str(value)
        if len(text) > 500 or any(ord(c) < 32 for c in text):
            raise ProviderError("external_parameters_invalid")
        if "{" + name + "}" in endpoint["url"].split("?", 1)[0] and (
            text in {".", ".."} or "/" in text or "\\" in text or "%" in text
        ):
            raise ProviderError("external_parameters_invalid")
        url = url.replace("{" + name + "}", quote(text, safe=""))
    original, rendered = urlsplit(endpoint["url"]), urlsplit(url)
    if original.netloc != rendered.netloc or rendered.username or rendered.fragment:
        raise ProviderError("external_destination_invalid")
    query = args.get("query", {})
    if any(not isinstance(value, (str, int, float, bool)) for value in query.values()):
        raise ProviderError("external_parameters_invalid")
    if endpoint["method"] == "GET" and args.get("body"):
        raise ProviderError("external_body_not_allowed")
    return endpoint, url


_NESTED_LIST_KEYS = (
    "refRates",
    "items",
    "data",
    "results",
    "records",
    "rows",
    "entries",
    "articles",
    "events",
    "series",
    "points",
    "values",
    "tables",
    "list",
)


def _list_payload(payload: Any) -> list[Any] | None:
    """Dict payloads with a primary list become real rows so samples stay small."""

    if not isinstance(payload, dict):
        return None
    results = payload.get("Results")
    if isinstance(results, dict) and isinstance(results.get("series"), list) and results["series"]:
        return results["series"]
    for key in _NESTED_LIST_KEYS:
        value = payload.get(key)
        if isinstance(value, list) and value:
            return value
    return None


class PageText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data: str) -> None:
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


def response_rows(raw: bytes, content_type: str, encoding: str = "utf-8") -> list[dict[str, Any]]:
    text = raw.decode(encoding, errors="replace")
    stripped = text.lstrip()
    if "json" in content_type or stripped.startswith(("{", "[")):
        try:
            payload = json.loads(text)
        except ValueError:
            raise ProviderError("external_invalid_json") from None
        if isinstance(payload, dict):
            for key in ("errorcode", "error_code", "errcode"):
                if key in payload and payload[key] not in (0, "0", None):
                    raise ProviderError("vendor_rejected")
            if payload.get("success") is False or payload.get("error"):
                raise ProviderError("vendor_rejected")
            if "code" in payload and payload["code"] not in (0, "0", 200, "200", None):
                raise ProviderError("vendor_rejected")
            if isinstance(payload.get("chart"), dict) and payload["chart"].get("error"):
                raise ProviderError("vendor_rejected")
        list_rows = _list_payload(payload)
        if list_rows is not None:
            return [row if isinstance(row, dict) else {"value": row} for row in list_rows]
        if isinstance(payload, list):
            return [row if isinstance(row, dict) else {"value": row} for row in payload]
        return [payload if isinstance(payload, dict) else {"value": payload}]
    if "csv" in content_type or stripped.startswith(("DATE,", "observation_date,")):
        return list(csv.DictReader(io.StringIO(text.lstrip("\ufeff"))))
    if "xml" in content_type or stripped.startswith(("<?xml", "<rss", "<feed")):
        if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
            raise ProviderError("external_xml_invalid")
        try:
            root = ElementTree.fromstring(text)
        except ElementTree.ParseError:
            raise ProviderError("external_xml_invalid") from None
        entries = [
            item
            for item in root.iter()
            if item.tag.rsplit("}", 1)[-1] in {"item", "entry", "event"}
        ]
        return [
            {
                child.tag.rsplit("}", 1)[-1]: "".join(child.itertext()).strip() or child.get("href")
                for child in entry
            }
            for entry in entries
        ] or [{"text": text}]
    if "html" in content_type or stripped.lower().startswith(("<html", "<!doctype html")):
        parser = PageText()
        parser.feed(text)
        return [{"text": "\n".join(parser.parts), "format": "page_text"}]
    return [{"text": text, "format": "source_text"}]


def _rows_reflect_credentials(rows: list[dict[str, Any]], secrets: list[str]) -> bool:
    """Inspect decoded strings before publishing; never log credential contents."""
    sensitive = tuple(secret for secret in secrets if secret)
    if not sensitive:
        return False
    pending: list[Any] = [rows]
    while pending:
        value = pending.pop()
        if isinstance(value, str):
            if any(secret in value for secret in sensitive):
                return True
        elif isinstance(value, dict):
            pending.extend(value.keys())
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
    return False


async def bounded_response(
    client: httpx.AsyncClient, method: str, url: str, **kwargs: Any
) -> tuple[bytes, str, str]:
    async with client.stream(method, url, **kwargs) as response:
        if response.is_redirect:
            raise ProviderError("redirect_denied")
        if response.status_code != 200:
            raise ProviderError(f"http_{response.status_code}")
        chunks, size = [], 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                raise ProviderError("response_size_limit")
            chunks.append(chunk)
        return (
            b"".join(chunks),
            response.headers.get("content-type", ""),
            response.encoding or "utf-8",
        )


async def credentials(
    client: httpx.AsyncClient, source_id: str, connections: Any
) -> tuple[str, list[str]]:
    if connections is None:
        raise ProviderError("blocked_config")
    try:
        secret = await asyncio.to_thread(connections.read_source_secret, source_id)
    except Exception:  # noqa: BLE001 - credential backends must fail closed without secret details.
        raise ProviderError("blocked_config") from None
    if not isinstance(secret, str) or not secret:
        raise ProviderError("blocked_config")
    if source_id != "ext_ths":
        return secret, [secret]
    # Access-token rotation stays inside the provider, never in dataset rows.
    try:
        config = json.loads(secret) if secret.startswith("{") else {"access_token": secret}
        if not isinstance(config, dict):
            raise ProviderError("vendor_auth_failed")
        refresh = config.get("refresh_token")
        if refresh:
            if not isinstance(refresh, str):
                raise ProviderError("vendor_auth_failed")
            raw, _, _ = await bounded_response(
                client,
                "POST",
                "https://quantapi.51ifind.com/api/v1/get_access_token",
                headers={"refresh_token": config["refresh_token"]},
            )
            body = json.loads(raw)
            if not isinstance(body, dict) or not isinstance(body.get("data"), dict):
                raise ProviderError("vendor_auth_failed")
            token = body["data"].get("access_token")
            if body.get("errorcode", 0) != 0 or not isinstance(token, str) or not token:
                raise ProviderError("vendor_auth_failed")
            return token, [secret, refresh, token]
        token = config["access_token"]
        if not isinstance(token, str) or not token:
            raise ProviderError("vendor_auth_failed")
        return token, [secret, token]
    except (KeyError, TypeError, ValueError):
        raise ProviderError("vendor_auth_failed") from None


async def cicc_request(
    client: httpx.AsyncClient, url: str, args: dict[str, Any], secret: str
) -> tuple[tuple[bytes, str, str], list[str]]:
    if urlsplit(url).scheme != "https":
        raise ProviderError("credential_transport_blocked")
    try:
        config = json.loads(secret)
        app_id, app_secret = config["app_id"], config["app_secret"]
        if (
            not isinstance(app_id, str)
            or not isinstance(app_secret, str)
            or not app_id
            or not app_secret
        ):
            raise ProviderError("blocked_config")
    except (ValueError, KeyError, TypeError):
        raise ProviderError("blocked_config") from None
    token_raw, _, _ = await bounded_response(
        client,
        "POST",
        "https://www.research.cicc.com/api/oauth2.0/accessToken",
        data={"grant_type": "client_credentials", "client_id": app_id, "client_secret": app_secret},
    )
    token_body = json.loads(token_raw)
    if not isinstance(token_body, dict) or not isinstance(token_body.get("data"), dict):
        raise ProviderError("vendor_auth_failed")
    if token_body.get("code") != 0:
        raise ProviderError("vendor_auth_failed")
    token = token_body.get("data", {}).get("accessToken")
    if not isinstance(token, str) or not token:
        raise ProviderError("vendor_auth_failed")
    body = json.dumps(args.get("body", {}))
    params = {"timestamp": str(int(time.time() * 1000))}
    signing = "\n".join(
        [
            "POST",
            "/llm/dianjing-agent/search/integration",
            "timestamp=" + params["timestamp"],
            hashlib.sha256(body.encode()).hexdigest(),
        ]
    )
    signature = hmac.new(app_secret.encode(), signing.encode(), hashlib.sha256).hexdigest()
    response = await bounded_response(
        client,
        "POST",
        url,
        params=params,
        content=body,
        headers={
            "Authorization": "Bearer " + token,
            "X-CICC-Signature": signature,
            "Content-Type": "application/json",
        },
    )
    return response, [app_secret, token]


async def fetch(
    query: BusinessQuery,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    connections: Any = None,
) -> Result:
    source_id = query.source
    result = Result(provider_id=source_id)
    try:
        dataset = query.parameters.get("dataset", "catalog")
        if dataset == "catalog":
            result.rows = inventory_rows(source_id)
            result.status = "snapshot"
            result.limitations = ["目录信息不代表实时取数验证。"]
            return result
        if source_id not in EXTERNAL_SOURCES:
            raise ProviderError("external_source_required")
        args = arguments(query.parameters.get("arguments_json"))
        endpoint, url = endpoint_request(source_id, dataset, args)
        if credential_transport_blocked(endpoint):
            raise ProviderError("credential_transport_blocked")
        limit = query.parameters.get("limit", MAX_ROWS)
        if type(limit) is not int or not 1 <= limit <= MAX_ROWS:
            raise ProviderError("external_limit_invalid")
        reflected: list[str] = []
        async with asyncio.timeout(DEADLINE):
            async with httpx.AsyncClient(
                transport=transport,
                timeout=DEADLINE,
                trust_env=False,
                follow_redirects=False,
                headers={
                    "User-Agent": "Mozilla/5.0 ResearchWorkbench/1.0",
                    "Accept": "application/json,text/csv,application/xml,text/html",
                },
            ) as client:
                headers = dict(endpoint.get("headers", {}))
                if endpoint.get("specialAuth"):
                    secret, reflected = await credentials(client, source_id, connections)
                    (raw, content_type, encoding), exchanged = await cicc_request(
                        client, url, args, secret
                    )
                    reflected.extend(exchanged)
                else:
                    if endpoint.get("auth"):
                        secret, sensitive = await credentials(client, source_id, connections)
                        reflected.extend(sensitive)
                        auth = endpoint["auth"]
                        headers[auth["header"]] = auth.get("prefix", "") + secret
                    request = {"headers": headers}
                    if args.get("query"):
                        # Preserve fixed query parameters while applying explicit business filters.
                        combined = dict(httpx.URL(url).params)
                        combined.update(args["query"])
                        request["params"] = combined
                    if endpoint["method"] == "POST":
                        request["json"] = args.get("body", {})
                    raw, content_type, encoding = await bounded_response(
                        client, endpoint["method"], url, **request
                    )
        if any(value and value.encode() in raw for value in reflected):
            raise ProviderError("credential_reflection")
        rows = response_rows(raw, content_type, encoding)
        if _rows_reflect_credentials(rows, reflected):
            raise ProviderError("credential_reflection")
        result.rows = rows[:limit]
        result.status = "partial" if len(rows) > limit else "snapshot" if rows else "empty"
        result.raw = [raw]
        result.raw_bytes = len(raw)
        result.pages_fetched = 1
        result.source_url = url
        result.as_of = datetime.now(UTC).isoformat()
        result.fields = {
            key: {"type": "source", "unit": "provider_defined"}
            for row in result.rows
            for key in row
        }
        result.limitations = ["single_response_not_complete_history", "provider_native_fields"]
        if len(rows) > limit:
            result.limitations.append("row_limit")
    except asyncio.CancelledError:
        log.info("external_source_cancelled", source=source_id)
        raise
    except (ProviderError, httpx.HTTPError, TimeoutError, ValueError, LookupError) as exc:
        reason = (
            str(exc)
            if isinstance(exc, ProviderError)
            else (
                "deadline"
                if isinstance(exc, TimeoutError)
                else "external_transport_or_schema_error"
            )
        )
        result.status = "failed"
        result.rows = []
        result.raw = []
        result.limitations = [reason]
        log.warning("external_source_failed", source=source_id, reason=reason)
    return result
