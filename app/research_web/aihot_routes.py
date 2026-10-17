"""Owned local AIHOT reading adapter; no public-site fallback or model calls."""

import asyncio
import hashlib
import json
import math
import re
import time
from collections import OrderedDict
from collections.abc import Callable
from datetime import date
from email.utils import parsedate_to_datetime
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, HTTPException, Path, Query, Request

from core.observability import get_logger
from research_workbench_entrypoint.ai_news_transport import AiNewsConnection, AiNewsError

from .aihot_content import reading_tree
from .aihot_media import AihotMedia

router = APIRouter(prefix="/api/research/aihot", tags=["aihot"])
log = get_logger(__name__)
RESPONSE_LIMIT = 2 * 1024 * 1024
EditionDate = Annotated[str, Path(pattern=r"^\d{4}-\d{2}-\d{2}$")]


def _failure(code: str, message: str, status: int = 502, retry: int | None = None):
    log.warning("aihot_read_failed", code=code, status=status)
    return HTTPException(
        status_code=status,
        detail={"code": code, "message": message},
        headers={"Retry-After": str(retry)} if retry else None,
    )


def _ttl(headers: httpx.Headers, previous: int = 60) -> int:
    control = headers.get("cache-control", "")
    match = re.search(r"(?:^|,)\s*s-maxage=(\d+)", control) or re.search(
        r"(?:^|,)\s*max-age=(\d+)", control
    )
    return max(60, int(match[1])) if match else previous


