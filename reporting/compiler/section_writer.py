"""
分节写作器 - 报告编译器第一阶段.

按 ReportOutline 逐节生成正文，每节只使用匹配 required_claim_types 的 facts。
对应 deep-research-report.md "分节写作器" 技能。

关键约束：禁止输出未支撑数字。prompt 中注入 facts 时带编号（[fact_id]），
要求 writer 在正文中用 [fact_id] 标记引用位置，供 citation_binder 解析为
格式化 [N] 引用。正文是自由文本，用 model_gateway.chat 而非 structured_output。
"""

import re
from typing import Optional

from core.contracts import (
    CompiledSection,
    FactRecord,
    OutlineSection,
    ReportOutline,
)
from core.interfaces import ModelGateway
from core.observability import get_logger

logger = get_logger(__name__)

# 正文中引用标记的正则，如 [fact_abc123]
_FACT_REF_PATTERN = re.compile(r"\[(fact_[A-Za-z0-9_\-]+)\]")


class SectionWriter:
    """分节写作器.

    按 outline 逐节生成正文，输出 CompiledSection（含 content + fact_ids + 待绑定 citation 槽）。
    """

    def __init__(self, model_gateway: Optional[ModelGateway] = None):
        self.model_gateway = model_gateway

    def write(
        self,
        outline: ReportOutline,
        facts: list[FactRecord],
    ) -> list[CompiledSection]:
        """按大纲逐节生成正文.

        Args:
            outline: 大纲规划器产出的标题树
            facts: 事实抽取器产出的 FactRecord 列表

        Returns:
            每节一个 CompiledSection（content 含 [fact_id] 标记，待 citation_binder 绑定）
        """
        facts_by_id = {f.fact_id: f for f in facts}
        sections: list[CompiledSection] = []

        for outline_section in outline.sections:
            section_facts = self._select_facts(outline_section, facts)
            content = self._generate_section(outline_section, section_facts)
            used_fact_ids = self._extract_used_fact_ids(content, facts_by_id)

            sections.append(
                CompiledSection(
                    section_id=outline_section.section_id,
                    title=outline_section.title,
                    content=content,
                    fact_ids=used_fact_ids,
                )
            )
            logger.info(
                "Section written",
                section_id=outline_section.section_id,
                facts_used=len(used_fact_ids),
            )

        return sections

    def _select_facts(
        self,
        outline_section: OutlineSection,
        facts: list[FactRecord],
    ) -> list[FactRecord]:
        """按 outline 的 required_claim_types 筛选本节可用 facts.

        若 outline 未指定 claim_types 或无匹配，回退到全部 facts（截断）。
        """
        if not outline_section.required_claim_types:
            return facts[:40]
        required = set(outline_section.required_claim_types)
        matched = [f for f in facts if f.claim_type in required]
        return matched if matched else facts[:40]

    def _generate_section(
        self,
        outline_section: OutlineSection,
        section_facts: list[FactRecord],
    ) -> str:
        """生成单节正文."""
        if not self.model_gateway:
            return self._stub_section(outline_section, section_facts)

        try:
            response = self.model_gateway.chat(
                messages=self._build_messages(outline_section, section_facts),
                temperature=0.3,
                max_tokens=1600,
            )
            return response.content.strip()
        except Exception as e:
            logger.error(
                "Section generation failed, using stub",
                section_id=outline_section.section_id,
                error=str(e),
                exc_info=True,
            )
            return self._stub_section(outline_section, section_facts)

    def _build_messages(
        self,
        outline_section: OutlineSection,
        section_facts: list[FactRecord],
    ) -> list[dict[str, str]]:
        """构建分节写作 prompt."""
        system_msg = (
            "你是资深行业研究员，按大纲写一节报告正文。"
            "规则：1) 只使用给定的事实，禁止编造未支撑的数字；"
            "2) 引用某条事实时，在该句末尾标注 [fact_id]（fact_id 见事实列表）；"
            "3) 必须覆盖大纲指定的风险与反证，不只写利多；"
            "4) 直接输出正文，不要标题、不要解释。"
        )
        facts_lines: list[str] = []
        for f in section_facts:
            value_str = f"{f.value}{f.unit}" if f.value is not None else ""
            facts_lines.append(
                f"- [{f.fact_id}] {f.claim_text} {value_str}"
                f"（{f.provenance.source_name}, {f.provenance.source_tier.value}）"
            )
        facts_block = (
            "\n".join(facts_lines) if facts_lines else "（本节无可用事实，请说明证据不足）"
        )
        counterpoints = (
            "；".join(outline_section.counterpoints) if outline_section.counterpoints else "无"
        )
        user_msg = (
            f"章节: {outline_section.title}\n"
            f"目标: {outline_section.goal}\n"
            f"必须回答: {', '.join(outline_section.must_answer) or '无'}\n"
            f"风险与反证（必须覆盖）: {counterpoints}\n"
            f"目标字数: {outline_section.target_words}\n"
            f"可用事实:\n{facts_block}\n"
        )
        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

    def _stub_section(
        self,
        outline_section: OutlineSection,
        section_facts: list[FactRecord],
    ) -> str:
        """无 LLM 时的占位正文（带 [fact_id] 标记，便于 citation_binder 测试）."""
        lines = [f"【{outline_section.title}】"]
        lines.append(outline_section.goal or "")
        for f in section_facts[:10]:
            value_str = f"{f.value}{f.unit}" if f.value is not None else ""
            lines.append(f"- {f.claim_text} {value_str} [{f.fact_id}]")
        return "\n".join(lines)

    def _extract_used_fact_ids(
        self,
        content: str,
        facts_by_id: dict[str, FactRecord],
    ) -> list[str]:
        """从正文提取实际引用的 fact_id（去重保序）."""
        seen: set[str] = set()
        ordered: list[str] = []
        for match in _FACT_REF_PATTERN.finditer(content):
            fid = match.group(1)
            if fid in facts_by_id and fid not in seen:
                seen.add(fid)
                ordered.append(fid)
        return ordered
