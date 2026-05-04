"""
混合搜索 - 向量+关键词
"""
from typing import Any, Dict, List, Optional

from core.observability import get_logger
from knowledge_layer.retrieval.vector_store import VectorStore

logger = get_logger(__name__)


class HybridSearcher:
    """混合搜索器"""

    def __init__(
        self,
        vector_store: VectorStore,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
    ):
        self._vector_store = vector_store
        self._vector_weight = vector_weight
        self._keyword_weight = keyword_weight

        # 简单的关键词索引（内存）
        self._keyword_index: Dict[str, List[str]] = {}  # keyword -> [doc_ids]
        self._doc_texts: Dict[str, str] = {}  # doc_id -> text

    def index_document(
        self,
        doc_id: str,
        text: str,
        metadata: Optional[Dict] = None,
    ) -> None:
        """
        索引文档

        Args:
            doc_id: 文档 ID
            text: 文档文本
            metadata: 元数据
        """
        # 添加到向量存储
        self._vector_store.add_document(doc_id, text, metadata)

        # 关键词索引
        keywords = self._extract_keywords(text)
        for keyword in keywords:
            if keyword not in self._keyword_index:
                self._keyword_index[keyword] = []
            if doc_id not in self._keyword_index[keyword]:
                self._keyword_index[keyword].append(doc_id)

        self._doc_texts[doc_id] = text

        logger.debug(f"Indexed document: {doc_id}")

    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict] = None,
    ) -> List[Dict]:
        """
        混合搜索

        Args:
            query: 查询文本
            top_k: 返回数量
            filters: 过滤条件

        Returns:
            搜索结果列表
        """
        # 1. 向量搜索
        vector_results = self._vector_store.search(query, top_k * 2, filters)

        # 2. 关键词搜索
        keyword_results = self._keyword_search(query, top_k * 2)

        # 3. 合并结果
        combined = self._merge_results(vector_results, keyword_results)

        # 4. 排序并取 top_k
        combined.sort(key=lambda x: x["score"], reverse=True)
        return combined[:top_k]

    def _keyword_search(
        self,
        query: str,
        top_k: int,
    ) -> List[Dict]:
        """关键词搜索"""
        query_keywords = self._extract_keywords(query)

        if not query_keywords:
            return []

        # 统计文档匹配的关键词数量
        doc_scores: Dict[str, float] = {}
        for keyword in query_keywords:
            if keyword in self._keyword_index:
                for doc_id in self._keyword_index[keyword]:
                    doc_scores[doc_id] = doc_scores.get(doc_id, 0.0) + 1.0

        # 归一化分数
        max_score = max(doc_scores.values()) if doc_scores else 1.0
        normalized_scores = {doc_id: score / max_score for doc_id, score in doc_scores.items()}

        # 构建结果
        results = []
        for doc_id, score in sorted(normalized_scores.items(), key=lambda x: x[1], reverse=True)[
            :top_k
        ]:
            results.append(
                {
                    "doc_id": doc_id,
                    "text": self._doc_texts.get(doc_id, ""),
                    "metadata": {},
                    "score": score,
                    "type": "keyword",
                }
            )

        return results

    def _merge_results(
        self,
        vector_results: List[Dict],
        keyword_results: List[Dict],
    ) -> List[Dict]:
        """合并搜索结果"""
        doc_scores: Dict[str, Dict] = {}

        # 处理向量结果
        for result in vector_results:
            doc_id = result["doc_id"]
            doc_scores[doc_id] = {
                "doc_id": doc_id,
                "text": result.get("text", ""),
                "metadata": result.get("metadata", {}),
                "vector_score": result["score"],
                "keyword_score": 0.0,
            }

        # 处理关键词结果
        for result in keyword_results:
            doc_id = result["doc_id"]
            if doc_id in doc_scores:
                doc_scores[doc_id]["keyword_score"] = result["score"]
            else:
                doc_scores[doc_id] = {
                    "doc_id": doc_id,
                    "text": result.get("text", ""),
                    "metadata": result.get("metadata", {}),
                    "vector_score": 0.0,
                    "keyword_score": result["score"],
                }

        # 计算综合分数
        merged = []
        for doc in doc_scores.values():
            combined_score = (
                doc["vector_score"] * self._vector_weight
                + doc["keyword_score"] * self._keyword_weight
            )
            merged.append(
                {
                    "doc_id": doc["doc_id"],
                    "text": doc["text"],
                    "metadata": doc["metadata"],
                    "score": combined_score,
                    "vector_score": doc["vector_score"],
                    "keyword_score": doc["keyword_score"],
                }
            )

        return merged

    def _extract_keywords(self, text: str) -> List[str]:
        """简单的关键词提取"""
        # 简单实现：分词，去停用词
        stop_words = {
            "的",
            "是",
            "在",
            "和",
            "与",
            "了",
            "也",
            "对",
            "为",
            "the",
            "a",
            "an",
            "is",
            "are",
            "and",
            "of",
            "in",
            "to",
        }

        # 简单分词（中文用字符，英文用空格）
        words = []
        # 英文部分
        import re

        english_words = re.findall(r"[a-zA-Z]{3,}", text.lower())
        words.extend([w for w in english_words if w not in stop_words])

        # 中文部分（取单字）
        chinese_chars = [c for c in text if "一" <= c <= "鿿"]
        # 简单取 2-4 字的组合
        for i in range(len(chinese_chars)):
            for j in range(2, 5):
                if i + j <= len(chinese_chars):
                    word = "".join(chinese_chars[i : i + j])
                    if word not in stop_words:
                        words.append(word)

        return words[:20]  # 限制数量
