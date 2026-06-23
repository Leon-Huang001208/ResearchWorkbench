"""Dashboard 专用数据仓储"""
import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, List, Tuple

from sqlalchemy import DateTime, String, and_, cast, desc, func

from core.contracts import DocType
from core.observability import get_logger
from data_layer.repositories.models import (
    AlphaSignalDB,
    CanonicalEvent,
    DocumentV1DB,
    Entity,
    EntityMentionV1DB,
    IngestionQueueItemDB,
)

logger = get_logger(__name__)

# LLM importance scoring prompt for batch news evaluation
_IMPORTANCE_SYSTEM_PROMPT = """\
你是一位全球宏观对冲基金的研究主管。评估以下新闻对全球资本市场的重要性。

评分标准（0.0-1.0）：
- 0.8-1.0: 行业里程碑事件——重大科技突破（SpaceX发射、AI大模型发布、芯片制程突破、新药获批）、
         旗舰产品发布（英伟达新GPU、Apple发布会）、颠覆性创新、可控核聚变进展
- 0.6-0.8: 重大宏观/政策——美联储利率决议、央行降准降息、政治局会议定调、
         关税/贸易战/制裁升级、地缘政治重大变化
- 0.4-0.6: 重要行业动态——龙头公司财报超预期、重大并购重组、行业趋势拐点、
         监管新规影响全行业
- 0.2-0.4: 常规市场报道——日常涨跌、板块轮动、个股公告、外围市场小波动
- 0.0-0.2: 噪音——非金融社会新闻（火山、地震、天气、景区）、无市场影响的琐事

对于每条新闻，返回JSON数组：
[{"id": 编号, "importance": 0.0-1.0, "reason": "一句话判断理由"}]"""

_IMPORTANCE_USER_PROMPT_TEMPLATE = """请评估以下新闻的重要性：

{news_list}

返回JSON数组，按顺序对应每条新闻。"""

_NON_CONTENT_MARKERS = (
    "权威、专业、价值 尽在上海证券报客户端",
    "AI帮你提炼, 10秒 看完要点",
    "AI帮你提炼，10秒 看完要点",
)
_ZQ_REFERENCE_MARKER_RE = re.compile(r"##\d+\$\$")
_PDF_PAGE_MARKER_RE = re.compile(r"<!--\s*page:\s*\d+\s*-->", flags=re.I)
_PDF_TABLE_MARKER_RE = re.compile(r"\[/?Table[_A-Za-z0-9]*\]")
_PDF_NOISE_MARKERS = (
    "本报告仅供",
    "请阅读最后评级说明",
    "评级说明和重要声明",
    "免责声明",
    "证券研究报告",
    "SAC执业证书",
    "SFC CE",
    "DOCID",
    "OBJID",
    "mailto:",
    "邮箱",
    "电话",
    "报告告读",
    "TT aabbll",
    "T2a0b",
)


def _single_line_text(text: Any) -> str:
    """Normalize UI titles without destroying meaningful Chinese punctuation."""
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _clean_live_document_text(text: Any) -> str:
    cleaned = _ZQ_REFERENCE_MARKER_RE.sub("", str(text or ""))
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    return cleaned.strip()


def _looks_like_pdf_noise_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if _PDF_PAGE_MARKER_RE.search(stripped) or _PDF_TABLE_MARKER_RE.search(stripped):
        return True
    if any(marker in stripped for marker in _PDF_NOISE_MARKERS):
        return True
    if stripped.count("|") >= 4:
        return True
    if re.fullmatch(r"[\|\-—_\s:：,，.。;；/\\\[\]\(\)（）]+", stripped):
        return True
    return False


def _clean_pdf_report_text_for_display(text: str) -> str:
    """Turn noisy PDF extraction into a readable live-monitor detail excerpt."""
    if not text:
        return ""

    cleaned_lines: list[str] = []
    for raw_line in _PDF_PAGE_MARKER_RE.sub("\n", text).splitlines():
        line = raw_line.strip()
        if _looks_like_pdf_noise_line(line):
            continue
        line = _PDF_TABLE_MARKER_RE.sub("", line)
        line = re.sub(r"\[[^\]]*(?:Table|T\s*a\s*b\s*l|T\s*abl|abl投e)[^\]]*\]", "", line, flags=re.I)
        line = re.sub(r"\[\[[^\]]+\]\]", "", line)
        line = re.sub(r"\bT\s*2?a\s*0?b\s*2?l\s*e[\w_.-]*\b", "", line, flags=re.I)
        line = re.sub(r"\bTT\s+aabbll[\w\s_.（）()-]*", "", line, flags=re.I)
        line = re.sub(r"[*`#]+", "", line)
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _split_leading_bracket(text: str) -> Tuple[str, str]:
    match = re.match(r"^【([^】]{2,120})】\s*(.*)$", text.strip(), flags=re.S)
    if not match:
        return "", text.strip()
    return _single_line_text(match.group(1)), match.group(2).strip()


