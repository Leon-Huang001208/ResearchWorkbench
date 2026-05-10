"""产业链图谱 API"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core.observability import get_logger
from core.services.graph_data_service import GraphDataService

logger = get_logger(__name__)
router = APIRouter(prefix="/api/graph", tags=["graph"])


def get_graph_data_service() -> GraphDataService:
    """获取图谱数据服务实例"""
    return GraphDataService()


@router.get("/industry-chain/{industry}")
async def get_industry_chain(
    industry: str,
    use_evidence: bool = Query(True, description="是否使用真实证据"),
    min_evidence_count: int = Query(1, description="最低证据数量阈值"),
    regime_filter: Optional[str] = Query(None, description="市场环境过滤"),
    data_service: GraphDataService = Depends(get_graph_data_service),
):
    """获取产业链图谱

    当 use_evidence=true 时，注入 GraphDataService 获取真实实体和关系数据；
    当无历史数据时，保留 placeholder 逻辑作为显式 fallback。
    """
    try:
        if use_evidence:
            params = {
                "industry": industry,
                "event_type": None,
                "regime": regime_filter,
            }
            enriched = data_service.enrich_graph(
                graph_type="industry_chain",
                params=params,
            )

            # 如果有真实数据，使用真实数据
            if enriched.get("data_source") == "real":
                return {
                    "industry": industry,
                    "nodes": enriched["nodes"],
                    "edges": enriched["edges"],
                    "propagation_paths": enriched.get("propagation_paths", []),
                    "outcome_paths": enriched.get("outcome_paths", []),
                    "data_source": "real",
                }
            else:
                # 显式 fallback 到 placeholder
                return {
                    "industry": industry,
                    "nodes": [],
                    "edges": [],
                    "propagation_paths": [],
                    "outcome_paths": [],
                    "data_source": "placeholder",
                    "hint": "No historical data available for this industry",
                }
        else:
            # use_evidence=false，不查询真实数据
            return {"industry": industry, "nodes": [], "edges": [], "data_source": "disabled"}
    except Exception as e:
        logger.error(f"Failed to get industry chain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/propagation/{event_id}")
async def get_propagation_path(
    event_id: str,
    use_evidence: bool = Query(True, description="是否使用真实证据"),
    min_evidence_count: int = Query(1, description="最低证据数量阈值"),
    regime_filter: Optional[str] = Query(None, description="市场环境过滤"),
    data_service: GraphDataService = Depends(get_graph_data_service),
):
    """获取事件传播路径

    当 use_evidence=true 时，从存储获取传播路径和 Outcome 实现；
    当无历史数据时，保留 placeholder 逻辑作为显式 fallback。
    """
    try:
        if use_evidence:
            params = {
                "event_id": event_id,
                "regime": regime_filter,
            }
            enriched = data_service.enrich_graph(
                graph_type="propagation",
                params=params,
            )

            propagation_paths = enriched.get("propagation_paths", [])
            outcome_paths = enriched.get("outcome_paths", [])

            # 如果有真实传播路径，使用真实数据
            if propagation_paths and propagation_paths[0].get("path"):
                return {
                    "event_id": event_id,
                    "path": propagation_paths,
                    "outcome_paths": outcome_paths,
                    "nodes": enriched.get("nodes", []),
                    "edges": enriched.get("edges", []),
                    "data_source": "real",
                }
            else:
                # 显式 fallback
                return {
                    "event_id": event_id,
                    "path": [],
                    "outcome_paths": [],
                    "data_source": "placeholder",
                    "hint": "No propagation data available for this event",
                }
        else:
            # use_evidence=false
            return {"event_id": event_id, "path": [], "data_source": "disabled"}
    except Exception as e:
        logger.error(f"Failed to get propagation path: {e}")
        raise HTTPException(status_code=500, detail=str(e))