class AihotReader:
    """Per-app bounded LRU with conditional revalidation and shared cooldowns."""

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
        connection: Callable[[], AiNewsConnection] | None = None,
    ):
        self.clock = clock
        self.wall_clock = wall_clock
        self.connection = connection
        self._transport_identity = None
        self.cache: OrderedDict[str, dict] = OrderedDict()
        self.lock = asyncio.Lock()
        self.media = AihotMedia(connection=connection)

    async def read(self, endpoint: str) -> dict:
        try:
            if self.connection is None:
                raise AiNewsError("ai_news_not_configured")
            connection = self.connection()
            headers = connection.headers()
            identity = (
                connection.endpoint,
                hashlib.sha256(headers["x-rwb-ai-news-token"].encode()).hexdigest(),
            )
            if self._transport_identity is not None and self._transport_identity != identity:
                self.cache.clear()
                self.media.urls.clear()
            self._transport_identity = identity
            cached = self._fresh(endpoint)
            if cached is not None:
                return self._project(endpoint, cached)
            async with asyncio.timeout(20):
                async with self.lock:
                    payload = await self._read(endpoint)
            return self._project(endpoint, payload)
        except AiNewsError as exc:
            raise _failure(str(exc), "AI 资讯自主服务尚未配置或未启动。", 503) from None
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise _failure("aihot_timeout", "AIHOT 读取超时，请重试。", 504) from exc
        except httpx.HTTPError as exc:
            raise _failure("aihot_unavailable", "无法连接 AIHOT，请稍后重试。") from exc
        except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
            raise _failure("aihot_invalid_response", "AIHOT 返回了异常数据。") from exc

    def _project(self, endpoint: str, payload: dict) -> dict:
        if not endpoint.startswith("/site/"):
            return payload
        result = self.media.project(payload)
        if endpoint.startswith("/site/items/") and isinstance(result.get("body"), dict):
            body = result["body"]
            html = body.get("original") if endpoint.endswith("/original") else body.get("zh")
            html = html or body.get("original") or body.get("zh") or ""
            result["body"] = {
                key: value for key, value in body.items() if key not in {"zh", "original"}
            }
            result["body"]["content"] = reading_tree(
                html,
                self.media._image,
                source_base=(result.get("links") or {}).get("original"),
                local_origin=self.connection().endpoint if self.connection else None,
            )
        return result

    def _fresh(self, endpoint: str) -> dict | None:
        previous = self.cache.get(endpoint)
        if previous:
            self.cache.move_to_end(endpoint)
            if self.clock() < previous["until"]:
                if "failure" in previous:
                    status, code, message = previous["failure"]
                    remaining = max(1, int(previous["until"] - self.clock()) + 1)
                    raise _failure(code, message, status, remaining)
                return previous["payload"]
        return None

    async def _read(self, endpoint: str) -> dict:
        cached = self._fresh(endpoint)
        if cached is not None:
            return cached
        previous = self.cache.get(endpoint)
        if self.connection is None:
            raise AiNewsError("ai_news_not_configured")
        connection = self.connection()
        headers = {"User-Agent": "ResearchWorkbench-AIHOT/1.0", "Accept": "application/json"}
        headers.update(connection.headers())
        if previous and previous.get("etag"):
            headers["If-None-Match"] = previous["etag"]
        async with (
            httpx.AsyncClient(timeout=20, follow_redirects=False, trust_env=False) as client,
            client.stream(
                "GET",
                connection.endpoint
                + ("/api" if endpoint.startswith("/site/") else "/api/v1")
                + endpoint,
                headers=headers,
            ) as response,
        ):
            if response.status_code == 304 and previous and "payload" in previous:
                previous["ttl"] = _ttl(response.headers, previous["ttl"])
                previous["until"] = self.clock() + previous["ttl"]
                log.info("aihot_read_revalidated")
                return previous["payload"]
            if response.status_code in (429, 503):
                raw_retry = response.headers.get("retry-after", "60")
                try:
                    retry = (
                        int(raw_retry)
                        if raw_retry.isdigit()
                        else math.ceil(
                            parsedate_to_datetime(raw_retry).timestamp() - self.wall_clock()
                        )
                    )
                except (ValueError, TypeError, OverflowError):
                    retry = 60
                retry = max(60, retry)
                message = "AIHOT 暂时限流或不可用，请稍后重试。"
                self._remember(
                    endpoint,
                    {
                        "until": self.clock() + retry,
                        "failure": (response.status_code, "aihot_retry_later", message),
                    },
                )
                raise _failure("aihot_retry_later", message, response.status_code, retry)
            if response.status_code == 404:
                raise _failure("aihot_not_found", "该内容不存在、已撤回或暂不可用。", 404)
            if response.status_code not in (
                {200, 308} if endpoint.startswith("/site/stories/") else {200}
            ):
                raise _failure("aihot_unavailable", "AIHOT 暂不可用，请稍后重试。")
            mime = response.headers.get("content-type", "").split(";", 1)[0].strip()
            if mime != "application/json":
                raise _failure("aihot_invalid_response", "AIHOT 返回了异常数据。")
            body = bytearray()
            async for chunk in response.aiter_bytes():
                if len(body) + len(chunk) > RESPONSE_LIMIT:
                    raise _failure("aihot_response_too_large", "AIHOT 数据超出读取上限。")
                body.extend(chunk)
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise TypeError("invalid AIHOT payload")
            if endpoint.startswith("/site/"):
                self._validate_page(endpoint, payload)
            elif payload.get("schemaVersion") != 1:
                raise ValueError("unsupported AIHOT schema")
            elif endpoint.startswith("/dailies/"):
                report = payload.get("report")
                if (
                    not isinstance(report, dict)
                    or report.get("date") != endpoint.rsplit("/", 1)[1]
                    or not isinstance(report.get("lead"), dict)
                    or not isinstance(report.get("sections"), list)
                    or not isinstance(report.get("flashes"), list)
                ):
                    raise ValueError("invalid AIHOT edition")
            elif not isinstance(payload.get("items"), list) or not all(
                isinstance(item, dict) for item in payload["items"]
            ):
                raise ValueError("invalid AIHOT collection")
            ttl = _ttl(response.headers)
            if "no-store" in response.headers.get("cache-control", "").lower():
                log.info("aihot_read_completed", kind="related")
                return payload
            self._remember(
                endpoint,
                {
                    "payload": payload,
                    "etag": response.headers.get("etag"),
                    "ttl": ttl,
                    "until": self.clock() + ttl,
                },
            )
            log.info(
                "aihot_read_completed",
                kind="report" if endpoint.startswith(("/dailies", "/site/reports")) else "hot",
            )
            return payload

    @staticmethod
    def _validate_page(endpoint: str, payload: dict) -> None:
        if endpoint.startswith("/site/items/"):
            if (
                payload.get("id") != endpoint.split("/")[3]
                or not isinstance(payload.get("title"), str)
                or not all(
                    isinstance(payload.get(key), list)
                    for key in ("outline", "relatedStories", "topics")
                )
                or (payload.get("body") is not None and not isinstance(payload.get("body"), dict))
            ):
                raise ValueError("invalid article identity")
        elif endpoint.startswith("/site/stories/"):
            merged = payload.get("mergedInto")
            if merged is not None:
                if not isinstance(merged, str) or not re.fullmatch(
                    r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", merged
                ):
                    raise ValueError("invalid merged story")
            elif (
                payload.get("publicId") != endpoint.rsplit("/", 1)[1]
                or not isinstance(payload.get("title"), str)
                or not all(
                    isinstance(payload.get(key), list)
                    for key in (
                        "timeline",
                        "developments",
                        "officialReports",
                        "heat",
                        "related",
                        "topics",
                    )
                )
                or not isinstance(payload.get("whyHot"), dict)
            ):
                raise ValueError("invalid story identity")
        elif endpoint.startswith("/site/groups/"):
            if payload.get("factId") != endpoint.split("/")[3] or not isinstance(
                payload.get("reports"), list
            ):
                raise ValueError("invalid reading group")
        elif endpoint.startswith("/site/topics/"):
            identity = endpoint.split("?")[0].rsplit("/", 1)[1]
            page = int(endpoint.rsplit("=", 1)[1])
            if (
                not isinstance(payload.get("topic"), dict)
                or payload["topic"].get("slug") != identity
                or not isinstance(payload.get("items"), list)
                or payload.get("page") != page
                or type(payload.get("pageCount")) is not int
                or payload["pageCount"] < 0
            ):
                raise ValueError("invalid topic identity")
        elif endpoint == "/site/hot":
            if not isinstance(payload.get("entries"), list) or not all(
                isinstance(item, dict)
                and isinstance(item.get("rank"), int)
                and not isinstance(item.get("rank"), bool)
                and 1 <= item["rank"] <= 10
                and isinstance(item.get("story"), dict)
                and isinstance(item.get("spark"), list)
                for item in payload["entries"]
            ):
                raise ValueError("invalid hot page")
        elif endpoint.endswith("/latest-page"):
            if not isinstance(payload.get("index"), list):
                raise ValueError("invalid report index")
            report = payload.get("report")
            if report is not None and (
                not isinstance(report, dict)
                or report.get("kind") != endpoint.split("/")[3]
                or not isinstance(report.get("key"), str)
                or not all(
                    isinstance(report.get(key), list)
                    for key in ("sections", "flashes", "highlights")
                )
            ):
                raise ValueError("invalid report page")
        elif "/navigation/" in endpoint or "/months/" in endpoint or len(endpoint.split("/")) == 4:
            if not isinstance(payload.get("items"), list):
                raise ValueError("invalid report navigation")
        elif (
            payload.get("kind") != endpoint.split("/")[3]
            or payload.get("key") != endpoint.rsplit("/", 1)[1]
            or not all(
                isinstance(payload.get(key), list) for key in ("sections", "flashes", "highlights")
            )
        ):
            raise ValueError("invalid report identity")

    def _remember(self, endpoint: str, entry: dict) -> None:
        self.cache[endpoint] = entry
        self.cache.move_to_end(endpoint)
        while len(self.cache) > 64:
            self.cache.popitem(last=False)