def _remove_duplicate_prefix(title: str, content: str) -> str:
    content = (content or "").strip()
    title = (title or "").strip()
    if not title or not content:
        return content
    if content == title:
        return ""
    if content.startswith(title):
        return content[len(title) :].lstrip(" \t\r\n，。,.:：;；")
    title_line = content.splitlines()[0].strip() if content.splitlines() else ""
    if title_line == title:
        return "\n".join(content.splitlines()[1:]).strip()
    return content


def _has_independent_content(text: str, title: str) -> bool:
    compact = _single_line_text(text)
    if not compact or compact == _single_line_text(title):
        return False
    return not any(marker in compact for marker in _NON_CONTENT_MARKERS)


def _extract_json_document_text(text: str) -> Tuple[str, str, bool]:
    stripped = (text or "").strip()
    if not stripped.startswith("{"):
        return "", text, False
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return "", text, False
    if not isinstance(payload, dict):
        return "", text, False

    content_fields = (
        "coreViewpoint",
        "viewpoint",
        "core",
        "content",
        "summary",
        "abstract",
    )
    content_parts = [
        str(payload.get(field) or "").strip()
        for field in content_fields
        if str(payload.get(field) or "").strip()
    ]
    return _single_line_text(payload.get("title")), "\n\n".join(content_parts), True


def _normalize_crawl_document_text(doc: DocumentV1DB) -> Dict[str, str]:
    raw_title = (doc.title or "").strip()
    raw_summary = _clean_live_document_text(doc.summary)
    raw_content = _clean_live_document_text(doc.content)
    source_type_value = getattr(doc, "source_type", "")
    source_type = source_type_value if isinstance(source_type_value, str) else ""
    if source_type == "zhiqiu_reports" or _PDF_PAGE_MARKER_RE.search(raw_content):
        raw_content = _clean_pdf_report_text_for_display(raw_content)
    json_title, json_content, content_was_json = _extract_json_document_text(raw_content)
    if content_was_json:
        if not raw_title and json_title:
            raw_title = json_title
        raw_content = _clean_live_document_text(json_content)
        if source_type == "zhiqiu_reports" or _PDF_PAGE_MARKER_RE.search(raw_content):
            raw_content = _clean_pdf_report_text_for_display(raw_content)

    bracket_title, title_tail = _split_leading_bracket(raw_title)
    content_bracket_title, content_tail = _split_leading_bracket(raw_content)

    display_title = bracket_title or content_bracket_title or _single_line_text(raw_title)
    if not display_title:
        display_title = _single_line_text(raw_content[:80]) or "(无标题)"

    detail_content = raw_content
    if content_bracket_title:
        detail_content = content_tail
    elif bracket_title and raw_content.startswith(raw_title):
        detail_content = raw_content[len(raw_title) :].strip()
    else:
        detail_content = _remove_duplicate_prefix(raw_title, raw_content)

    if not _has_independent_content(detail_content, display_title):
        detail_content = ""

    summary = raw_summary
    if summary:
        summary_bracket_title, summary_tail = _split_leading_bracket(summary)
        if summary_bracket_title:
            summary = summary_tail
        summary = _remove_duplicate_prefix(display_title, summary)
        if not _has_independent_content(summary, display_title):
            summary = ""

    if not summary and title_tail and _has_independent_content(title_tail, display_title):
        summary = title_tail

    return {
        "title": display_title,
        "raw_title": raw_title,
        "summary": summary,
        "content": detail_content,
        "has_content": bool(detail_content or summary),
    }


