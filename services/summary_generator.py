"""
文档总结生成器 - Issue #44

提供多种总结方式：
- 简短摘要
- 要点列表
- 章节总结
"""
import re
from typing import List, Optional

from core.contracts import DocumentSummaryV1, DocumentV1
from core.observability import get_logger
from core.utils.id_gen import generate_id

logger = get_logger(__name__)


class SummaryGenerator:
    """总结生成器"""

    def __init__(self):
        self.max_short_summary_len = 200
        self.max_bullets = 5

    def generate_short_summary(self, doc: DocumentV1, update_doc: bool = True) -> str:
        """
        生成简短摘要

        Args:
            doc: 文档
            update_doc: 是否更新文档

        Returns:
            简短摘要
        """
        # 1. 如果已有标题和摘要，直接使用
        if doc.summary:
            return doc.summary

        # 2. 从内容中提取
        content = doc.content

        # 先尝试找第一段
        paragraphs = re.split(r"\n\s*\n", content.strip())
        if paragraphs:
            first_para = paragraphs[0].strip()

            # 如果第一段长度合适
            if len(first_para) <= self.max_short_summary_len:
                summary = first_para
            else:
                # 截取第一句话
                first_sentence = self._extract_first_sentence(first_para)
                if first_sentence:
                    summary = first_sentence
                else:
                    summary = first_para[: self.max_short_summary_len] + "..."
        else:
            # 如果没有分段，直接截取
            summary = content[: self.max_short_summary_len] + "..."

        # 如果有标题，结合起来
        if doc.title and doc.title not in summary:
            summary = f"{doc.title}。{summary}"

        # 更新文档
        if update_doc:
            doc.summary = summary

        return summary

    def generate_bullet_points(
        self, doc: DocumentV1, num_bullets: Optional[int] = None
    ) -> List[str]:
        """
        生成要点列表

        Args:
            doc: 文档
            num_bullets: 要点数量

        Returns:
            要点列表
        """
        if num_bullets is None:
            num_bullets = self.max_bullets

        content = doc.content
        bullets: List[str] = []

        # 1. 尝试提取现有的列表项
        list_items = self._extract_list_items(content)
        if list_items:
            bullets.extend(list_items[:num_bullets])

        if len(bullets) >= num_bullets:
            return bullets[:num_bullets]

        # 2. 提取关键句子
        key_sentences = self._extract_key_sentences(content, num_bullets - len(bullets))
        bullets.extend(key_sentences)

        return bullets[:num_bullets]

    def generate_document_summary(
        self, doc: DocumentV1, summary_type: str = "short"
    ) -> DocumentSummaryV1:
        """
        生成完整的 DocumentSummaryV1 对象

        Args:
            doc: 文档
            summary_type: 摘要类型

        Returns:
            DocumentSummaryV1 对象
        """
        short_summary = self.generate_short_summary(doc, update_doc=False)
        bullet_points = self.generate_bullet_points(doc)

        return DocumentSummaryV1(
            summary_id=generate_id(),
            doc_id=doc.doc_id,
            summary_type=summary_type,
            summary=short_summary,
            bullet_points=bullet_points,
            generator_version="v1.0",
            quality_score=0.7,
        )

    def _extract_first_sentence(self, text: str) -> Optional[str]:
        """提取第一句话"""
        # 中文句号
        match = re.search(r"([^。！？!?]+[。！？!?])", text)
        if match:
            return match.group(1).strip()

        # 如果没有明确的句子结束，尝试逗号或换行
        match = re.search(r"([^，,\n]+)", text)
        if match:
            return match.group(1).strip()

        return None

    def _extract_list_items(self, content: str) -> List[str]:
        """提取列表项"""
        items: List[str] = []

        # 常见的列表标记
        list_patterns = [
            r"^[0-9]+[、\.\)\s](.+)$",  # 数字列表
            r"^[一二三四五六七八九十]+[、\.\)\s](.+)$",  # 中文数字
            r"^[•\-\*]\s(.+)$",  # 项目符号
        ]

        lines = content.split("\n")
        for line in lines:
            stripped = line.strip()
            for pattern in list_patterns:
                match = re.match(pattern, stripped)
                if match:
                    item = match.group(1).strip()
                    if item and len(item) > 5:
                        items.append(item)
                    break

        return items

    def _extract_key_sentences(self, content: str, num_sentences: int) -> List[str]:
        """提取关键句子"""
        sentences = self._split_sentences(content)
        key_sentences: List[str] = []

        # 评分句子
        scored = []
        for s in sentences:
            score = self._score_sentence(s)
            if score > 0:
                scored.append((-score, s))  # 负分用于排序

        # 按分数排序
        scored.sort()
        key_sentences = [s for (neg_score, s) in scored[:num_sentences]]

        return key_sentences

    def _split_sentences(self, text: str) -> List[str]:
        """分割句子"""
        # 先按中文标点分割
        raw_sentences = re.split(r"([。！？!?])", text)

        # 重新组合（把标点放回）
        sentences = []
        for i in range(0, len(raw_sentences) - 1, 2):
            if i + 1 < len(raw_sentences):
                sentence = raw_sentences[i] + raw_sentences[i + 1]
                sentence = sentence.strip()
                if sentence:
                    sentences.append(sentence)

        # 添加最后一个（如果有）
        if len(raw_sentences) % 2 == 1 and raw_sentences[-1].strip():
            sentences.append(raw_sentences[-1].strip())

        return sentences

    def _score_sentence(self, sentence: str) -> float:
        """给句子评分"""
        score = 0.0
        s = sentence

        # 长度：太短或太长的分数低
        length = len(s)
        if length < 10:
            return 0.0
        if 20 <= length <= 100:
            score += 2.0
        elif 10 < length < 20 or 100 < length < 200:
            score += 1.0

        # 是否有数字/数据
        if any(c.isdigit() for c in s):
            score += 2.0

        # 是否有重要关键词
        keywords = [
            "宣布",
            "公告",
            "发布",
            "业绩",
            "增长",
            "净利润",
            "政策",
            "新规",
            "通知",
            "收购",
            "并购",
            "突破",
            "首款",
            "首次",
            "新",
        ]
        for kw in keywords:
            if kw in s:
                score += 1.5

        # 是否在开头
        # (这里不处理位置，因为我们没有上下文)

        return score
