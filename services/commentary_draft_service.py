"""Generate editable market commentary drafts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from core.contracts.commentary import CommentaryDraftRequest, CommentaryDraftResponse
from core.interfaces import ModelGateway
from core.observability import get_logger

logger = get_logger(__name__)


RECIPE_SECTION_MAP: dict[str, list[str]] = {
    "daily-close": ["今日市场表现", "行业与风格变化", "资金与情绪", "核心归因", "后续观察"],
    "market-drawdown": ["发生了什么", "主要拖累方向", "直接触发因素", "深层原因判断", "明日观察变量"],
    "sector-review": ["核心观点", "行情表现", "景气度证据", "估值与预期差", "配置建议与风险"],
    "theme-event": ["事件概述", "产业链传导", "受益与受损方向", "市场分歧", "跟踪指标"],
    "global-shock": ["海外市场表现", "触发因素", "跨市场传导", "A股映射方向", "风险边界"],
    "etf-allocation": ["配置结论", "板块表现", "基本面与估值", "催化因素", "产品映射与风险提示"],
}

RECIPE_TITLE_MAP: dict[str, str] = {
    "daily-close": "每日收盘点评",
    "market-drawdown": "市场大跌归因",
    "sector-review": "行业板块点评",
    "theme-event": "主题事件点评",
    "global-shock": "海外扰动点评",
    "etf-allocation": "产品/ETF配置点评",
}

COMMENTARY_MODEL = "deepseek-v4-pro"


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
            return CommentaryDraftResponse(
                recipe_id=request.recipe_id,
                draft_markdown=draft,
                sections=self._extract_sections(draft),
                citations=self._build_citations(request),
                attribution_signals=self._build_attribution_response(request),
                warnings=[],
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

    def _build_messages(self, request: CommentaryDraftRequest) -> list[dict[str, str]]:
        title = RECIPE_TITLE_MAP.get(request.recipe_id, RECIPE_TITLE_MAP["daily-close"])
        sections = RECIPE_SECTION_MAP.get(request.recipe_id, RECIPE_SECTION_MAP["daily-close"])
        system = (
            "你是买方基金投研团队的市场点评写作助手。"
            "请基于已确认数据、媒体报道和用户主观判断写一篇可直接编辑的中文点评。"
            "不要编造未提供的数据；对媒体报道、市场传闻和解释性归因要用谨慎措辞。"
            "输出 Markdown，标题用一级标题，段落用二级标题。"
        )
        user = "\n".join(
            [
                f"点评类型：{title}",
                f"建议段落：{' / '.join(sections)}",
                "",
                "【数据快照】",
                request.data_snapshot_text or "暂无数据快照。",
                "",
                "【证据包】",
                request.evidence_pack_text or "暂无证据包。",
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
                "写作要求：",
                "1. 先给核心判断，再解释数据和证据。",
                "2. 区分已确认事实、媒体报道和主观归因。",
                "3. 不输出投资承诺，不使用夸张营销语。",
                "4. 结尾给出后续观察变量。",
                "5. 对 verification_status 不是 verified 的证据，必须使用“据报道/显示/需要继续核验”等表述，不能当作已确认事实。",
                "6. 写作时按归因排序区分主因、次因和待核验因素，不要平均展开所有材料。",
            ]
        )
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    @staticmethod
    def _format_attribution_ranking(request: CommentaryDraftRequest) -> str:
        if not request.attribution_signals:
            return "暂无归因排序，请基于数据快照和证据包谨慎归因。"
        lines: list[str] = []
        for signal in sorted(request.attribution_signals, key=lambda item: item.rank or 999)[:8]:
            evidence = "；".join(signal.evidence_titles[:3])
            lines.append(
                f"[{signal.rank}][{signal.strength}][{signal.score:.0f}] "
                f"{signal.label}｜{signal.rationale}"
                + (f"｜证据：{evidence}" if evidence else "")
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
        reported_items = [
            item for item in items if item.source_type in {"news", "research"}
        ]
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
        return CommentaryDraftResponse(
            recipe_id=request.recipe_id,
            draft_markdown=draft,
            sections=self._extract_sections(draft),
            citations=self._build_citations(request),
            attribution_signals=self._build_attribution_response(request),
            warnings=warnings,
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
