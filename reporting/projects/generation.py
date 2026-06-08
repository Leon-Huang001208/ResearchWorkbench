"""Evidence-grounded report project generation.

This module connects report project configuration to the existing database
and model gateway:

Word placeholder -> section config -> prompt template -> evidence retrieval
-> DeepSeek/model generation -> placeholder replacement.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Protocol

from sqlalchemy import or_

from core.interfaces.model_gateway import ModelResponse
from core.model_gateway.gateway import ModelGatewayImpl
from core.observability import get_logger
from core.settings import settings
from reporting.projects.project_manager import ReportProject

logger = get_logger(__name__)


@dataclass(frozen=True)
class PromptTemplateBlock:
    """Parsed Markdown prompt template block."""

    title: str
    retrieval_query: str
    writing_requirements: str
    raw_text: str


@dataclass(frozen=True)
class EvidenceSnippet:
    """Retrieved evidence item passed to the LLM."""

    source: str
    title: str
    content: str
    published_at: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class GeneratedSectionInfo:
    """Generation metadata for one placeholder."""

    placeholder: str
    title: str
    prompt_template: str
    retrieval_query: str
    evidence_count: int
    model_name: str
    provider: str
    tokens_used: int
    warnings: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReportGenerationResult:
    """Generated placeholder map plus run metadata."""

    placeholders: Dict[str, str]
    sections: List[GeneratedSectionInfo]
    warnings: List[str] = field(default_factory=list)


class EvidenceRetriever(Protocol):
    """Retrieves factual evidence for a section query."""

    def retrieve(
        self,
        query: str,
        *,
        title: str,
        params: Dict[str, Any],
        lookback_days: int,
        limit: int,
    ) -> List[EvidenceSnippet]:
        """Return evidence snippets for a report section."""


class DatabaseEvidenceRetriever:
    """Keyword evidence retriever over existing AlphaFoundry database tables."""

    def retrieve(
        self,
        query: str,
        *,
        title: str,
        params: Dict[str, Any],
        lookback_days: int,
        limit: int,
    ) -> List[EvidenceSnippet]:
        """Retrieve evidence from ingestion queue and canonical events."""
        try:
            from data_layer.repositories.base import SessionLocal

            with SessionLocal() as session:
                snippets = self._retrieve_ingestion_items(
                    session,
                    query=query,
                    title=title,
                    params=params,
                    lookback_days=lookback_days,
                    limit=limit,
                )
                if len(snippets) < limit:
                    snippets.extend(
                        self._retrieve_events(
                            session,
                            query=query,
                            title=title,
                            params=params,
                            lookback_days=lookback_days,
                            limit=limit - len(snippets),
                        )
                    )
                return snippets[:limit]
        except Exception as exc:
            logger.warning(
                "Failed to retrieve report evidence",
                title=title,
                error=str(exc),
            )
            return []

    def _retrieve_ingestion_items(
        self,
        session: Any,
        *,
        query: str,
        title: str,
        params: Dict[str, Any],
        lookback_days: int,
        limit: int,
    ) -> List[EvidenceSnippet]:
        from data_layer.repositories.models import IngestionQueueItemDB

        terms = self._extract_terms(query, title=title, params=params)
        cutoff = datetime.now() - timedelta(days=lookback_days)
        filters = [
            or_(
                IngestionQueueItemDB.title.ilike(f"%{term}%"),
                IngestionQueueItemDB.raw_content.ilike(f"%{term}%"),
            )
            for term in terms
        ]
        query_obj = session.query(IngestionQueueItemDB)
        if filters:
            query_obj = query_obj.filter(or_(*filters))
        query_obj = query_obj.filter(IngestionQueueItemDB.created_at >= cutoff)
        rows = query_obj.order_by(IngestionQueueItemDB.created_at.desc()).limit(limit).all()
        return [
            EvidenceSnippet(
                source=f"ingestion:{row.source_type}",
                title=row.title or row.source_id or row.item_id,
                content=self._compact_text(row.raw_content),
                published_at=row.published_at
                or (row.created_at.isoformat() if row.created_at else None),
                url=row.url,
            )
            for row in rows
            if row.raw_content
        ]

    def _retrieve_events(
        self,
        session: Any,
        *,
        query: str,
        title: str,
        params: Dict[str, Any],
        lookback_days: int,
        limit: int,
    ) -> List[EvidenceSnippet]:
        from data_layer.repositories.models import CanonicalEvent

        terms = self._extract_terms(query, title=title, params=params)
        cutoff = datetime.now() - timedelta(days=lookback_days)
        filters = [
            or_(
                CanonicalEvent.summary.ilike(f"%{term}%"),
                CanonicalEvent.event_type.ilike(f"%{term}%"),
            )
            for term in terms
        ]
        query_obj = session.query(CanonicalEvent)
        if filters:
            query_obj = query_obj.filter(or_(*filters))
        query_obj = query_obj.filter(CanonicalEvent.created_at >= cutoff)
        rows = query_obj.order_by(CanonicalEvent.created_at.desc()).limit(limit).all()
        return [
            EvidenceSnippet(
                source="canonical_event",
                title=row.event_type,
                content=self._compact_text(row.summary),
                published_at=(row.event_time or row.created_at).isoformat()
                if (row.event_time or row.created_at)
                else None,
                url=None,
            )
            for row in rows
            if row.summary
        ]

    @staticmethod
    def _extract_terms(query: str, *, title: str, params: Dict[str, Any]) -> List[str]:
        raw_terms: List[str] = []
        raw_terms.append(title)
        for value in params.values():
            if isinstance(value, str):
                raw_terms.append(value)
        raw_terms.extend(part.strip() for part in re.split(r"[，,、；;。\n\s]+", query) if part.strip())

        stop_terms = {
            "请基于上传的全部新闻内容",
            "撰写一段关于",
            "最新动态",
            "包括",
            "涵盖",
            "方面",
            "市场",
            "新闻",
        }
        terms: List[str] = []
        for term in raw_terms:
            cleaned = re.sub(r"^(请基于上传的全部新闻内容|撰写一段关于)", "", term).strip()
            cleaned = re.sub(r"(的最新动态|等)$", "", cleaned).strip()
            if not cleaned or cleaned in stop_terms or len(cleaned) < 2:
                continue
            if cleaned not in terms:
                terms.append(cleaned)
        return terms[:12]

    @staticmethod
    def _compact_text(text: str, max_chars: int = 900) -> str:
        compacted = re.sub(r"\s+", " ", text).strip()
        return compacted[:max_chars]


class ReportProjectGenerationService:
    """Generates Word placeholders from project config, evidence, and LLM."""

    def __init__(
        self,
        *,
        retriever: EvidenceRetriever | None = None,
        model_gateway: Any | None = None,
    ) -> None:
        self.retriever = retriever or DatabaseEvidenceRetriever()
        self.model_gateway = model_gateway or ModelGatewayImpl()

    def generate_placeholders(
        self,
        *,
        project: ReportProject,
        section_config: Dict[str, Any],
        prompt_templates_source: str,
        manual_placeholders: Dict[str, str] | None = None,
        lookback_days: int = 7,
    ) -> ReportGenerationResult:
        """Generate configured placeholders, with manual values as overrides."""
        manual_placeholders = manual_placeholders or {}
        templates = parse_prompt_templates(prompt_templates_source)
        warnings: List[str] = []
        generated: Dict[str, str] = {}
        section_infos: List[GeneratedSectionInfo] = []

        for placeholder, config in iter_placeholder_configs(section_config):
            if placeholder in manual_placeholders and manual_placeholders[placeholder]:
                generated[placeholder] = manual_placeholders[placeholder]
                continue

            title = str(config.get("title") or placeholder)
            template_name = str(config.get("prompt_template") or title)
            template = templates.get(template_name) or build_fallback_template(config, title)
            raw_params = config.get("params")
            params: Dict[str, Any] = dict(raw_params) if isinstance(raw_params, dict) else {}
            max_words = int(config.get("max_words") or config.get("target_words") or 300)
            evidence_limit = int(config.get("evidence_limit") or 8)

            evidence = self.retriever.retrieve(
                template.retrieval_query,
                title=title,
                params=params,
                lookback_days=lookback_days,
                limit=evidence_limit,
            )
            if not evidence:
                warnings.append(f"{placeholder}: 未检索到证据，生成将提示材料不足")

            response = self._generate_section(
                project=project,
                placeholder=placeholder,
                title=title,
                template=template,
                params=params,
                max_words=max_words,
                evidence=evidence,
            )

            content = self._clean_model_content(response.content, title=title)
            section_warnings: List[str] = []
            if not content or content.startswith("Error:"):
                section_warnings.append(content or "模型未返回内容")
                content = self._fallback_content(title, evidence)

            generated[placeholder] = content
            section_infos.append(
                GeneratedSectionInfo(
                    placeholder=placeholder,
                    title=title,
                    prompt_template=template_name,
                    retrieval_query=template.retrieval_query,
                    evidence_count=len(evidence),
                    model_name=response.model_name,
                    provider=response.provider,
                    tokens_used=response.tokens_used,
                    warnings=section_warnings,
                )
            )

        generated.update({key: value for key, value in manual_placeholders.items() if value})
        return ReportGenerationResult(
            placeholders=generated,
            sections=section_infos,
            warnings=warnings,
        )

    def _generate_section(
        self,
        *,
        project: ReportProject,
        placeholder: str,
        title: str,
        template: PromptTemplateBlock,
        params: Dict[str, Any],
        max_words: int,
        evidence: List[EvidenceSnippet],
    ) -> ModelResponse:
        messages = build_generation_messages(
            project=project,
            placeholder=placeholder,
            title=title,
            template=template,
            params=params,
            max_words=max_words,
            evidence=evidence,
        )
        logger.info(
            "Generating report section",
            project=project.name,
            placeholder=placeholder,
            title=title,
            evidence_count=len(evidence),
        )
        task_name = "reporting" if "reporting" in settings.TASK_ROUTES else "default"
        return self.model_gateway.chat(
            messages=messages,
            task=task_name,
            temperature=0.2,
            max_tokens=max(300, min(1600, max_words * 3)),
        )

    @staticmethod
    def _fallback_content(title: str, evidence: List[EvidenceSnippet]) -> str:
        if not evidence:
            return f"{title}相关材料不足，暂无法形成基于事实的周报段落。"
        facts = "；".join(item.content[:80] for item in evidence[:3])
        return f"{title}方面，本周材料显示：{facts}。相关判断仍需结合后续数据验证。"

    @staticmethod
    def _clean_model_content(content: str, *, title: str) -> str:
        """Keep only the final report paragraph from a chat response."""
        text = content.strip()
        if not text:
            return ""
        text = re.sub(r"^```(?:text|markdown)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = re.sub(r"\s+", " ", text).strip()

        for marker in ["可以写：", "可以写:", "生成结果：", "生成结果:", "正文：", "正文:"]:
            if marker in text:
                text = text.split(marker)[-1].strip()

        title_markers = [f"{title}方面", f"{title}行业方面", f"{title}市场方面"]
        for marker in title_markers:
            index = text.find(marker)
            if index > 0:
                text = text[index:].strip()
                break

        meta_prefixes = [
            "我们根据提供的evidence",
            "根据提供的evidence",
            "我们根据提供的材料",
            "根据提供的材料",
        ]
        for prefix in meta_prefixes:
            if text.startswith(prefix):
                first_sentence_end = re.search(r"[。.!！]", text)
                if first_sentence_end:
                    text = text[first_sentence_end.end() :].strip()
        return text


def iter_placeholder_configs(
    section_config: Dict[str, Any]
) -> Iterable[tuple[str, Dict[str, Any]]]:
    """Yield normalized placeholder configs from both new and legacy schemas."""
    placeholders = section_config.get("placeholders")
    if isinstance(placeholders, dict):
        for placeholder, config in placeholders.items():
            if isinstance(config, dict):
                yield str(placeholder), config
            else:
                yield str(placeholder), {"title": str(placeholder), "value": str(config)}
        return

    sections = section_config.get("sections")
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, dict):
                continue
            placeholder = section.get("placeholder") or section.get("key")
            if placeholder:
                yield str(placeholder), section


def parse_prompt_templates(source: str) -> Dict[str, PromptTemplateBlock]:
    """Parse Markdown prompt templates keyed by second-level heading."""
    templates: Dict[str, PromptTemplateBlock] = {}
    if not source.strip():
        return templates

    matches = list(re.finditer(r"^##\s+(.+?)\s*$", source, flags=re.MULTILINE))
    for index, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        raw_block = source[start:end].strip()
        block = _strip_code_fences(raw_block)
        retrieval_query = _extract_label_value(block, "检索 Query")
        writing_requirements = _extract_label_value(block, "写作要求")
        templates[title] = PromptTemplateBlock(
            title=title,
            retrieval_query=retrieval_query or block or title,
            writing_requirements=writing_requirements or block,
            raw_text=block,
        )
    return templates


def build_fallback_template(config: Dict[str, Any], title: str) -> PromptTemplateBlock:
    """Build a prompt template from legacy section config."""
    required_facets = config.get("required_facets")
    if isinstance(required_facets, list) and required_facets:
        facets_text = "、".join(str(item) for item in required_facets)
    else:
        facets_text = title
    query = str(config.get("query") or f"检索本周与{title}相关的事实材料，覆盖{facets_text}。")
    requirements = str(
        config.get("prompt") or f"围绕{title}撰写正式周报段落，覆盖{facets_text}。严格依据证据材料，不输出投资建议。"
    )
    return PromptTemplateBlock(
        title=title,
        retrieval_query=query,
        writing_requirements=requirements,
        raw_text=requirements,
    )


def build_generation_messages(
    *,
    project: ReportProject,
    placeholder: str,
    title: str,
    template: PromptTemplateBlock,
    params: Dict[str, Any],
    max_words: int,
    evidence: List[EvidenceSnippet],
) -> List[Dict[str, str]]:
    """Build strict evidence-grounded LLM messages."""
    evidence_context = format_evidence_context(evidence)
    params_text = "\n".join(f"- {key}: {value}" for key, value in params.items()) or "无"
    system = (
        "你是基金/ETF周报写作助手。必须只依据用户提供的 evidence 写作；"
        "不得添加外部知识、不得虚构数字、不得输出直接投资建议、收益承诺、目标价或买卖指令。"
        "如果 evidence 不足，直接说明材料不足，避免编造。"
    )
    user = f"""项目：{project.name}
Word 占位符：{{{{{placeholder}}}}}
段落标题：{title}
目标字数：不超过 {max_words} 字

检索 Query：
{template.retrieval_query}

配置参数：
{params_text}

写作要求：
{template.writing_requirements}

Evidence：
{evidence_context}

请直接输出可替换进 Word 的正文段落，不要输出标题、编号、项目符号或解释过程。"""
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def format_evidence_context(evidence: List[EvidenceSnippet]) -> str:
    """Format evidence snippets for an LLM prompt."""
    if not evidence:
        return "未检索到可用证据。"
    lines: List[str] = []
    for index, item in enumerate(evidence, start=1):
        meta = " | ".join(
            part for part in [item.source, item.published_at, item.title, item.url] if part
        )
        lines.append(f"[{index}] {meta}\n{item.content}")
    return "\n\n".join(lines)


def _strip_code_fences(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.strip().startswith("```"):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _extract_label_value(text: str, label: str) -> str:
    pattern = re.compile(
        rf"{re.escape(label)}\s*[：:]\s*(.*?)(?=\n\s*(?:检索 Query|写作要求)\s*[：:]|\Z)",
        flags=re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return ""
    return match.group(1).strip()
