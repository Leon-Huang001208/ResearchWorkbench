"""
标签生成模块

提供各类标签生成器用于监督学习。
"""
from .base import Labeler
from .event_driven import EventDrivenLabeler
from .relative_return import RelativeReturnLabeler
from .simple import compute_relative_return_label

__all__ = [
    "Labeler",
    "compute_relative_return_label",
    "RelativeReturnLabeler",
    "EventDrivenLabeler",
]
