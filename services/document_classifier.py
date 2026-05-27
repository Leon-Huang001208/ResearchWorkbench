"""
文档分类器 - Issue #44

提供文档的智能分类：
- 文档类型判断
- 行业分类
- 主题标签
- 事件类型识别
"""
import re
from typing import List, Optional, Tuple

from core.contracts import (
    DocumentClassification,
    DocumentEvidenceProfile,
    DocumentQuality,
    DocumentTagV1,
    DocumentV1,
    SourceReliabilityLevel,
    SourceType,
    SubjectivityLevel,
)
from core.observability import get_logger
from core.utils.id_gen import generate_id
from services.taxonomy_service import TaxonomyService

logger = get_logger(__name__)


class DocumentClassifier:
    """文档分类器"""

    def __init__(self, taxonomy: Optional[TaxonomyService] = None):
        self.taxonomy = taxonomy or TaxonomyService()

    def classify(
        self, doc: DocumentV1, update_doc: bool = True
    ) -> Tuple[DocumentClassification, List[DocumentTagV1]]:
        """
        分类文档

        Args:
            doc: 文档
            update_doc: 是否更新文档对象

        Returns:
            (分类结果, 标签列表)
        """
        logger.info(f"Classifying document: {doc.doc_id}")

        classification = DocumentClassification()
        tags: List[DocumentTagV1] = []

        # 1. 使用分类体系服务进行行业和主题分类
        taxo_result = self.taxonomy.classify(doc.content, doc.title)
        classification.primary_industry = taxo_result.primary_industry
        classification.secondary_industries = taxo_result.secondary_industries
        classification.topics = taxo_result.themes

        # 2. 事件类型识别
        event_types = self._identify_event_types(doc.title, doc.content)
        classification.event_types = event_types

        # 3. 生成标签
        # 行业标签
        if classification.primary_industry:
            industry = self.taxonomy.industries.get(classification.primary_industry)
            if industry:
                tags.append(
                    DocumentTagV1(
                        tag_id=generate_id(),
                        doc_id=doc.doc_id,
                        tag=industry.name,
                        tag_type="industry",
                        confidence=taxo_result.confidence_scores.get(
                            f"industry:{classification.primary_industry}", 0.5
                        ),
                        source="auto",
                    )
                )

        # 主题标签
        for theme_id in classification.topics:
            theme = self.taxonomy.themes.get(theme_id)
            if theme:
                tags.append(
                    DocumentTagV1(
                        tag_id=generate_id(),
                        doc_id=doc.doc_id,
                        tag=theme.name,
                        tag_type="theme",
                        confidence=taxo_result.confidence_scores.get(f"theme:{theme_id}", 0.5),
                        source="auto",
                    )
                )

        # 事件类型标签
        for event_type in event_types:
            tags.append(
                DocumentTagV1(
                    tag_id=generate_id(),
                    doc_id=doc.doc_id,
                    tag=event_type,
                    tag_type="event_type",
                    confidence=0.7,
                    source="auto",
                )
            )

        # 4. 更新文档
        if update_doc:
            doc.classification = classification

        logger.info(f"Classified document: {len(tags)} tags")
        return classification, tags

    def analyze_quality(self, doc: DocumentV1, update_doc: bool = True) -> DocumentQuality:
        """
        分析文档质量

        Args:
            doc: 文档
            update_doc: 是否更新文档

        Returns:
            质量评分
        """
        quality = DocumentQuality()

        # 1. 来源可信度
        quality.source_reliability_level = self._estimate_source_reliability(
            doc.source_type, doc.source_name
        )

        # 2. 主观性判断
        quality.subjectivity_level, quality.fact_opinion_ratio = self._estimate_subjectivity(
            doc.content
        )

        # 3. 研究可用性评分
        quality.research_usability_score = self._estimate_usability(doc)

        # 4. 内容质量评分
        quality.content_quality_score = self._estimate_content_quality(doc)

        # 5. 是否事实源
        quality.is_fact_source = quality.subjectivity_level in [
            SubjectivityLevel.FACT_ONLY,
            SubjectivityLevel.FACT_HEAVY,
        ]

        if update_doc:
            doc.quality = quality

        return quality

    def analyze_evidence(self, doc: DocumentV1, update_doc: bool = True) -> DocumentEvidenceProfile:
        """
        分析文档的证据概况

        Args:
            doc: 文档
            update_doc: 是否更新文档

        Returns:
            证据概况
        """
        profile = DocumentEvidenceProfile()
        text = doc.title + "\n" + doc.content

        # 检查是否有明确的事实陈述
        profile.has_explicit_facts = self._has_explicit_facts(text)

        # 检查是否有明确的观点
        profile.has_explicit_opinions = self._has_explicit_opinions(text)

        # 检查是否有数据点
        profile.has_data_points = self._has_data_points(text)

        # 检查是否有引述
        profile.has_quotes = self._has_quotes(text)

        # 检查是否有分析
        profile.has_analysis = self._has_analysis(text)

        # 证据质量评分
        score = 0.0
        if profile.has_explicit_facts:
            score += 0.3
        if profile.has_data_points:
            score += 0.25
        if profile.has_quotes:
            score += 0.15
        if profile.has_analysis:
            score += 0.2
        if profile.has_explicit_opinions:
            score += 0.1
        profile.evidence_quality_score = min(score, 1.0)

        if update_doc:
            doc.evidence_profile = profile

        return profile

    def _identify_event_types(self, title: Optional[str], content: str) -> List[str]:
        """识别事件类型"""
        event_types: List[str] = []
        text = (title or "") + "\n" + content

        event_patterns = {
            "earnings": [
                "业绩",
                "财报",
                "年报",
                "季报",
                "净利润",
                "营收",
                "增长",
                "亏损",
            ],
            "policy": [
                "政策",
                "新规",
                "通知",
                "意见",
                "监管",
                "审批",
                "通过",
                "获批",
            ],
            "product": [
                "发布",
                "推出",
                "上市",
                "新品",
                "量产",
                "产能",
            ],
            "merger": [
                "收购",
                "并购",
                "重组",
                "合并",
                "分立",
                "资产",
            ],
            "rating": [
                "评级",
                "上调",
                "下调",
                "买入",
                "卖出",
                "增持",
                "减持",
            ],
            "price": [
                "涨价",
                "提价",
                "降价",
                "价格",
                "调价",
            ],
            "contract": [
                "订单",
                "合同",
                "中标",
                "签约",
            ],
            "leadership": [
                "董事长",
                "总经理",
                "CEO",
                "离职",
                "辞职",
                "任命",
            ],
        }

        for event_type, keywords in event_patterns.items():
            for keyword in keywords:
                if keyword in text:
                    if event_type not in event_types:
                        event_types.append(event_type)
                    break

        return event_types

    def _estimate_source_reliability(
        self, source_type: Optional[SourceType], source_name: Optional[str]
    ) -> SourceReliabilityLevel:
        """估计来源可信度"""
        if not source_type:
            return SourceReliabilityLevel.UNKNOWN

        # 根据来源类型判断 — 优先从注册表读取，未注册的来源使用默认映射
        from core.source_registry import get as _get_spec

        _spec = _get_spec(source_type)
        if _spec:
            return _spec.reliability

        reliability_map = {
            SourceType.COMPANY_ANNOUNCEMENT: SourceReliabilityLevel.OFFICIAL,
            SourceType.GOVERNMENT_POLICY: SourceReliabilityLevel.OFFICIAL,
            SourceType.WIND: SourceReliabilityLevel.RESEARCH_INSTITUTE,
            SourceType.BLOOMBERG: SourceReliabilityLevel.ESTABLISHED_MEDIA,
            SourceType.REUTERS: SourceReliabilityLevel.ESTABLISHED_MEDIA,
            SourceType.INTERNAL: SourceReliabilityLevel.UNKNOWN,
            SourceType.OTHER: SourceReliabilityLevel.UNKNOWN,
        }

        level = reliability_map.get(source_type, SourceReliabilityLevel.UNKNOWN)

        # 可以再根据source_name调整
        if source_name:
            name_lower = source_name.lower()
            if "新华社" in name_lower or "证监会" in name_lower:
                level = SourceReliabilityLevel.OFFICIAL
            elif "券商" in name_lower or "证券" in name_lower:
                level = SourceReliabilityLevel.RESEARCH_INSTITUTE

        return level

    def _estimate_subjectivity(self, content: str) -> Tuple[SubjectivityLevel, float]:
        """估计主观性"""
        opinion_words = [
            "认为",
            "预计",
            "预期",
            "预测",
            "判断",
            "观点",
            "看好",
            "看空",
            "乐观",
            "悲观",
            "可能",
            "或许",
            "应该",
            "建议",
            "推荐",
            "we believe",
            "we expect",
            "we think",
            "we forecast",
            "expect",
            "anticipate",
            "believe",
            "forecast",
            "estimate",
        ]

        fact_words = [
            "宣布",
            "公告",
            "发布",
            "数据显示",
            "统计",
            "据报道",
            "消息称",
            "according to",
            "reported",
            "announced",
            "data shows",
        ]

        opinion_count = sum(1 for word in opinion_words if word in content)
        fact_count = sum(1 for word in fact_words if word in content)

        total = opinion_count + fact_count
        if total == 0:
            return SubjectivityLevel.MIXED, 0.5

        fact_ratio = fact_count / total

        if fact_ratio >= 0.8:
            level = SubjectivityLevel.FACT_ONLY
        elif fact_ratio >= 0.6:
            level = SubjectivityLevel.FACT_HEAVY
        elif fact_ratio >= 0.4:
            level = SubjectivityLevel.MIXED
        elif fact_ratio >= 0.2:
            level = SubjectivityLevel.OPINION_HEAVY
        else:
            level = SubjectivityLevel.OPINION_ONLY

        return level, fact_ratio

    def _estimate_usability(self, doc: DocumentV1) -> Optional[float]:
        """估计研究可用性"""
        score = 0.0
        content = doc.content

        # 长度因子
        content_len = len(content)
        if content_len > 1000:
            score += 0.2
        elif content_len > 500:
            score += 0.1

        # 是否有数据
        if any(char.isdigit() for char in content):
            score += 0.2

        # 是否有具体公司/实体
        company_patterns = [
            r"[0-9]{6}\.(SZ|SH|BJ)",  # A股代码
            r"股份有限公司",
            r"有限公司",
            r"集团",
        ]
        for pattern in company_patterns:
            if re.search(pattern, content):
                score += 0.2
                break

        # 是否有明确时间
        date_patterns = [
            r"20[2-9][0-9]年[0-1]?[0-9]月",
            r"20[2-9][0-9]-[0-1][0-9]-[0-3][0-9]",
        ]
        for pattern in date_patterns:
            if re.search(pattern, content):
                score += 0.2
                break

        # 来源可信度
        if doc.quality:
            if doc.quality.source_reliability_level in [
                SourceReliabilityLevel.OFFICIAL,
                SourceReliabilityLevel.RESEARCH_INSTITUTE,
            ]:
                score += 0.2

        return min(score, 1.0)

    def _estimate_content_quality(self, doc: DocumentV1) -> Optional[float]:
        """估计内容质量"""
        score = 0.5  # 基础分
        content = doc.content

        # 长度
        content_len = len(content)
        if content_len > 2000:
            score += 0.15
        elif content_len > 1000:
            score += 0.1

        # 结构
        if "\n" in content:
            paragraphs = content.split("\n")
            paragraphs = [p for p in paragraphs if p.strip()]
            if len(paragraphs) >= 3:
                score += 0.1

        # 是否有标题分段
        if doc.classification and doc.classification.topics:
            score += 0.1

        return min(score, 1.0)

    def _has_explicit_facts(self, text: str) -> bool:
        """检查是否有明确的事实陈述"""
        fact_indicators = [
            "宣布",
            "公告",
            "发布",
            "数据显示",
            "统计",
            "据报道",
            "消息称",
            "according to",
            "reported",
            "announced",
            "released",
            r"20[2-9][0-9]年",
            r"[0-9]+(\.[0-9]+)?%",  # 百分比
            r"[0-9]+(\.[0-9]+)?亿",  # 亿单位
        ]

        for indicator in fact_indicators:
            if isinstance(indicator, str):
                if indicator in text:
                    return True
            else:  # regex
                if re.search(indicator, text):
                    return True

        return False

    def _has_explicit_opinions(self, text: str) -> bool:
        """检查是否有明确的观点"""
        opinion_indicators = [
            "认为",
            "预计",
            "预期",
            "预测",
            "判断",
            "观点",
            "看好",
            "看空",
            "乐观",
            "悲观",
            "可能",
            "或许",
            "应该",
            "建议",
            "推荐",
            "we believe",
            "we expect",
            "we think",
            "we forecast",
        ]

        for indicator in opinion_indicators:
            if indicator in text:
                return True

        return False

    def _has_data_points(self, text: str) -> bool:
        """检查是否有数据点"""
        data_indicators = [
            r"[0-9]+(\.[0-9]+)?%",  # 百分比
            r"[0-9]+(\.[0-9]+)?亿",  # 亿
            r"[0-9]+(\.[0-9]+)?万",  # 万
            r"[0-9]+(\.[0-9]+)?元",  # 元
            r"[0-9]+(\.[0-9]+)?美元",  # 美元
            r"[0-9]{4}年[0-9]{1,2}月",  # 年月
        ]

        for pattern in data_indicators:
            if re.search(pattern, text):
                return True

        return False

    def _has_quotes(self, text: str) -> bool:
        """检查是否有引述"""
        quote_patterns = [
            r'"[^"]{10,}"',  # 双引号
            r'"[^"]{10,}"',  # 中文双引号
            r"'[^']{10,}'",  # 单引号
            r"'[^']{10,}'",  # 中文单引号
        ]

        for pattern in quote_patterns:
            if re.search(pattern, text):
                return True

        return False

    def _has_analysis(self, text: str) -> bool:
        """检查是否有分析"""
        analysis_indicators = [
            "分析",
            "研究",
            "指出",
            "显示",
            "表明",
            "意味着",
            "analysis",
            "research",
            "study",
            "shows",
            "indicates",
        ]

        for indicator in analysis_indicators:
            if indicator in text:
                return True

        return False
