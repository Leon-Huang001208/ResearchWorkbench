"""
声明抽取器 - 报告编译器第三阶段 3.3.

从 CompiledReport 的每个 CompiledSection 中拆解原子性声明（AtomicClaim）。
优先使用 model_gateway.structured_output（LLM），失败或无 gateway 时回退到
规则抽取（句子拆分 + 数值检测 + fact 匹配）。

模式与 FactExtractor 一致：私有 _ClaimItem / _ClaimExtractionResult schema
用于 structured_output，对外输出 AtomicClaim 列表。
"""

import re

from core.contracts import (
    AtomicClaim,
    ClaimType,
    CompiledReport,
    CompiledSection,
    FactRecord,
    VerificationStatus,
)
from core.contracts.compiler import _ClaimExtractionResult, _ClaimItem
from core.observability import get_logger
from core.utils.id_gen import generate_id

logger = get_logger(__name__)

# 句子拆分（中英文）
_SENTENCE_SPLIT = re.compile(r"[。！？!?\n]+")
# 数字检测
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
# 引用标记清理
_CITATION_MARKER = re.compile(r"\[[^\]]*?\d+[^\]]*?\]")
# 最小句子长度
_MIN_SENTENCE_LEN = 5


class ClaimExtractor:
    """声明抽取器.

    从报告章节中抽取可独立验证的原子声明。支持 LLM 抽取与规则回退两条路径。
    """

    def __init__(self, model_gateway=None):
        """初始化.

        Args:
            model_gateway: 可选的 ModelGateway，用于 structured_output 抽取
        """
        self.model_gateway = model_gateway

    def extract_from_report(self, report: CompiledReport) -> list[AtomicClaim]:
        """从完整报告中抽取声明.

        Args:
            report: 编译后的报告

        Returns:
            list[AtomicClaim]: 所有章节的声明汇总
        """
        all_claims: list[AtomicClaim] = []
        for section in report.sections:
            claims = self.extract_from_section(section, report.facts)
            all_claims.extend(claims)

        logger.info(
            "Claim extraction complete",
            sections=len(report.sections),
            claims=len(all_claims),
        )
        return all_claims

    def extract_from_section(
        self,
        section: CompiledSection,
        facts: list[FactRecord],
    ) -> list[AtomicClaim]:
        """从单个章节抽取声明.

        Args:
            section: 编译后的章节
            facts: 全局事实表（用于交叉验证）

        Returns:
            list[AtomicClaim]: 该章节的声明列表
        """
        content = section.content
        if not content or not content.strip():
            return []

        # 尝试 LLM 抽取
        if self.model_gateway is not None:
            try:
                return self._extract_structured(content, section.section_id, facts)
            except Exception as e:
                logger.warning(
                    "LLM claim extraction failed, falling back to rule-based",
                    section_id=section.section_id,
                    error=str(e),
                )

        # 规则回退
        return self._extract_rule_based(content, section.section_id, facts)

    # ── LLM 路径 ────────────────────────────────────────────────────────

    def _extract_structured(
        self,
        content: str,
        section_id: str,
        facts: list[FactRecord],
    ) -> list[AtomicClaim]:
        """通过 structured_output 抽取声明."""
        clean = _CITATION_MARKER.sub("", content)
        messages = [
            {
                "role": "system",
                "content": (
                    "你是声明分解器。将段落拆分为原子性声明。"
                    "每条声明应是一个可独立验证的断言。"
                    "只输出 JSON：claims 列表，每条含 claim_text/claim_type/confidence。"
                    "claim_type 取值：metric(数值)/event(事件)/spec(规格)/guidance(指引)/risk(风险)。"
                ),
            },
            {"role": "user", "content": clean[:4000]},
        ]
        result = self.model_gateway.structured_output(
            messages=messages,
            output_schema=_ClaimExtractionResult,
            temperature=0.1,
        )
        claims: list[AtomicClaim] = []
        for i, item in enumerate(result.claims):
            if not item.claim_text:
                continue
            claim = self._to_atomic_claim(item, section_id, i, facts)
            claims.append(claim)
        return claims

    # ── 规则回退路径 ─────────────────────────────────────────────────────

    def _extract_rule_based(
        self,
        content: str,
        section_id: str,
        facts: list[FactRecord],
    ) -> list[AtomicClaim]:
        """规则抽取：句子拆分 → 数值检测 → fact 匹配."""
        clean = _CITATION_MARKER.sub("", content)
        sentences = _SENTENCE_SPLIT.split(clean)
        claims: list[AtomicClaim] = []
        claim_idx = 0
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < _MIN_SENTENCE_LEN:
                continue

            claim_type = self._guess_claim_type(sentence)
            claim = AtomicClaim(
                claim_id=generate_id(prefix="aclaim"),
                claim_text=sentence[:200],
                section_id=section_id,
                claim_type=claim_type,
                fact_ids=[],
                verification=VerificationStatus.UNVERIFIABLE,
                confidence=0.4,  # 规则抽取置信度低
            )

            # 尝试匹配 fact
            self._resolve_claim_verification(claim, facts)
            claims.append(claim)
            claim_idx += 1

        return claims

    # ── Claim → AtomicClaim 转换 ────────────────────────────────────────

    def _to_atomic_claim(
        self,
        item: _ClaimItem,
        section_id: str,
        index: int,
        facts: list[FactRecord],
    ) -> AtomicClaim:
        """把 LLM 输出转为 AtomicClaim."""
        claim_type = self._parse_claim_type(item.claim_type)
        claim = AtomicClaim(
            claim_id=generate_id(prefix="aclaim"),
            claim_text=item.claim_text,
            section_id=section_id,
            claim_type=claim_type,
            fact_ids=[],
            verification=VerificationStatus.UNVERIFIABLE,
            confidence=item.confidence,
        )
        # 交叉验证
        self._resolve_claim_verification(claim, facts)
        return claim

    # ── 交叉验证 ─────────────────────────────────────────────────────────

    def _resolve_claim_verification(
        self,
        claim: AtomicClaim,
        facts: list[FactRecord],
    ) -> None:
        """将声明与 fact 表交叉验证，设置 verification 状态与 fact_ids."""
        best_fact: FactRecord | None = None
        best_score = 0.0

        for fact in facts:
            score = self._match_score(claim.claim_text, fact)
            if score > best_score:
                best_score = score
                best_fact = fact

        if best_fact is None or best_score < 0.3:
            claim.verification = VerificationStatus.UNVERIFIABLE
            return

        claim.fact_ids = [best_fact.fact_id]

        # 有数值的 fact 做数值匹配
        if best_fact.value is not None:
            numbers = _NUMBER_RE.findall(claim.claim_text)
            matched = False
            for n_str in numbers:
                try:
                    n = float(n_str)
                except ValueError:
                    continue
                if abs(n - best_fact.value) / max(abs(best_fact.value), 1e-6) < 0.05:
                    matched = True
                    break
            if matched:
                claim.verification = VerificationStatus.VERIFIED
            else:
                claim.verification = VerificationStatus.CONTRADICTED
        else:
            # 无数值 fact：文本匹配即 VERIFIED
            if best_score >= 0.5:
                claim.verification = VerificationStatus.VERIFIED
            else:
                claim.verification = VerificationStatus.UNVERIFIABLE

    # ── 匹配工具 ─────────────────────────────────────────────────────────

    @staticmethod
    def _match_score(claim_text: str, fact: FactRecord) -> float:
        """计算声明与 fact 的匹配分数（0.0-1.0）."""
        score = 0.0

        # 文本重叠
        if _text_overlap(claim_text, fact.claim_text):
            score += 0.4

        # 数值匹配
        if fact.value is not None:
            numbers = _NUMBER_RE.findall(claim_text)
            for n_str in numbers:
                try:
                    n = float(n_str)
                except ValueError:
                    continue
                if abs(n - fact.value) / max(abs(fact.value), 1e-6) < 0.05:
                    score += 0.6
                    break

        return min(1.0, score)

    @staticmethod
    def _guess_claim_type(text: str) -> ClaimType:
        """启发式推测声明类型."""
        if any(kw in text for kw in ("风险", "不确定", "可能", "下行")):
            return ClaimType.RISK
        if any(kw in text for kw in ("指引", "展望", "预计", "目标", "guidance")):
            return ClaimType.GUIDANCE
        if any(kw in text for kw in ("规格", "速率", "功耗", "尺寸", "Gbps", "nm")):
            return ClaimType.SPEC
        if any(kw in text for kw in ("订单", "投产", "发布", "收购", "合作", "人事")):
            return ClaimType.EVENT
        return ClaimType.METRIC

    @staticmethod
    def _parse_claim_type(raw: str) -> ClaimType:
        """把 LLM 输出的字符串转为 ClaimType."""
        raw_lower = raw.lower().strip()
        mapping = {
            "metric": ClaimType.METRIC,
            "event": ClaimType.EVENT,
            "spec": ClaimType.SPEC,
            "guidance": ClaimType.GUIDANCE,
            "risk": ClaimType.RISK,
        }
        return mapping.get(raw_lower, ClaimType.METRIC)


def _text_overlap(text1: str, text2: str) -> bool:
    """判断两段文本是否有足够的关键词重叠（与 critic.py/citation_verifier.py 一致）."""
    has_spaces = " " in text1 or " " in text2
    if has_spaces:
        words1 = {w for w in text1.split() if len(w) > 1}
        words2 = {w for w in text2.split() if len(w) > 1}
        return len(words1 & words2) >= 2
    else:
        bigrams1 = {text1[i : i + 2] for i in range(len(text1) - 1)}
        bigrams2 = {text2[i : i + 2] for i in range(len(text2) - 1)}
        return len(bigrams1 & bigrams2) >= 2
