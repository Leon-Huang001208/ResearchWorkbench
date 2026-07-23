"""PGVectorStore 纯逻辑单元测试 - 第二阶段 2.3.

DB 读写由 scripts/e2e_phase2_facts_store.py 之外的 2.3 端到端脚本覆盖。
此处测不依赖 DB 的静态方法：余弦相似度、dummy 嵌入、chunk 过滤。
"""

from knowledge_layer.retrieval.vector_store import PGVectorStore


class TestCosineSimilarity:
    def test_identical_vectors_score_one(self):
        v = [1.0, 0.0, 0.0]
        assert abs(PGVectorStore._cosine_similarity(v, v) - 1.0) < 1e-6

    def test_orthogonal_vectors_score_zero(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert abs(PGVectorStore._cosine_similarity(a, b)) < 1e-6

    def test_zero_vector_score_zero(self):
        assert PGVectorStore._cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


class TestDummyEmbedding:
    def test_returns_normalized_vector(self):
        emb = PGVectorStore._dummy_embedding("某公司营收增长")
        assert len(emb) == 256
        norm = sum(x * x for x in emb) ** 0.5
        assert abs(norm - 1.0) < 1e-6

    def test_similar_text_higher_similarity(self):
        a = PGVectorStore._dummy_embedding("光模块营收增长")
        b = PGVectorStore._dummy_embedding("光模块营收下滑")
        c = PGVectorStore._dummy_embedding("美联储加息")
        sim_similar = PGVectorStore._cosine_similarity(a, b)
        sim_different = PGVectorStore._cosine_similarity(a, c)
        assert sim_similar > sim_different


class TestChunkFilters:
    def test_doc_id_filter_match(self):
        class _Row:
            doc_id = "d1"
            chunk_metadata = {"source": "cninfo"}

        assert PGVectorStore._match_chunk_filters(_Row(), {"doc_id": "d1"}) is True
        assert PGVectorStore._match_chunk_filters(_Row(), {"doc_id": "d2"}) is False

    def test_metadata_filter(self):
        class _Row:
            doc_id = "d1"
            chunk_metadata = {"source": "cninfo"}

        assert PGVectorStore._match_chunk_filters(_Row(), {"source": "cninfo"}) is True
        assert PGVectorStore._match_chunk_filters(_Row(), {"source": "cls"}) is False
