"""PDF 解析器"""
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from core.observability import get_logger

logger = get_logger(__name__)


@dataclass
class PDFParseResult:
    """PDF 解析结果"""

    text: str
    metadata: dict[str, Any]
    pages: int


class PDFParser:
    """PDF 文档解析器"""

    def __init__(self, chunk_size: int = 2000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def parse(self, pdf_source: Path | bytes) -> PDFParseResult:
        """解析 PDF 文件"""
        try:
            import pdfplumber
        except ImportError:
            logger.error("pdfplumber not installed. Please install it first.")
            raise

        if isinstance(pdf_source, Path):
            pdf = pdfplumber.open(pdf_source)
            source_path = str(pdf_source)
        else:
            pdf = pdfplumber.open(BytesIO(pdf_source))
            source_path = None

        try:
            full_text = []
            metadata = self._extract_metadata(pdf.metadata)

            for page_num, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text() or ""
                if page_text.strip():
                    full_text.append(f"--- Page {page_num} ---\n{page_text}")

            combined_text = "\n".join(full_text)
            cleaned_text = self._clean_text(combined_text)

            result = PDFParseResult(
                text=cleaned_text,
                metadata={
                    **metadata,
                    "pages": len(pdf.pages),
                    "source_path": source_path,
                },
                pages=len(pdf.pages),
            )

            logger.info(f"Successfully parsed PDF: {len(pdf.pages)} pages")
            return result

        finally:
            pdf.close()

    def _extract_metadata(self, pdf_metadata: dict[str, Any]) -> dict[str, Any]:
        """提取 PDF 元数据"""
        metadata = {}
        for key, value in pdf_metadata.items():
            if value:
                if isinstance(value, bytes):
                    try:
                        value = value.decode("utf-8", errors="ignore")
                    except Exception:
                        continue
                metadata[key.lower()] = str(value).strip()
        return metadata

    def _clean_text(self, text: str) -> str:
        """清洗文本"""
        # 去除多余的空行
        text = re.sub(r"\n\s*\n", "\n\n", text)
        # 去除行尾空格
        text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
        # 去除不可见字符（保留换行、制表符等基本空白字符）
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        return text.strip()

    def split_chunks(self, text: str) -> list[str]:
        """将文本分割为块"""
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0
        text_length = len(text)

        while start < text_length:
            end = start + self.chunk_size
            if end > text_length:
                end = text_length

            chunk = text[start:end]

            # 尝试在句子或段落边界处分割
            if end < text_length:
                # 查找合适的分割点
                split_points = [
                    chunk.rfind("\n\n"),
                    chunk.rfind("。\n"),
                    chunk.rfind("！\n"),
                    chunk.rfind("？\n"),
                    chunk.rfind("\n"),
                ]

                valid_splits = [p for p in split_points if p > self.chunk_size // 2]
                if valid_splits:
                    split_pos = max(valid_splits)
                    chunk = chunk[: split_pos + 1]
                    end = start + len(chunk)

            chunks.append(chunk.strip())
            start = end - self.chunk_overlap

        logger.debug(f"Split text into {len(chunks)} chunks")
        return chunks