@router.get("/dailies")
async def dailies(request: Request):
    return await request.app.state.aihot.read("/dailies?limit=31")


@router.get("/dailies/{edition_date}")
async def daily(request: Request, edition_date: EditionDate):
    try:
        date.fromisoformat(edition_date)
    except ValueError as exc:
        raise _failure("aihot_invalid_date", "请选择有效的日报日期。", 422) from exc
    return await request.app.state.aihot.read("/dailies/" + edition_date)


@router.get("/hot-topics")
async def hot_topics(request: Request):
    return await request.app.state.aihot.read("/hot-topics")


ReportKind = Literal["daily", "weekly", "monthly"]
ReportKey = Annotated[str, Path(pattern=r"^[0-9W-]{7,10}$")]


def _report_key(kind: ReportKind, key: str) -> str:
    try:
        if kind == "daily":
            date.fromisoformat(key)
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", key):
                raise ValueError("date format")
        elif kind == "monthly":
            date.fromisoformat(key + "-01")
        else:
            if not re.fullmatch(r"\d{4}-W\d{2}", key):
                raise ValueError("week format")
            date.fromisocalendar(int(key[:4]), int(key[6:]), 1)
    except ValueError as exc:
        raise _failure("aihot_invalid_date", "请选择有效期次。", 422) from exc
    return key


