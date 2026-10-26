"""Bounded raw Intel news identities; no URL fetching, model or event fabrication."""

from datetime import UTC, datetime, timedelta

from core.observability import get_logger

from .models import DiscoveryError
from .sources import digest, display_fields, evidence_projection, objects, safe_url, stamp, string

log = get_logger(__name__)
MAX_NEWS = 180
CLOCK_FIELDS = {"retrieved_at", "acquired_at", "fetched_at"}


def stable(value):
    if isinstance(value, dict):
        return {key: stable(item) for key, item in value.items() if key not in CLOCK_FIELDS}
    if isinstance(value, list):
        return [stable(item) for item in value]
    return value


def published(value):
    result = stamp(value)
    if not result or len(result) == 10:
        return None
    try:
        if datetime.fromisoformat(result) > datetime.now(UTC) + timedelta(minutes=5):
            return None
    except ValueError:
        return None
    return result


def observation(payload):
    return {
        "cache_status": (
            "expired"
            if payload.get("cache_stale") is True
            else "not_expired" if payload.get("cache_stale") is False else "not_reported"
        ),
        "source_as_of": stamp(payload.get("as_of")) or stamp(payload.get("generated_at")),
        "source_generated_at_label": string(payload.get("generated_at"), 200),
        "coverage": payload.get("stats") if isinstance(payload.get("stats"), dict) else {},
    }


def collect(payload):
    """Keep full returned records private; reject conflicting same-source URL versions."""
    if not isinstance(payload, dict) or not isinstance(payload.get("industries"), list):
        raise DiscoveryError("原始资讯结构暂不可核验", "discovery_news_invalid", 502)
    result = {}
    for group in objects(payload["industries"]):
        for row in objects(group.get("items")):
            title = string(row.get("title"), 1000)
            if not title.strip():
                continue
            source, url = string(row.get("source"), 200), safe_url(row.get("url"))
            identity = {"source": source, "url": url}
            identifier = "news-" + digest(identity if source and url else stable(row))[:48]
            # A human-relative label is archived but cannot manufacture evidence novelty.
            canonical = {key: value for key, value in stable(row).items() if key != "time"}
            if identifier in result:
                existing = result[identifier]
                existing["ambiguous"] |= digest(existing["canonical"]) != digest(canonical)
                existing["groups"].add(string(group.get("name") or group.get("key"), 200))
                continue
            result[identifier] = {
                "id": identifier,
                "identity": identity,
                "record": row,
                "canonical": canonical,
                "published_at": published(row.get("ts")),
                "groups": {string(group.get("name") or group.get("key"), 200)},
                "ambiguous": False,
            }
    for item in result.values():
        item["groups"] = sorted(filter(None, item["groups"]))
    return result


def projection(item):
    return {
        "source_kind": "news",
        "news_id": item["id"],
        "identity": item["identity"],
        "canonical": item["canonical"],
        "groups": item["groups"],
        "ambiguous": item["ambiguous"],
    }


def theme(item, acquired):
    row, identifier = item["record"], item["id"]
    actionable = bool(all(item["identity"].values()) and not item["ambiguous"])
    limitations = []
    if not item["published_at"]:
        limitations.append("原始发布时间未知或不可核验，不以读取时间补造")
    if not actionable:
        limitations.append("来源身份缺失或同一地址存在冲突版本，仅供阅读，不能冻结或跟踪")
    material = {
        "id": "raw-" + digest(projection(item))[:48],
        "source_kind": "news",
        "news_id": identifier,
        "label": "N1",
        "title": string(row.get("title"), 1000),
        "publisher": item["identity"]["source"] or "来源未报告",
        "url": item["identity"]["url"],
        "kind": "原始资讯归档",
        "note": "现有资讯源的标题、摘要与归档正文；未独立抓取或核验链接网页全文",
        "published_at": item["published_at"],
        "acquired_at": acquired,
        "revision": None,
        "content_sha256": digest(projection(item)),
    }
    return {
        "id": identifier,
        "source_kind": "news",
        "name": material["title"],
        "title": material["title"],
        "category": item["groups"][0] if item["groups"] else "未分类",
        "publisher": material["publisher"],
        "importance": string(row.get("importance") or row.get("priority"), 80),
        "published_at": item["published_at"],
        "judgment_as_of": None,
        "state": "未形成研判",
        "description": string(row.get("summary") or row.get("raw_content"), 600),
        "change": "原始资讯，尚未关联本条RWB研判",
        "next": "核对原始来源、关键事实与反证",
        "counter": [],
        "invalidation": [],
        "assets": [],
        "chain": [],
        "limitations": limitations,
        "materials": [material],
        "actionable": actionable,
        "evidence_state": "unverified_news",
        "related_events": [],
        "is_counter": False,
    }


def fingerprint(detail):
    """Published time/content and verified links count; source display clocks do not."""
    associations = [
        {**row, "detail": evidence_projection(row["detail"])}
        for row in detail.get("associations", [])
    ]
    return digest({"news": projection(detail["news"]), "associations": stable(associations)})


def source_state(detail, acquired):
    """Freeze the latest read status without treating it as content novelty."""
    return {
        **detail["observation"],
        "status": "ready",
        "retrieved_at": acquired,
        "last_attempt_at": acquired,
        "latest_published_at": detail["news"]["published_at"],
        "association_cache_expired": any(
            row["detail"].get("cache_stale") is True for row in detail["associations"]
        ),
    }


def source_stale(state):
    return state["cache_status"] == "expired" or state["association_cache_expired"]


def verified_association(item, detail, event_id):
    event = detail.get("event") if isinstance(detail, dict) else None
    if not isinstance(event, dict) or event.get("id") != event_id:
        raise DiscoveryError("关联事件身份不可核验", "discovery_association_invalid", 409)
    articles = objects(detail.get("articles"))
    matched = [row for row in articles if safe_url(row.get("url")) == item["identity"]["url"]]
    if not item["identity"]["url"] or not matched:
        raise DiscoveryError("未通过归档报道地址关联核对", "discovery_association_unverified", 409)
    # Freeze the full event archive too; a relation does not promote its quality.
    return {
        "event_id": event_id,
        "title": string(event.get("title"), 1000),
        "matched_url": item["identity"]["url"],
        "matched_article_sha256": sorted(digest(stable(row)) for row in matched),
        "judgment_as_of": stamp(event.get("judgment_as_of")),
        "event_updated_at": stamp(event.get("updated_at")),
        "judgment": display_fields(event),
        "detail": detail,
    }


def observed(records, identifier):
    item = records.get(identifier)
    if item is None:
        log.warning("discovery_news_not_observable")
        raise DiscoveryError(
            "原始资讯本次不可观察，可能已滚出来源窗口；未判为无变化",
            "discovery_news_not_observable",
            409,
        )
    if item["ambiguous"] or not all(item["identity"].values()):
        raise DiscoveryError(
            "原始资讯身份或版本存在歧义", "discovery_news_identity_unverified", 409
        )
    return item
