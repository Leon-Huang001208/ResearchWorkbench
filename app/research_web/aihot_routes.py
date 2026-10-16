"""Anonymous AIHOT reading adapter; no collection, credentials or model calls."""

import asyncio
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
from fastapi import APIRouter, HTTPException, Path, Request

from core.observability import get_logger

from .aihot_media import AihotMedia

router = APIRouter(prefix="/api/research/aihot", tags=["aihot"])
log = get_logger(__name__)
UPSTREAM = "https://aihot.news/api/v1"
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
    ):
        self.clock = clock
        self.wall_clock = wall_clock
        self.cache: OrderedDict[str, dict] = OrderedDict()
        self.lock = asyncio.Lock()
        self.media = AihotMedia()

    async def read(self, endpoint: str) -> dict:
        try:
            cached = self._fresh(endpoint)
            if cached is not None:
                return self.media.project(cached) if endpoint.startswith("/site/") else cached
            async with asyncio.timeout(20):
                async with self.lock:
                    payload = await self._read(endpoint)
            return self.media.project(payload) if endpoint.startswith("/site/") else payload
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise _failure("aihot_timeout", "AIHOT 读取超时，请重试。", 504) from exc
        except httpx.HTTPError as exc:
            raise _failure("aihot_unavailable", "无法连接 AIHOT，请稍后重试。") from exc
        except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
            raise _failure("aihot_invalid_response", "AIHOT 返回了异常数据。") from exc

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
        headers = {"User-Agent": "ResearchWorkbench-AIHOT/1.0", "Accept": "application/json"}
        if previous and previous.get("etag"):
            headers["If-None-Match"] = previous["etag"]
        async with (
            httpx.AsyncClient(timeout=20, follow_redirects=False, trust_env=False) as client,
            client.stream(
                "GET",
                ("https://aihot.news/api" if endpoint.startswith("/site/") else UPSTREAM)
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
                raise _failure("aihot_not_found", "该日期暂无可用日报。", 404)
            if response.status_code != 200:
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
        if endpoint == "/site/hot":
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
