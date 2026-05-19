"""测试文本切分工具"""

from knowledge_layer.extraction import split_text


class TestSplitText:
    """测试 split_text 函数"""

    def test_empty_text_returns_empty_list(self):
        assert split_text("", 100, 20) == []

    def test_short_text_returns_single_element(self):
        result = split_text("short", chunk_size=100, overlap=20)
        assert result == ["short"]

    def test_text_shorter_than_chunk_size_returns_single(self):
        result = split_text("hello world", chunk_size=100, overlap=10)
        assert len(result) == 1
        assert result[0] == "hello world"

    def test_multi_chunk_no_overlap(self):
        result = split_text("Hello World!", chunk_size=5, overlap=0)
        assert len(result) == 3
        assert result == ["Hello", "Worl", "d!"]

    def test_multi_chunk_with_overlap(self):
        text = "abcdefghij"
        result = split_text(text, chunk_size=4, overlap=2)
        assert len(result) == 4
        assert result[0] == "abcd"
        assert result[1] == "cdef"
        assert result[2] == "efgh"
        assert result[3] == "ghij"

    def test_chinese_text(self):
        text = "这是一段中文测试文本，用于验证切分功能是否正常工作。"
        result = split_text(text, chunk_size=10, overlap=3)
        assert len(result) > 1
        # 验证所有 chunk 合并回去包含关键内容
        combined = "".join(result)
        assert "中文测试" in combined

    def test_exact_chunk_size(self):
        text = "1234567890"
        result = split_text(text, chunk_size=5, overlap=0)
        assert len(result) == 2
        assert result == ["12345", "67890"]

    def test_overlap_preserves_context(self):
        text = "ABCDEFGHIJ"
        result = split_text(text, chunk_size=6, overlap=2)
        assert len(result) == 2
        # 第一块末尾 "EF" 应出现在第二块开头
        assert result[0].endswith("EF")
        assert result[1].startswith("EF")
