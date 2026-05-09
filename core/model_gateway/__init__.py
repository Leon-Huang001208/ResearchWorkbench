"""
Model gateway implementation for unified LLM access.

This package provides the ModelGatewayImpl and BaseProvider abstract base class,
plus concrete providers (VolcanoProvider, OpenAICompatibleProvider) in AlphaFoundry.
"""
from .base import BaseProvider
from .gateway import ModelGatewayImpl
from .providers.openai_compatible import OpenAICompatibleProvider
from .providers.volcano import VolcanoProvider

__all__ = ["ModelGatewayImpl", "BaseProvider", "VolcanoProvider", "OpenAICompatibleProvider"]
