"""
Model gateway implementation for unified multi-provider LLM access.

This package provides ModelGatewayImpl (multi-provider + task routing),
BaseProvider (abstract base class), and concrete providers:
OpenAICompatibleProvider (Volcano/DeepSeek/OpenAI/local) and
AnthropicProvider (Anthropic native protocol).
"""
from .base import BaseProvider
from .gateway import ModelGatewayImpl
from .providers.anthropic import AnthropicProvider
from .providers.openai_compatible import OpenAICompatibleProvider

__all__ = [
    "ModelGatewayImpl",
    "BaseProvider",
    "AnthropicProvider",
    "OpenAICompatibleProvider",
]
