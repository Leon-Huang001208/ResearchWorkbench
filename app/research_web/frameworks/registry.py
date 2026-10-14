"""Thin registry for framework-owned definitions, stores and DSH contexts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict

from core.observability import get_logger

from .base import FrameworkDefinition, FrameworkError
from .dollar import DEFINITION as DOLLAR_DEFINITION
from .dollar import DollarSnapshotStore
from .dollar import build_context as build_dollar_context
from .embedded import EmbeddedSnapshotStore
from .embedded import build_context as build_embedded_context
from .embedded.contracts import EmbeddedSnapshot
from .goldar import DEFINITION as GOLD_DEFINITION
from .goldar import GoldSnapshotStore
from .goldar import build_context as build_gold_context
from .storage import AtomicSnapshotStore, compute_revision

log = get_logger(__name__)
IMPORT_DATE = "2026-10-14"


@dataclass(frozen=True)
class FrameworkRuntime:
    definition: FrameworkDefinition
    store: AtomicSnapshotStore[Any]
    context_builder: Callable[[Any], dict]

    def display(self) -> dict:
        native = self.definition.slug in {"gold", "dollar"}
        return {
            "kind": "native-embed" if native else "static-embed",
            "url": f"/frameworks-embed/{self.definition.slug}/",
            "imported_at": IMPORT_DATE,
            "bot_enabled": native,
        }

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
            "display": self.display(),
        }


class EmbeddedConfig(TypedDict):
    slug: str
    name: str
    domain: str
    question: str
    chain: list[str]


class FrameworkRegistry:
    def __init__(self, root: Path) -> None:
        self._items: dict[str, FrameworkRuntime] = {
            "gold": FrameworkRuntime(
                GOLD_DEFINITION, GoldSnapshotStore(root / "gold"), build_gold_context
            ),
            "dollar": FrameworkRuntime(
                DOLLAR_DEFINITION, DollarSnapshotStore(root / "dollar"), build_dollar_context
            ),
        }
        self._register_embedded(root)
        log.info("framework_registry_initialized", count=len(self._items))

    def _register_embedded(self, root: Path) -> None:
        embed_base = "/frameworks-embed"
        embedded_configs: list[EmbeddedConfig] = [
            {
                "slug": "gold",
                "name": "黄金研究框架",
                "domain": "commodity",
                "question": "黄金当前由哪组实际利率、美元、避险需求与实物资金力量共同定价？",
                "chain": ["宏观状态", "定价驱动", "供需资金", "期权配置"],
            },
            {
                "slug": "dollar",
                "name": "美元流动性研究框架",
                "domain": "liquidity",
                "question": "美元流动性当前由总量、资金价格、财政水流、融资管道与跨境需求中的哪一环主导？",
                "chain": ["Q 总量", "P 价格", "g 财政", "M 管道", "X 跨境"],
            },
            {
                "slug": "ai-economy",
                "name": "AI如何改变经济与市场",
                "domain": "industry",
                "question": "AI 如何从算力、模型、应用到宏观经济与市场定价逐层传导？",
                "chain": ["算力", "模型", "应用", "经济", "市场"],
            },
            {
                "slug": "bond-framework",
                "name": "债市分析框架",
                "domain": "macro",
                "question": "当前债市由基本面、政策面、资金面和供需面中的哪些力量主导？",
                "chain": ["基本面", "政策面", "资金面", "供需面"],
            },
            {
                "slug": "elnino",
                "name": "厄尔尼诺",
                "domain": "macro",
                "question": "厄尔尼诺/拉尼娜周期如何影响农产品、能源与全球资产定价？",
                "chain": ["周期", "气候", "农业", "能源", "资产"],
            },
            {
                "slug": "fund-track-selection",
                "name": "如何通过赛道选基金",
                "domain": "strategy",
                "question": "如何用赛道视角筛选、比较和跟踪主题基金？",
                "chain": ["赛道定义", "基金筛选", "业绩比较", "跟踪调仓"],
            },
            {
                "slug": "memory-chips-60",
                "name": "存储芯片60年",
                "domain": "industry",
                "question": "存储芯片60年产业周期与技术变迁如何影响当前投资？",
                "chain": ["历史", "周期", "技术", "竞争", "投资"],
            },
            {
                "slug": "inference-chips-42",
                "name": "推理芯片42年",
                "domain": "industry",
                "question": "推理芯片42年演进如何塑造 AI 算力竞争格局？",
                "chain": ["历史", "架构", "生态", "竞争", "投资"],
            },
            {
                "slug": "model-hardware-chain",
                "name": "模型如何催化硬件产业链",
                "domain": "industry",
                "question": "大模型迭代如何沿硬件产业链传导需求与供给？",
                "chain": ["模型", "算力", "网络", "存储", "制造"],
            },
            {
                "slug": "gold-cycle",
                "name": "黄金大周期研究框架",
                "domain": "commodity",
                "question": "黄金在大周期中由哪些长期力量定价？",
                "chain": ["货币", "实际利率", "央行", "地缘", "周期"],
            },
            {
                "slug": "ainvest",
                "name": "AInvest AI产业链雷达",
                "domain": "industry",
                "question": "AI 产业链各环节的热度、映射、业绩与实物拆解如何变化？",
                "chain": ["热力图", "产业链", "焦点", "实物拆解", "宏观"],
            },
        ]
        for config in embedded_configs:
            if config["slug"] in self._items:
                continue
            store = EmbeddedSnapshotStore(root / config["slug"])
            snapshot = store.read().model_dump(mode="json")
            snapshot["external_app"] = {
                "url": f"{embed_base}/{config['slug']}/",
            }
            snapshot["research_state"]["note"] = "静态导入快照；没有实时采集或框架 Bot。"
            snapshot["overview"]["sources"] = [
                {
                    "name": config["name"],
                    "url": snapshot["external_app"]["url"],
                    "observed_at": snapshot["as_of"],
                    "unit": "元数据",
                    "method": "站内内嵌静态应用",
                    "proxy": False,
                }
            ]
            snapshot["revision"] = compute_revision(snapshot)
            validated = EmbeddedSnapshot.model_validate(snapshot)
            store.write(validated)
            definition = FrameworkDefinition.model_validate(
                {
                    "slug": config["slug"],
                    "name": config["name"],
                    "domain": config["domain"],
                    "version": "1.0.0",
                    "source_revision": "f68372fb07429a9e284e867ab033b07ed24d82c8",
                    "question": config["question"],
                    "chain": config["chain"],
                    "counter_evidence": ["内嵌静态资源缺失", "内嵌数据文件过期或损坏"],
                    "sections": [
                        {
                            "id": "overview",
                            "label": "总览",
                            "question": "当前框架状态与入口是什么？",
                        },
                        {"id": "external", "label": "项目全景", "question": config["question"]},
                        {
                            "id": "data",
                            "label": "数据回传",
                            "question": "哪些结论可以回传到主研究台？",
                        },
                    ],
                    "method": "项目代码并入本仓库并构建为静态资产，以 iframe 同源嵌入，保留完整交互。",
                }
            )
            self._items[config["slug"]] = FrameworkRuntime(
                definition, store, build_embedded_context
            )

    def all(self) -> tuple[FrameworkRuntime, ...]:
        return tuple(self._items.values())

    def get(self, slug: str) -> FrameworkRuntime:
        try:
            return self._items[slug]
        except KeyError as exc:
            raise FrameworkError("研究框架不存在", "framework_not_found", 404) from exc
