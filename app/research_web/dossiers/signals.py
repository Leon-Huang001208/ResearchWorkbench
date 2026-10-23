"""Bounded, deterministic review signals from Host-verified frozen evidence.

Signals request research; they never revise opinions, infer company identities,
convert retrieval dates to disclosure dates, or execute providers/models.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from core.observability import get_logger

log = get_logger(__name__)
RULE_VERSION = "dossier-signals-1"
# Scheduled approvals are invalidated by every evaluator source change, even
# when an author accidentally forgets to bump the human-readable version.
RULES_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
MAX_ROWS = 1000
MAX_EVIDENCE = 100
MAX_AGE_DAYS = {"financials": 120}
NATIVE = {"financials", "announcements", "search_announcements"}
QUALIFIED = {"earnings_revision", "profit_notice_surprise", "risk_alerts"}


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


def _day(value):
    if not isinstance(value, str) or len(value) < 10:
        raise ValueError("publication_time_unknown")
    return date.fromisoformat(value[:10])


def evaluate_signals(dossier: dict, materials: dict[str, dict], cutoff: str) -> dict:
    """Consume already-authorized native manifests/rows, never user-made facts."""
    as_of = date.fromisoformat(cutoff)
    evidence = dossier.get("evidence", [])
    if len(evidence) > MAX_EVIDENCE:
        raise ValueError("dossier_signal_budget_exceeded")
    subject = dossier.get("subject", {})
    asset = subject.get("key", "")
    valid_asset = subject.get("kind") == "company" and bool(
        re.fullmatch(r"[0-9]{6}\.(SH|SZ|BJ)", asset)
    )
    missing: list[dict] = []
    items: dict[str, dict] = {}
    available: set[str] = set()
    accepted = 0
    covered = set()

    def gap(code, eid=None, capability=None):
        value = {"code": code, "evidence_id": eid, "capability": capability}
        if value not in missing:
            missing.append(value)

    def signal(
        rule,
        key,
        title,
        body,
        ids,
        *,
        published=None,
        source=None,
        state="open",
        source_record_id=None,
    ):
        identity = _digest([RULE_VERSION, dossier["id"], rule, key])
        current = items.get(identity)
        if current:
            current["evidence_ids"] = sorted(set(current["evidence_ids"] + ids))
            current["source"] = sorted(set(current["source"] + ([source] if source else [])))
            return
        items[identity] = {
            "id": uuid5(NAMESPACE_URL, identity).hex,
            "dossier_id": dossier["id"],
            "kind": "signal",
            "rule": rule,
            "rule_version": RULE_VERSION,
            "title": title[:240],
            "body": body[:4000],
            "state": state,
            "reason": "冻结证据规则触发，须研究者核验",
            "evidence_ids": sorted(ids),
            "as_of": published or cutoff,
            "source": [source] if source else [],
            "coverage": "evidence_only",
            "missing": [],
            "stale": False,
            "source_record_id": source_record_id,
        }

    for evidence_row in evidence:
        eid = evidence_row.get("id")
        if evidence_row.get("state") != "available" or eid not in materials:
            gap(evidence_row.get("error_code") or "evidence_unavailable", eid)
            continue
        data = materials[eid]
        manifest, rows = data.get("manifest", {}), data.get("rows")
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            gap("structured_data_unavailable", eid)
            continue
        if len(rows) > MAX_ROWS:
            raise ValueError("dossier_signal_budget_exceeded")
        capability = manifest.get("capability")
        admission = manifest.get("provider_metadata", {}).get("admission", {})
        if (manifest.get("snapshot_kind") == "mcp_evidence" or capability in QUALIFIED) and (
            admission.get("status") != "accepted"
            or not re.fullmatch(r"[a-f0-9]{64}", str(admission.get("source_proof", "")))
        ):
            gap("source_not_admitted", eid, capability)
            continue
        if capability not in NATIVE | QUALIFIED:
            gap("rule_not_covered", eid, capability)
            continue
        if not valid_asset:
            gap("subject_not_covered", eid, capability)
            continue
        if (
            manifest.get("status") not in {"snapshot", "complete", "success", "ok", "empty"}
            or manifest.get("pagination_complete") is not True
            or manifest.get("provider_total") not in {None, len(rows)}
            or manifest.get("row_count", len(rows)) != len(rows)
            or manifest.get("missing")
        ):
            gap("coverage_incomplete", eid, capability)
            continue
        try:
            observed = _day(manifest.get("as_of"))
        except ValueError:
            gap("data_time_unknown", eid, capability)
            continue
        if observed > as_of:
            gap("future_evidence", eid, capability)
            continue
        if (as_of - observed).days > MAX_AGE_DAYS.get(capability, 30):
            gap("stale_evidence", eid, capability)
            continue
        covered.add(capability)
        available.add(eid)
        accepted += 1
        for row in rows:
            if row.get("asset") != asset:
                gap("security_identity_mismatch", eid, capability)
                continue
            try:
                publication = row.get("published_at")
                # This native adapter explicitly distinguishes publication_date
                # from report_period/report_date/supplier_update_time.
                if (
                    capability == "financials"
                    and manifest.get("source") == "akshare"
                    and manifest.get("provider_metadata", {}).get("schema_version")
                    == "akshare-sina-financial-disclosure-v1"
                    and row.get("publication_precision") == "date"
                ):
                    publication = row.get("publication_date")
                published = _day(publication)
            except ValueError:
                gap("publication_time_unknown", eid, capability)
                continue
            if published > as_of:
                gap("future_evidence", eid, capability)
                continue
            if capability in {"announcements", "search_announcements"}:
                title = row.get("title")
                if not isinstance(title, str) or not title.strip():
                    gap("announcement_title_missing", eid, capability)
                    continue
                signal(
                    "announcement",
                    [asset, published.isoformat(), title.strip()],
                    "公告资料待研究",
                    f"已取得 {published.isoformat()} 公告：{title}。影响方向待核验。",
                    [eid],
                    published=published.isoformat(),
                    source=manifest.get("source"),
                )
            elif capability == "financials":
                period = row.get("report_period")
                try:
                    _day(period)
                except ValueError:
                    gap("report_period_unknown", eid, capability)
                    continue
                signal(
                    "financial_disclosure",
                    [asset, period, published.isoformat()],
                    "财务披露待研究",
                    f"已取得 {period} 报告期的财务披露；数值、单位、同比口径及变动原因待核验。",
                    [eid],
                    published=published.isoformat(),
                    source=manifest.get("source"),
                )
            else:
                # Qualified adapters still need an explicit source-bound event,
                # never a generic supplier sentiment or prose direction label.
                proof, event = row.get("source_evidence_id"), row.get("event_id")
                if (
                    not isinstance(proof, str)
                    or not proof
                    or not isinstance(event, str)
                    or not event
                ):
                    gap("event_provenance_missing", eid, capability)
                    continue
                signal(
                    capability,
                    [asset, event, published.isoformat()],
                    "结构化研究线索待核验",
                    f"已取得 {capability} 事件 {event}；原始证据 {proof}，需对照档案判断。",
                    [eid],
                    published=published.isoformat(),
                    source=manifest.get("source"),
                )

    for record in dossier.get("records", []):
        if record.get("kind") not in {"catalyst", "risk"} or record.get("state") != "open":
            continue
        ids = record.get("evidence_ids", [])
        if not ids or not set(ids).issubset(available):
            gap("watch_evidence_unavailable")
            continue
        try:
            start = _day(record.get("watch_from"))
            until = _day(record.get("watch_until")) if record.get("watch_until") else start
        except ValueError:
            gap("watch_window_unknown")
            continue
        if until < start:
            gap("watch_window_invalid")
        elif start <= as_of + timedelta(days=7):
            ended = until < as_of
            signal(
                "watch_window",
                record["id"],
                "观察窗口已结束" if ended else "催化剂／风险观察窗口",
                f"{record.get('title', '')}：{start} 至 {until}。{'窗口已结束，结果仍待核验。' if ended else '进入七日观察范围，触发与影响仍需验证。'}",
                ids,
                state="open",
                source_record_id=record["id"],
            )

    if not evidence:
        gap("no_frozen_evidence")
    for capability in sorted(QUALIFIED - covered):
        gap("capability_not_covered", capability=capability)
    result = sorted(items.values(), key=lambda item: item["id"])
    for item in result:
        # A new scan day is observation metadata, not a changed investment fact.
        item["fingerprint"] = _digest({key: value for key, value in item.items() if key != "as_of"})
    eligible = bool(accepted) and not any(
        item["code"] != "capability_not_covered" for item in missing
    )
    log.info(
        "dossier_signal_evaluated",
        dossier_id=dossier["id"],
        evidence_count=len(evidence),
        accepted=accepted,
        signal_count=len(result),
        gap_count=len(missing),
    )
    return {
        "items": result,
        "coverage": {
            "evidence_total": len(evidence),
            "accepted": accepted,
            "eligible": eligible,
            "rules": sorted(covered),
            "as_of": cutoff,
            "rule_version": RULE_VERSION,
        },
        "missing": missing,
    }
