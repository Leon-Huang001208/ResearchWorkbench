"""按需补全实时事件流正文。"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any, Dict, Optional

from core.observability import get_logger
from data_layer.adapters.cnstock_adapter import _clean_content_body
from data_layer.repositories.dashboard_data import _normalize_crawl_document_text
from data_layer.repositories.models import DocumentV1DB

logger = get_logger(__name__)


class CNStockArticleContentFetcher:
    """中国证券网详情页正文抓取器。

    实时列表抓取不能等待正文详情；这里仅在用户打开详情时尝试一次。
    """

    def fetch(self, *, article_id: str, url: str) -> Dict[str, str]:
        from data_layer.crawlers.cnstock.cnstock import CnstockConfig, CnstockCrawler

        today = datetime.now().strftime("%Y-%m-%d")
        crawler = CnstockCrawler(
            CnstockConfig(
                start_date=today,
                end_date=today,
                fetch_content=False,
                verbose=False,
            )
        )
        crawler.initialize()
        return crawler._fetch_article_content(article_id, url, max_retries=0)


class CrawlFeedContentService:
    """为实时事件流详情按需补正文。"""

    SUPPORTED_SOURCES = {"cnstock", "cnstock_flash"}

    def __init__(self, session, fetcher: Optional[Any] = None):
        self.session = session
        self.fetcher = fetcher or CNStockArticleContentFetcher()

    def refresh_content(self, doc_id: str) -> Dict[str, Any]:
        doc = self.session.get(DocumentV1DB, doc_id)
        if not doc:
            return {"success": False, "reason": "not_found", "message": "文档不存在"}

        if doc.source_type not in self.SUPPORTED_SOURCES:
            return {
                "success": False,
                "reason": "unsupported_source",
                "message": "当前来源暂不支持按需补正文",
            }

        normalized = _normalize_crawl_document_text(doc)
        if normalized["has_content"]:
            return self._result(doc, cached=True)

        article_id = self._article_id_for(doc)
        url = doc.source_url or ""
        if not article_id and not url:
            self._mark_refresh(doc, "missing_article_ref")
            return {
                "success": False,
                "reason": "missing_article_ref",
                "message": "缺少文章链接，无法补抓正文",
            }

        try:
            detail = self.fetcher.fetch(article_id=article_id, url=url)
        except Exception as exc:
            logger.warning(
                "cnstock_content_refresh_failed",
                extra={"doc_id": doc_id, "error": str(exc)},
                exc_info=True,
            )
            self._mark_refresh(doc, "failed", str(exc))
            return {"success": False, "reason": "fetch_failed", "message": str(exc)}

        content_text = _clean_content_body((detail or {}).get("content_text", ""))
        if not content_text:
            self._mark_refresh(doc, "empty")
            return {
                "success": False,
                "reason": "empty_content",
                "message": "中国证券网详情页暂未返回可读正文",
            }

        source_name = (detail or {}).get("source") or doc.source_name
        doc.content = f"{doc.title}\n{content_text}" if doc.title else content_text
        doc.source_name = source_name
        doc.content_hash = hashlib.sha256(doc.content.encode("utf-8")).hexdigest()
        self._mark_refresh(doc, "success")
        self.session.commit()
        self.session.refresh(doc)

        return self._result(doc, cached=False)

    def _result(self, doc: DocumentV1DB, *, cached: bool) -> Dict[str, Any]:
        normalized = _normalize_crawl_document_text(doc)
        return {
            "success": True,
            "cached": cached,
            "doc_id": doc.doc_id,
            "title": normalized["title"],
            "raw_title": normalized["raw_title"],
            "summary": normalized["summary"],
            "content": normalized["content"] or normalized["summary"],
            "has_content": normalized["has_content"],
            "source_name": doc.source_name or "",
            "url": doc.source_url or "",
        }

    def _article_id_for(self, doc: DocumentV1DB) -> str:
        metadata: dict[str, Any] = (
            doc.source_metadata if isinstance(doc.source_metadata, dict) else {}
        )
        article_id = str(metadata.get("article_id") or "").strip()
        if article_id:
            return article_id
        match = re.search(r"/commonDetail/(\d+)", str(doc.source_url or ""))
        return match.group(1) if match else ""

    def _mark_refresh(self, doc: DocumentV1DB, status: str, error: str = "") -> None:
        extra = dict(doc.extra or {})
        extra["content_refresh"] = {
            "status": status,
            "error": error,
            "refreshed_at": datetime.utcnow().isoformat(),
        }
        doc.extra = extra
        doc.updated_at = datetime.utcnow()
        self.session.commit()