class DashboardDataRepository:
    """仪表盘数据专用仓储"""

    def __init__(self, session):
        self.session = session

    def get_global_news_from_events(
        self, limit: int = 10, days: int = 7, allowed_sources: List[str] = None
    ) -> List[Dict]:
        """
        从 CanonicalEvent 获取全球新闻

        Args:
            limit: 返回数量上限
            days: 时间范围（天）
            allowed_sources: 允许的来源名称列表，默认仅财联社

        Returns:
            新闻数据列表
        """
        if allowed_sources is None:
            allowed_sources = ["财联社"]

        cutoff = datetime.now(UTC) - timedelta(days=days)

        events = (
            self.session.query(CanonicalEvent)
            .filter(
                and_(
                    func.coalesce(CanonicalEvent.event_time, CanonicalEvent.created_at) >= cutoff,
                    CanonicalEvent.reviewer_status != "rejected",
                )
            )
            .order_by(desc(CanonicalEvent.created_at))
            .limit(limit * 2)
            .all()
        )

        news_items = []
        for event in events:
            payload = event.payload or {}
            source_name = payload.get("source_name", "Unknown")
            # 过滤非财联社来源
            if source_name not in allowed_sources:
                continue
            novelty_score = payload.get("novelty_score", 0.5)
            impacted_symbols = payload.get("impacted_symbols", [])
            title = payload.get("title", event.summary or "")

            # 计算重要性评分：结合 novelty_score 和 confidence
            importance_score = (novelty_score * 0.6) + (float(event.confidence) * 0.4)

            # 时间衰减：基于事件实际发生时间
            ref_time = event.event_time if event.event_time else event.created_at
            if ref_time.tzinfo is None:
                ref_time = ref_time.replace(tzinfo=UTC)
            age_seconds = (datetime.now(UTC) - ref_time).total_seconds()
            age_days = int(age_seconds / 86400)
            decay = 1.0 / (1.0 + age_days * 0.15)
            importance_score *= decay

            # 提取区域信息
            region = "Global"
            impacted_industries = payload.get("impacted_industries", [])
            if any("China" in ind or "中国" in ind for ind in impacted_industries):
                region = "China"
            elif any("US" in ind or "美国" in ind for ind in impacted_industries):
                region = "US"
            elif any("Europe" in ind or "欧洲" in ind for ind in impacted_industries):
                region = "Europe"

            news_items.append(
                {
                    "news_id": f"event-{event.event_id}",
                    "title": title or event.summary or "市场事件",
                    "source": source_name,
                    "importance_score": importance_score,
                    "summary": event.summary or "",
                    "content_url": None,
                    "published_at": (
                        event.event_time.isoformat()
                        if event.event_time
                        else event.created_at.isoformat()
                    ),
                    "related_symbols": impacted_symbols[:5],
                    "region": region,
                    "event_type": event.event_type,
                }
            )

        # 按重要性评分排序
        news_items.sort(key=lambda x: x["importance_score"], reverse=True)
        return news_items[:limit]

    def get_global_news_from_documents(
        self, limit: int = 10, days: int = 7, source_types: List[str] = None
    ) -> List[Dict]:
        """
        从 DocumentV1 获取全球新闻

        Args:
            limit: 返回数量上限
            days: 时间范围（天）
            source_types: 来源类型过滤，默认财联社 + 中国证券网快讯

        Returns:
            新闻数据列表
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)

        if source_types is None:
            source_types = ["cls", "cnstock_flash"]

        # 只查询新闻类文档，排除研报和评论
        doc_types = [DocType.NEWS.value, DocType.TELEGRAM.value]
        documents = (
            self.session.query(DocumentV1DB)
            .filter(
                and_(
                    DocumentV1DB.doc_type.in_(doc_types),
                    DocumentV1DB.source_type.in_(source_types),
                    func.coalesce(
                        cast(
                            func.json_extract_path_text(DocumentV1DB.timeliness, "publish_time"),
                            DateTime(timezone=True),
                        ),
                        DocumentV1DB.created_at,
                    )
                    >= cutoff,
                )
            )
            .order_by(desc(DocumentV1DB.created_at))
            .limit(limit * 4)
            .all()
        )

        # Pre-compute rule-based quality scores for docs missing them.
        # NOTE: dict() copy is required — SQLAlchemy JSON columns don't
        # track in-place mutation; reassigning the same dict ref is a no-op.
        pre_filled = 0
        for doc in documents:
            quality = dict(doc.quality or {})
            has_usability = quality.get("research_usability_score") is not None
            has_content = quality.get("content_quality_score") is not None
            if not has_usability or not has_content:
                usability, content_q = self._compute_quality_scores(doc)
                if not has_usability:
                    quality["research_usability_score"] = usability
                if not has_content:
                    quality["content_quality_score"] = content_q
                doc.quality = quality
                pre_filled += 1
        if pre_filled:
            logger.info("quality pre-fill", filled=pre_filled, total=len(documents))

        # Batch LLM importance scoring (caches to doc.quality.importance_score)
        llm_scores = self._batch_score_importance(documents)

        news_items = []
        for doc in documents:
            try:
                quality = doc.quality or {}
                classification = doc.classification or {}
                timeliness = doc.timeliness or {}

                # 计算重要性评分：规则质量分 + LLM 影响力评分
                research_score = quality.get("research_usability_score") or 0.5
                content_score = quality.get("content_quality_score") or 0.5
                quality_avg = (research_score + content_score) / 2
                llm_score = llm_scores.get(doc.doc_id, quality_avg)
                importance_score = (quality_avg * 0.3) + (llm_score * 0.7)

                # 时间衰减（温和系数，重要旧闻仍可胜出今日噪音）
                publish_time_str = timeliness.get("publish_time")
                if publish_time_str:
                    try:
                        if isinstance(publish_time_str, datetime):
                            publish_dt = publish_time_str
                        elif isinstance(publish_time_str, str):
                            publish_dt = datetime.fromisoformat(publish_time_str)
                        else:
                            publish_dt = doc.created_at
                        if publish_dt.tzinfo is None:
                            publish_dt = publish_dt.replace(tzinfo=UTC)
                        else:
                            publish_dt = publish_dt.astimezone(UTC)
                    except (ValueError, TypeError):
                        publish_dt = doc.created_at
                else:
                    publish_dt = doc.created_at
                age_seconds = (datetime.now(UTC) - publish_dt).total_seconds()
                age_days = int(age_seconds / 86400)
                decay = 1.0 / (1.0 + age_days * 0.15)
                importance_score *= decay

                # 获取区域信息
                region = classification.get("region") or "Global"

                # 获取相关标的（从 entity mentions）
                related_symbols = self._get_related_symbols_for_doc(doc.doc_id)

                # 生成摘要
                raw_text = doc.summary or doc.content or ""
                summary = raw_text[:200] + "..." if len(raw_text) > 200 else raw_text

                # 为财联社等来源提取有意义的标题，避免显示内部ID
                title = doc.title or "市场资讯"
                use_clean_title = title.startswith("财联社电报") or title.startswith("电报")
                if not use_clean_title and title.startswith("【"):
                    # CLS adapter 提取了首句作为标题，缩短为【】内的内容
                    use_clean_title = True
                if use_clean_title:
                    title = self._extract_news_headline(doc.summary, doc.content, title)
                    # 从摘要中移除重复的【标题】前缀
                    summary = self._strip_headline_from_summary(title, summary)

                # 获取发布时间
                published_at = timeliness.get("publish_time")
                if not published_at:
                    published_at = doc.created_at.isoformat() if doc.created_at else ""
                elif isinstance(published_at, datetime):
                    published_at = published_at.isoformat()
                else:
                    published_at = str(published_at)

                news_items.append(
                    {
                        "news_id": f"doc-{doc.doc_id}",
                        "title": title,
                        "source": doc.source_name or "Unknown",
                        "importance_score": importance_score,
                        "summary": summary or "",
                        "content_url": doc.source_url or "",
                        "published_at": published_at,
                        "related_symbols": related_symbols[:5],
                        "region": region,
                        "doc_type": doc.doc_type or "",
                    }
                )
            except Exception:
                continue

        # 按重要性评分排序
        news_items.sort(key=lambda x: x["importance_score"], reverse=True)
        return news_items[:limit]

    # ── inline quality scoring (rule-based) ──────────────────────────

    @staticmethod
    def _compute_quality_scores(doc: DocumentV1DB) -> Tuple[float, float]:
        """Compute (research_usability_score, content_quality_score) for a DocumentV1DB.

        Mirrors DocumentClassifier.analyze_quality() logic but works directly
        with ORM objects (string fields / JSON dicts) instead of Pydantic contracts.
        """
        content = str(doc.content or "")
        content_len = len(content)

        # --- financial relevance penalty ---
        # Heavily penalise content clearly unrelated to markets / industry
        _NON_FINANCIAL_PATTERNS = [
            r"火山(喷发|灰柱|地震)",
            r"地震",
            r"景区.*(岩石|塌方|关闭|事故)",
            r"高架桥.*(拆除|坍塌)",
            r"体育(赛事|比赛|联赛|冠军)",
            r"天气(预报|预警)",
        ]
        non_financial_penalty = 0.0
        for pat in _NON_FINANCIAL_PATTERNS:
            if re.search(pat, content):
                non_financial_penalty = 0.25
                break

        # --- research_usability_score ---
        usability = 0.30

        if content_len > 500:
            usability += 0.10
        if content_len > 1000:
            usability += 0.10

        if any(c.isdigit() for c in content):
            usability += 0.15

        if re.search(r"(股份有限公司|有限公司|集团|[0-9]{6}\.(SZ|SH|BJ))", content):
            usability += 0.15

        if re.search(r"20[2-9][0-9]年", content):
            usability += 0.10

        # CLS = established media
        usability += 0.20

        usability = max(0.0, min(usability - non_financial_penalty, 1.0))

        # --- content_quality_score ---
        quality = 0.40

        if content_len > 500:
            quality += 0.10
        if content_len > 1000:
            quality += 0.10

        paragraphs = [p for p in content.split("\n") if p.strip()]
        if len(paragraphs) >= 3:
            quality += 0.10

        classification: Dict[str, Any] = dict(doc.classification) if doc.classification else {}
        if classification.get("topics"):
            quality += 0.10

        quality = max(0.0, min(quality - non_financial_penalty, 1.0))

        return usability, quality

    # ── LLM batch importance scoring ─────────────────────────────────

    def _batch_score_importance(self, docs: list) -> Dict[str, float]:
        """Return cached global importance scores without blocking the dashboard."""
        # Separate already-scored from unscored
        unscored: list = []
        cached: Dict[str, float] = {}
        for i, doc in enumerate(docs):
            quality = doc.quality or {}
            cached_score = quality.get("importance_score") if isinstance(quality, dict) else None
            if cached_score is not None:
                cached[doc.doc_id] = float(cached_score)
            else:
                unscored.append((i, doc))

        # 首页首屏不能被外部 LLM 调用阻塞；未缓存的新闻使用规则质量分排序。
        if unscored:
            logger.info(
                "Skipping synchronous LLM importance scoring for dashboard",
                cached=len(cached),
                unscored=len(unscored),
            )
        return cached

    def _llm_score_batch(self, gateway, docs: list) -> Dict[str, float]:
        """Call LLM to score a batch of documents. Returns {doc_id: importance_score}."""
        # Build numbered news list for the prompt
        items: list[str] = []
        for i, doc in enumerate(docs):
            title = (doc.title or "")[:120]
            summary = (doc.summary or doc.content or "")[:200]
            text = f"{title}。{summary}" if summary else title
            items.append(f"[{i}] {text}")

        news_text = "\n\n".join(items)
        user_prompt = _IMPORTANCE_USER_PROMPT_TEMPLATE.format(news_list=news_text)

        try:
            response = gateway.chat(
                messages=[
                    {"role": "system", "content": _IMPORTANCE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=2048,
                task="classification",
                extra_body={"thinking": {"type": "disabled"}},
            )
            raw = response.content.strip()
        except Exception:
            logger.warning("LLM chat call failed", exc_info=True)
            return {}

        # Parse JSON response (handle markdown wrapping)
        if raw.startswith("```json"):
            raw = raw[7:]
        elif raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM importance response", extra={"raw": raw[:200]})
            return {}

        scores: Dict[str, float] = {}
        for item in parsed:
            try:
                idx = int(item["id"])
                score = max(0.0, min(1.0, float(item["importance"])))
                if 0 <= idx < len(docs):
                    scores[docs[idx].doc_id] = score
            except (KeyError, ValueError, IndexError):
                continue

        return scores

    def _get_related_symbols_for_doc(self, doc_id: str) -> List[str]:
        """获取文档相关的标的符号"""
        mentions = (
            self.session.query(EntityMentionV1DB)
            .filter(EntityMentionV1DB.doc_id == doc_id)
            .order_by(desc(EntityMentionV1DB.is_primary))
            .limit(10)
            .all()
        )

        symbols = []
        for mention in mentions:
            # 获取 Entity 的 canonical_id
            if mention.entity_id:
                entity = (
                    self.session.query(Entity).filter(Entity.entity_id == mention.entity_id).first()
                )
                if entity and entity.canonical_id:
                    symbols.append(entity.canonical_id)
            # 也可以直接使用 entity_name（如果它看起来像股票代码）
            elif mention.entity_name and len(mention.entity_name) <= 10:
                symbols.append(mention.entity_name)

        return symbols

    @staticmethod
    def _strip_headline_from_summary(title: str, summary: str) -> str:
        """从摘要中移除与标题重复的前缀（如【...】）"""
        if not summary:
            return summary
        import re

        # 移除开头的【标题内容】及其变体
        result = re.sub(r"^【[^】]*】\s*", "", summary, count=1)
        # 如果提取的标题不在括号中也尝试匹配
        if result == summary and title and len(title) > 3:
            if summary.startswith(title):
                result = summary[len(title) :].lstrip("，,。；;：:、\n\r ")
        return result

    @staticmethod
    def _extract_news_headline(summary: str, content: str, fallback: str) -> str:
        """从 summary 或 content 中提取有意义的新闻标题"""
        text = (summary or content or "").strip()
        if not text:
            return fallback

        # 尝试提取【...】中的内容作为标题
        import re

        bracket_match = re.search(r"【(.+?)】", text)
        if bracket_match:
            headline = bracket_match.group(1).strip()
            if len(headline) >= 4:
                return headline

        # 没有括号标题则取第一句
        for sep in ["。", "，", "、", "\n"]:
            if sep in text:
                return text.split(sep)[0].strip()[:100]

        return text[:100]

    def get_combined_global_news(self, limit: int = 10, days: int = 7) -> Tuple[List[Dict], bool]:
        """
        获取组合的全球新闻（优先事件，补充文档）

        Returns:
            (新闻列表, 是否使用了真实数据)
        """
        event_news = self.get_global_news_from_events(limit=limit, days=days)
        doc_news = self.get_global_news_from_documents(limit=limit, days=days)

        # 合并并去重（基于标题相似度）
        combined = []
        seen_titles = set()

        # 优先添加事件新闻
        for news in event_news:
            title_key = news["title"][:30].lower()
            if title_key not in seen_titles:
                combined.append(news)
                seen_titles.add(title_key)

        # 补充文档新闻
        for news in doc_news:
            title_key = news["title"][:30].lower()
            if title_key not in seen_titles and len(combined) < limit:
                combined.append(news)
                seen_titles.add(title_key)

        # 再次按重要性排序
        combined.sort(key=lambda x: x["importance_score"], reverse=True)

        has_real_data = len(combined) > 0
        return combined[:limit], has_real_data

    def get_sector_changes_from_signals(
        self, days: int = 7, limit_per_direction: int = 10
    ) -> Tuple[List[Dict], List[Dict], bool, float]:
        """
        从 AKShare 同花顺行业板块接口获取真实板块涨跌幅

        Returns:
            (上涨板块列表, 下跌板块列表, 是否使用了真实数据, 数据获取时间戳)
        """
        try:
            from data_layer.crawlers.akshare.board import (
                get_last_fetch_time,
                get_top_gainers,
                get_top_losers,
            )
        except ImportError:
            logger.warning("AKShare board module not available")
            return [], [], False, 0.0

        try:
            gainers = get_top_gainers(limit=limit_per_direction)
            losers = get_top_losers(limit=limit_per_direction)
        except Exception as e:
            logger.error(f"Failed to fetch sector board data: {e}")
            return [], [], False, 0.0

        fetched_at = get_last_fetch_time()

        up_sectors = []
        for s in gainers:
            if s.change_pct <= 0:
                continue
            up_sectors.append(
                {
                    "sector_id": f"sector-{hash(s.name) % 10000}",
                    "name": s.name,
                    "change_pct": round(s.change_pct, 2),
                    "leading_stocks": [],
                    "related_news_count": s.up_count + s.down_count,
                    "is_concept": self._is_concept_sector(s.name),
                }
            )

        down_sectors = []
        for s in losers:
            if s.change_pct >= 0:
                continue
            down_sectors.append(
                {
                    "sector_id": f"sector-{hash(s.name) % 10000}",
                    "name": s.name,
                    "change_pct": round(s.change_pct, 2),
                    "leading_stocks": [],
                    "related_news_count": s.up_count + s.down_count,
                    "is_concept": self._is_concept_sector(s.name),
                }
            )

        has_real_data = bool(up_sectors or down_sectors)
        return up_sectors, down_sectors, has_real_data, fetched_at

    def _is_concept_sector(self, name: str) -> bool:
        """判断是否为概念板块（而非传统行业）"""
        concept_keywords = [
            # AI / 人工智能
            "AI",
            "人工智能",
            "ChatGPT",
            "AIGC",
            "大模型",
            "具身智能",
            "人形机器人",
            "脑机接口",
            "机器人",
            "智能体",
            "Agent",
            "机器学习",
            "深度学习",
            "神经网络",
            "GPU",
            "NPU",
            "TPU",
            # 元宇宙 / 虚拟
            "元宇宙",
            "区块链",
            "Web3",
            "NFT",
            "数字孪生",
            "VR",
            "AR",
            "MR",
            "虚拟现实",
            "增强现实",
            "混合现实",
            "虚拟人",
            "数字人",
            "虚拟数字人",
            # 互联网 / 新媒体
            "网红",
            "直播",
            "短视频",
            "私域",
            "跨境电商",
            "社区团购",
            "互联网",
            "电商",
            "小程序",
            "社交",
            "平台经济",
            "共享经济",
            "在线",
            "线上",
            # 数字经济 / 算力
            "数字经济",
            "数据要素",
            "数据确权",
            "东数西算",
            "算力",
            "云计算",
            "大数据",
            "数据中心",
            "边缘计算",
            "算力网络",
            "数字",
            "数据",
            # 碳中和
            "碳中和",
            "碳交易",
            "碳捕捉",
            "CCUS",
            "碳达峰",
            "碳减排",
            "绿色",
            "新能源",
            "清洁能源",
            # 智能驾驶
            "自动驾驶",
            "无人驾驶",
            "智能座舱",
            "车路协同",
            "飞行汽车",
            "eVTOL",
            "低空经济",
            "智能汽车",
            "智能网联",
            "智慧交通",
            # 新消费
            "医美",
            "预制菜",
            "露营",
            "盲盒",
            "电子烟",
            "新消费",
            "新零售",
            "国潮",
            "潮玩",
            "谷子经济",
            "宠物",
            "美妆",
            "颜值经济",
            "单身经济",
            "银发经济",
            "代糖",
            "植物肉",
            "功能性食品",
            # 生物技术
            "创新药",
            "CXO",
            "CRO",
            "CDMO",
            "基因编辑",
            "细胞治疗",
            "合成生物",
            "基因",
            "免疫治疗",
            "mRNA",
            "ADC",
            "双抗",
            "CAR-T",
            "精准医疗",
            "再生医学",
            "生物制药",
            # 信创 / 国产替代
            "信创",
            "国产替代",
            "鸿蒙",
            "欧拉",
            "国产",
            "自主可控",
            "国产化",
            # 前沿技术
            "量子",
            "6G",
            "超导",
            "可控核聚变",
            "钙钛矿",
            "固态电池",
            "室温超导",
            "拓扑绝缘体",
            "纳米",
            "石墨烯",
            "液态金属",
            # 新兴制造
            "工业互联网",
            "专精特新",
            "新型工业化",
            "3D打印",
            "增材制造",
            "智能制造",
            # 太空 / 深海
            "航天",
            "商业航天",
            "卫星互联网",
            "北斗",
            "太空",
            "深海",
            "深地",
            "深空",
            # 金融科技
            "金融科技",
            "数字货币",
            "移动支付",
            "第三方支付",
            "跨境支付",
            "数字人民币",
            "金融IT",
            # 游戏 / 电竞 / 文化娱乐
            "游戏",
            "电竞",
            "动漫",
            "二次元",
            "IP经济",
            "网文",
            "短视频",
            "MCN",
            "自媒体",
            "内容创作",
            # 安全
            "网络安全",
            "数据安全",
            "信息安全",
            "安防",
            # 新材料
            "新材料",
            "碳纤维",
            "高温合金",
            "钛合金",
            "稀土永磁",
            # 泛科技概念
            "智能",
            "智慧",
            "物联网",
            "车联网",
            "工业软件",
            "SaaS",
            "PaaS",
            "API",
            "开源",
            "RISC-V",
            # 教育
            "在线教育",
            "素质教育",
            "职业教育",
            # 体育 / 健康
            "体育",
            "健身",
            "户外",
            "极限运动",
            # 其他概念
            "外贸",
            "出海",
            "RCEP",
            "一带一路",
            "自贸区",
            "国企改革",
            "混改",
            "重组",
            "借壳",
            "高股息",
            "高分红",
            "破净",
            "回购",
            "美容",
            "护理",
            "医美",
            "轻医美",
            "抗衰老",
            "微短剧",
            "短剧",
        ]
        traditional_keywords = [
            # 能源资源
            "煤炭",
            "石油",
            "天然气",
            "电力",
            "水力",
            "火力",
            "油气",
            "油田",
            "燃气",
            "供暖",
            # 金属矿产
            "钢铁",
            "有色",
            "贵金属",
            "黄金",
            "稀土",
            "矿产",
            "金属",
            "采矿",
            "冶炼",
            "锻造",
            "铸造",
            "铜",
            "铝",
            "锌",
            "铅",
            "镍",
            "锡",
            "锂矿",
            # 金融
            "银行",
            "保险",
            "证券",
            "期货",
            "信托",
            "金融",
            "多元金融",
            "资产管理",
            "基金",
            "租赁",
            "担保",
            "典当",
            "拍卖",
            "不良资产",
            # 地产基建
            "房地产",
            "建筑",
            "建材",
            "水泥",
            "玻璃",
            "装修",
            "地产",
            "物业",
            "不动产",
            # 交通物流
            "交通运输",
            "物流",
            "铁路",
            "公路",
            "港口",
            "航运",
            "航空",
            "机场",
            "高速公路",
            "快递",
            "轨交",
            "高铁",
            "地铁",
            "公交",
            "出租",
            "运输",
            # 消费
            "食品",
            "饮料",
            "白酒",
            "啤酒",
            "乳业",
            "调味品",
            "零售",
            "百货",
            "超市",
            "家电",
            "家居",
            "纺织",
            "服装",
            "造纸",
            "包装",
            "厨卫",
            "电器",
            "小家电",
            "厨房",
            "卫生",
            "香烟",
            "烟草",
            "酿酒",
            # 汽车
            "汽车",
            "摩托车",
            "乘用车",
            "商用车",
            "重卡",
            "轻卡",
            "客车",
            "轿车",
            "SUV",
            "电动车",
            # 医药
            "医药",
            "医疗",
            "中药",
            "化药",
            "生物制品",
            "医疗器械",
            "药店",
            "药房",
            "制剂",
            "原料药",
            "疫苗",
            "血制品",
            "诊断",
            "体外诊断",
            "IVD",
            # 农业
            "农业",
            "林业",
            "牧业",
            "渔业",
            "化肥",
            "农药",
            "饲料",
            "养殖",
            "种业",
            "种子",
            "种植",
            "畜牧",
            "水产",
            "农产品",
            "农化",
            "农机",
            "农资",
            # 化工
            "化工",
            "化学",
            "塑料",
            "橡胶",
            "石化",
            "炼化",
            "煤化工",
            "盐化工",
            "精细化工",
            # 机械设备
            "机械",
            "通用设备",
            "专用设备",
            "工程机械",
            "仪器仪表",
            "设备",
            "电机",
            "机床",
            "泵",
            "阀",
            "轴承",
            "齿轮",
            "模具",
            "刀具",
            "量具",
            "自动化",
            # 军工
            "军工",
            "航天",
            "航空装备",
            "船舶",
            "武器",
            "弹药",
            "雷达",
            "电子对抗",
            # 公用事业
            "水务",
            "燃气",
            "供热",
            "环保",
            "环卫",
            "供水",
            "排水",
            "污水处理",
            "固废",
            "危废",
            "环境",
            "治理",
            "监测",
            "园林",
            # 传媒
            "出版",
            "广告",
            "广电",
            "影视",
            "报纸",
            "杂志",
            "图书",
            "传媒",
            # 通信
            "通信",
            "电信",
            "卫星",
            # 电子
            "电子",
            "半导体",
            "元件",
            "光学",
            "光电子",
            "芯片",
            "LED",
            "OLED",
            "MiniLED",
            "MicroLED",
            "PCB",
            "FPC",
            "传感器",
            "连接器",
            "电容器",
            "电阻",
            "电感",
            "集成电路",
            "IC",
            "晶圆",
            # 计算机
            "计算机",
            "软件",
            "IT服务",
            "信息服务",
            # 商贸
            "贸易",
            "商业",
            "批发",
            "零售",
            "连锁",
            "供应链",
            # 旅游
            "旅游",
            "酒店",
            "餐饮",
            "景区",
            # 新能源制造（实体制造 → 板块，不是概念）
            "光伏",
            "风电",
            "储能",
            "锂电池",
            "电池",
            "新能源车",
            "充电桩",
            # 教育
            "教育",
            "体育",
            "学校",
            "培训",
            "考试",
            "留学",
            # 其他制造
            "钢铁",
            "金属",
            "采矿",
            "冶炼",
            "锻造",
            "铸造",
            "纺织",
            "印染",
            "皮革",
            "家具",
            "木材",
            # 电力设备
            "电网",
            "电缆",
            "变压器",
            "开关",
            "配电",
            "发电",
            "火电",
            "水电",
            "核电",
            "光电",
            "风电",
            "电力设备",
            "电源",
            # 社会服务
            "社会服务",
            "职业",
            "人力资源",
            "劳务",
            "咨询",
            "检测",
            "认证",
            # 综合类
            "综合",
            # 建筑装饰
            "装饰",
            "幕墙",
            "钢结构",
            "防水",
            # 地产链
            "地产",
            "开发",
            "中介",
        ]

        name_lower = name.lower()
        has_concept = any(k.lower() in name_lower for k in concept_keywords)
        has_traditional = any(k in name for k in traditional_keywords)

        return has_concept and not has_traditional

    def get_recent_crawled_documents(
        self, limit: int = 20, since: str = None, source_type: str = None
    ) -> Dict[str, Any]:
        """
        获取最近抓取的文档（用于首页实时抓取流）

        Args:
            limit: 返回数量上限
            since: ISO 时间戳，只返回此时间之后的数据（增量查询）
            source_type: 按来源类型过滤 (cls / cnstock / zhiqiu_reports)

        Returns:
            {"items": [...], "total_today": N, "last_crawled_at": "..."}
        """
        base_query = self.session.query(DocumentV1DB)
        if source_type:
            base_query = base_query.filter(DocumentV1DB.source_type == source_type)
        if source_type == "zhiqiu_reports":
            base_query = base_query.filter(~DocumentV1DB.content.like('{"OBJID"%'))

        # Today's total count: prefer timeliness.publish_time, fall back to created_at
        today_str = datetime.now().strftime("%Y-%m-%d")
        publish_or_created_coalesce = func.coalesce(
            func.json_extract_path_text(DocumentV1DB.timeliness, "publish_time"),
            cast(DocumentV1DB.created_at, String),
        )
        total_today = base_query.filter(publish_or_created_coalesce.like(f"{today_str}%")).count()

        query = base_query
        if since:
            try:
                since_dt = datetime.fromisoformat(since)
                query = query.filter(DocumentV1DB.created_at > since_dt)
            except (ValueError, TypeError):
                pass

        publish_or_created = func.coalesce(
            func.json_extract_path_text(DocumentV1DB.timeliness, "publish_time"),
            cast(DocumentV1DB.created_at, String),
        )
        if source_type == "zhiqiu_reports":
            documents = query.order_by(desc(DocumentV1DB.created_at)).limit(limit).all()
        else:
            documents = query.order_by(desc(publish_or_created)).limit(limit).all()

        results = []
        for doc in documents:
            normalized_text = _normalize_crawl_document_text(doc)
            published_at = ""
            timeliness = doc.timeliness or {}
            publish_time = timeliness.get("publish_time") if isinstance(timeliness, dict) else None
            if publish_time:
                if hasattr(publish_time, "isoformat"):
                    published_at = publish_time.isoformat()
                else:
                    published_at = str(publish_time)
            if not published_at and doc.created_at:
                published_at = doc.created_at.isoformat()

            results.append(
                {
                    "doc_id": doc.doc_id,
                    "title": normalized_text["title"],
                    "raw_title": normalized_text["raw_title"],
                    "summary": normalized_text["summary"],
                    "content": normalized_text["content"],
                    "has_content": normalized_text["has_content"],
                    "source_type": doc.source_type or "",
                    "source_name": doc.source_name or "",
                    "doc_type": doc.doc_type or "",
                    "url": doc.source_url or "",
                    "published_at": published_at,
                    "crawled_at": doc.created_at.isoformat() if doc.created_at else "",
                }
            )

        # 最近一次爬虫执行时间：取该 source 最新入队记录的 created_at
        last_crawl = (
            self.session.query(IngestionQueueItemDB.created_at)
            .filter(IngestionQueueItemDB.source_type == source_type)
            .order_by(desc(IngestionQueueItemDB.created_at))
            .first()
        )
        last_crawled_at = last_crawl[0].isoformat() if last_crawl and last_crawl[0] else None

        return {
            "items": results,
            "total_today": total_today,
            "last_crawled_at": last_crawled_at,
        }

    def has_enough_data(self) -> bool:
        """检查是否有足够的真实数据"""

        doc_count = self.session.query(func.count(DocumentV1DB.doc_id)).scalar()
        event_count = self.session.query(func.count(CanonicalEvent.event_id)).scalar()
        signal_count = self.session.query(func.count(AlphaSignalDB.signal_id)).scalar()

        return doc_count >= 5 or event_count >= 3 or signal_count >= 3
