"""投资主题生成路由"""

from fastapi import APIRouter, Depends, HTTPException

from core.contracts.events import CanonicalEvent
from core.contracts.industry_chain import IndustryGraph, ThesisCard
from services.thesis_generator_service import ThesisGeneratorService, get_thesis_generator_service

router = APIRouter(prefix="/api/thesis", tags=["thesis-generator"])


@router.get(
    "/graphs",
    response_model=list[dict],
    responses={500: {"description": "Internal error"}},
)
async def list_industry_graphs(
    service: ThesisGeneratorService = Depends(get_thesis_generator_service),
):
    """列出所有可用的产业链图"""
    try:
        return service.list_graphs()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/graphs/{graph_id}",
    response_model=IndustryGraph,
    responses={404: {"description": "Graph not found"}, 500: {"description": "Internal error"}},
)
async def get_industry_graph(
    graph_id: str,
    service: ThesisGeneratorService = Depends(get_thesis_generator_service),
):
    """获取指定产业链图"""
    graph = service.get_graph(graph_id)
    if not graph:
        raise HTTPException(status_code=404, detail=f"Graph {graph_id} not found")
    return graph


@router.post(
    "/generate",
    response_model=list[ThesisCard],
    responses={500: {"description": "Internal error"}},
)
async def generate_theses(
    event: CanonicalEvent,
    graph_id: str | None = None,
    service: ThesisGeneratorService = Depends(get_thesis_generator_service),
):
    """从输入事件生成投资主题卡片"""
    try:
        theses = service.generate_theses_from_event(event, graph_id=graph_id)
        return theses
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
