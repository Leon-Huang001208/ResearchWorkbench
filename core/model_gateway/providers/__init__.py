"""
Concrete model provider implementations.

Provides OpenAICompatibleProvider (for OpenAI-compatible endpoints: Volcano,
DeepSeek, OpenAI, local), AnthropicProvider (for Anthropic native protocol),
and LocalEmbeddingProvider (for offline sentence-transformers embeddings).
"""
from .anthropic import AnthropicProvider
from .local_embedding import LocalEmbeddingProvider
from .openai_compatible import OpenAICompatibleProvider

__all__ = ["AnthropicProvider", "LocalEmbeddingProvider", "OpenAICompatibleProvider"]
