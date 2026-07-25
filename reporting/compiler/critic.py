"""
批判器（完整版）- 报告编译器第三阶段 3.1.

对编译后的章节做多维度质量检查。第一阶段只做禁止词/数字粗检/引用覆盖的简化版；
第三阶段升级为完整 critic，输出 CritiqueReport 驱动 revision_pass 循环。

检查维度：
- claim_support_rate: 正文中每个有数字的句子，是否在 facts 中有匹配（值相近或 claim_text 关键词命中）
- conflict_detection: 正文数字与 fact 值矛盾（差异 > 20%）
- counterpoint_coverage: 大纲反证点在正文中是否被覆盖
- structure_coherence: 章节结构连贯性（有无导语/小结、字数偏差）
- evidence_sufficiency: 每百字 citation 密度、facts 覆盖
- forbidden_terms: 禁用词（复用第一阶段）
"""

import re
from typing import Optional

from core.contracts import (
    CompiledSection,
    CritiqueCategory,
    CritiqueIssue,
    CritiqueReport,
    CritiqueSeverity,
    FactRecord,
    ReportOutline,
    ValidationResult,
    ValidationResults,
)
from core.observability import get_logger
from core.utils.id_gen import generate_id

logger = get_logger(__name__)

_NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")
_CITATION_PATTERN = re.compile(r"\[\d+\]")
# 引用标记内的数字（如 [f1]/[fact_123]/[1]），不应被视为内容数字
_CITATION_MARKER_PATTERN = re.compile(r"\[[^\]]*?\d+[^\]]*?\]")
# 中文数字匹配（十/百/千/万/亿）
_CN_NUM_PATTERN = re.compile(r"[\d,.]+\s*[万亿千百]?[亿元]?%?百分点?倍?")


