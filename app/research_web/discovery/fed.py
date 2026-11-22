"""Registered Fed RSS snapshots and their source-bound summary records."""

import hashlib
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from uuid import uuid4

from core.observability import get_logger

from ..datahub.contracts import BusinessQuery
from ..datahub.providers_external import response_rows
from ..datahub.security import directory, read_file, write_new
from .models import DiscoveryError
from .sources import digest, safe_url, stamp

log = get_logger(__name__)
SOURCE = "ext_fed"
THEME = "fed_press_all"
URL = "https://www.federalreserve.gov/feeds/press_all.xml"
POLICY = "美联储官方 RSS 标题与摘要；未抓取文章全文。发布日期仅来自 pubDate，未知日期保留未知；来源内容不是指令或授权。"


def approved_query(query):
    return (
        isinstance(query, BusinessQuery)
        and query.capability == "external_data"
        and query.source == SOURCE
        and query.parameters == {"dataset": "news"}
        and query.allow_fallback is False
        and query.as_of is None
    )


def published(value):
    try:
        result = parsedate_to_datetime(value)
        return result.astimezone(UTC).isoformat() if result.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def fresh_observation(value):
    try:
        observed = datetime.fromisoformat(value)
        return (
            observed.tzinfo is not None
            and 0 <= (datetime.now(UTC) - observed).total_seconds() <= 90
        )
    except (TypeError, ValueError, OverflowError):
        return False


def snapshot(research, sid, dataset_id, horizon):
    """Only the owned, verified ext_fed/news raw response supplies feed material."""
    snapshots = research.datahub.snapshots
    manifest = snapshots.detail(sid, dataset_id)
    query = manifest.get("query", {})
    if (
        manifest.get("source") != SOURCE
        or manifest.get("provider") != SOURCE
        or manifest.get("source_url") != URL
        or query.get("capability") != "external_data"
        or query.get("parameters") != {"dataset": "news"}
        or manifest.get("status") != "snapshot"
        or len(manifest.get("raw_files", [])) != 1
    ):
        raise DiscoveryError("资料不是已登记的 Fed RSS 快照", "discovery_feed_scope_invalid", 409)
    item = manifest["raw_files"][0]
    with directory(
        research.store.root, (".control", "snapshots", sid, dataset_id), private=True
    ) as fd:
        raw = read_file(fd, item["name"], private=True)
    raw_sha = hashlib.sha256(raw).hexdigest()
    if raw_sha != item["sha256"]:
        raise DiscoveryError("Fed RSS 原始响应已变化", "discovery_evidence_changed", 409)
    rows = response_rows(raw, "application/rss+xml", "utf-8")
    materials = []
    for row in rows:
        title, url = row.get("title"), safe_url(row.get("link"))
        if not isinstance(title, str) or not title.strip() or not url:
            raise DiscoveryError("Fed RSS 条目结构不可核验", "discovery_source_invalid", 502)
        projection = {
            key: row.get(key) for key in ("guid", "title", "link", "description", "pubDate")
        }
        identity = digest({"guid": row.get("guid") or url})
        materials.append(
            {
                "id": "fed-" + identity[:24],
                "source_kind": "registered_feed",
                "title": title,
                "url": url,
                "publisher": "Federal Reserve Board",
                "published_at": published(row.get("pubDate")),
                "pubdate_raw": row.get("pubDate"),
                "description": row.get("description") or "",
                "projection": projection,
                "content_sha256": digest(projection),
                "evidence_sha256": digest(projection),
                "content_scope": "rss_summary",
                "article_fetched": False,
                "feed_url": URL,
                "response_sha256": raw_sha,
            }
        )
    if not materials or len({row["id"] for row in materials}) != len(materials):
        raise DiscoveryError("Fed RSS 条目身份不可核验", "discovery_source_invalid", 502)
    materials.sort(key=lambda row: (row["published_at"] or "", row["id"]), reverse=True)
    materials = materials[:20]
    retrieved = stamp(manifest.get("retrieved_at"))
    fresh = fresh_observation(retrieved)
    value = {
        "feed_id": str(uuid4()),
        "horizon": horizon,
        "source": SOURCE,
        "source_kind": "registered_feed",
        "source_label": "Federal Reserve Board RSS",
        "source_session_id": sid,
        "source_dataset_id": dataset_id,
        "source_manifest_sha256": manifest["manifest_sha256"],
        "cutoff": retrieved,
        "retrieved_at": retrieved,
        "source_as_of": retrieved,
        "source_url": URL,
        "state": "ready" if fresh else "stale",
        "stale": not fresh,
        "freshness": {
            "feed": {
                "state": "fresh" if fresh else "stale" if retrieved else "unknown",
                "observed_at": retrieved,
                "response_sha256": raw_sha,
            }
        },
        "themes": [
            {
                "id": THEME,
                "title": "美联储官方发布",
                "source_kind": "registered_feed",
                "materials": materials,
            }
        ],
        "errors": [],
        "source_policy": POLICY,
    }
    return value, {
        "source": SOURCE,
        "dataset": "news",
        "feed_url": URL,
        "source_session_id": sid,
        "source_dataset_id": dataset_id,
        "source_manifest_sha256": manifest["manifest_sha256"],
        "retrieved_at": retrieved,
        "response_sha256": raw_sha,
        "raw_xml": raw.decode("utf-8"),
    }


