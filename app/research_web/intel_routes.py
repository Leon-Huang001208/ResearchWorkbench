"""Read-only intelligence radar adapter for the fixed public Golddata service."""

import asyncio
import json
from typing import Annotated, Literal
from urllib.parse import quote

import httpx
from fastapi import APIRouter, HTTPException, Path, Query

from core.observability import get_logger

router = APIRouter(prefix="/api/research/intel", tags=["intelligence-radar"])
log = get_logger(__name__)
UPSTREAM = "http://47.92.168.126/vibe-research/api"
RESPONSE_LIMIT = 16 * 1024 * 1024
Identifier = Annotated[str, Path(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9_-]+$")]
StockCode = Annotated[str, Query(pattern=r"^[0-9]{6}$")]


def _failure(code: str, message: str, status: int = 502) -> HTTPException:
    log.warning("intel_upstream_failed", code=code)
    return HTTPException(status_code=status, detail={"code": code, "message": message})


async def read_upstream(path: str, params: dict | None = None):
    """Fetch bounded JSON without forwarding local credentials or redirects."""
    try:
        async with asyncio.timeout(20):
            async with (
                httpx.AsyncClient(timeout=20, follow_redirects=False, trust_env=False) as client,
                client.stream("GET", UPSTREAM + path, params=params) as response,
            ):
                if response.status_code == 404:
                    raise _failure("intel_not_found", "资讯内容已不存在。", 404)
                if response.status_code != 200:
                    raise _failure("intel_upstream_unavailable", "资讯服务暂不可用，请稍后重试。")
                mime = response.headers.get("content-type", "").split(";", 1)[0].strip()
                if mime != "application/json" and not mime.endswith("+json"):
                    raise _failure("intel_invalid_response", "资讯服务返回了异常数据。")
                chunks = bytearray()
                async for chunk in response.aiter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > RESPONSE_LIMIT:
                        raise _failure("intel_response_too_large", "资讯数据过大，请稍后重试。")
                payload = json.loads(chunks)
                data = payload.get("data", payload) if isinstance(payload, dict) else payload
                if not isinstance(data, (dict, list)):
                    raise _failure("intel_invalid_response", "资讯服务返回了异常数据。")
                log.info("intel_upstream_read", endpoint=path.split("/")[1])
                return data
    except (httpx.TimeoutException, TimeoutError) as exc:
        raise _failure("intel_upstream_timeout", "资讯读取超时，请重试。", 504) from exc
    except httpx.HTTPError as exc:
        raise _failure("intel_upstream_unavailable", "无法连接资讯服务，请稍后重试。") from exc
    except (ValueError, UnicodeError) as exc:
        raise _failure("intel_invalid_response", "资讯服务返回了异常数据。") from exc


@router.get("/overview")
async def overview(impact: Literal["all", "medium_high", "high"] = "medium_high"):
    return await read_upstream("/intelligence", {"impact": impact, "view": "compact"})


@router.get("/story-focus")
async def story_focus():
    return await read_upstream("/intelligence/story-focus")


@router.get("/breakfast-focus")
async def breakfast_focus():
    return await read_upstream("/intelligence/breakfast-focus")


@router.get("/events/{event_id}")
async def event_detail(event_id: Identifier):
    return await read_upstream(f"/intelligence/events/{quote(event_id, safe='')}")


@router.get("/reports")
async def reports(
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
):
    return await read_upstream("/report-records", {"limit": limit, "offset": offset})


@router.get("/reports/{report_id}")
async def report_detail(report_id: Identifier):
    return await read_upstream(f"/report-records/{quote(report_id, safe='')}")


@router.get("/radar")
async def radar():
    return await read_upstream("/radar")


@router.get("/wsc")
async def wsc(cursor: Annotated[str | None, Query(max_length=256)] = None):
    return await read_upstream("/wsc/live", {"cursor": cursor} if cursor else None)


@router.get("/social")
async def social():
    return await read_upstream("/social/accounts")


@router.get("/news")
async def news(code: StockCode):
    return await read_upstream("/news", {"code": code})


@router.get("/announcements")
async def announcements(code: StockCode):
    return await read_upstream("/announcements", {"code": code})
