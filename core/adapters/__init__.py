"""Adapters for converting between DB models and Pydantic contracts."""

from core.adapters.event_adapter import db_event_to_pydantic

__all__ = ["db_event_to_pydantic"]