class Critic:
    """批判器（完整版）.

    输出 CritiqueReport（含结构化 CritiqueIssue 与修复建议），供 revision_pass 消费。
    同时保持 review() 向后兼容，返回 dict[str, ValidationResults]。
    """

    # 数字冲突阈值：正文数字与 fact 值差异超过此比例视为矛盾
    CONFLICT_RATIO = 0.20
    # claim support 数值容差（相对误差）
    SUPPORT_TOLERANCE = 0.05
    # 字数目标偏差容忍度（超过此比例记为 structure 问题）
    WORD_COUNT_DEVIATION = 0.50
    # 最低引用密度（每百字 citation 条数）
    MIN_CITATION_DENSITY = 0.5
    # 最低事实密度（每百字 fact 覆盖数）
    MIN_FACT_DENSITY = 0.8

    def __init__(self, forbidden_terms: Optional[list[str]] = None):
        self._forbidden_terms = set(forbidden_terms or [])

    # ── 向后兼容接口（第一阶段） ──────────────────────────────────

    def review(
        self,
        sections: list[CompiledSection],
        facts: list[FactRecord],
    ) -> dict[str, ValidationResults]:
        """审查所有章节（第一阶段兼容接口）.

        内部委托给 review_full，再转为旧格式。
        """
        # 构建空大纲（向后兼容：旧调用方不提供 outline）
        empty_outline = ReportOutline(report_title="")
        report = self.review_full(sections, facts, empty_outline)
        return self._to_legacy_results(report, sections)

    # ── 完整批判接口（第三阶段） ──────────────────────────────────

    def review_full(
        self,
        sections: list[CompiledSection],
        facts: list[FactRecord],
        outline: ReportOutline,
    ) -> CritiqueReport:
        """完整批判审查.

        Args:
            sections: 引用绑定后的章节
            facts: 事实表
            outline: 报告大纲（用于 counterpoint_coverage / structure 检查）

        Returns:
            CritiqueReport：结构化问题列表 + 整体严重度 + 指标
        """
        # 预处理事实表为高效查询结构
        facts_by_section: dict[str, list[FactRecord]] = {}
        for section in sections:
            facts_by_section[section.section_id] = [
                f for f in facts if f.fact_id in section.fact_ids
            ]
        # 构建 fact value -> fact 映射，用于冲突检测
        fact_values: dict[float, FactRecord] = {}
        for f in facts:
            if f.value is not None:
                # 保留最近值（同值合并）
                fact_values[f.value] = f

        # 构建反证关键词映射
        outline_sections = {s.section_id: s for s in outline.sections}

        all_issues: list[CritiqueIssue] = []
        section_level_stats: list[dict] = []

        for section in sections:
            section_facts = facts_by_section.get(section.section_id, [])
            outline_sec = outline_sections.get(section.section_id)

            # 1. 禁用词
            all_issues.extend(self._check_forbidden_terms(section))

            # 2. claim support
            all_issues.extend(self._check_claim_support(section, section_facts))

            # 3. conflict detection
            all_issues.extend(self._check_conflicts(section, section_facts, fact_values))

            # 4. counterpoint coverage
            if outline_sec:
                all_issues.extend(self._check_counterpoints(section, outline_sec))

            # 5. structure coherence
            if outline_sec:
                all_issues.extend(self._check_structure(section, outline_sec))

            # 6. evidence sufficiency
            all_issues.extend(self._check_evidence_sufficiency(section, section_facts))

            section_level_stats.append(
                {
                    "section_id": section.section_id,
                    "word_count": len(section.content),
                    "citation_count": len(section.citations),
                    "fact_count": len(section_facts),
                }
            )

        # 计算汇总指标
        metrics = self._compute_metrics(sections, facts, all_issues, section_level_stats)

        # 决定整体严重度
        overall = self._determine_severity(all_issues)
        suggestions = self._build_suggestions(all_issues, metrics)

        logger.info(
            "Critic review_full complete",
            issues=len(all_issues),
            severity=overall.value,
            support_rate=metrics.get("claim_support_rate", 0),
        )
        return CritiqueReport(
            report_id="critic_" + generate_id(),
            overall_severity=overall,
            issues=all_issues,
            revision_suggestions=suggestions,
            metrics=metrics,
        )

    # ── 各维度检查 ───────────────────────────────────────────────

    def _check_forbidden_terms(self, section: CompiledSection) -> list[CritiqueIssue]:
        """禁用词检查."""
        issues: list[CritiqueIssue] = []
        for term in self._forbidden_terms:
            if term in section.content:
                # 找出现位置
                idx = section.content.index(term)
                snippet = section.content[max(0, idx - 20) : idx + len(term) + 20]
                issues.append(
                    CritiqueIssue(
                        issue_id=generate_id(),
                        category=CritiqueCategory.FORBIDDEN_TERM,
                        severity="error",
                        section_id=section.section_id,
                        description=f"正文包含禁用词「{term}」",
                        location=snippet,
                        suggested_fix=f"删除或替换「{term}」",
                    )
                )
        return issues

    def _check_claim_support(
        self, section: CompiledSection, section_facts: list[FactRecord]
    ) -> list[CritiqueIssue]:
        """claim support rate 检查：正文中的每个数字是否在 facts 中有匹配.

        逐数字检查：数值型 fact（有 value）按值容差匹配；
        非数值型 fact（event/spec/risk/guidance）按文本重叠匹配。
        """
        issues: list[CritiqueIssue] = []
        sentences = self._split_sentences(section.content)
        # 分组：有值的 fact 做数值匹配，无值的 fact 做文本匹配
        valued_facts = [f for f in section_facts if f.value is not None and f.value != 0]
        non_valued_texts = {f.claim_text.lower() for f in section_facts if f.value is None}

        for sent in sentences:
            # 剔除引用标记（如 [f1]/[1]），避免其中的数字被误提取
            clean_sent = _CITATION_MARKER_PATTERN.sub("", sent)
            # 预存每个数字在句中的位置（基于清洗后的句子）
            num_positions: list[tuple[float, int]] = []
            for m in re.finditer(_NUMBER_PATTERN, clean_sent):
                val = float(m.group())
                if not (len(m.group()) == 4 and 1990 <= int(val) <= 2099):
                    num_positions.append((val, m.start()))
            if not num_positions:
                continue

            sent_lower = sent.lower()
            for n, n_pos in num_positions:
                # 1. 数值型 fact：按值容差匹配
                if any(
                    f.value is not None
                    and abs(n - f.value) / max(abs(f.value), 1e-6) < self.SUPPORT_TOLERANCE
                    for f in valued_facts
                ):
                    continue

                # 2. 非数值型 fact：文本关键词重叠匹配（数字周围 ±15 窗口）
                if non_valued_texts:
                    window_start = max(0, n_pos - 15)
                    window_end = min(len(sent), n_pos + 15)
                    window = sent_lower[window_start:window_end]
                    if any(self._text_overlap(window, ft) for ft in non_valued_texts):
                        continue

                # 该数字无支撑
                issues.append(
                    CritiqueIssue(
                        issue_id=generate_id(),
                        category=CritiqueCategory.CLAIM_SUPPORT,
                        severity="warning",
                        section_id=section.section_id,
                        description=f"句子中的数字 {n} 缺少事实支撑",
                        location=sent[:150],
                        suggested_fix="为此句添加引用标记 [fact_id]，或确认该数字可追溯至事实表",
                    )
                )
                break  # 每句至多一个 issue 足够
        return issues

    def _check_conflicts(
        self,
        section: CompiledSection,
        section_facts: list[FactRecord],
        all_fact_values: dict[float, FactRecord],
    ) -> list[CritiqueIssue]:
        """冲突检测：正文数字与 fact 值矛盾.

        对每个含数字的句子，在 section_facts（以及全局 facts）中找关联值。
        若差异 > CONFLICT_RATIO，标记为 CONFLICT。
        """
        issues: list[CritiqueIssue] = []
        sentences = self._split_sentences(section.content)

        # 优先用本节 facts，不足时用全局
        local_values = {f.value: f for f in section_facts if f.value is not None}
        combined = {**all_fact_values, **local_values}  # 局部覆盖全局

        for sent in sentences:
            # 剔除引用标记中的数字干扰
            clean_sent = _CITATION_MARKER_PATTERN.sub("", sent)
            numbers = _NUMBER_PATTERN.findall(clean_sent)
            meaningful = [
                float(n) for n in numbers if not (len(n) == 4 and 1990 <= int(float(n)) <= 2099)
            ]
            if not meaningful:
                continue

            for n in meaningful:
                # 找最近似的事实值（同量级优先）
                candidates = [
                    (abs(n - fv), fv, fact)
                    for fv, fact in combined.items()
                    if fv != 0 and abs(n - fv) / fv < self.CONFLICT_RATIO * 3
                ]
                if not candidates:
                    continue
                candidates.sort()
                _dist, best_val, best_fact = candidates[0]

                # 若差异超过阈值 → 矛盾
                if best_val != 0 and abs(n - best_val) / best_val > self.CONFLICT_RATIO:
                    pct = (n - best_val) / best_val * 100
                    direction = "高于" if n > best_val else "低于"
                    issues.append(
                        CritiqueIssue(
                            issue_id=generate_id(),
                            category=CritiqueCategory.CONFLICT,
                            severity="error",
                            section_id=section.section_id,
                            description=(
                                f"数字矛盾：正文 {n} {direction} " f"事实表 {best_val}（偏差 {abs(pct):.0f}%）"
                            ),
                            location=sent[:150],
                            conflicting_fact_id=best_fact.fact_id,
                            suggested_fix=f"将正文中的 {n} 替换为事实表值 {best_val}",
                        )
                    )
        return issues

    def _check_counterpoints(self, section: CompiledSection, outline_sec) -> list[CritiqueIssue]:
        """反证覆盖检查：大纲中列出的 counterpoints 是否在正文中有回应."""
        issues: list[CritiqueIssue] = []
        content_lower = section.content.lower()
        for cp in outline_sec.counterpoints:
            if not cp:
                continue
            # 提取反证的关键词（前 3 个非停用词）
            keywords = [w for w in cp.lower().split() if len(w) > 2][:3]
            if not keywords:
                continue
            # 至少一个关键词在正文中出现
            covered = any(kw in content_lower for kw in keywords)
            if not covered:
                issues.append(
                    CritiqueIssue(
                        issue_id=generate_id(),
                        category=CritiqueCategory.COUNTERPOINT,
                        severity="warning",
                        section_id=section.section_id,
                        description=f"反证点未覆盖：「{cp}」",
                        location="",
                        suggested_fix=f"在正文中加入对「{cp}」的讨论（至少提及风险或不同观点）",
                    )
                )
        return issues

    def _check_structure(self, section: CompiledSection, outline_sec) -> list[CritiqueIssue]:
        """结构连贯性检查."""
        issues: list[CritiqueIssue] = []
        content = section.content
        word_count = len(content) if content else 0
        target = getattr(outline_sec, "target_words", 500) or 500

        # 1. 字数偏差
        if target > 0 and word_count > 0:
            deviation = abs(word_count - target) / target
            if deviation > self.WORD_COUNT_DEVIATION:
                direction = "超出" if word_count > target else "不足"
                issues.append(
                    CritiqueIssue(
                        issue_id=generate_id(),
                        category=CritiqueCategory.STRUCTURE,
                        severity="warning",
                        section_id=section.section_id,
                        description=(
                            f"字数{direction}目标（实际 {word_count} vs 目标 {target}，"
                            f"偏差 {deviation:.0%}）"
                        ),
                        location="",
                        suggested_fix=("压缩内容至目标字数内" if word_count > target else "补充内容达到目标字数"),
                    )
                )

        # 2. must_answer 覆盖
        for question in outline_sec.must_answer:
            if not question:
                continue
            q_words = [w for w in question.lower().split() if len(w) > 2][:3]
            if q_words and not any(kw in content.lower() for kw in q_words):
                issues.append(
                    CritiqueIssue(
                        issue_id=generate_id(),
                        category=CritiqueCategory.STRUCTURE,
                        severity="warning",
                        section_id=section.section_id,
                        description=f"must_answer 问题可能未被回答：「{question}」",
                        location="",
                        suggested_fix=f"确保正文回答「{question}」",
                    )
                )

        return issues

    def _check_evidence_sufficiency(
        self, section: CompiledSection, section_facts: list[FactRecord]
    ) -> list[CritiqueIssue]:
        """证据充足性检查."""
        issues: list[CritiqueIssue] = []
        word_count = max(len(section.content), 1)
        citation_count = len(section.citations)

        # 1. 引用密度
        density = citation_count / (word_count / 100)
        if density < self.MIN_CITATION_DENSITY:
            issues.append(
                CritiqueIssue(
                    issue_id=generate_id(),
                    category=CritiqueCategory.EVIDENCE_SUFFICIENCY,
                    severity="warning",
                    section_id=section.section_id,
                    description=(
                        f"引用密度不足（{density:.1f} 条/百字 < " f"{self.MIN_CITATION_DENSITY} 条/百字）"
                    ),
                    location="",
                    suggested_fix="为更多声明添加 [fact_id] 引用标记",
                )
            )

        # 2. 事实覆盖
        fact_density = len(section_facts) / (word_count / 100)
        if fact_density < self.MIN_FACT_DENSITY:
            issues.append(
                CritiqueIssue(
                    issue_id=generate_id(),
                    category=CritiqueCategory.EVIDENCE_SUFFICIENCY,
                    severity="info",
                    section_id=section.section_id,
                    description=(
                        f"事实覆盖不足（{fact_density:.1f} 条/百字 < " f"{self.MIN_FACT_DENSITY} 条/百字）"
                    ),
                    location="",
                    suggested_fix="增加事实记录以支撑本节内容",
                )
            )

        return issues

    # ── 汇总指标 ─────────────────────────────────────────────────

    def _compute_metrics(
        self,
        sections: list[CompiledSection],
        facts: list[FactRecord],
        issues: list[CritiqueIssue],
        stats: list[dict],
    ) -> dict:
        """计算 Critic 汇总指标."""
        total_words = sum(len(s.content) for s in sections)
        total_citations = sum(len(s.citations) for s in sections)
        total_facts = len(facts)

        claim_support_issues = len(
            [i for i in issues if i.category == CritiqueCategory.CLAIM_SUPPORT]
        )
        conflict_issues = len([i for i in issues if i.category == CritiqueCategory.CONFLICT])
        counterpoint_issues = len(
            [i for i in issues if i.category == CritiqueCategory.COUNTERPOINT]
        )
        structure_issues = len([i for i in issues if i.category == CritiqueCategory.STRUCTURE])
        evidence_issues = len(
            [i for i in issues if i.category == CritiqueCategory.EVIDENCE_SUFFICIENCY]
        )
        forbidden_issues = len([i for i in issues if i.category == CritiqueCategory.FORBIDDEN_TERM])

        # claim_support_rate = 1 - (unsupported 句子数 / 总含数字句子数)
        total_number_sentences = sum(
            sum(
                1
                for raw_s in self._split_sentences(sec.content)
                if _NUMBER_PATTERN.search(_CITATION_MARKER_PATTERN.sub("", raw_s))
            )
            for sec in sections
        )
        support_rate = (
            1.0 - claim_support_issues / max(total_number_sentences, 1)
            if total_number_sentences > 0
            else 1.0
        )

        return {
            "total_words": total_words,
            "total_citations": total_citations,
            "total_facts": total_facts,
            "total_issues": len(issues),
            "claim_support_rate": round(support_rate, 3),
            "conflict_count": conflict_issues,
            "counterpoint_gaps": counterpoint_issues,
            "structure_warnings": structure_issues,
            "evidence_warnings": evidence_issues,
            "forbidden_term_hits": forbidden_issues,
            "citation_density": round(total_citations / max(total_words / 100, 1), 2),
            "fact_density": round(total_facts / max(total_words / 100, 1), 2),
        }

    # ── 严重度判定 ───────────────────────────────────────────────

    def _determine_severity(self, issues: list[CritiqueIssue]) -> CritiqueSeverity:
        """根据 issue 集合判定整体严重度."""
        errors = [i for i in issues if i.severity == "error"]
        warnings = [i for i in issues if i.severity == "warning"]
        if not issues:
            return CritiqueSeverity.PASS
        if not errors and len(warnings) <= 2:
            return CritiqueSeverity.MINOR
        if len(errors) <= 2 and len(warnings) <= 5:
            return CritiqueSeverity.MAJOR
        return CritiqueSeverity.CRITICAL

    def _build_suggestions(self, issues: list[CritiqueIssue], metrics: dict) -> list[str]:
        """生成高层修复建议."""
        suggestions: list[str] = []
        if metrics.get("conflict_count", 0) > 0:
            suggestions.append(f"{metrics['conflict_count']} 处数字矛盾需要修正")
        if metrics.get("claim_support_rate", 1.0) < 0.80:
            suggestions.append(f"声明支撑率 {metrics['claim_support_rate']:.0%} 偏低，" "需为更多声明添加引用")
        if metrics.get("counterpoint_gaps", 0) > 0:
            suggestions.append(f"{metrics['counterpoint_gaps']} 个反证点未被覆盖，建议补充风险视角")
        if metrics.get("citation_density", 0) < self.MIN_CITATION_DENSITY:
            suggestions.append("引用密度不足，建议为关键声明增加引用")
        if not suggestions:
            suggestions.append("报告质量良好，无需修订")
        return suggestions

    # ── 辅助方法 ─────────────────────────────────────────────────

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """简易中文分句：按 。！？; ！? \n 切分."""
        if not text:
            return []
        # 保护小数点与引用标记不被误切
        parts = re.split(r"[。！？!?\n]+", text)
        return [p.strip() for p in parts if p.strip() and len(p.strip()) > 3]

    @staticmethod
    def _text_overlap(text1: str, text2: str) -> bool:
        """判断两段文本是否有足够的关键词重叠（中英文自适应）.

        - 英文（含空格）：至少 2 个共同非短单词
        - 中文（无空格）：至少 2 个共同字符二元组
        """
        has_spaces = " " in text1 or " " in text2
        if has_spaces:
            words1 = {w for w in text1.split() if len(w) > 1}
            words2 = {w for w in text2.split() if len(w) > 1}
            return len(words1 & words2) >= 2
        else:
            # 中文：字符二元组（bigram）重叠
            bigrams1 = {text1[i : i + 2] for i in range(len(text1) - 1)}
            bigrams2 = {text2[i : i + 2] for i in range(len(text2) - 1)}
            return len(bigrams1 & bigrams2) >= 2

    def _to_legacy_results(
        self, report: CritiqueReport, sections: list[CompiledSection]
    ) -> dict[str, ValidationResults]:
        """CritiqueReport → dict[str, ValidationResults]（向后兼容）."""
        issues_by_section: dict[str, list[CritiqueIssue]] = {}
        for issue in report.issues:
            issues_by_section.setdefault(issue.section_id, []).append(issue)

        legacy: dict[str, ValidationResults] = {}
        for section in sections:
            sec_issues = issues_by_section.get(section.section_id, [])
            results: list[ValidationResult] = []
            for cat in CritiqueCategory:
                cat_issues = [i for i in sec_issues if i.category == cat]
                if cat_issues:
                    results.append(
                        ValidationResult(
                            check_name=cat.value,
                            passed=all(i.severity != "error" for i in cat_issues),
                            message=f"{len(cat_issues)} 个 {cat.value} 问题",
                            severity=(
                                "error"
                                if any(i.severity == "error" for i in cat_issues)
                                else "warning"
                            ),
                        )
                    )
            if not results:
                results.append(
                    ValidationResult(
                        check_name="all",
                        passed=True,
                        message="全部检查通过",
                        severity="info",
                    )
                )
            legacy[section.section_id] = ValidationResults(
                overall_passed=all(r.passed for r in results),
                results=results,
                word_count=len(section.content),
            )
        return legacy
