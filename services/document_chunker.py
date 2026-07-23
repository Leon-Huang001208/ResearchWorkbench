"""
文档分块服务 - Issue #44

根据文档类型，采用不同的分块策略：
- 电报/快讯：单条为一个块
- 新闻：按段落 + 长度限制
- 研报 PDF：按标题/小节/段落切分
- 会议纪要：按发言轮次或主题切分
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

from core.contracts import DocType, DocumentChunkV1, DocumentV1
from core.observability import get_logger
from core.utils.id_gen import generate_id

logger = get_logger(__name__)


class ChunkingStrategy(str, Enum):
    """分块策略"""

    SIMPLE = "simple"  # 简单固定长度
    PARAGRAPH = "paragraph"  # 按段落
    SEMANTIC = "semantic"  # 按语义单元（标题等）
    SPEAKER = "speaker"  # 按发言人（会议纪要）


@dataclass
class ChunkingOptions:
    """分块选项"""

    chunk_size: int = 2000  # 目标分块大小（字符数）
    chunk_overlap: int = 200  # 重叠大小
    min_chunk_size: int = 100  # 最小分块大小
    max_chunk_size: int = 4000  # 最大分块大小


class DocumentChunker:
    """文档分块器"""

    def __init__(self, options: Optional[ChunkingOptions] = None):
        self.options = options or ChunkingOptions()

    def chunk_document(self, doc: DocumentV1) -> List[DocumentChunkV1]:
        """
        分块文档

        Args:
            doc: 文档

        Returns:
            分块列表
        """
        logger.info(f"Chunking document: {doc.doc_id}, type: {doc.doc_type}")

        # 根据文档类型选择策略
        strategy = self._select_strategy(doc.doc_type)

        # 执行分块
        chunks = self._chunk_by_strategy(doc.content, strategy, doc.doc_type, self.options)

        # 构造 DocumentChunkV1 对象
        result_chunks: List[DocumentChunkV1] = []
        for i, chunk_text in enumerate(chunks):
            result_chunks.append(
                DocumentChunkV1(
                    chunk_id=generate_id(),
                    doc_id=doc.doc_id,
                    chunk_index=i,
                    chunk_type=str(strategy),
                    title=self._extract_chunk_title(chunk_text, i),
                    content=chunk_text,
                    token_count=len(chunk_text) // 4,  # 粗略估计
                    topics=[],
                    entities=[],
                    summary=None,
                    embedding=None,
                    metadata={
                        "strategy": str(strategy),
                        "doc_type": doc.doc_type.value if doc.doc_type else None,
                    },
                )
            )

        logger.info(f"Chunked document into {len(result_chunks)} chunks")
        return result_chunks

    def _select_strategy(self, doc_type: Optional[DocType]) -> ChunkingStrategy:
        """选择分块策略"""
        if not doc_type:
            return ChunkingStrategy.PARAGRAPH

        strategy_map = {
            DocType.TELEGRAM: ChunkingStrategy.SIMPLE,  # 电报通常较短
            DocType.NEWS: ChunkingStrategy.PARAGRAPH,
            DocType.COMMENTARY: ChunkingStrategy.PARAGRAPH,
            DocType.REPORT: ChunkingStrategy.SEMANTIC,
            DocType.WECHAT: ChunkingStrategy.PARAGRAPH,
            DocType.TRANSCRIPT: ChunkingStrategy.SPEAKER,
            DocType.FILING: ChunkingStrategy.SEMANTIC,
            DocType.POLICY: ChunkingStrategy.SEMANTIC,
            DocType.INTERNAL_NOTE: ChunkingStrategy.PARAGRAPH,
        }

        return strategy_map.get(doc_type, ChunkingStrategy.PARAGRAPH)

    def _chunk_by_strategy(
        self,
        text: str,
        strategy: ChunkingStrategy,
        doc_type: Optional[DocType],
        options: ChunkingOptions,
    ) -> List[str]:
        """按策略分块"""
        if strategy == ChunkingStrategy.SIMPLE:
            return self._chunk_simple(text, options)
        elif strategy == ChunkingStrategy.PARAGRAPH:
            return self._chunk_by_paragraph(text, options)
        elif strategy == ChunkingStrategy.SEMANTIC:
            return self._chunk_semantic(text, options)
        elif strategy == ChunkingStrategy.SPEAKER:
            return self._chunk_by_speaker(text, options)
        else:
            return self._chunk_simple(text, options)

    def _chunk_simple(self, text: str, options: ChunkingOptions) -> List[str]:
        """简单固定长度分块"""
        if len(text) <= options.max_chunk_size:
            return [text.strip()] if text.strip() else []

        chunks: List[str] = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + options.chunk_size, text_len)

            # 尝试在边界处切分
            if end < text_len:
                split_positions = [
                    text.rfind("\n\n", start, end),
                    text.rfind("\n", start, end),
                    text.rfind("。", start, end),
                    text.rfind("！", start, end),
                    text.rfind("？", start, end),
                ]
                min_split = start + options.chunk_overlap + options.min_chunk_size
                valid_splits = [p for p in split_positions if p > min_split]
                if valid_splits:
                    end = max(valid_splits) + 1

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            if end == text_len:
                break

            next_start = end - options.chunk_overlap
            if next_start <= start:
                next_start = end
            start = next_start

        return chunks

    def _chunk_by_paragraph(self, text: str, options: ChunkingOptions) -> List[str]:
        """按段落分块"""
        # 先按段落拆分
        raw_paragraphs = re.split(r"\n\s*\n", text.strip())
        paragraphs = [p.strip() for p in raw_paragraphs if p.strip()]

        chunks: List[str] = []
        current_chunk: List[str] = []
        current_length = 0

        for para in paragraphs:
            para_length = len(para)

            # 如果当前段落就超长，单独切分
            if para_length > options.max_chunk_size:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = []
                    current_length = 0

                # 切分长段落
                sub_chunks = self._chunk_simple(para, options)
                chunks.extend(sub_chunks)
                continue

            # 如果加上这个段落会超过目标大小，先输出当前块
            if current_length + para_length > options.chunk_size and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_length = para_length
            else:
                current_chunk.append(para)
                current_length += para_length

        # 处理剩余内容
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks

    def _chunk_semantic(self, text: str, options: ChunkingOptions) -> List[str]:
        """按语义单元分块（标题、小节等）"""
        # 先尝试按常见标题模式切分
        lines = text.split("\n")
        chunks: List[str] = []
        current_chunk: List[str] = []
        current_length = 0

        for line in lines:
            line = line.rstrip()
            line_length = len(line) + 1  # 加上换行符

            # 检查是否是标题行
            is_heading = self._is_heading_line(line)

            # 如果是标题且当前块已有内容，先输出
            if is_heading and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = [line]
                current_length = line_length
                continue

            # 如果加上这行会超过目标大小
            if current_length + line_length > options.chunk_size and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = [line]
                current_length = line_length
            else:
                current_chunk.append(line)
                current_length += line_length

        # 处理剩余内容
        if current_chunk:
            chunks.append("\n".join(current_chunk))

        # 合并过小的块
        merged_chunks = self._merge_small_chunks(chunks, options.min_chunk_size)

        # 对超长块再次切分
        final_chunks: List[str] = []
        for chunk in merged_chunks:
            if len(chunk) > options.max_chunk_size:
                final_chunks.extend(self._chunk_simple(chunk, options))
            else:
                final_chunks.append(chunk)

        return final_chunks

    def _chunk_by_speaker(self, text: str, options: ChunkingOptions) -> List[str]:
        """按发言人分块（会议纪要）"""
        # 常见发言人模式
        speaker_patterns = [
            r"^[\s]*[一-龥]{2,4}[:：]",  # 中文人名 + 冒号
            r"^[\s]*[A-Za-z\s]+[:：]",  # 英文名 + 冒号
            r"^[\s]*Q[:：]",  # Q:
            r"^[\s]*A[:：]",  # A:
            r"^[\s]*问[:：]",
            r"^[\s]*答[:：]",
        ]

        combined_pattern = "|".join(f"({p})" for p in speaker_patterns)

        # 按发言人分割
        segments: List[Tuple[str, str]] = []
        current_speaker = ""
        current_text: List[str] = []

        for line in text.split("\n"):
            speaker_match = re.match(combined_pattern, line)
            if speaker_match:
                # 保存之前的
                if current_speaker and current_text:
                    segments.append((current_speaker, "\n".join(current_text)))

                # 开始新的发言人
                speaker_part = speaker_match.group(0).strip()
                current_speaker = speaker_part.rstrip("：:").strip()
                content_part = line[len(speaker_match.group(0)) :].strip()
                current_text = [content_part] if content_part else []
            else:
                current_text.append(line)

        # 保存最后一段
        if current_speaker and current_text:
            segments.append((current_speaker, "\n".join(current_text)))
        elif current_text and any(t.strip() for t in current_text):
            # 无发言人的剩余内容
            segments.append(("", "\n".join(current_text)))

        # 合并相邻相同发言人的段落
        merged_segments: List[Tuple[str, str]] = []
        for speaker, seg_text in segments:
            if merged_segments and merged_segments[-1][0] == speaker:
                merged_segments[-1] = (speaker, merged_segments[-1][1] + "\n" + seg_text)
            else:
                merged_segments.append((speaker, seg_text))

        # 生成最终块
        chunks: List[str] = []
        current_chunk: List[str] = []
        current_length = 0

        for speaker, seg_text in merged_segments:
            block = f"{speaker}：\n{seg_text}" if speaker else seg_text
            block_length = len(block)

            if block_length > options.max_chunk_size:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = []
                    current_length = 0
                sub_chunks = self._chunk_simple(block, options)
                chunks.extend(sub_chunks)
            elif current_length + block_length > options.chunk_size and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [block]
                current_length = block_length
            else:
                current_chunk.append(block)
                current_length += block_length

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks

    def _is_heading_line(self, line: str) -> bool:
        """判断是否是标题行"""
        stripped = line.strip()

        # 太短不是标题
        if len(stripped) < 2 or len(stripped) > 100:
            return False

        # 常见标题模式
        heading_patterns = [
            r"^[一二三四五六七八九十]+[、\.]",  # 中文数字序号
            r"^[0-9]+[、\.\s]",  # 阿拉伯数字序号
            r"^第[一二三四五六七八九十百]+[章节篇节条]",  # 第X章/节
            r"^【.*】$",  # 【标题】
            r"^[A-Z][A-Za-z0-9\s]+$",  # 全大写英文
            r"^\s*[#]+",  # Markdown 标题
        ]

        for pattern in heading_patterns:
            if re.match(pattern, stripped):
                return True

        return False

    def _merge_small_chunks(self, chunks: List[str], min_size: int) -> List[str]:
        """合并过小的块"""
        if len(chunks) <= 1:
            return chunks

        merged: List[str] = []
        current: List[str] = []
        current_len = 0

        for chunk in chunks:
            chunk_len = len(chunk)
            if current_len + chunk_len < min_size * 2:
                current.append(chunk)
                current_len += chunk_len
            else:
                if current:
                    merged.append("\n\n".join(current))
                current = [chunk]
                current_len = chunk_len

        if current:
            if current_len < min_size and merged:
                merged[-1] = merged[-1] + "\n\n" + "\n\n".join(current)
            else:
                merged.append("\n\n".join(current))

        return merged

    def _extract_chunk_title(self, chunk_text: str, index: int) -> Optional[str]:
        """从分块中提取标题"""
        lines = chunk_text.strip().split("\n")
        for line in lines[:3]:  # 检查前3行
            stripped = line.strip()
            if self._is_heading_line(stripped):
                # 清理标题
                cleaned = re.sub(r"^[#\s]*", "", stripped)
                cleaned = re.sub(r"^【|】$", "", cleaned)
                if cleaned:
                    return cleaned[:200]

        # 如果没有标题，返回第一句话
        first_sentence = re.split(r"[。！？.!?]", chunk_text.strip())[0]
        if first_sentence:
            return first_sentence[:200]

        return f"Chunk {index}"
