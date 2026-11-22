"""Independent bounded read lanes and truthful refresh receipts for Discovery."""

import asyncio
import copy
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException

from core.observability import get_logger

from ..client import RuntimeFailure
from . import news
from .models import DiscoveryError
from .sources import SOURCE, SOURCE_LABEL, SOURCE_POLICY, objects, projection, stamp, theme

log = get_logger(__name__)


async def build_feed(reader, previous, horizon, acquired, event_limit=60):
    results = await asyncio.gather(
        reader("/intelligence", {"impact": "medium_high", "view": "compact"}),
        reader("/radar"),
        return_exceptions=True,
    )
    for value in results:
        if isinstance(value, asyncio.CancelledError):
            raise value
    attempted = acquired
    acquired = datetime.now(UTC).isoformat()
    old = previous or {}
    values, proofs, freshness, errors = {}, {}, {}, []
    for lane, response in zip(("events", "news"), results):
        try:
            if isinstance(response, BaseException):
                raise response
            if lane == "events":
                if not isinstance(response, dict) or not isinstance(response.get("reading"), list):
                    raise ValueError("events_schema_invalid")
                logical = {
                    x["id"]: x.get("name", x["id"])
                    for x in objects(response.get("logics"))
                    if isinstance(x.get("id"), str)
                }
                counters = {x.get("id") for x in objects(response.get("challenges"))}
                ordered = sorted(
                    objects(response["reading"]),
                    key=lambda x: stamp(x.get("first_public_at")) or "",
                    reverse=True,
                )
                selected, seen = [], set()
                for event in ordered:
                    item = theme(event, acquired, logical, event.get("id") in counters)
                    if item is None or item["id"] in seen or item["id"].startswith("news-"):
                        continue
                    seen.add(item["id"])
                    item.update(
                        source_kind="event",
                        published_at=stamp(event.get("first_public_at")),
                        event_updated_at=stamp(event.get("updated_at")),
                        judgment_as_of=stamp(event.get("judgment_as_of")),
                        publisher=SOURCE_LABEL,
                    )
                    selected.append(item)
                    proofs[item["id"]] = projection(event)
                    if len(selected) >= event_limit:
                        break
                daily = response.get("daily_reading")
                if isinstance(daily, dict) and daily.get("analysis_error"):
                    errors.append(
                        {
                            "code": "upstream_judgment_unverified",
                            "message": "上游精选判断有核验缺口，不能作为已验证结论。",
                        }
                    )
                meta = {
                    "source_as_of": stamp(response.get("as_of")),
                    "cache_status": (
                        "expired"
                        if response.get("cache_stale") is True
                        else (
                            "not_expired"
                            if response.get("cache_stale") is False
                            else "not_reported"
                        )
                    ),
                }
                bounded = len(ordered) > len(selected)
            else:
                records = news.collect(response)
                ordered = sorted(
                    records.values(), key=lambda x: x["published_at"] or "", reverse=True
                )
                selected = [news.theme(x, acquired) for x in ordered[: news.MAX_NEWS]]
                for item in selected:
                    proofs[item["id"]] = {
                        "source_kind": "news",
                        "content_sha256": item["materials"][0]["content_sha256"],
                    }
                meta = news.observation(response)
                bounded = len(ordered) > len(selected)
            values[lane] = selected
            freshness[lane] = {
                **meta,
                "status": "ready" if selected else "empty",
                "retrieved_at": acquired,
                "last_attempt_at": attempted,
                "latest_published_at": max(
                    (x.get("published_at") or "" for x in selected), default=""
                )
                or None,
                "bounded": bounded,
            }
        except (
            HTTPException,
            DiscoveryError,
            RuntimeFailure,
            OSError,
            ValueError,
            TypeError,
            TimeoutError,
        ) as exc:
            # Read failures remain lane-specific. Old bytes never acquire a new read timestamp.
            values[lane] = copy.deepcopy(
                old.get(lane, old.get("themes", []) if lane == "events" else [])
            )
            previous_meta = copy.deepcopy(old.get("freshness", {}).get(lane, {}))
            freshness[lane] = {
                **previous_meta,
                "status": "unavailable",
                "retrieved_at": previous_meta.get(
                    "retrieved_at", old.get("retrieved_at") if values[lane] else None
                ),
                "last_attempt_at": attempted,
            }
            errors.append(
                {
                    "code": "discovery_" + lane + "_unavailable",
                    "message": (
                        "本次原始资讯读取失败，保留上次资料。"
                        if lane == "news"
                        else "本次事件研判读取失败，保留上次资料。"
                    ),
                }
            )
            log.warning("discovery_read_lane_failed", lane=lane, error_type=type(exc).__name__)
    if all(x["status"] == "unavailable" for x in freshness.values()) and not previous:
        raise DiscoveryError("发现来源暂不可用，请稍后重试", "discovery_source_unavailable", 502)
    themes = values["news"] + values["events"]
    any_ready = any(x["status"] in {"ready", "empty"} for x in freshness.values())
    value = {
        "feed_id": str(uuid4()),
        "horizon": horizon,
        "cutoff": acquired,
        "retrieved_at": acquired if any_ready else old.get("retrieved_at"),
        "source": SOURCE,
        "source_label": SOURCE_LABEL,
        "source_as_of": freshness["events"].get("source_as_of"),
        # Legacy aggregate flag remains conservative; modern UI uses the individual lanes.
        "stale": any(
            x["status"] == "unavailable" or x.get("cache_status") == "expired"
            for x in freshness.values()
        ),
        "state": "stale" if not any_ready else "ready" if themes else "empty",
        "themes": themes,
        **values,
        "freshness": freshness,
        "errors": errors,
        "source_policy": SOURCE_POLICY,
        "bounded": any(x.get("bounded") for x in freshness.values()),
        "limitations": [
            "原始资讯先展示；未关联研判不证明上游没有分析。",
            "资讯发布时间、事件更新时间、研判截止与Host读取时间分别保存；未知时间不补造。",
            "仅归档现有来源返回内容，未独立抓取链接网页全文；跟踪来源滚出窗口时标不可观察。",
        ],
    }
    return value, proofs
