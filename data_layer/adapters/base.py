"""数据适配器基类"""
from abc import ABC
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from core.contracts import DocumentEnvelope
from core.interfaces import DataAdapter
from core.observability import get_logger

logger = get_logger(__name__)


class BaseDataAdapter(DataAdapter, ABC):
    """数据适配器抽象基类"""

    def __init__(self, source_type: str):
        self.source_type = source_type

    def _generate_idempotency_key(self, content: str | bytes) -> str:
        """生成幂等键，用于去重"""
        if isinstance(content, str):
            content_bytes = content.encode("utf-8")
        else:
            content_bytes = content
        return sha256(content_bytes).hexdigest()

    def _create_document_envelope(
        self,
        content: str,
        title: str | None = None,
        source_path: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DocumentEnvelope:
        """创建 DocumentEnvelope"""
        doc_id = self._generate_idempotency_key(content)
        now = datetime.utcnow()

        return DocumentEnvelope(
            doc_id=doc_id,
            title=title or f"Document-{now.strftime('%Y%m%d%H%M%S')}",
            raw_text=content,
            canonical_text=content,
            source_type=self.source_type,
            source_name=self.source_type,
            published_at=now,
            metadata=metadata or {},
        )

    def fetch_batch(
        self, sources: list[Path | str | bytes], **kwargs: Any
    ) -> list[DocumentEnvelope]:
        """批量获取数据"""
        results = []
        for source in sources:
            try:
                result = self.parse(source, **kwargs)
                results.append(result)
                logger.debug(f"Successfully parsed source: {source!r}")
            except Exception as e:
                logger.error(f"Failed to parse source {source!r}: {e}", exc_info=True)
        return results
