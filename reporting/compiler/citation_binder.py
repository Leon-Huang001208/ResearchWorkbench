"""
引用绑定器 - 报告编译器第一阶段.

解析正文中的 [fact_id] 标记，替换为格式化引用 [1]、[2]，并为每个引用生成
Citation 对象（含 display_text、anchor）。对应 deep-research-report.md "引用绑定器"
技能，实现 LongCite 式句级引用可验证。

同时检测：
- orphan citation：正文引用了不存在的 fact
- unsupported claim：正文含数字但无 fact 支撑（第一阶段做数字粗检）
"""

import re

from core.contracts import (
    Citation,
    CitationAnchor,
    CompiledSection,
    FactRecord,
)
from core.observability import get_logger
from core.utils.id_gen import generate_id

logger = get_logger(__name__)

_FACT_REF_PATTERN = re.compile(r"\[(fact_[A-Za-z0-9_\-]+)\]")
# 粗匹配正文中的数字（用于 unsupported claim 检测）
_NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")


class CitationBinder:
    """引用绑定器.

    把正文中的 [fact_id] 替换为 [N]，生成结构化 Citation 列表。
    """

    def bind(
        self,
        sections: list[CompiledSection],
        facts: list[FactRecord],
    ) -> list[CompiledSection]:
        """为每个 section 绑定引用.

        Args:
            sections: 分节写作器产出的章节（content 含 [fact_id] 标记）
            facts: 事实表

        Returns:
            绑定后的章节（content 含 [N] 引用 + citations 列表）
        """
        facts_by_id = {f.fact_id: f for f in facts}
        bound_sections: list[CompiledSection] = []

        for section in sections:
            content, citations, used_ids = self._bind_section(section, facts_by_id)
            bound_sections.append(
                section.model_copy(
                    update={
                        "content": content,
                        "citations": citations,
                        "fact_ids": used_ids,
                    }
                )
            )

        total_citations = sum(len(s.citations) for s in bound_sections)
        logger.info(
            "Citation binding complete", sections=len(bound_sections), citations=total_citations
        )
        return bound_sections

    def _bind_section(
        self,
        section: CompiledSection,
        facts_by_id: dict[str, FactRecord],
    ) -> tuple[str, list[Citation], list[str]]:
        """绑定单节引用.

        Returns:
            (替换后的 content, citation 列表, 实际引用的 fact_id 列表)
        """
        # 按 appearance 顺序分配 [N]
        citation_map: dict[str, int] = {}  # fact_id -> citation number
        citations: list[Citation] = []
        ordered_fact_ids: list[str] = []
        orphan_count = 0

        def replace_match(match: re.Match[str]) -> str:
            nonlocal orphan_count
            fact_id = match.group(1)
            fact = facts_by_id.get(fact_id)
            if fact is None:
                orphan_count += 1
                logger.warning(
                    "Orphan citation: fact_id not in facts table",
                    fact_id=fact_id,
                    section=section.section_id,
                )
                return ""  # 移除无效引用标记

            if fact_id not in citation_map:
                citation_map[fact_id] = len(citation_map) + 1
                ordered_fact_ids.append(fact_id)
                citations.append(self._build_citation(fact, citation_map[fact_id]))
            return f"[{citation_map[fact_id]}]"

        new_content = _FACT_REF_PATTERN.sub(replace_match, section.content)

        # 检测 unsupported claim：含数字但无任何引用的句子
        unsupported = self._detect_unsupported_claims(new_content, len(citations))
        if unsupported:
            logger.warning(
                "Possible unsupported claims detected",
                section=section.section_id,
                count=unsupported,
            )

        if orphan_count:
            logger.warning(
                "Orphan citations removed",
                section=section.section_id,
                count=orphan_count,
            )

        return new_content, citations, ordered_fact_ids

    def _build_citation(self, fact: FactRecord, number: int) -> Citation:
        """为一条 fact 构建格式化引用."""
        prov = fact.provenance
        date_str = prov.published_at.strftime("%Y-%m-%d") if prov.published_at else "无日期"
        display_text = f"[{number}] {prov.source_name} {date_str}"
        return Citation(
            citation_id=generate_id(),
            fact_ids=[fact.fact_id],
            display_text=display_text,
            anchor=CitationAnchor(
                locator_type="span",
                locator_value=fact.evidence_span[:200] if fact.evidence_span else "",
                chunk_index=None,
            ),
        )

    def _detect_unsupported_claims(self, content: str, citation_count: int) -> int:
        """粗略检测 unsupported claim：正文含数字但零引用.

        第一阶段做最简单的检测——若正文有数字但无任何引用，记为可疑。
        第三阶段 numeric_checker 会做精确的逐数字匹配。
        """
        if citation_count > 0:
            return 0
        # 含数字且无引用
        numbers = _NUMBER_PATTERN.findall(content)
        # 过滤掉年份等（4 位且在 1990-2099）
        meaningful = [n for n in numbers if not (len(n) == 4 and 1990 <= int(float(n)) <= 2099)]
        return 1 if meaningful else 0
