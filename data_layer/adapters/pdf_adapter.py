"""PDF 数据适配器"""
from pathlib import Path
from typing import Any

from core.contracts import DocumentEnvelope
from core.observability import get_logger
from data_layer.adapters.base import BaseDataAdapter
from data_layer.parsers.pdf_parser import PDFParser

logger = get_logger(__name__)


class PDFAdapter(BaseDataAdapter):
    """PDF 文件数据适配器"""

    def __init__(self, chunk_size: int = 2000, chunk_overlap: int = 200):
        super().__init__(source_type="pdf")
        self.parser = PDFParser(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    def fetch(self, **kwargs: Any) -> list[DocumentEnvelope]:
        """
        获取 PDF 文档

        kwargs:
            directory: Path - 目录路径，扫描该目录下的所有 PDF
            pattern: str - 文件匹配模式，默认 "*.pdf"
            recursive: bool - 是否递归扫描，默认 False
        """
        directory = kwargs.get("directory")
        if not directory:
            raise ValueError("directory is required for fetch")

        directory = Path(directory)
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        pattern = kwargs.get("pattern", "*.pdf")
        recursive = kwargs.get("recursive", False)

        logger.info(f"Scanning PDF files in {directory} (pattern: {pattern})")

        if recursive:
            pdf_files = list(directory.rglob(pattern))
        else:
            pdf_files = list(directory.glob(pattern))

        logger.info(f"Found {len(pdf_files)} PDF files")

        return self.fetch_batch(pdf_files, **kwargs)

    def parse(self, source: Path | bytes | str, **kwargs: Any) -> DocumentEnvelope:
        """解析 PDF 文件"""
        if isinstance(source, str):
            source = Path(source)

        logger.debug(f"Parsing PDF: {source if isinstance(source, Path) else 'bytes'}")

        parse_result = self.parser.parse(source)

        title = self._extract_title(parse_result.metadata, source)

        return self._create_document_envelope(
            content=parse_result.text,
            title=title,
            source_path=str(source) if isinstance(source, Path) else None,
            metadata=parse_result.metadata,
        )

    def _extract_title(self, metadata: dict[str, Any], source: Path | bytes) -> str:
        """从元数据或文件名中提取标题"""
        # 尝试从元数据获取
        title = metadata.get("title") or metadata.get("Title")
        if title and title.strip():
            return title.strip()

        # 尝试从文件名获取
        if isinstance(source, Path):
            return source.stem

        return "Untitled PDF"
