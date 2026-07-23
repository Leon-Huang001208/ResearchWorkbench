"""
引用验证器 - 报告编译器第三阶段 3.2.

对编译后章节的引用质量做细粒度验证：
- citation precision: 引用的 fact 是否真正支撑其所在句子（文本重叠+数值匹配）
- orphan citation: 引用的 fact_ids 是否存在于全局事实表
- source diversity: 引用来源是否过于集中
- citation coverage: 全局 fact 中有多少被至少引用一次

所有检查全结构化/规则驱动，不调用 LLM。
输出 list[CritiqueIssue]，复用 CritiqueIssue + CritiqueCategory，无缝接入 RevisionPass。
"""

import re
from collections import Counter

from core.contracts import (
    Citation,
    CompiledSection,
    CritiqueCategory,
    CritiqueIssue,
    FactRecord,
)
from core.observability import get_logger
from core.utils.id_gen import generate_id

logger = get_logger(__name__)

# 引用标记 [N] 用于在正文中定位引用位置
_CITATION_NUM_PATTERN = re.compile(r"\[(\d+)\]")
# 数字抽取（复用 critic.py 模式）
_NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")

# 来源集中度阈值：单一来源超过此比例记 issue
_MAX_SOURCE_RATIO = 0.80
# 引用精度最低分数
_MIN_PRECISION_SCORE = 0.5
# 引用覆盖率最低阈值
_MIN_COVERAGE_RATE = 0.80


