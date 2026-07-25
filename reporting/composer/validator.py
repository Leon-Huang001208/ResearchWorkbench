"""
报告校验器 - 验证生成内容的质量和合规性.

Report validator checks quality and compliance of generated content.
"""

from typing import List, Optional, Set

from core.contracts import FactCard, SectionSpec, ValidationResult, ValidationResults
from core.interfaces import ModelGateway
from core.observability import get_logger

logger = get_logger(__name__)


class ReportValidator:
    """报告校验器.

    Validates generated report content for quality, compliance,
    and adherence to requirements. Performs multiple checks:
    - Word count validation
    - Forbidden term detection
    - Source traceability
    - Objectivity checks
    - Fact consistency check (optional, requires LLM)
    """

    def __init__(self, model_gateway: Optional[ModelGateway] = None):
        """初始化校验器.

        Args:
            model_gateway: Optional model gateway for LLM-based checks (fact consistency).
        """
        self._default_forbidden_terms: Set[str] = set()
        self._model_gateway = model_gateway

    def set_default_forbidden_terms(self, terms: List[str]):
        """设置默认禁用词列表.

        Args:
            terms: List of forbidden terms.
        """
        self._default_forbidden_terms = set(terms)
        logger.info(f"Set {len(terms)} default forbidden terms")

    def validate_section(
        self,
        content: str,
        spec: SectionSpec,
        evidence_refs: Optional[List[str]] = None,
        fact_card: Optional[FactCard] = None,
        evidence_content: Optional[List[str]] = None,
    ) -> ValidationResults:
        """校验单个段落.

        Args:
            content: Generated section content.
            spec: Section specification.
            evidence_refs: List of evidence references used.
            fact_card: Optional fact card used for generation (for fact consistency check).
            evidence_content: Optional raw evidence content (for fact consistency check).

        Returns:
            Validation results.
        """
        logger.info(f"Validating section: {spec.key}")

        results: List[ValidationResult] = []

        # Word count check
        word_count = self._count_words(content)
        results.append(self._check_word_count(word_count, spec.target_words))

        # Forbidden terms check
        forbidden_terms = set(spec.forbidden_terms) | self._default_forbidden_terms
        results.append(self._check_forbidden_terms(content, forbidden_terms))

        # Source traceability check
        if spec.evidence_policy == "strict":
            results.append(self._check_source_traceability(content, evidence_refs))

        # Objectivity check
        results.append(self._check_objectivity(content))

        # Required facets check
        if spec.required_facets:
            results.append(self._check_required_facets(content, spec.required_facets))

        # Fact consistency check (if LLM available and evidence provided)
        if self._model_gateway and fact_card and evidence_content:
            results.append(self._check_fact_consistency(content, fact_card, evidence_content))

        overall_passed = all(r.passed for r in results if r.severity == "error")

        validation_results = ValidationResults(
            overall_passed=overall_passed,
            results=results,
            word_count=word_count,
        )

        logger.info(
            f"Section validation complete: {spec.key}, "
            f"passed={overall_passed}, checks={len(results)}"
        )
        return validation_results

    def _count_words(self, content: str) -> int:
        """计算词数.

        Args:
            content: Text content.

        Returns:
            Word count (Chinese characters count as words).
        """
        import re

        # Count Chinese characters
        chinese_chars = len(re.findall(r"[一-鿿]", content))

        # Count English words
        english_words = len(re.findall(r"\b[a-zA-Z]+\b", content))

        return chinese_chars + english_words

    def _check_word_count(self, word_count: int, target_words: int) -> ValidationResult:
        """检查词数.

        Args:
            word_count: Actual word count.
            target_words: Target word count.

        Returns:
            Validation result.
        """
        tolerance = 0.3  # 30% tolerance
        min_words = int(target_words * (1 - tolerance))
        max_words = int(target_words * (1 + tolerance))

        if min_words <= word_count <= max_words:
            return ValidationResult(
                check_name="word_count",
                passed=True,
                message=f"Word count: {word_count} (target: {target_words})",
                severity="info",
            )
        else:
            return ValidationResult(
                check_name="word_count",
                passed=False,
                message=f"Word count {word_count} outside target range [{min_words}, {max_words}]",
                severity="warning",
            )

    def _check_forbidden_terms(
        self,
        content: str,
        forbidden_terms: Set[str],
    ) -> ValidationResult:
        """检查禁用词.

        Args:
            content: Text content.
            forbidden_terms: Set of forbidden terms.

        Returns:
            Validation result.
        """
        found_terms = []
        content_lower = content.lower()

        for term in forbidden_terms:
            if term.lower() in content_lower:
                found_terms.append(term)

        if found_terms:
            return ValidationResult(
                check_name="forbidden_terms",
                passed=False,
                message=f"Found forbidden terms: {', '.join(found_terms)}",
                severity="error",
            )
        else:
            return ValidationResult(
                check_name="forbidden_terms",
                passed=True,
                message="No forbidden terms found",
                severity="info",
            )

    def _check_source_traceability(
        self,
        content: str,
        evidence_refs: Optional[List[str]],
    ) -> ValidationResult:
        """检查来源可追溯性.

        Args:
            content: Text content.
            evidence_refs: List of evidence references.

        Returns:
            Validation result.
        """
        import re

        citations = re.findall(r"\[(\d+)\]", content)

        if citations:
            return ValidationResult(
                check_name="source_traceability",
                passed=True,
                message=f"Found {len(citations)} citations: {', '.join(citations)}",
                severity="info",
            )
        else:
            return ValidationResult(
                check_name="source_traceability",
                passed=False,
                message="No source citations found in strict mode",
                severity="warning",
            )

    def _check_objectivity(self, content: str) -> ValidationResult:
        """检查客观性.

        Checks for overly subjective language.

        Args:
            content: Text content.

        Returns:
            Validation result.
        """
        subjective_terms = [
            "我认为",
            "我觉得",
            "在我看来",
            "我相信",
            "毫无疑问",
            "绝对",
            "肯定",
            "必然",
            "一定",
            "最",
            "非常",
            "I think",
            "I believe",
            "in my opinion",
            "definitely",
            "absolutely",
            "certainly",
            "must",
        ]

        found_subjective = []
        content_lower = content.lower()

        for term in subjective_terms:
            if term.lower() in content_lower:
                found_subjective.append(term)

        if len(found_subjective) <= 2:
            return ValidationResult(
                check_name="objectivity",
                passed=True,
                message="Content appears objective",
                severity="info",
            )
        else:
            return ValidationResult(
                check_name="objectivity",
                passed=False,
                message=f"Found potentially subjective terms: {', '.join(found_subjective[:5])}",
                severity="warning",
            )

    def _check_required_facets(
        self,
        content: str,
        required_facets: List[str],
    ) -> ValidationResult:
        """检查必填方面是否覆盖.

        Args:
            content: Text content.
            required_facets: List of required facets.

        Returns:
            Validation result.
        """
        content_lower = content.lower()
        missing_facets = []

        for facet in required_facets:
            if facet.lower() not in content_lower:
                # Check for partial matches
                found = False
                words = facet.lower().split()
                if len(words) > 1:
                    found = any(word in content_lower for word in words)
                if not found:
                    missing_facets.append(facet)

        if missing_facets:
            return ValidationResult(
                check_name="required_facets",
                passed=False,
                message=f"Missing facets: {', '.join(missing_facets)}",
                severity="warning",
            )
        else:
            return ValidationResult(
                check_name="required_facets",
                passed=True,
                message="All required facets covered",
                severity="info",
            )

    def _check_fact_consistency(
        self,
        content: str,
        fact_card: FactCard,
        evidence_content: List[str],
    ) -> ValidationResult:
        """检查事实一致性，确保内容完全基于提供的证据，没有编造信息.

        Args:
            content: Generated section content.
            fact_card: Fact card used for generation.
            evidence_content: List of raw evidence content.

        Returns:
            Validation result.
        """
        logger.info("Performing fact consistency check")
        model_gateway = self._model_gateway
        if model_gateway is None:
            return ValidationResult(
                check_name="fact_consistency",
                passed=True,
                message="Skipped fact consistency check: model gateway unavailable",
                severity="info",
            )

        try:
            # Build prompt for LLM
            facts = []
            if fact_card.key_changes:
                facts.extend([f"- 关键变化: {c}" for c in fact_card.key_changes])
            if fact_card.drivers:
                facts.extend([f"- 驱动因素: {d}" for d in fact_card.drivers])
            if fact_card.impacts:
                facts.extend([f"- 影响分析: {i}" for i in fact_card.impacts])
            if fact_card.risks:
                facts.extend([f"- 风险提示: {r}" for r in fact_card.risks])
            if fact_card.watch_points:
                facts.extend([f"- 观察重点: {w}" for w in fact_card.watch_points])

            evidence_parts = [f"证据{i+1}:\n{content}" for i, content in enumerate(evidence_content)]

            facts_text = "\n".join(facts)
            evidence_text = "\n\n".join(evidence_parts)

            prompt = f"""
你是一个事实核查员，请检查下面的报告内容是否完全基于提供的事实和证据，有没有编造、夸大或超出证据范围的信息。

# 报告内容：
{content}

# 提取的事实：
{facts_text}

# 原始证据：
{evidence_text}

# 检查要求：
1. 只报告内容是否完全基于事实和证据，没有编造
2. 如果发现不一致的地方，请具体指出
3. 输出格式：
首先回答"PASSED"或"FAILED"，然后换行说明原因。

示例：
FAILED
报告中提到"行业增长率达到20%"，但证据中只提到增长率为10%。
"""

            # Call LLM
            response = model_gateway.chat(
                messages=[{"role": "user", "content": prompt}],
                model="default",
                temperature=0.1,  # Low temperature for consistency
            )

            response_text = response.content.strip()

            if response_text.startswith("PASSED"):
                return ValidationResult(
                    check_name="fact_consistency",
                    passed=True,
                    message="Fact consistency check passed",
                    severity="info",
                )
            else:
                # Extract reason
                lines = response_text.split("\n", 1)
                reason = lines[1] if len(lines) > 1 else "Unknown inconsistency found"
                return ValidationResult(
                    check_name="fact_consistency",
                    passed=False,
                    message=f"Fact consistency check failed: {reason}",
                    severity="error",
                )

        except Exception as e:
            logger.error(f"Fact consistency check failed: {e}", exc_info=True)
            return ValidationResult(
                check_name="fact_consistency",
                passed=False,
                message=f"Fact consistency check error: {str(e)}",
                severity="warning",
            )

    def quick_check(self, content: str) -> bool:
        """快速检查内容是否基本合格.

        Args:
            content: Text content.

        Returns:
            True if content passes quick checks.
        """
        if not content or len(content.strip()) < 10:
            return False

        # Check for obvious garbage
        if len(set(content)) < 3:  # Too few unique characters
            return False

        return True
