"""Thin registry for framework-owned definitions, stores and DSH contexts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import FrameworkDefinition, FrameworkError
from .dollar import DEFINITION as DOLLAR_DEFINITION
from .dollar import DollarSnapshotStore
from .dollar import build_context as build_dollar_context
from .goldar import DEFINITION as GOLD_DEFINITION
from .goldar import GoldSnapshotStore
from .goldar import build_context as build_gold_context
from .storage import AtomicSnapshotStore


@dataclass(frozen=True)
class FrameworkRuntime:
    definition: FrameworkDefinition
    store: AtomicSnapshotStore[Any]
    context_builder: Callable[[Any], dict]

    def snapshot(self) -> Any:
        return self.store.read()

    def catalog_item(self) -> dict:
        snapshot = self.snapshot()
        return {
            "slug": self.definition.slug,
            "name": self.definition.name,
            "domain": self.definition.domain,
            "version": self.definition.version,
            "question": self.definition.question,
            "sections": [section.model_dump(mode="json") for section in self.definition.sections],
            "status": snapshot.status,
            "coverage": snapshot.coverage,
            "updated_at": snapshot.as_of,
            "revision": snapshot.revision,
        }


class FrameworkRegistry:
    def __init__(self, root: Path) -> None:
        gold_store = GoldSnapshotStore(root / "gold")
        dollar_store = DollarSnapshotStore(root / "dollar")
        self._items = {
            "gold": FrameworkRuntime(GOLD_DEFINITION, gold_store, build_gold_context),
            "dollar": FrameworkRuntime(
                DOLLAR_DEFINITION,
                dollar_store,
                build_dollar_context,
            ),
        }

    def all(self) -> tuple[FrameworkRuntime, ...]:
        return tuple(self._items.values())

    def get(self, slug: str) -> FrameworkRuntime:
        try:
            return self._items[slug]
        except KeyError as exc:
            raise FrameworkError("研究框架不存在", "framework_not_found", 404) from exc
