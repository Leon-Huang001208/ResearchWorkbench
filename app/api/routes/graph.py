"""产业链图谱 API"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core.observability import get_logger
from core.services.graph_data_service import GraphDataService

logger = get_logger(__name__)
router = APIRouter(prefix="/api/graph", tags=["graph"])


def get_graph_data_service() -> GraphDataService:
    """获取图谱数据服务实例"""
    return GraphDataService()


def _convert_to_frontend_format(enriched: Dict[str, Any]) -> Dict[str, Any]:
    """将后端格式转换为前端期望的格式"""
    raw_nodes = enriched.get("nodes", [])
    raw_edges = enriched.get("edges", [])

    # 转换节点：entity_id -> id, name -> label
    nodes = []
    for i, node in enumerate(raw_nodes):
        if "hint" in node:
            continue
        node_id = node.get("entity_id", f"node_{i}")
        node_name = node.get("name", node_id)
        node_type = node.get("type", "unknown")
        # 根据类型分配 group
        group = "midstream"
        if "up" in node_type.lower() or "上游" in node_name:
            group = "upstream"
        elif "down" in node_type.lower() or "下游" in node_name:
            group = "downstream"

        nodes.append(
            {
                "id": node_id,
                "label": node_name,
                "group": group,
                "type": node_type,
                "real_entity": node.get("real_entity", False),
            }
        )

    # 转换边：source/target -> source/target, 添加 label
    links = []
    for edge in raw_edges:
        source = edge.get("source")
        target = edge.get("target")
        if source and target:
            # 根据证据强度确定标签
            evidence_strength = edge.get("evidence_strength", "none")
            label_map = {
                "high": "强关联",
                "medium": "中关联",
                "low": "弱关联",
                "none": "关联",
            }
            links.append(
                {
                    "source": source,
                    "target": target,
                    "label": label_map.get(evidence_strength, "关联"),
                    "evidence_count": edge.get("evidence_count", 0),
                    "evidence_strength": evidence_strength,
                }
            )

    return {
        "nodes": nodes,
        "edges": links,
    }


def _get_default_industry_chain(industry: str) -> Dict[str, Any]:
    """获取默认的产业链数据（当无真实数据时使用）"""
    # 根据行业名称生成合理的默认数据
    industry_nodes = {
        "白酒": [
            {"id": "up_grain", "label": "粮食", "group": "upstream"},
            {"id": "up_packaging", "label": "包装材料", "group": "upstream"},
            {"id": "mid_liquor", "label": "白酒", "group": "midstream"},
            {"id": "down_distribution", "label": "经销商", "group": "downstream"},
            {"id": "down_retail", "label": "零售", "group": "downstream"},
        ],
        "新能源": [
            {"id": "up_mining", "label": "矿产", "group": "upstream"},
            {"id": "up_material", "label": "电池材料", "group": "upstream"},
            {"id": "mid_cell", "label": "电池", "group": "midstream"},
            {"id": "down_ev", "label": "电动车", "group": "downstream"},
            {"id": "down_energy_storage", "label": "储能", "group": "downstream"},
        ],
        "半导体": [
            {"id": "up_material", "label": "硅片", "group": "upstream"},
            {"id": "up_equipment", "label": "设备", "group": "upstream"},
            {"id": "mid_fab", "label": "晶圆厂", "group": "midstream"},
            {"id": "mid_design", "label": "设计", "group": "midstream"},
            {"id": "down_device", "label": "终端设备", "group": "downstream"},
        ],
        "消费": [
            {"id": "up_raw", "label": "原材料", "group": "upstream"},
            {"id": "mid_manufacture", "label": "制造", "group": "midstream"},
            {"id": "down_retail", "label": "零售", "group": "downstream"},
        ],
    }

    industry_links = {
        "白酒": [
            {"source": "up_grain", "target": "mid_liquor", "label": "供应"},
            {"source": "up_packaging", "target": "mid_liquor", "label": "供应"},
            {"source": "mid_liquor", "target": "down_distribution", "label": "销售"},
            {"source": "down_distribution", "target": "down_retail", "label": "分销"},
        ],
        "新能源": [
            {"source": "up_mining", "target": "up_material", "label": "供应"},
            {"source": "up_material", "target": "mid_cell", "label": "供应"},
            {"source": "mid_cell", "target": "down_ev", "label": "配套"},
            {"source": "mid_cell", "target": "down_energy_storage", "label": "配套"},
        ],
        "半导体": [
            {"source": "up_material", "target": "mid_fab", "label": "供应"},
            {"source": "up_equipment", "target": "mid_fab", "label": "供应"},
            {"source": "mid_fab", "target": "mid_design", "label": "生产"},
            {"source": "mid_design", "target": "down_device", "label": "供应"},
        ],
        "消费": [
            {"source": "up_raw", "target": "mid_manufacture", "label": "供应"},
            {"source": "mid_manufacture", "target": "down_retail", "label": "销售"},
        ],
    }

    # 如果有特定行业的默认数据，使用它；否则使用通用数据
    nodes = industry_nodes.get(
        industry,
        [
            {"id": "up_1", "label": "上游", "group": "upstream"},
            {"id": "up_2", "label": "供应商", "group": "upstream"},
            {"id": "mid_1", "label": "中游", "group": "midstream"},
            {"id": "down_1", "label": "下游", "group": "downstream"},
            {"id": "down_2", "label": "终端", "group": "downstream"},
        ],
    )

    links = industry_links.get(
        industry,
        [
            {"source": "up_1", "target": "mid_1", "label": "供应"},
            {"source": "up_2", "target": "mid_1", "label": "供应"},
            {"source": "mid_1", "target": "down_1", "label": "供应"},
            {"source": "down_1", "target": "down_2", "label": "销售"},
        ],
    )

    return {
        "industry": industry,
        "nodes": nodes,
        "edges": links,
        "data_source": "placeholder",
        "hint": "暂无真实产业链数据，显示示例结构",
    }


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
    当无历史数据时，返回合理的默认数据结构。
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

            # 如果有真实数据，转换为前端格式并返回
            if enriched.get("data_source") == "real":
                converted = _convert_to_frontend_format(enriched)
                return {
                    "industry": industry,
                    "nodes": converted["nodes"],
                    "edges": converted["edges"],
                    "propagation_paths": enriched.get("propagation_paths", []),
                    "outcome_paths": enriched.get("outcome_paths", []),
                    "data_source": "real",
                }
            else:
                # 返回默认的产业链数据结构
                return _get_default_industry_chain(industry)
        else:
            # use_evidence=false，返回默认数据
            return _get_default_industry_chain(industry)
    except Exception as e:
        logger.error(f"Failed to get industry chain: {e}")
        # 出错时也返回默认数据
        return _get_default_industry_chain(industry)


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
