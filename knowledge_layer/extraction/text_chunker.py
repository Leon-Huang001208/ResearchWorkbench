"""文本切分工具 - 为 LLM 提取设计的轻量级 sliding window 切分器"""


def split_text(text: str, chunk_size: int = 3500, overlap: int = 300) -> list[str]:
    """将长文本切分为固定大小的 chunk，相邻 chunk 之间有 overlap。

    Args:
        text: 输入文本
        chunk_size: 每个 chunk 的最大字符数
        overlap: 相邻 chunk 之间的重叠字符数

    Returns:
        chunk 列表；空文本返回空列表
    """
    if not text:
        return []

    n = len(text)
    if n <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0

    while start < n:
        end = min(start + chunk_size, n)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= n:
            break
        start = end - overlap

    return chunks
