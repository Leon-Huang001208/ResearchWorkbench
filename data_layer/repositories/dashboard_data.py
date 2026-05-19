"""Dashboard 专用数据仓储"""
from datetime import UTC, datetime, timedelta
from typing import Dict, List, Tuple

from sqlalchemy import and_, desc, func

from core.contracts import DocType
from core.observability import get_logger
from data_layer.repositories.models import (
    AlphaSignalDB,
    CanonicalEvent,
    DocumentV1DB,
    Entity,
    EntityMentionV1DB,
)

logger = get_logger(__name__)


class DashboardDataRepository:
    """仪表盘数据专用仓储"""

    def __init__(self, session):
        self.session = session

    def get_global_news_from_events(self, limit: int = 10, days: int = 7) -> List[Dict]:
        """
        从 CanonicalEvent 获取全球新闻

        Args:
            limit: 返回数量上限
            days: 时间范围（天）

        Returns:
            新闻数据列表
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)

        events = (
            self.session.query(CanonicalEvent)
            .filter(
                and_(
                    CanonicalEvent.created_at >= cutoff,
                    CanonicalEvent.reviewer_status != "rejected",
                )
            )
            .order_by(desc(CanonicalEvent.created_at))
            .limit(limit * 2)
            .all()
        )

        news_items = []
        for event in events:
            payload = event.payload or {}
            novelty_score = payload.get("novelty_score", 0.5)
            impacted_symbols = payload.get("impacted_symbols", [])
            source_name = payload.get("source_name", "Unknown")
            title = payload.get("title", event.summary or "")

            # 计算重要性评分：结合 novelty_score 和 confidence
            importance_score = (novelty_score * 0.6) + (float(event.confidence) * 0.4)

            # 提取区域信息
            region = "Global"
            impacted_industries = payload.get("impacted_industries", [])
            if any("China" in ind or "中国" in ind for ind in impacted_industries):
                region = "China"
            elif any("US" in ind or "美国" in ind for ind in impacted_industries):
                region = "US"
            elif any("Europe" in ind or "欧洲" in ind for ind in impacted_industries):
                region = "Europe"

            news_items.append(
                {
                    "news_id": f"event-{event.event_id}",
                    "title": title or event.summary or "市场事件",
                    "source": source_name,
                    "importance_score": importance_score,
                    "summary": event.summary or "",
                    "content_url": None,
                    "published_at": (
                        event.event_time.isoformat()
                        if event.event_time
                        else event.created_at.isoformat()
                    ),
                    "related_symbols": impacted_symbols[:5],
                    "region": region,
                    "event_type": event.event_type,
                }
            )

        # 按重要性评分排序
        news_items.sort(key=lambda x: x["importance_score"], reverse=True)
        return news_items[:limit]

    def get_global_news_from_documents(self, limit: int = 10, days: int = 7) -> List[Dict]:
        """
        从 DocumentV1 获取全球新闻

        Args:
            limit: 返回数量上限
            days: 时间范围（天）

        Returns:
            新闻数据列表
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)

        # 查询新闻类文档
        doc_types = [DocType.NEWS.value, DocType.REPORT.value, DocType.COMMENTARY.value]
        documents = (
            self.session.query(DocumentV1DB)
            .filter(
                and_(
                    DocumentV1DB.doc_type.in_(doc_types),
                    DocumentV1DB.created_at >= cutoff,
                )
            )
            .order_by(desc(DocumentV1DB.created_at))
            .limit(limit * 2)
            .all()
        )

        news_items = []
        for doc in documents:
            quality = doc.quality or {}
            classification = doc.classification or {}
            timeliness = doc.timeliness or {}

            # 计算重要性评分
            research_score = quality.get("research_usability_score", 0.5)
            content_score = quality.get("content_quality_score", 0.5)
            importance_score = (research_score * 0.5) + (content_score * 0.5)

            # 获取区域信息
            region = classification.get("region", "Global")

            # 获取相关标的（从 entity mentions）
            related_symbols = self._get_related_symbols_for_doc(doc.doc_id)

            # 生成摘要
            summary = doc.summary or (doc.content[:200] + "..." if doc.content else "")

            # 获取发布时间
            published_at = timeliness.get("publish_time")
            if not published_at:
                published_at = doc.created_at.isoformat()
            elif isinstance(published_at, datetime):
                published_at = published_at.isoformat()

            news_items.append(
                {
                    "news_id": f"doc-{doc.doc_id}",
                    "title": doc.title or "市场资讯",
                    "source": doc.source_name or "Unknown",
                    "importance_score": importance_score,
                    "summary": summary,
                    "content_url": doc.source_url,
                    "published_at": published_at,
                    "related_symbols": related_symbols[:5],
                    "region": region,
                    "doc_type": doc.doc_type,
                }
            )

        # 按重要性评分排序
        news_items.sort(key=lambda x: x["importance_score"], reverse=True)
        return news_items[:limit]

    def _get_related_symbols_for_doc(self, doc_id: str) -> List[str]:
        """获取文档相关的标的符号"""
        mentions = (
            self.session.query(EntityMentionV1DB)
            .filter(EntityMentionV1DB.doc_id == doc_id)
            .order_by(desc(EntityMentionV1DB.is_primary))
            .limit(10)
            .all()
        )

        symbols = []
        for mention in mentions:
            # 获取 Entity 的 canonical_id
            if mention.entity_id:
                entity = (
                    self.session.query(Entity).filter(Entity.entity_id == mention.entity_id).first()
                )
                if entity and entity.canonical_id:
                    symbols.append(entity.canonical_id)
            # 也可以直接使用 entity_name（如果它看起来像股票代码）
            elif mention.entity_name and len(mention.entity_name) <= 10:
                symbols.append(mention.entity_name)

        return symbols

    def get_combined_global_news(self, limit: int = 10, days: int = 7) -> Tuple[List[Dict], bool]:
        """
        获取组合的全球新闻（优先事件，补充文档）

        Returns:
            (新闻列表, 是否使用了真实数据)
        """
        event_news = self.get_global_news_from_events(limit=limit, days=days)
        doc_news = self.get_global_news_from_documents(limit=limit, days=days)

        # 合并并去重（基于标题相似度）
        combined = []
        seen_titles = set()

        # 优先添加事件新闻
        for news in event_news:
            title_key = news["title"][:30].lower()
            if title_key not in seen_titles:
                combined.append(news)
                seen_titles.add(title_key)

        # 补充文档新闻
        for news in doc_news:
            title_key = news["title"][:30].lower()
            if title_key not in seen_titles and len(combined) < limit:
                combined.append(news)
                seen_titles.add(title_key)

        # 再次按重要性排序
        combined.sort(key=lambda x: x["importance_score"], reverse=True)

        has_real_data = len(combined) > 0
        return combined[:limit], has_real_data

    def get_sector_changes_from_signals(
        self, days: int = 7, limit_per_direction: int = 5
    ) -> Tuple[List[Dict], List[Dict], bool]:
        """
        从 EventAlphaSignal 获取板块变化

        Returns:
            (上涨板块列表, 下跌板块列表, 是否使用了真实数据)
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)

        signals = (
            self.session.query(AlphaSignalDB)
            .filter(
                and_(
                    AlphaSignalDB.discriminator == "event_alpha_signal",
                    AlphaSignalDB.created_at >= cutoff,
                )
            )
            .order_by(desc(AlphaSignalDB.created_at))
            .limit(100)
            .all()
        )

        if not signals:
            return [], [], False

        # 按行业聚合
        sector_data: Dict[str, Dict] = {}

        for signal in signals:
            industries = signal.industry_impacts or []
            bullish = signal.bullish_companies or []
            bearish = signal.bearish_companies or []

            for industry in industries:
                if industry not in sector_data:
                    sector_data[industry] = {
                        "sector_id": f"sector-{hash(industry) % 10000}",
                        "name": industry,
                        "bullish_count": 0,
                        "bearish_count": 0,
                        "bullish_companies": set(),
                        "bearish_companies": set(),
                        "signal_count": 0,
                        "avg_score": 0.0,
                    }

                data = sector_data[industry]
                data["signal_count"] += 1
                data["avg_score"] += float(signal.score)

                for company in bullish:
                    data["bullish_companies"].add(company)
                data["bullish_count"] += len(bullish)

                for company in bearish:
                    data["bearish_companies"].add(company)
                data["bearish_count"] += len(bearish)

        # 计算最终数据
        sectors = []
        for name, data in sector_data.items():
            if data["signal_count"] > 0:
                data["avg_score"] /= data["signal_count"]

            # 计算变化百分比
            total = data["bullish_count"] + data["bearish_count"]
            if total > 0:
                change_pct = ((data["bullish_count"] - data["bearish_count"]) / total) * 10
            else:
                change_pct = (data["avg_score"] - 0.5) * 10

            # 判断是否为概念板块
            is_concept = self._is_concept_sector(name)

            sectors.append(
                {
                    "sector_id": data["sector_id"],
                    "name": name,
                    "change_pct": change_pct,
                    "leading_stocks": list(data["bullish_companies"])[:3]
                    if change_pct > 0
                    else list(data["bearish_companies"])[:3],
                    "related_news_count": data["signal_count"],
                    "is_concept": is_concept,
                }
            )

        # 分离上涨和下跌
        up_sectors = [s for s in sectors if s["change_pct"] > 0]
        down_sectors = [s for s in sectors if s["change_pct"] < 0]

        # 排序
        up_sectors.sort(key=lambda x: x["change_pct"], reverse=True)
        down_sectors.sort(key=lambda x: x["change_pct"])

        return up_sectors[:limit_per_direction], down_sectors[:limit_per_direction], True

    def _is_concept_sector(self, name: str) -> bool:
        """判断是否为概念板块（而非传统行业）"""
        concept_keywords = [
            "AI",
            "人工智能",
            "新能源",
            "半导体",
            "芯片",
            "元宇宙",
            "区块链",
            "Web3",
            "VR",
            "AR",
            "自动驾驶",
            "电动车",
            "光伏",
            "风电",
            "储能",
            "创新药",
            "CXO",
            "医美",
            "网红",
            "直播",
        ]
        traditional_keywords = [
            "银行",
            "保险",
            "证券",
            "房地产",
            "钢铁",
            "煤炭",
            "石油",
            "天然气",
            "消费",
            "零售",
            "家电",
            "汽车",
            "医药",
            "医疗",
            "交通运输",
            "物流",
            "建筑",
            "建材",
        ]

        name_lower = name.lower()
        has_concept = any(k.lower() in name_lower for k in concept_keywords)
        has_traditional = any(k in name for k in traditional_keywords)

        return has_concept and not has_traditional

    def has_enough_data(self) -> bool:
        """检查是否有足够的真实数据"""

        doc_count = self.session.query(func.count(DocumentV1DB.doc_id)).scalar()
        event_count = self.session.query(func.count(CanonicalEvent.event_id)).scalar()
        signal_count = self.session.query(func.count(AlphaSignalDB.signal_id)).scalar()

        return doc_count >= 5 or event_count >= 3 or signal_count >= 3
