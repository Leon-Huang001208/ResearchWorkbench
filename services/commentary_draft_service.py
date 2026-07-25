"""Generate editable market commentary drafts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from core.contracts.commentary import (
    CommentaryDraftRequest,
    CommentaryDraftResponse,
    CommentaryQualityCheckResponse,
    CommentaryQualityIssue,
    CommentaryRecipe,
    CommentaryRecipeCatalog,
    CommentarySectionRewriteResponse,
)
from core.interfaces import ModelGateway
from core.observability import get_logger

logger = get_logger(__name__)


COMMENTARY_RECIPES: list[CommentaryRecipe] = [
    CommentaryRecipe(
        id="daily-close",
        title="每日收盘点评",
        tag="市场点评",
        tone="克制、归因清晰、适合收盘后发布",
        sections=["今日市场表现", "行业与风格变化", "资金与情绪", "核心归因", "后续观察"],
    ),
    CommentaryRecipe(
        id="market-drawdown",
        title="市场大跌归因",
        tag="异动复盘",
        tone="先解释冲击，再判断是否改变中期逻辑",
        sections=["发生了什么", "主要拖累方向", "直接触发因素", "深层原因判断", "明日观察变量"],
    ),
    CommentaryRecipe(
        id="sector-review",
        title="行业板块点评",
        tag="行业观点",
        tone="研究员口径，强调景气、估值、催化和配置含义",
        sections=["核心观点", "行情表现", "景气度证据", "估值与预期差", "配置建议与风险"],
    ),
    CommentaryRecipe(
        id="theme-event",
        title="主题事件点评",
        tag="主题研究",
        tone="围绕事件传导链和受益方向展开",
        sections=["事件概述", "产业链传导", "受益与受损方向", "市场分歧", "跟踪指标"],
    ),
    CommentaryRecipe(
        id="global-shock",
        title="海外扰动点评",
        tag="全球映射",
        tone="区分海外事实、A股映射和情绪外溢",
        sections=["海外市场表现", "触发因素", "跨市场传导", "A股映射方向", "风险边界"],
    ),
    CommentaryRecipe(
        id="etf-allocation",
        title="产品/ETF配置点评",
        tag="产品转化",
        tone="观点先行，产品承接，风险提示完整",
        sections=["配置结论", "板块表现", "基本面与估值", "催化因素", "产品映射与风险提示"],
    ),
]

RECIPE_SECTION_MAP: dict[str, list[str]] = {
    recipe.id: recipe.sections for recipe in COMMENTARY_RECIPES
}

RECIPE_TITLE_MAP: dict[str, str] = {recipe.id: recipe.title for recipe in COMMENTARY_RECIPES}

COMMENTARY_MODEL = "deepseek-v4-pro"


def get_commentary_recipe_catalog() -> CommentaryRecipeCatalog:
    """Return the shared commentary recipe catalog."""
    return CommentaryRecipeCatalog(
        default_recipe_id="daily-close",
        recipes=COMMENTARY_RECIPES,
    )


class CommentaryDraftService:
    """Generate commentary drafts from prepared data and evidence."""

    def __init__(self, model_gateway: ModelGateway | None = None):
        self.model_gateway = model_gateway

    def generate_draft(self, request: CommentaryDraftRequest) -> CommentaryDraftResponse:
        """Generate a draft with LLM first and deterministic fallback second."""
        if self.model_gateway is None:
            return self._fallback_response(request, ["llm_unavailable"])

        messages = self._build_messages(request)
        try:
            response = self.model_gateway.chat(
                messages=messages,
                model=COMMENTARY_MODEL,
                temperature=0.35,
                max_tokens=2200,
                task="reporting",
            )
            draft = self._clean_markdown(response.content)
            if not draft:
                return self._fallback_response(request, ["llm_returned_empty"])
            if self._looks_like_provider_error(draft):
                return self._fallback_response(request, ["llm_returned_error_text"])
            draft, guardrail_warnings = self._apply_draft_quality_guardrails(
                draft,
                request,
            )
            return CommentaryDraftResponse(
                recipe_id=request.recipe_id,
                draft_markdown=draft,
                sections=self._extract_sections(draft),
                citations=self._build_citations(request),
                attribution_signals=self._build_attribution_response(request),
                warnings=guardrail_warnings,
                model=response.model_name,
                provider=response.provider,
                tokens_used=response.tokens_used,
                generated_at=datetime.utcnow(),
            )
        except Exception as exc:
            logger.warning(
                "commentary_draft_llm_failed",
                recipe_id=request.recipe_id,
                error=str(exc),
            )
            return self._fallback_response(request, [f"llm_failed: {exc}"])

    def rewrite_section(
        self,
        *,
        recipe_id: str,
        section_heading: str,
        section_content: str,
        action: str,
        context: CommentaryDraftRequest,
    ) -> CommentarySectionRewriteResponse:
        """Rewrite one draft section while preserving evidence constraints."""
        if self.model_gateway is None:
            return self._fallback_section_response(
                recipe_id,
                section_heading,
                section_content,
                action,
                ["llm_unavailable"],
            )

        messages = self._build_section_rewrite_messages(
            recipe_id=recipe_id,
            section_heading=section_heading,
            section_content=section_content,
            action=action,
            context=context,
        )
        try:
            response = self.model_gateway.chat(
                messages=messages,
                model=COMMENTARY_MODEL,
                temperature=0.25,
                max_tokens=700,
                task="reporting",
            )
            rewritten = self._clean_markdown(response.content)
            if not rewritten:
                return self._fallback_section_response(
                    recipe_id,
                    section_heading,
                    section_content,
                    action,
                    ["llm_returned_empty"],
                )
            if self._looks_like_provider_error(rewritten):
                return self._fallback_section_response(
                    recipe_id,
                    section_heading,
                    section_content,
                    action,
                    ["llm_returned_error_text"],
                )
            return CommentarySectionRewriteResponse(
                recipe_id=recipe_id,
                section_heading=section_heading,
                rewritten_content=rewritten,
                action=action,
                warnings=[],
                model=response.model_name,
                provider=response.provider,
                tokens_used=response.tokens_used,
                generated_at=datetime.utcnow(),
            )
        except Exception as exc:
            logger.warning(
                "commentary_section_rewrite_llm_failed",
                recipe_id=recipe_id,
                section_heading=section_heading,
                action=action,
                error=str(exc),
            )
            return self._fallback_section_response(
                recipe_id,
                section_heading,
                section_content,
                action,
                [f"llm_failed: {exc}"],
            )

    def check_quality(
        self,
        *,
        draft_markdown: str,
        context: CommentaryDraftRequest,
    ) -> CommentaryQualityCheckResponse:
        """Run deterministic publish-gate checks for a commentary draft."""
        text = (draft_markdown or "").strip()
        issues: list[CommentaryQualityIssue] = []
        issues.extend(self._check_unverified_evidence_as_fact(text, context))
        missing_risk = self._check_missing_risk_disclosure(text)
        if missing_risk:
            issues.append(missing_risk)
        issues.extend(self._check_promissory_language(text))
        summary = {
            "blocked": sum(1 for issue in issues if issue.severity == "blocker"),
            "warning": sum(1 for issue in issues if issue.severity == "warning"),
            "info": sum(1 for issue in issues if issue.severity == "info"),
        }
        status = (
            "blocked" if summary["blocked"] else ("warning" if summary["warning"] else "passed")
        )
        return CommentaryQualityCheckResponse(
            status=status,
            summary=summary,
            issues=issues,
            checked_at=datetime.utcnow(),
        )

    def _build_messages(self, request: CommentaryDraftRequest) -> list[dict[str, str]]:
        title = RECIPE_TITLE_MAP.get(request.recipe_id, RECIPE_TITLE_MAP["daily-close"])
        sections = RECIPE_SECTION_MAP.get(request.recipe_id, RECIPE_SECTION_MAP["daily-close"])
        system = (
            "你是买方基金投研团队的市场点评写作助手。"
            "请基于已确认数据、媒体报道和用户主观判断写一篇可直接编辑的中文点评。"
            "不要编造未提供的数据；对媒体报道、市场传闻和解释性归因要用谨慎措辞。"
            "正文必须以消息面主线和具体触发事件为骨架，行情数据只用于验证和量化。"
            "输出 Markdown，标题用一级标题，段落用二级标题。"
        )
        user = "\n".join(
            [
                f"点评类型：{title}",
                f"建议段落：{' / '.join(sections)}",
                "",
                "【证据包】",
                request.evidence_pack_text or "暂无证据包。",
                "",
                "【数据快照】",
                request.data_snapshot_text or "暂无数据快照。",
                "",
                "【结构化证据与核验状态】",
                self._format_evidence_matrix(request),
                "",
                "【归因排序】",
                self._format_attribution_ranking(request),
                "",
                "【用户主观判断】",
                request.subjective_judgement or "暂无，请保持中性。",
                "",
                "【写作偏好】",
                self._format_writing_preferences(request),
                "",
                "写作要求：",
                "1. 先给核心判断，并先写消息面主线，再用行情数据验证；不要把正文写成指数和行业涨跌幅罗列。",
                "2. 区分已确认事实、媒体报道和主观归因。",
                "3. 不输出投资承诺，不使用夸张营销语。",
                "4. 结尾给出后续观察变量。",
                "5. 对 verification_status 不是 verified 的证据，必须使用“据报道/显示/需要继续核验”等表述，不能当作已确认事实。",
                "6. 写作时按归因排序区分主因、次因和待核验因素，不要平均展开所有材料。",
                "7. 优先写出最高相关的具体触发事件，再写泛化归因；不要只写“海外扰动”或“风险偏好回落”。",
                "8. 如果证据中出现 Meta、OpenAI、英伟达、美股科技股、AI 资本开支、模型发布等线索，必须说明该事件如何传导到本地科技成长板块。",
            ]
        )
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    def _build_section_rewrite_messages(
        self,
        *,
        recipe_id: str,
        section_heading: str,
        section_content: str,
        action: str,
        context: CommentaryDraftRequest,
    ) -> list[dict[str, str]]:
        title = RECIPE_TITLE_MAP.get(recipe_id, RECIPE_TITLE_MAP["daily-close"])
        action_label = self._section_action_label(action)
        system = "你是买方基金投研团队的中文点评编辑。" "只改写用户给出的单个段落，不输出标题，不扩写成整篇文章。" "必须遵守证据核验边界，不编造未提供的数据。"
        user = "\n".join(
            [
                f"点评类型：{title}",
                f"段落标题：{section_heading}",
                f"改写动作：{action_label}",
                "",
                "【原段落】",
                section_content or "暂无段落内容。",
                "",
                "【数据快照】",
                context.data_snapshot_text or "暂无数据快照。",
                "",
                "【结构化证据与核验状态】",
                self._format_evidence_matrix(context),
                "",
                "【归因排序】",
                self._format_attribution_ranking(context),
                "",
                "【写作偏好】",
                self._format_writing_preferences(context),
                "",
                "改写要求：",
                "1. 只输出改写后的段落正文。",
                "2. 保留事实、报道、主观判断的边界。",
                "3. 未核验证据使用谨慎措辞。",
                "4. 不输出投资承诺或营销化表达。",
            ]
        )
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    @staticmethod
    def _section_action_label(action: str) -> str:
        labels = {
            "shorten": "缩短并保留核心信息",
            "soften": "降低判断强度",
            "risk": "补充风险提示",
            "rewrite": "重写并保持证据边界",
        }
        return labels.get(action, labels["rewrite"])

    @staticmethod
    def _format_writing_preferences(request: CommentaryDraftRequest) -> str:
        preferences = request.writing_preferences or {}
        audience_labels = {
            "internal": "投研内部",
            "sales": "销售话术",
            "client": "客户简版",
            "product": "产品材料",
        }
        length_labels = {
            "short": "短评",
            "medium": "中评",
            "long": "长评",
        }
        tone_labels = {
            "balanced": "克制归因",
            "defensive": "防御解释",
            "decisive": "观点明确",
        }
        audience = audience_labels.get(preferences.get("audience", ""), "投研内部")
        length = length_labels.get(preferences.get("length", ""), "中评")
        tone = tone_labels.get(preferences.get("tone", ""), "克制归因")
        target_mode = preferences.get("target_mode") or "auto"
        target_name = (preferences.get("target_name") or "").strip()
        target_mode_label = "手动指定" if target_mode == "manual" else "系统自动识别"
        target_line = f"点评对象：{target_mode_label} - {target_name or '等待从当日热点板块和事件中识别'}"
        return (
            f"受众：{audience}\n"
            f"长度：{length}\n"
            f"风格：{tone}\n"
            f"{target_line}\n"
            "行业板块或主题事件点评必须围绕点评对象展开；若对象来自系统自动识别，需要说明其由当日涨跌幅、异动新闻和证据相关性共同推断。"
        )

    @staticmethod
    def _format_attribution_ranking(request: CommentaryDraftRequest) -> str:
        if not request.attribution_signals:
            return "暂无归因排序，请基于数据快照和证据包谨慎归因。"
        lines: list[str] = []
        for signal in sorted(request.attribution_signals, key=lambda item: item.rank or 999)[:8]:
            evidence = "；".join(signal.evidence_titles[:3])
            lines.append(
                f"[{signal.rank}][{signal.strength}][{signal.score:.0f}] "
                f"{signal.label}｜{signal.rationale}" + (f"｜证据：{evidence}" if evidence else "")
            )
        return "\n".join(lines)

    @staticmethod
    def _format_evidence_matrix(request: CommentaryDraftRequest) -> str:
        if not request.evidence_items:
            return "暂无结构化证据。"
        lines: list[str] = []
        for item in CommentaryDraftService._select_balanced_evidence(
            request.evidence_items,
            limit=16,
        ):
            label = item.display_label or item.kind
            lines.append(
                f"[{label}][{item.source_type}][{item.verification_status}]"
                f"[{item.confidence_score:.2f}] {item.title}"
                + (f"｜{item.summary}" if item.summary else "")
                + (f"｜来源：{item.source}" if item.source else "")
            )
        return "\n".join(lines)

    @staticmethod
    def _select_balanced_evidence(items, limit: int):
        market_items = [item for item in items if item.source_type == "market_data"]
        reported_items = [item for item in items if item.source_type in {"news", "research"}]
        other_items = [
            item for item in items if item.source_type not in {"market_data", "news", "research"}
        ]
        selected = CommentaryDraftService._interleave_evidence(
            market_items[: max(6, limit // 2)],
            reported_items[: max(6, limit // 2)],
        )
        if len(selected) < limit:
            selected.extend(other_items[: limit - len(selected)])
        return selected[:limit]

    @staticmethod
    def _interleave_evidence(left, right):
        selected = []
        max_len = max(len(left), len(right))
        for index in range(max_len):
            if index < len(left):
                selected.append(left[index])
            if index < len(right):
                selected.append(right[index])
        return selected

    def _fallback_response(
        self,
        request: CommentaryDraftRequest,
        warnings: list[str],
    ) -> CommentaryDraftResponse:
        draft = self._build_fallback_markdown(request)
        draft, guardrail_warnings = self._apply_draft_quality_guardrails(
            draft,
            request,
        )
        return CommentaryDraftResponse(
            recipe_id=request.recipe_id,
            draft_markdown=draft,
            sections=self._extract_sections(draft),
            citations=self._build_citations(request),
            attribution_signals=self._build_attribution_response(request),
            warnings=[*warnings, *guardrail_warnings],
            model="rule_based_fallback",
            provider="local",
            tokens_used=0,
            generated_at=datetime.utcnow(),
        )

    def _build_fallback_markdown(self, request: CommentaryDraftRequest) -> str:
        title = RECIPE_TITLE_MAP.get(request.recipe_id, RECIPE_TITLE_MAP["daily-close"])
        sections = RECIPE_SECTION_MAP.get(request.recipe_id, RECIPE_SECTION_MAP["daily-close"])
        judgement = request.subjective_judgement.strip() or "当前行情更适合先按多因素共振理解。"
        data_text = request.data_snapshot_text.strip() or "市场数据仍需补充。"
        evidence_text = request.evidence_pack_text.strip() or "证据包仍需补充。"
        body = [
            f"# {title}",
            "",
            "## 核心判断",
            judgement,
            "",
            f"## {sections[0]}",
            data_text,
            "",
            f"## {sections[1] if len(sections) > 1 else '证据线索'}",
            evidence_text,
            "",
            "## 后续观察",
            "后续重点观察成交额与资金流能否企稳，拖累方向是否继续扩散，以及新增新闻是否从情绪扰动转为基本面压力。",
        ]
        return "\n".join(body)

    def _fallback_section_response(
        self,
        recipe_id: str,
        section_heading: str,
        section_content: str,
        action: str,
        warnings: list[str],
    ) -> CommentarySectionRewriteResponse:
        rewritten = self._apply_local_section_action(section_content, action)
        return CommentarySectionRewriteResponse(
            recipe_id=recipe_id,
            section_heading=section_heading,
            rewritten_content=rewritten,
            action=action,
            warnings=warnings,
            model="rule_based_fallback",
            provider="local",
            tokens_used=0,
            generated_at=datetime.utcnow(),
        )

    @staticmethod
    def _check_unverified_evidence_as_fact(
        text: str,
        context: CommentaryDraftRequest,
    ) -> list[CommentaryQualityIssue]:
        issues: list[CommentaryQualityIssue] = []
        certainty_terms = ("确定", "证实", "必然", "一定", "已经导致", "直接导致")
        cautious_terms = ("据报道", "显示", "需要继续核验", "市场解释", "可能", "或")
        unverified_items = [
            item
            for item in context.evidence_items
            if item.verification_status != "verified" and item.title
        ]
        for item in unverified_items:
            title = item.title.strip()
            if title not in text:
                continue
            window_start = max(0, text.find(title) - 24)
            window_end = min(len(text), text.find(title) + len(title) + 42)
            excerpt = text[window_start:window_end]
            if any(term in excerpt for term in cautious_terms):
                continue
            if any(term in excerpt for term in certainty_terms):
                issues.append(
                    CommentaryQualityIssue(
                        code="unverified_evidence_as_fact",
                        severity="blocker",
                        title="未核验证据被写成确定事实",
                        detail=f"“{title}”不是已核验证据，需使用据报道、显示或待核验等措辞。",
                        excerpt=excerpt,
                    )
                )
        return issues

    @staticmethod
    def _check_missing_risk_disclosure(text: str) -> CommentaryQualityIssue | None:
        risk_terms = ("风险", "后续观察", "需要警惕", "若", "不确定", "待核验")
        if any(term in text for term in risk_terms):
            return None
        return CommentaryQualityIssue(
            code="missing_risk_disclosure",
            severity="blocker",
            title="缺少风险提示",
            detail="草稿缺少风险提示或后续观察变量，发布前需要补充边界条件。",
        )

    @staticmethod
    def _check_promissory_language(text: str) -> list[CommentaryQualityIssue]:
        issue_terms = ("一定会", "必然上涨", "稳赚", "无风险", "确定修复", "不会下跌")
        issues: list[CommentaryQualityIssue] = []
        for term in issue_terms:
            if term not in text:
                continue
            start = max(0, text.find(term) - 24)
            end = min(len(text), text.find(term) + len(term) + 36)
            issues.append(
                CommentaryQualityIssue(
                    code="promissory_language",
                    severity="blocker",
                    title="存在承诺式表达",
                    detail=f"草稿包含“{term}”等确定收益或确定结果表达，需要改为审慎表述。",
                    excerpt=text[start:end],
                )
            )
        return issues

    @staticmethod
    def _apply_local_section_action(content: str, action: str) -> str:
        text = (content or "").strip()
        if action == "shorten":
            sentences = [item.strip() for item in text.replace("；", "。").split("。") if item.strip()]
            return "。".join(sentences[:2]) + ("。" if sentences[:2] else "")
        if action == "soften":
            return (
                text.replace("必然", "更可能")
                .replace("一定", "需要观察")
                .replace("确定", "相对明确")
                .replace("不会", "短期不易")
            )
        if action == "risk":
            risk_text = "需要提示的是，若后续成交额、资金流或新增证据不能验证当前判断，相关归因仍需下修。"
            if risk_text in text:
                return text
            suffix = "" if text.endswith("。") else "。"
            return f"{text}{suffix}{risk_text}"
        return text

    def _apply_draft_quality_guardrails(
        self,
        draft: str,
        request: CommentaryDraftRequest,
    ) -> tuple[str, list[str]]:
        """Apply lightweight deterministic fixes before returning a draft."""
        text = draft.strip()
        warnings: list[str] = []
        normalized = self._normalize_inline_section_prefixes(text, request)
        if normalized != text:
            text = normalized
            warnings.append("quality_guardrail_normalized_sections")

        softened = self._soften_draft_language(text)
        if softened != text:
            text = softened
            warnings.append("quality_guardrail_softened_language")

        if self._check_missing_risk_disclosure(text):
            text = self._append_risk_disclosure(text, request)
            warnings.append("quality_guardrail_added_risk_disclosure")
        return text, warnings

    @staticmethod
    def _soften_draft_language(text: str) -> str:
        replacements = {
            "确定导致": "可能导致",
            "直接导致": "可能拖累",
            "一定会": "需要观察修复条件，可能",
            "必然上涨": "存在修复可能",
            "确定修复": "需要观察修复条件",
            "不会下跌": "下行风险相对受限但仍需观察",
            "稳赚": "风险收益比改善",
            "无风险": "风险相对可控",
        }
        softened = text
        for old, new in replacements.items():
            softened = softened.replace(old, new)
        return softened

    @staticmethod
    def _append_risk_disclosure(text: str, request: CommentaryDraftRequest) -> str:
        title = RECIPE_TITLE_MAP.get(request.recipe_id, RECIPE_TITLE_MAP["daily-close"])
        if "产品" in title or "ETF" in title:
            risk_text = "需要提示的是，产品映射不等于收益承诺，若后续资金流、成交额或基本面证据不能验证当前判断，相关配置结论仍需下修。"
        else:
            risk_text = "需要提示的是，若后续成交额、资金流或新增证据不能验证当前判断，相关归因仍需下修。"
        separator = "\n\n" if text else ""
        return f"{text}{separator}## 风险提示\n{risk_text}"

    @staticmethod
    def _normalize_inline_section_prefixes(
        text: str,
        request: CommentaryDraftRequest,
    ) -> str:
        known_sections = {
            "核心判断",
            "后续观察",
            "风险提示",
            *RECIPE_SECTION_MAP.get(request.recipe_id, RECIPE_SECTION_MAP["daily-close"]),
        }
        normalized_lines: list[str] = []
        changed = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or "：" not in stripped:
                normalized_lines.append(line)
                continue
            heading, content = stripped.split("：", 1)
            heading = heading.strip()
            content = content.strip()
            if heading not in known_sections or not content:
                normalized_lines.append(line)
                continue
            normalized_lines.append(f"## {heading}")
            normalized_lines.append(content)
            changed = True
        if not changed:
            return text
        return "\n".join(normalized_lines)

    @staticmethod
    def _clean_markdown(content: str) -> str:
        text = (content or "").strip()
        if text.startswith("```markdown"):
            text = text[len("```markdown") :]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    @staticmethod
    def _looks_like_provider_error(content: str) -> bool:
        normalized = content.strip().lower()
        return normalized.startswith("error:") or normalized.startswith("error code:")

    @staticmethod
    def _extract_sections(markdown: str) -> list[dict[str, str]]:
        sections: list[dict[str, str]] = []
        current_heading = ""
        current_lines: list[str] = []
        for line in markdown.splitlines():
            stripped = line.strip()
            if stripped.startswith("## "):
                if current_heading:
                    sections.append(
                        {"heading": current_heading, "content": "\n".join(current_lines).strip()}
                    )
                current_heading = stripped[3:].strip()
                current_lines = []
            elif current_heading:
                current_lines.append(line)
        if current_heading:
            sections.append(
                {"heading": current_heading, "content": "\n".join(current_lines).strip()}
            )
        return sections

    @staticmethod
    def _build_citations(request: CommentaryDraftRequest) -> list[dict[str, Any]]:
        citations: list[dict[str, Any]] = []
        for item in CommentaryDraftService._select_balanced_evidence(
            request.evidence_items,
            limit=12,
        ):
            citations.append(
                {
                    "kind": item.kind,
                    "title": item.title,
                    "summary": item.summary,
                    "source": item.source,
                    "source_type": item.source_type,
                    "verification_status": item.verification_status,
                    "confidence_score": item.confidence_score,
                    "display_label": item.display_label,
                    "url": item.url,
                    "metadata": item.metadata,
                }
            )
        return citations

    @staticmethod
    def _build_attribution_response(request: CommentaryDraftRequest) -> list[dict[str, Any]]:
        return [
            {
                "rank": item.rank,
                "tag": item.tag,
                "label": item.label,
                "strength": item.strength,
                "score": item.score,
                "confidence_score": item.confidence_score,
                "verification_status": item.verification_status,
                "rationale": item.rationale,
                "evidence_titles": item.evidence_titles,
            }
            for item in sorted(request.attribution_signals, key=lambda signal: signal.rank or 999)
        ]
