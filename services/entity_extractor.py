"""
Entity Extractor - Issue #44

Extract entities from documents:
- Company/Institution
- Person
- Product
- Industry
- Region
- Policy
"""
import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Set, Tuple

from core.contracts import DocumentV1, EntityMentionV1
from core.observability import get_logger
from core.utils.id_gen import generate_id

logger = get_logger(__name__)


class EntityType(str, Enum):
    """Entity types"""

    COMPANY = "company"
    PERSON = "person"
    PRODUCT = "product"
    INDUSTRY = "industry"
    REGION = "region"
    POLICY = "policy"
    STOCK_CODE = "stock_code"


@dataclass
class EntityCandidate:
    """Entity candidate"""

    text: str
    entity_type: EntityType
    start: int
    end: int
    confidence: float
    context: Optional[str] = None


class EntityExtractor:
    """Entity extractor"""

    def __init__(self):
        self._init_patterns()

    def _init_patterns(self):
        """Initialize regex patterns"""
        # Stock code pattern
        self.stock_code_pattern = re.compile(r"([0-9]{6})\.(SZ|SH|BJ|sz|sh|bj)")

        # Company suffixes
        self.company_suffixes = [
            "Company",
            "Co., Ltd.",
            "Co., Ltd",
            "Ltd.",
            "Ltd",
            "Inc.",
            "Inc",
            "Corp.",
            "Corp",
        ]

        # Well-known companies
        self.known_companies = [
            "Huawei",
            "Tencent",
            "Alibaba",
            "Baidu",
            "JD",
            "Meituan",
            "Moutai",
            "Wuliangye",
            "BYD",
            "Tesla",
        ]

        # Chinese regions
        self.chinese_regions = [
            "Beijing",
            "Shanghai",
            "Guangdong",
            "Shenzhen",
            "Hangzhou",
        ]

        # Simple policy pattern
        self.policy_pattern = re.compile(r'"[^"]{4,}"')

    def extract(self, doc: DocumentV1) -> List[EntityMentionV1]:
        """
        Extract entities from document

        Args:
            doc: Document

        Returns:
            List of entity mentions
        """
        logger.info(f"Extracting entities from document: {doc.doc_id}")

        mentions: List[EntityMentionV1] = []
        text = doc.content
        seen: Set[Tuple[str, str]] = set()

        # 1. Extract stock codes
        stock_mentions = self._extract_stock_codes(text, doc.doc_id)
        for m in stock_mentions:
            key = (m.entity_name, m.entity_type)
            if key not in seen:
                seen.add(key)
                mentions.append(m)

        # 2. Extract companies
        company_mentions = self._extract_companies(text, doc.doc_id)
        for m in company_mentions:
            key = (m.entity_name, m.entity_type)
            if key not in seen:
                seen.add(key)
                mentions.append(m)

        logger.info(f"Extracted {len(mentions)} entities")
        return mentions

    def _extract_stock_codes(self, text: str, doc_id: str) -> List[EntityMentionV1]:
        """Extract stock codes"""
        mentions: List[EntityMentionV1] = []

        for match in self.stock_code_pattern.finditer(text):
            code = match.group(1) + "." + match.group(2).upper()
            context = self._extract_context(text, match.start(), match.end())

            mentions.append(
                EntityMentionV1(
                    mention_id=generate_id(),
                    doc_id=doc_id,
                    entity_id=code,
                    entity_name=code,
                    entity_type=EntityType.STOCK_CODE.value,
                    start_offset=match.start(),
                    end_offset=match.end(),
                    context=context,
                    confidence=0.95,
                    is_primary=False,
                )
            )

        return mentions

    def _extract_companies(self, text: str, doc_id: str) -> List[EntityMentionV1]:
        """Extract company entities (simplified)"""
        mentions: List[EntityMentionV1] = []

        for company in self.known_companies:
            for match in re.finditer(re.escape(company), text):
                context = self._extract_context(text, match.start(), match.end())
                mentions.append(
                    EntityMentionV1(
                        mention_id=generate_id(),
                        doc_id=doc_id,
                        entity_id=company,
                        entity_name=company,
                        entity_type=EntityType.COMPANY.value,
                        start_offset=match.start(),
                        end_offset=match.end(),
                        context=context,
                        confidence=0.9,
                        is_primary=False,
                    )
                )

        return mentions

    def _extract_context(self, text: str, start: int, end: int, context_len: int = 100) -> str:
        """Extract context around entity"""
        context_start = max(0, start - context_len)
        context_end = min(len(text), end + context_len)
        return text[context_start:context_end]
