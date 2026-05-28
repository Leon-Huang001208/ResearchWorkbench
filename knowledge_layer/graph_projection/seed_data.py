"""启动时加载产业链种子数据到 IndustryGraphStore。

用法:
    from knowledge_layer.graph_projection.seed_data import seed_graph_store

    store = IndustryGraphStore()
    seed_graph_store(store)  # 加载 data/industry_graphs/*.json
"""

from pathlib import Path

from core.observability import get_logger
from knowledge_layer.graph_projection.graph_store import IndustryGraphStore

logger = get_logger(__name__)

_SEED_DIR = Path("data/industry_graphs")


def seed_graph_store(
    store: IndustryGraphStore | None = None,
    data_dir: str | Path | None = None,
) -> IndustryGraphStore:
    """将 data/industry_graphs/ 下所有 JSON 种子数据加载到 store。

    如未提供 store，则创建新的空 store 并填充后返回。
    """
    store = store or IndustryGraphStore()
    data_dir = Path(data_dir) if data_dir else _SEED_DIR

    if not data_dir.is_dir():
        logger.warning("Seed data directory not found: %s", data_dir)
        return store

    chains = store.load_all_seed_data(data_dir)
    logger.info("Seeded %d industry chain(s) into graph store", len(chains))
    return store
