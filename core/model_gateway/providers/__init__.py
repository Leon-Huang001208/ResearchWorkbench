"""
Concrete model provider implementations.

Provides OpenAICompatibleProvider (for OpenAI-compatible endpoints: Volcano,
DeepSeek, OpenAI, local), AnthropicProvider (for Anthropic native protocol),
and LocalEmbeddingProvider (for offline sentence-transformers embeddings).
"""

from .anthropic import AnthropicProvider
from .openai_compatible import OpenAICompatibleProvider

# LocalEmbeddingProvider 已改为按需加载（在 gateway.py 的 _init_providers 中导入），
# 避免模块顶层导入触发 sentence_transformers → torch（~51s 启动开销）。
__all__ = ["AnthropicProvider", "OpenAICompatibleProvider"]