@router.get("/pages/hot")
async def hot_page(request: Request):
    return await request.app.state.aihot.read("/site/hot")


@router.get("/reports/{kind}/latest-page")
async def latest_report(request: Request, kind: ReportKind):
    return await request.app.state.aihot.read(f"/site/reports/{kind}/latest-page")


@router.get("/reports/{kind}")
async def report_index(request: Request, kind: ReportKind):
    return await request.app.state.aihot.read(f"/site/reports/{kind}")


@router.get("/reports/daily/months/{month}")
async def report_month(request: Request, month: ReportKey):
    _report_key("monthly", month)
    return await request.app.state.aihot.read("/site/reports/daily/months/" + month)


@router.get("/reports/{kind}/navigation/{key}")
async def report_navigation(request: Request, kind: ReportKind, key: ReportKey):
    return await request.app.state.aihot.read(
        f"/site/reports/{kind}/navigation/{_report_key(kind, key)}"
    )


@router.get("/reports/{kind}/{key}")
async def report_detail(request: Request, kind: ReportKind, key: ReportKey):
    return await request.app.state.aihot.read(f"/site/reports/{kind}/{_report_key(kind, key)}")


@router.get("/media/{key}")
async def media(request: Request, key: Annotated[str, Path(pattern=r"^[a-f0-9]{64}$")]):
    return await request.app.state.aihot.media.read(key)


ItemId = Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{1,80}$")]
StoryId = Annotated[str, Path(pattern=r"^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$")]
TopicSlug = Annotated[str, Path(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")]


@router.get("/items/{item_id}")
async def item_detail(request: Request, item_id: ItemId):
    return await request.app.state.aihot.read("/site/items/" + item_id)


@router.get("/items/{item_id}/original")
async def item_original(request: Request, item_id: ItemId):
    return await request.app.state.aihot.read("/site/items/" + item_id + "/original")


@router.get("/stories/{story_id}")
async def story_detail(request: Request, story_id: StoryId):
    return await request.app.state.aihot.read("/site/stories/" + story_id)


@router.get("/topics/{slug}")
async def topic_detail(
    request: Request, slug: TopicSlug, page: Annotated[int, Query(ge=1, le=10000)] = 1
):
    return await request.app.state.aihot.read(f"/site/topics/{slug}?page={page}")


@router.get("/groups/{fact_id}/reports")
async def group_reports(request: Request, fact_id: ItemId):
    return await request.app.state.aihot.read(f"/site/groups/{fact_id}/reports")
