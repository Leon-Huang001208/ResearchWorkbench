"""
修订器 - 报告编译器第三阶段 3.1.

消费批判器输出的 CritiqueReport，按每个 issue 的 suggested_fix 自动修复
章节内容。硬限制 max 2 轮 revision→critic 循环，超限或不可自动修复时
标记为需人工审核。

修复规则：
- CONFLICT：替换正文矛盾数字为事实表值
- CLAIM_SUPPORT：在未支撑句子附近插入 [fact_id] 引用标记
- COUNTERPOINT：在节尾追加反证提示句（无法精确定位时标记人工）
- STRUCTURE / EVIDENCE_SUFFICIENCY / FORBIDDEN_TERM：标记为需人工审核
"""

from dataclasses import dataclass, field
from typing import Optional

from core.contracts import (
    CompiledSection,
    CritiqueCategory,
    CritiqueIssue,
    CritiqueReport,
    FactRecord,
    ReportOutline,
)
from core.observability import get_logger

logger = get_logger(__name__)


@dataclass
class RevisionResult:
    """修订结果."""

    sections: list[CompiledSection] = field(default_factory=list)
    fixed_issue_ids: list[str] = field(default_factory=list)
    unfixable_issue_ids: list[str] = field(default_factory=list)
    remaining_issues: list[CritiqueIssue] = field(default_factory=list)
    rounds: int = 0
    converged: bool = False
    summary: str = ""