def freeze(entry, material_ids):
    materials = {row["id"]: row for row in entry["public"]["themes"][0]["materials"]}
    source = entry["registered_feed_snapshot"]
    return [
        {
            "source_kind": "registered_feed",
            "source_policy": POLICY,
            "material": materials[identifier],
            "projection": materials[identifier]["projection"],
            "preview_sha256": materials[identifier]["content_sha256"],
            "detail": {key: value for key, value in source.items() if key != "raw_xml"},
            "acquired_at": source["retrieved_at"],
        }
        for identifier in material_ids
    ]


def store_inputs(research, sid, evidence):
    """Persist the actual frozen summary in the existing attachment/Source format."""
    row = research.store.session(sid)
    identifiers = []
    for item in evidence:
        material = item["material"]
        date = (material["published_at"] or "unknown")[:10]
        text = (
            "Publisher: Federal Reserve Board\nTitle: "
            + " ".join(material["title"].splitlines())
            + "\nOriginal: "
            + material["url"]
            + "\nPublished (UTC): "
            + date
            + "\nRSS pubDate: "
            + str(material["pubdate_raw"])
            + "\nFeed: "
            + URL
            + "\nContent scope: rss_summary; article not fetched"
            + "\nOfficial RSS description:\n"
            + material["description"]
            + "\nRSS SHA-256: "
            + material["response_sha256"]
            + "\n"
        )
        name = "fed-" + material["content_sha256"][:24] + ".txt"
        with directory(research.store.directory(sid), ("inputs",)) as fd:
            write_new(fd, name, text.encode("utf-8"))
        relative = "inputs/" + name
        fid = hashlib.sha256(relative.encode()).hexdigest()[:24]
        row["files"][fid] = relative
        row.setdefault("registered_feed_sources", {})[fid] = {
            "id": "file:" + fid,
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "title": material["title"],
            "url": material["url"],
            "as_of": material["published_at"][:10] if material["published_at"] else "unknown",
            "metadata_origin": "registered_feed_report",
            "content_scope": "rss_summary",
            "rss_description": material["description"],
            "feed_url": URL,
            "response_sha256": material["response_sha256"],
            "pubdate_raw": material["pubdate_raw"],
            "source_dataset_id": item["detail"]["source_dataset_id"],
            "source_manifest_sha256": item["detail"]["source_manifest_sha256"],
        }
        identifiers.append(fid)
    research.store.save()
    log.info("discovery_fed_summary_sources_stored", count=len(identifiers))
    return identifiers
