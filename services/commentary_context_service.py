"""Build data and evidence context packs for commentary production."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from core.contracts.commentary import (
    CommentaryAttributionSignal,
    CommentaryContextPack,
    CommentaryEvidenceItem,
)
from core.contracts.dashboard import (
    GlobalNewsItem,
    MarketBreadthSnapshot,
    MarketIndexItem,
    MarketOverviewSection,
    SectorChangeItem,
)
from core.observability import get_logger
from services.dashboard_service import DashboardService

logger = get_logger(__name__)


class CommentaryContextService:
    """Prepare the market context that feeds commentary drafts."""

    def __init__(self, dashboard_service: DashboardService):
        self.dashboard_service = dashboard_service

    def build_context(self, recipe_id: str = "daily-close") -> CommentaryContextPack:
        """Build textarea prefill text and structured evidence for one recipe."""
        try:
            overview = self.dashboard_service.get_market_overview_section()
            sector_view = self.dashboard_service.get_market_sector_view(
                "ths_industry", limit=8
            )
        except Exception:
            logger.exception("commentary_context_dashboard_fetch_failed")
            raise

        data_lines = self._build_data_snapshot_lines(overview, sector_view)
        evidence_items = self._build_evidence_items(overview, sector_view)
        evidence_lines = self._build_evidence_lines(evidence_items)
        attribution_signals = self._build_attribution_signals(
            overview,
            sector_view,
            evidence_items,
        )

        return CommentaryContextPack(
            recipe_id=recipe_id or "daily-close",
            data_snapshot_text="\n".join(data_lines),
            evidence_pack_text="\n".join(evidence_lines),
            evidence_items=evidence_items,
            attribution_signals=attribution_signals,
            generated_at=datetime.utcnow(),
        )

    def _build_data_snapshot_lines(
        self,
        overview: MarketOverviewSection,
        sector_view: dict[str, Any],
    ) -> list[str]:
        lines: list[str] = []
        index_line = self._format_index_line(overview.indices)
        if index_line:
            lines.append(f"宽基指数：{index_line}")

        breadth_line = self._format_breadth_line(overview.breadth)
        if breadth_line:
            lines.append(f"市场广度：{breadth_line}")

        stats_line = self._format_market_stats_line(overview.market_stats)
        if stats_line:
            lines.append(f"资金与情绪：{stats_line}")

        up_line = self._format_sector_line(sector_view.get("up") or overview.top_up_sectors)
        if up_line:
            lines.append(f"领涨方向：{up_line}")

        down_line = self._format_sector_line(
            sector_view.get("down") or overview.top_down_sectors
        )
        if down_line:
            lines.append(f"拖累方向：{down_line}")

        if not lines:
            lines.append("市场数据：等待仪表盘行情、行业涨跌幅和资金数据刷新。")
        return lines

    def _build_evidence_items(
        self,
        overview: MarketOverviewSection,
        sector_view: dict[str, Any],
    ) -> list[CommentaryEvidenceItem]:
        items: list[CommentaryEvidenceItem] = []

        for index in overview.indices[:6]:
            items.append(
                CommentaryEvidenceItem(
                    kind="confirmed",
                    title=f"{index.name} {self._format_pct(index.change)}",
                    summary=f"最新点位 {index.value}，来源 {index.source}。",
                    source="market_overview",
                    source_type="market_data",
                    verification_status="verified",
                    confidence_score=0.95,
                    display_label="已确认数据",
                    metadata={"code": index.code, "change": index.change},
                )
            )

        up_sectors = sector_view.get("up") or overview.top_up_sectors
        down_sectors = sector_view.get("down") or overview.top_down_sectors

        for sector in self._iter_sector_items(up_sectors, limit=4):
            items.append(self._sector_evidence_item(sector, "confirmed", "领涨方向"))

        for sector in self._iter_sector_items(down_sectors, limit=4):
            items.append(self._sector_evidence_item(sector, "confirmed", "拖累方向"))

        for news in overview.global_news[:8]:
            items.append(
                CommentaryEvidenceItem(
                    kind="reported" if not news.is_mock else "interpretation",
                    title=news.title,
                    summary=news.summary,
                    source=news.source,
                    source_type="news",
                    verification_status="source_published" if not news.is_mock else "unverified",
                    confidence_score=(
                        self._clamp_confidence(news.importance_score * 0.8)
                        if not news.is_mock
                        else 0.35
                    ),
                    display_label="媒体报道/新闻" if not news.is_mock else "市场解释",
                    url=news.content_url,
                    metadata={
                        "published_at": news.published_at,
                        "importance_score": news.importance_score,
                        "region": news.region,
                        "is_mock": news.is_mock,
                    },
                )
            )

        items.extend(self._build_crawl_feed_evidence_items())

        if not items:
            items.append(
                CommentaryEvidenceItem(
                    kind="interpretation",
                    title="证据包待补充",
                    summary="暂无可用新闻或行业证据，请先刷新仪表盘或补充主观判断。",
                    source="commentary_context",
                    source_type="interpretation",
                    verification_status="unverified",
                    confidence_score=0.3,
                    display_label="市场解释",
                )
            )
        return items

    @staticmethod
    def _build_evidence_lines(items: list[CommentaryEvidenceItem]) -> list[str]:
        label_by_kind = {
            "confirmed": "已确认数据",
            "reported": "媒体报道",
            "interpretation": "市场解释",
            "judgement": "主观判断",
        }
        return [
            f"{CommentaryContextService._evidence_line_label(item, label_by_kind)}：{item.title}"
            + (f"。{item.summary}" if item.summary else "")
            for item in CommentaryContextService._select_balanced_evidence(items, limit=12)
        ]

    @staticmethod
    def _select_balanced_evidence(
        items: list[CommentaryEvidenceItem],
        limit: int,
    ) -> list[CommentaryEvidenceItem]:
        market_items = [item for item in items if item.source_type == "market_data"]
        reported_items = [
            item for item in items if item.source_type in {"news", "research"}
        ]
        interpretation_items = [
            item for item in items if item.source_type not in {"market_data", "news", "research"}
        ]

        selected: list[CommentaryEvidenceItem] = []
        selected.extend(market_items[: max(4, limit // 2)])
        selected.extend(reported_items[: max(4, limit - len(selected))])
        if len(selected) < limit:
            selected.extend(interpretation_items[: limit - len(selected)])

        seen: set[tuple[str, str]] = set()
        deduped: list[CommentaryEvidenceItem] = []
        for item in selected:
            key = (item.source_type, item.title)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped[:limit]

    def _build_crawl_feed_evidence_items(self) -> list[CommentaryEvidenceItem]:
        if not hasattr(self.dashboard_service, "get_crawl_feed"):
            return []
        try:
            feed = self.dashboard_service.get_crawl_feed(limit=12)
        except Exception as exc:
            logger.warning("commentary_context_crawl_feed_fetch_failed", error=str(exc))
            return []

        items: list[CommentaryEvidenceItem] = []
        for raw_item in (feed or {}).get("items", [])[:12]:
            if not isinstance(raw_item, dict):
                continue
            title = str(raw_item.get("title") or raw_item.get("raw_title") or "").strip()
            if not title:
                continue
            source_type = self._normalize_source_type(raw_item.get("source_type"))
            summary = str(raw_item.get("summary") or raw_item.get("content") or "").strip()
            items.append(
                CommentaryEvidenceItem(
                    kind="reported",
                    title=title,
                    summary=summary[:180],
                    source=str(
                        raw_item.get("source_name")
                        or raw_item.get("source")
                        or raw_item.get("source_type")
                        or "crawl_feed"
                    ),
                    source_type=source_type,
                    verification_status="source_published",
                    confidence_score=0.72 if source_type == "research" else 0.68,
                    display_label=(
                        "媒体报道/研报" if source_type == "research" else "媒体报道/新闻"
                    ),
                    url=raw_item.get("url") or raw_item.get("source_url"),
                    metadata={
                        "doc_id": raw_item.get("doc_id") or raw_item.get("id"),
                        "published_at": raw_item.get("published_at"),
                        "raw_source_type": raw_item.get("source_type"),
                    },
                )
            )
        return items

    @staticmethod
    def _normalize_source_type(source_type: Any) -> str:
        raw = str(source_type or "").lower()
        if any(token in raw for token in ("report", "research", "transcript", "zq")):
            return "research"
        if any(token in raw for token in ("news", "flash", "cnstock", "wechat")):
            return "news"
        return "news"

    def _build_attribution_signals(
        self,
        overview: MarketOverviewSection,
        sector_view: dict[str, Any],
        evidence_items: list[CommentaryEvidenceItem],
    ) -> list[CommentaryAttributionSignal]:
        candidates = [
            self._score_ai_crowding(sector_view, evidence_items),
            self._score_liquidity_outflow(overview, evidence_items),
            self._score_overseas_shock(evidence_items),
            self._score_broad_selloff(overview, evidence_items),
        ]
        ranked = [
            item for item in sorted(candidates, key=lambda signal: signal.score, reverse=True)
            if item.score > 0
        ]
        for index, signal in enumerate(ranked, start=1):
            signal.rank = index
            signal.strength = self._attribution_strength(index, signal.score)
        return ranked[:6]

    @staticmethod
    def _score_ai_crowding(
        sector_view: dict[str, Any],
        evidence_items: list[CommentaryEvidenceItem],
    ) -> CommentaryAttributionSignal:
        ai_terms = ("AI", "算力", "芯片", "半导体", "通信", "电池", "科技", "软银")
        down_titles = [
            (
                f"{getattr(item, 'name', None) or item.get('name')} "
                f"{CommentaryContextService._format_pct(getattr(item, 'change_pct', None) if not isinstance(item, dict) else item.get('change_pct'))}"
            )
            for item in CommentaryContextService._iter_sector_items(
                sector_view.get("down"),
                limit=8,
            )
            if (getattr(item, "name", None) or item.get("name"))
        ]
        down_hits = [title for title in down_titles if any(term in title for term in ai_terms)]
        evidence_hits = [
            item.title
            for item in evidence_items
            if any(term in f"{item.title} {item.summary}" for term in ai_terms)
        ][:4]
        score = 0
        if down_hits:
            score += 52
        if evidence_hits:
            score += 34
        rationale = "AI/科技相关拖累方向较集中，且新闻或研报证据显示海外科技链扰动。"
        if down_hits:
            rationale = f"{'、'.join(down_hits[:3])}等方向领跌，叠加 AI/科技链证据。"
        return CommentaryAttributionSignal(
            tag="ai_crowding",
            label="AI拥挤交易降温",
            score=min(score, 92),
            confidence_score=0.78 if score >= 80 else 0.62,
            verification_status="derived",
            rationale=rationale,
            evidence_titles=[*down_hits[:3], *evidence_hits[:3]] or ["AI/科技链相关证据不足"],
        )

    @staticmethod
    def _score_liquidity_outflow(
        overview: MarketOverviewSection,
        evidence_items: list[CommentaryEvidenceItem],
    ) -> CommentaryAttributionSignal:
        score = 0
        evidence_titles: list[str] = []
        net_flow = overview.market_stats.get("capital_flow_net") if overview.market_stats else None
        try:
            numeric_flow = float(net_flow)
        except (TypeError, ValueError):
            numeric_flow = None
        if numeric_flow is not None and numeric_flow < 0:
            score += 60 if numeric_flow <= -300 else 42
            evidence_titles.append(f"大盘资金净流入 {numeric_flow:g} 亿元")
        elif overview.breadth and overview.breadth.netInflow:
            parsed_flow = CommentaryContextService._extract_signed_number(
                overview.breadth.netInflow
            )
            if parsed_flow is not None and parsed_flow < 0:
                score += 60 if parsed_flow <= -300 else 42
                evidence_titles.append(f"资金净流入 {overview.breadth.netInflow}")
        if overview.breadth and overview.breadth.down > max(overview.breadth.up * 3, 1000):
            score += 18
            evidence_titles.append(f"下跌 {overview.breadth.down} 家 / 上涨 {overview.breadth.up} 家")
        return CommentaryAttributionSignal(
            tag="liquidity_outflow",
            label="资金净流出放大",
            score=min(score, 88),
            confidence_score=0.9 if score else 0.5,
            verification_status="verified",
            rationale="资金净流出与市场广度走弱共同指向风险偏好下降。",
            evidence_titles=evidence_titles or [item.title for item in evidence_items[:1]],
        )

    @staticmethod
    def _score_overseas_shock(
        evidence_items: list[CommentaryEvidenceItem],
    ) -> CommentaryAttributionSignal:
        overseas_terms = ("日经", "软银", "韩国", "亚太", "美股", "OpenAI", "纳指", "科技股")
        hits = [
            item.title
            for item in evidence_items
            if item.source_type in {"news", "research"}
            and any(term in f"{item.title} {item.summary}" for term in overseas_terms)
        ][:5]
        score = 74 if len(hits) >= 2 else (58 if hits else 0)
        return CommentaryAttributionSignal(
            tag="overseas_shock",
            label="海外科技链扰动",
            score=score,
            confidence_score=0.68 if hits else 0.4,
            verification_status="source_published" if hits else "unverified",
            rationale="海外科技股或亚太市场下跌通过风险偏好传导至本地成长板块。",
            evidence_titles=hits or ["暂无海外扰动证据"],
        )

    @staticmethod
    def _score_broad_selloff(
        overview: MarketOverviewSection,
        evidence_items: list[CommentaryEvidenceItem],
    ) -> CommentaryAttributionSignal:
        if not overview.breadth:
            return CommentaryAttributionSignal(
                tag="broad_selloff",
                label="普跌情绪扩散",
                score=0,
                rationale="暂无市场广度数据。",
                evidence_titles=[],
            )
        down = overview.breadth.down
        up = overview.breadth.up
        score = 66 if down > max(up * 4, 2500) else (46 if down > up * 2 else 0)
        return CommentaryAttributionSignal(
            tag="broad_selloff",
            label="普跌情绪扩散",
            score=score,
            confidence_score=0.86 if score else 0.5,
            verification_status="verified",
            rationale="下跌家数显著多于上涨家数，说明调整已从局部板块扩散至市场广度。",
            evidence_titles=[f"下跌 {down} 家 / 上涨 {up} 家"] if score else [item.title for item in evidence_items[:1]],
        )

    @staticmethod
    def _attribution_strength(rank: int, score: float) -> str:
        if rank == 1 and score >= 80:
            return "primary"
        if score >= 65:
            return "secondary"
        if score >= 45:
            return "watch"
        return "noise"

    @staticmethod
    def _extract_signed_number(text: Any) -> float | None:
        import re

        match = re.search(r"[-+]?\d+(?:\.\d+)?", str(text or ""))
        if not match:
            return None
        try:
            return float(match.group(0))
        except ValueError:
            return None

    @staticmethod
    def _evidence_line_label(
        item: CommentaryEvidenceItem,
        label_by_kind: dict[str, str],
    ) -> str:
        if item.source_type == "research":
            return "研报/纪要"
        if item.source_type == "news":
            return "媒体报道"
        return label_by_kind.get(item.kind, item.kind)

    @staticmethod
    def _format_index_line(indices: list[MarketIndexItem]) -> str:
        parts = [
            f"{item.name} {CommentaryContextService._format_pct(item.change)}"
            for item in indices[:6]
        ]
        return "，".join(parts)

    @staticmethod
    def _format_breadth_line(breadth: MarketBreadthSnapshot | None) -> str:
        if breadth is None:
            return ""
        parts = [f"上涨 {breadth.up} 家", f"下跌 {breadth.down} 家"]
        if breadth.turnover and breadth.turnover != "--":
            parts.append(f"成交额 {breadth.turnover}")
        if breadth.turnoverDelta:
            parts.append(f"较前日 {breadth.turnoverDelta}")
        if breadth.netInflow:
            parts.append(f"资金净流入 {breadth.netInflow}")
        return "，".join(parts)

    @staticmethod
    def _format_market_stats_line(stats: dict[str, Any]) -> str:
        if not stats:
            return ""
        parts: list[str] = []
        net_flow = stats.get("capital_flow_net")
        if net_flow is not None:
            parts.append(f"大盘资金净流入 {net_flow} 亿元")
        limit_up = stats.get("limit_up_count")
        limit_down = stats.get("limit_down_count")
        if limit_up is not None or limit_down is not None:
            parts.append(f"涨停 {limit_up or 0} 家 / 跌停 {limit_down or 0} 家")
        yesterday = stats.get("yesterday_limit_up_performance")
        if yesterday is not None:
            parts.append(f"昨日涨停表现 {yesterday}")
        return "，".join(parts)

    @staticmethod
    def _format_sector_line(sectors: Iterable[SectorChangeItem | dict[str, Any]]) -> str:
        parts = []
        for item in list(sectors)[:6]:
            name = getattr(item, "name", None) or item.get("name")
            change = getattr(item, "change_pct", None)
            if change is None and isinstance(item, dict):
                change = item.get("change_pct")
            if not name:
                continue
            parts.append(f"{name} {CommentaryContextService._format_pct(change)}")
        return "，".join(parts)

    @staticmethod
    def _iter_sector_items(
        sectors: Iterable[SectorChangeItem | dict[str, Any]] | None,
        limit: int,
    ) -> list[SectorChangeItem | dict[str, Any]]:
        if sectors is None:
            return []
        return list(sectors)[:limit]

    @staticmethod
    def _sector_evidence_item(
        sector: SectorChangeItem | dict[str, Any],
        kind: str,
        prefix: str,
    ) -> CommentaryEvidenceItem:
        name = getattr(sector, "name", None) or sector.get("name")
        change = getattr(sector, "change_pct", None)
        if change is None and isinstance(sector, dict):
            change = sector.get("change_pct")
        source = getattr(sector, "source", None)
        if source is None and isinstance(sector, dict):
            source = sector.get("source")
        view_label = getattr(sector, "view_label", None)
        if view_label is None and isinstance(sector, dict):
            view_label = sector.get("view_label")
        return CommentaryEvidenceItem(
            kind=kind,
            title=f"{prefix}：{name} {CommentaryContextService._format_pct(change)}",
            summary=f"{view_label or '行业/概念'}涨跌幅快照。",
            source=source or "sector_movers",
            source_type="market_data",
            verification_status="verified",
            confidence_score=0.9,
            display_label="已确认数据",
        )

    @staticmethod
    def _format_pct(value: Any) -> str:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return "--"
        sign = "+" if numeric > 0 else ""
        return f"{sign}{numeric:.2f}%"

    @staticmethod
    def _clamp_confidence(value: float) -> float:
        return max(0.0, min(1.0, round(value, 2)))