class RevisionPass:
    """修订器.

    按 CritiqueReport 自动修复章节内容。不做 LLM 调用——所有修复基于
    结构化数据（数字替换、引用插入、反证追加），不能自动修复的标记为
    需人工审核。
    """

    MAX_ROUNDS = 2

    def __init__(self):
        self._total_fixes = 0

    def revise(
        self,
        sections: list[CompiledSection],
        critique: CritiqueReport,
        facts: list[FactRecord],
        outline: ReportOutline,
        round_number: int = 1,
    ) -> RevisionResult:
        """执行一轮修订.

        Args:
            sections: 当前章节列表
            critique: 批判器输出
            facts: 事实表
            outline: 报告大纲（供反证覆盖参考）
            round_number: 当前修订轮次

        Returns:
            RevisionResult：修订后的章节 + 修复追踪
        """
        if round_number > self.MAX_ROUNDS:
            logger.warning(
                "RevisionPass exceeded max rounds, returning sections unchanged",
                max=self.MAX_ROUNDS,
            )
            return RevisionResult(
                sections=sections,
                remaining_issues=critique.issues,
                rounds=round_number,
                converged=False,
                summary=f"已达最大修订轮次上限 ({self.MAX_ROUNDS})，以下问题需人工审核",
            )

        facts_by_id = {f.fact_id: f for f in facts}
        sections_by_id = {s.section_id: s for s in sections}

        fixed_ids: list[str] = []
        unfixable_ids: list[str] = []
        remaining: list[CritiqueIssue] = []

        # 按严重度排序处理：error 优先
        issues_sorted = sorted(
            critique.issues,
            key=lambda i: (0 if i.severity == "error" else 1 if i.severity == "warning" else 2),
        )

        for issue in issues_sorted:
            section = sections_by_id.get(issue.section_id)
            if section is None:
                unfixable_ids.append(issue.issue_id)
                continue

            fixed = self._fix_issue(issue, section, facts_by_id, sections_by_id)
            if fixed:
                fixed_ids.append(issue.issue_id)
                sections_by_id[issue.section_id] = fixed
            else:
                unfixable_ids.append(issue.issue_id)
                remaining.append(issue)

        self._total_fixes += len(fixed_ids)
        updated = [sections_by_id[s.section_id] for s in sections]

        # 判断是否可以收敛：没有 error 级别的剩余问题
        unconverged_errors = [i for i in remaining if i.severity == "error"]
        actually_converged = len(unconverged_errors) == 0

        summary = (
            f"第 {round_number} 轮修订：修复 {len(fixed_ids)} 个问题，"
            f"{len(unfixable_ids)} 个问题无法自动修复"
            + (f"（{len(unconverged_errors)} 个 error 级别）" if unconverged_errors else "，所有错误已修复")
        )

        logger.info(
            "RevisionPass round complete",
            round=round_number,
            fixed=len(fixed_ids),
            unfixable=len(unfixable_ids),
            converged=actually_converged,
        )

        return RevisionResult(
            sections=updated,
            fixed_issue_ids=fixed_ids,
            unfixable_issue_ids=unfixable_ids,
            remaining_issues=remaining,
            rounds=round_number,
            converged=actually_converged,
            summary=summary,
        )

    def _fix_issue(
        self,
        issue: CritiqueIssue,
        section: CompiledSection,
        facts_by_id: dict[str, FactRecord],
        sections_by_id: dict[str, CompiledSection],
    ) -> Optional[CompiledSection]:
        """尝试修复单个 issue，返回修复后的 section 或 None（无法修复）."""
        if issue.category == CritiqueCategory.CONFLICT:
            return self._fix_conflict(issue, section, facts_by_id)
        elif issue.category == CritiqueCategory.CLAIM_SUPPORT:
            return self._fix_claim_support(issue, section, facts_by_id)
        elif issue.category == CritiqueCategory.COUNTERPOINT:
            return self._fix_counterpoint(issue, section)
        elif issue.category == CritiqueCategory.FORBIDDEN_TERM:
            return self._fix_forbidden_term(issue, section)
        # Phase 3.2 新增类别
        elif issue.category == CritiqueCategory.CITATION_PRECISION:
            return self._fix_citation_precision(issue, section)
        elif issue.category == CritiqueCategory.ORPHAN_CITATION:
            return self._fix_orphan_citation(issue, section)
        elif issue.category == CritiqueCategory.UNIT_MISMATCH:
            return self._fix_unit_mismatch(issue, section, facts_by_id)
        elif issue.category == CritiqueCategory.PERIOD_MISMATCH:
            return self._fix_period_mismatch(issue, section, facts_by_id)
        elif issue.category in (
            CritiqueCategory.STRUCTURE,
            CritiqueCategory.EVIDENCE_SUFFICIENCY,
            CritiqueCategory.SOURCE_DIVERSITY,
            CritiqueCategory.FABRICATED_NUMBER,
        ):
            # 结构化/来源多样性/虚构数字不能自动修复，标记人工
            return None
        return None

    # ── 各类型修复方法 ──────────────────────────────────────────

    def _fix_conflict(
        self,
        issue: CritiqueIssue,
        section: CompiledSection,
        facts_by_id: dict[str, FactRecord],
    ) -> Optional[CompiledSection]:
        """修复数字矛盾：将正文中的错误数字替换为事实表值."""
        fact = (
            facts_by_id.get(issue.conflicting_fact_id or "") if issue.conflicting_fact_id else None
        )
        if fact is None or fact.value is None:
            return None

        import re

        content = section.content
        # 在 location 中找可能的错误数字
        # location 存储了含有矛盾的句子的前 150 字符
        if issue.location and issue.location in content:
            # 在包含矛盾数字的句子范围内找数字
            start = content.index(issue.location[:50])
            end = min(start + len(issue.location), len(content))
            snippet = content[start:end]
            # 替换 snippet 中的数字为事实表值
            numbers = re.findall(r"\d+(?:\.\d+)?", snippet)
            if numbers:
                # 替换第一个非年份数字
                for n_str in numbers:
                    n_val = float(n_str)
                    if len(n_str) == 4 and 1990 <= int(n_val) <= 2099:
                        continue
                    # 替换：保持整数/小数格式一致
                    if fact.value == int(fact.value):
                        replacement = str(int(fact.value))
                    else:
                        replacement = f"{fact.value:.{max(2, len(n_str.split('.')[-1]) if '.' in n_str else 0)}f}"
                    new_snippet = snippet.replace(n_str, replacement, 1)
                    new_content = content[:start] + new_snippet + content[end:]
                    logger.info(
                        "Fixed conflict",
                        section=section.section_id,
                        old=n_str,
                        new=replacement,
                    )
                    return section.model_copy(update={"content": new_content})
        return None

    def _fix_claim_support(
        self,
        issue: CritiqueIssue,
        section: CompiledSection,
        facts_by_id: dict[str, FactRecord],
    ) -> Optional[CompiledSection]:
        """修复声明支撑不足：在 location 句子附近插入最相关 fact 的引用.

        优先找与 location 文本关键词重叠的 fact，在其后插入 [fact_id]。
        中英文自适应：空格分隔用词重叠，中文用字符二元组重叠。
        """
        location = issue.location
        if not location or location not in section.content:
            return None

        location_lower = location.lower()
        # 尝试从 location 提取数字，找值相近的 fact
        import re

        numbers = re.findall(r"\d+(?:\.\d+)?", location)
        meaningful = [
            float(n) for n in numbers if not (len(n) == 4 and 1990 <= int(float(n)) <= 2099)
        ]

        # 找与 location 最匹配的 fact
        best_fact: Optional[FactRecord] = None
        best_score = 0
        for fact_id, fact in facts_by_id.items():
            if fact_id in section.fact_ids:
                continue  # 已引用

            score = 0
            # 1. 数值匹配加分
            if fact.value is not None and meaningful:
                for n in meaningful:
                    if fact.value != 0 and abs(n - fact.value) / fact.value < 0.10:
                        score += 3

            # 2. 文本重叠加分
            fact_text_lower = fact.claim_text.lower()
            if self._text_overlap(location_lower, fact_text_lower):
                score += 2

            if score > best_score:
                best_score = score
                best_fact = fact

        if best_fact is None or best_score < 2:
            return None

        # 在 location 句子后面插入引用
        ref = f"[{best_fact.fact_id}]"
        idx = section.content.index(location) + len(location)
        new_content = section.content[:idx] + ref + section.content[idx:]
        new_fact_ids = list(section.fact_ids) + [best_fact.fact_id]
        logger.info(
            "Fixed claim support",
            section=section.section_id,
            fact=best_fact.fact_id,
            score=best_score,
        )
        return section.model_copy(update={"content": new_content, "fact_ids": new_fact_ids})

    def _fix_counterpoint(
        self, issue: CritiqueIssue, section: CompiledSection
    ) -> Optional[CompiledSection]:
        """修复反证覆盖：在节尾追加反证提醒句."""
        # 从 description 提取反证文本
        # description 格式：反证点未覆盖：「xxx」
        import re

        match = re.search(r"「(.+?)」", issue.description)
        if not match:
            return None
        cp_text = match.group(1)
        suffix = f"\n\n（注：需关注风险——{cp_text}）"
        new_content = section.content.rstrip() + suffix
        logger.info(
            "Fixed counterpoint",
            section=section.section_id,
            counterpoint=cp_text,
        )
        return section.model_copy(update={"content": new_content})

    def _fix_forbidden_term(
        self, issue: CritiqueIssue, section: CompiledSection
    ) -> Optional[CompiledSection]:
        """修复禁用词：删除出现位置."""
        import re

        match = re.search(r"「(.+?)」", issue.description)
        if not match:
            return None
        term = match.group(1)
        if term in section.content:
            new_content = section.content.replace(term, "（已删除违规表述）")
            logger.info(
                "Fixed forbidden term",
                section=section.section_id,
                term=term,
            )
            return section.model_copy(update={"content": new_content})
        return None

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

    # ── Phase 3.2 新增修复方法 ─────────────────────────────────────

    @staticmethod
    def _fix_citation_precision(
        issue: CritiqueIssue, section: CompiledSection
    ) -> Optional[CompiledSection]:
        """修复引用精度不足：移除低精度引用标记.

        从 issue.description 提取引用标记（如 [1]），在正文中移除。
        """
        import re

        match = re.search(r"引用\s*(\[\d+\])", issue.description)
        if not match:
            return None
        marker = match.group(1)
        if marker in section.content:
            new_content = section.content.replace(marker, "")
            logger.info(
                "Fixed citation precision: removed low-precision citation",
                section=section.section_id,
                marker=marker,
            )
            return section.model_copy(update={"content": new_content})
        return None

    @staticmethod
    def _fix_orphan_citation(
        issue: CritiqueIssue, section: CompiledSection
    ) -> Optional[CompiledSection]:
        """修复孤立引用：移除指向不存在 fact 的引用标记.

        从 citation.display_text 或 conflicting_fact_id 定位引用。
        """
        # 尝试从 display_text 提取引用编号
        import re

        marker_match = re.search(r"\[(\d+)\]", issue.location)
        if marker_match:
            marker = f"[{marker_match.group(1)}]"
        else:
            # fallback: 尝试用 fact_id 在正文中搜索
            fact_id = issue.conflicting_fact_id
            if fact_id and f"[{fact_id}]" in section.content:
                marker = f"[{fact_id}]"
            else:
                return None

        if marker in section.content:
            new_content = section.content.replace(marker, "")
            logger.info(
                "Fixed orphan citation",
                section=section.section_id,
                marker=marker,
            )
            return section.model_copy(update={"content": new_content})
        return None

    @staticmethod
    def _fix_unit_mismatch(
        issue: CritiqueIssue,
        section: CompiledSection,
        facts_by_id: dict[str, FactRecord],
    ) -> Optional[CompiledSection]:
        """修复单位不一致：将正文单位替换为 fact.unit.

        issue.description 格式：「正文使用「xxx」，事实记录为「yyy」」
        issue.conflicting_fact_id 指向正确的 fact。
        """
        fact = (
            facts_by_id.get(issue.conflicting_fact_id or "") if issue.conflicting_fact_id else None
        )
        if fact is None or fact.unit is None:
            return None

        import re

        # 从 description 提取错误单位
        m = re.search(r"正文使用「(.+?)」", issue.description)
        if not m:
            return None
        wrong_unit = m.group(1)

        # 在 location 范围内替换
        if issue.location and wrong_unit in issue.location:
            # 在 section.content 中找到 location 段
            if issue.location in section.content:
                new_snippet = issue.location.replace(wrong_unit, fact.unit, 1)
                new_content = section.content.replace(issue.location, new_snippet, 1)
                logger.info(
                    "Fixed unit mismatch",
                    section=section.section_id,
                    old=wrong_unit,
                    new=fact.unit,
                )
                return section.model_copy(update={"content": new_content})
        return None

    @staticmethod
    def _fix_period_mismatch(
        issue: CritiqueIssue,
        section: CompiledSection,
        facts_by_id: dict[str, FactRecord],
    ) -> Optional[CompiledSection]:
        """修复期间不一致：将正文期间文本替换为 fact.period.

        issue.description 格式：「正文引用「xxx」，事实记录为「yyy」」
        """
        fact = (
            facts_by_id.get(issue.conflicting_fact_id or "") if issue.conflicting_fact_id else None
        )
        if fact is None or fact.period is None or fact.period == "":
            return None

        import re

        m = re.search(r"正文引用「(.+?)」", issue.description)
        if not m:
            return None
        wrong_period = m.group(1)

        if issue.location and wrong_period in issue.location:
            if issue.location in section.content:
                new_snippet = issue.location.replace(wrong_period, fact.period, 1)
                new_content = section.content.replace(issue.location, new_snippet, 1)
                logger.info(
                    "Fixed period mismatch",
                    section=section.section_id,
                    old=wrong_period,
                    new=fact.period,
                )
                return section.model_copy(update={"content": new_content})
        return None