class CitationVerifier:
    """引用验证器.

    验证章节引用的精度、完整性、多样性。所有检查纯结构化，不调用 LLM。
    """

    MAX_SOURCE_RATIO = _MAX_SOURCE_RATIO
    MIN_PRECISION_SCORE = _MIN_PRECISION_SCORE
    MIN_COVERAGE_RATE = _MIN_COVERAGE_RATE

    def verify(
        self,
        sections: list[CompiledSection],
        facts: list[FactRecord],
    ) -> list[CritiqueIssue]:
        """验证所有章节的引用质量.

        Args:
            sections: 引用绑定后的章节
            facts: 全局事实表

        Returns:
            list[CritiqueIssue]: 引用相关的问题列表
        """
        facts_by_id: dict[str, FactRecord] = {f.fact_id: f for f in facts}
        all_cited_fact_ids: set[str] = set()
        all_issues: list[CritiqueIssue] = []

        for section in sections:
            # 1. 引用精度
            all_issues.extend(self._check_citation_precision(section, facts_by_id))

            # 2. 孤立引用
            all_issues.extend(self._check_orphan_citations(section, facts_by_id))

            # 3. 收集被引用的 fact，用于来源多样性与覆盖率
            section_cited = self._collect_cited_fact_ids(section, facts_by_id)
            all_cited_fact_ids.update(section_cited)

            # 4. 来源多样性（基于本节已引用的 fact）
            if section_cited:
                all_issues.extend(self._check_source_diversity(section, section_cited, facts_by_id))

        # 5. 全局引用覆盖率（跨所有 section）
        all_issues.extend(self._check_coverage(sections, all_cited_fact_ids, facts))

        logger.info(
            "Citation verification complete",
            sections=len(sections),
            issues=len(all_issues),
            cited_facts=len(all_cited_fact_ids),
            total_facts=len(facts),
        )
        return all_issues

    # ── 各维度检查 ───────────────────────────────────────────────────

    def _check_citation_precision(
        self, section: CompiledSection, facts_by_id: dict[str, FactRecord]
    ) -> list[CritiqueIssue]:
        """引用精度检查：每个引用的 fact 是否支撑其所在句子.

        对 section.citations 中的每个 Citation：
        1. 在正文中找 [N] 的位置与所在句子
        2. 取 fact_ids[0] 对应的 FactRecord
        3. 算精度分数：数值匹配 + 文本重叠
        4. 分数过低 → CITATION_PRECISION issue
        """
        issues: list[CritiqueIssue] = []
        content = section.content

        for i, citation in enumerate(section.citations):
            citation_num = i + 1  # Citation 按 [1], [2], ... 编号
            fact = self._resolve_fact(citation, facts_by_id)
            if fact is None:
                continue  # orphan 由 _check_orphan_citations 处理

            # 在正文中找 [N] 标记的位置
            marker = f"[{citation_num}]"
            if marker not in content:
                continue  # 引用未在正文中出现（罕见）

            # 找包含此引用的句子
            sentence = self._find_sentence_with_citation(content, marker)
            if not sentence:
                continue

            # 计算精度分数
            score = self._compute_precision_score(sentence, fact)
            if score < self.MIN_PRECISION_SCORE:
                issues.append(
                    CritiqueIssue(
                        issue_id=generate_id(),
                        category=CritiqueCategory.CITATION_PRECISION,
                        severity="warning",
                        section_id=section.section_id,
                        description=(
                            f"引用 {marker} 的 fact「{fact.claim_text[:40]}」"
                            f"与所在句子支撑度不足（精度 {score:.1f}）"
                        ),
                        location=sentence[:150],
                        conflicting_fact_id=fact.fact_id,
                        suggested_fix="检查此引用是否被错误放置，或替换为更相关的 fact",
                    )
                )

        return issues

    def _check_orphan_citations(
        self, section: CompiledSection, facts_by_id: dict[str, FactRecord]
    ) -> list[CritiqueIssue]:
        """孤立引用检查：citation.fact_ids 中是否有 fact_id 不在全局 facts 中."""
        issues: list[CritiqueIssue] = []
        for citation in section.citations:
            for fact_id in citation.fact_ids:
                if fact_id not in facts_by_id:
                    issues.append(
                        CritiqueIssue(
                            issue_id=generate_id(),
                            category=CritiqueCategory.ORPHAN_CITATION,
                            severity="error",
                            section_id=section.section_id,
                            description=f"引用指向不存在的 fact「{fact_id}」",
                            location=citation.display_text,
                            conflicting_fact_id=fact_id,
                            suggested_fix="删除此引用或确保 fact_id 存在",
                        )
                    )
        return issues

    def _check_source_diversity(
        self,
        section: CompiledSection,
        cited_fact_ids: set[str],
        facts_by_id: dict[str, FactRecord],
    ) -> list[CritiqueIssue]:
        """来源多样性检查：引用来源是否过度集中."""
        issues: list[CritiqueIssue] = []
        source_counts: Counter[str] = Counter()
        total = 0
        for fact_id in cited_fact_ids:
            fact = facts_by_id.get(fact_id)
            if fact:
                source_name = fact.provenance.source_name or fact.provenance.doc_id
                source_counts[source_name] += 1
                total += 1

        if total == 0:
            return issues

        most_common, most_count = source_counts.most_common(1)[0]
        ratio = most_count / total
        if ratio > self.MAX_SOURCE_RATIO:
            issues.append(
                CritiqueIssue(
                    issue_id=generate_id(),
                    category=CritiqueCategory.SOURCE_DIVERSITY,
                    severity="info",
                    section_id=section.section_id,
                    description=(
                        f"引用来源过于集中：{most_count}/{total}（{ratio:.0%}）来自「{most_common}」，"
                        f"共引用 {len(source_counts)} 个来源"
                    ),
                    location="",
                    suggested_fix="增加其他来源的引用以提升多样性",
                )
            )
        return issues

    def _check_coverage(
        self,
        sections: list[CompiledSection],
        all_cited: set[str],
        facts: list[FactRecord],
    ) -> list[CritiqueIssue]:
        """引用覆盖率检查：全局 facts 被引用的比例."""
        issues: list[CritiqueIssue] = []
        total_facts = len(facts)
        if total_facts == 0:
            return issues

        coverage = len(all_cited) / total_facts
        if coverage < self.MIN_COVERAGE_RATE:
            uncited_ids = [f.fact_id for f in facts if f.fact_id not in all_cited]
            # 只在第一个 section 上报告（避免重复）
            if sections:
                issues.append(
                    CritiqueIssue(
                        issue_id=generate_id(),
                        category=CritiqueCategory.CITATION_PRECISION,
                        severity="info",
                        section_id=sections[0].section_id,
                        description=(
                            f"全局引用覆盖率偏低（{coverage:.0%} < {self.MIN_COVERAGE_RATE:.0%}），"
                            f"{len(uncited_ids)} 个 fact 未被任何章节引用"
                        ),
                        location="",
                        suggested_fix="在正文中为以下 fact 添加引用：" + ", ".join(uncited_ids[:5]),
                    )
                )
        return issues

    # ── 辅助方法 ───────────────────────────────────────────────────────

    @staticmethod
    def _resolve_fact(citation: Citation, facts_by_id: dict[str, FactRecord]) -> FactRecord | None:
        """从 Citation 中解析主 fact（取 fact_ids[0]）."""
        if not citation.fact_ids:
            return None
        return facts_by_id.get(citation.fact_ids[0])

    @staticmethod
    def _find_sentence_with_citation(content: str, marker: str) -> str:
        """找到包含指定引用标记的句子."""
        idx = content.find(marker)
        if idx == -1:
            return ""

        # 向前搜索句子开头（默认为文本起始位置，无分句点时从开头截取）
        sent_start = 0
        for ch in [r"。", r"！", r"？", r"!", r"?", "\n"]:
            pos = content.rfind(ch, 0, idx)
            if pos != -1:
                sent_start = max(sent_start, pos + 1)

        # 向后搜索句子结尾
        sent_end = len(content)
        for ch in [r"。", r"！", r"？", r"!", r"?", "\n"]:
            pos = content.find(ch, idx + len(marker))
            if pos != -1 and pos < sent_end:
                sent_end = pos + 1
                break

        return content[sent_start:sent_end].strip()

    def _compute_precision_score(self, sentence: str, fact: FactRecord) -> float:
        """计算引用精度分数（0.0-1.0）.

        分数组成：
        - 0.5: fact 的数值在句子中出现（±20 字符范围内）
        - 0.5: fact.claim_text 与句子有文本重叠
        """
        score = 0.0

        # 1. 数值匹配
        if fact.value is not None and fact.value != 0:
            numbers = _NUMBER_PATTERN.findall(sentence)
            for n_str in numbers:
                try:
                    n = float(n_str)
                except ValueError:
                    continue
                if abs(n - fact.value) / max(abs(fact.value), 1e-6) < 0.05:
                    score += 0.5
                    break

        # 2. 文本重叠
        if self._text_overlap(sentence, fact.claim_text):
            score += 0.5

        return score

    @staticmethod
    def _collect_cited_fact_ids(
        section: CompiledSection, facts_by_id: dict[str, FactRecord]
    ) -> set[str]:
        """收集本节所有实际被引用的有效 fact_ids."""
        cited: set[str] = set()
        for citation in section.citations:
            for fact_id in citation.fact_ids:
                if fact_id in facts_by_id:
                    cited.add(fact_id)
        return cited

    # ── 文本工具（与 critic.py 一致） ─────────────────────────────────

    @staticmethod
    def _text_overlap(text1: str, text2: str) -> bool:
        """判断两段文本是否有足够的关键词重叠（中英文自适应）."""
        has_spaces = " " in text1 or " " in text2
        if has_spaces:
            words1 = {w for w in text1.split() if len(w) > 1}
            words2 = {w for w in text2.split() if len(w) > 1}
            return len(words1 & words2) >= 2
        else:
            bigrams1 = {text1[i : i + 2] for i in range(len(text1) - 1)}
            bigrams2 = {text2[i : i + 2] for i in range(len(text2) - 1)}
            return len(bigrams1 & bigrams2) >= 2
