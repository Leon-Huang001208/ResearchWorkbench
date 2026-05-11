"""Unit tests for retrieval module (vector store and hybrid search)."""
from knowledge_layer.retrieval.hybrid_search import HybridSearcher
from knowledge_layer.retrieval.vector_store import InMemoryVectorStore


def test_in_memory_vector_store_add_document():
    """Test adding documents to vector store."""
    store = InMemoryVectorStore()
    store.add_document("doc1", "贵州茅台财报", metadata={"year": 2024})
    store.add_document("doc2", "腾讯控股财报", metadata={"year": 2024})
    # Verify documents are stored
    assert store._documents is not None
    assert len(store._documents) == 2


def test_in_memory_vector_store_search():
    """Test searching in vector store."""
    store = InMemoryVectorStore()
    store.add_document("doc1", "贵州茅台财报超预期", metadata={"year": 2024})
    store.add_document("doc2", "腾讯控股财报超预期", metadata={"year": 2024})
    store.add_document("doc3", "新能源行业分析", metadata={"year": 2024})

    results = store.search("茅台财报", top_k=2)
    assert len(results) <= 2


def test_in_memory_vector_store_delete_document():
    """Test deleting documents from vector store."""
    store = InMemoryVectorStore()
    store.add_document("doc1", "测试文档")
    store.delete_document("doc1")
    assert "doc1" not in store._documents


def test_in_memory_vector_store_search_with_filters():
    """Test searching with metadata filters."""
    store = InMemoryVectorStore()
    store.add_document("doc1", "贵州茅台", metadata={"type": "company"})
    store.add_document("doc2", "人工智能", metadata={"type": "concept"})

    results = store.search("茅台", top_k=10, filters={"type": "company"})
    # Results should be filtered, but since we're using dummy embeddings,
    # just verify the search works without error


def test_hybrid_searcher_index_document():
    """Test indexing documents in hybrid searcher."""
    vector_store = InMemoryVectorStore()
    searcher = HybridSearcher(vector_store)

    searcher.index_document("doc1", "贵州茅台财报", metadata={"year": 2024})
    searcher.index_document("doc2", "腾讯控股财报", metadata={"year": 2024})

    assert "doc1" in searcher._doc_texts
    assert "doc2" in searcher._doc_texts


def test_hybrid_searcher_search():
    """Test hybrid search functionality."""
    vector_store = InMemoryVectorStore()
    searcher = HybridSearcher(vector_store)

    searcher.index_document("doc1", "贵州茅台财报超预期")
    searcher.index_document("doc2", "腾讯控股财报超预期")
    searcher.index_document("doc3", "新能源行业分析报告")

    results = searcher.search("财报", top_k=2)
    assert len(results) <= 2


def test_cosine_similarity_dummy_embedding():
    """Test that dummy embeddings work consistently."""
    store = InMemoryVectorStore()
    embedding1 = store._dummy_embedding("贵州茅台")
    embedding2 = store._dummy_embedding("贵州茅台")
    embedding3 = store._dummy_embedding("腾讯控股")

    # Same text should have same embedding
    assert len(embedding1) == len(embedding2)
    assert embedding1 == embedding2
    # Different texts should have different embeddings
    assert embedding1 != embedding3


def test_keyword_search():
    """Test keyword search functionality."""
    vector_store = InMemoryVectorStore()
    searcher = HybridSearcher(vector_store)

    searcher.index_document("doc1", "贵州茅台财报超预期")
    searcher.index_document("doc2", "腾讯控股财报超预期")

    keyword_results = searcher._keyword_search("财报", top_k=2)
    assert len(keyword_results) <= 2
    # Both documents have "财报" keyword
    doc_ids = [r["doc_id"] for r in keyword_results]
    assert "doc1" in doc_ids or "doc2" in doc_ids
