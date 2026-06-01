"""
Signal Lab API 路由

提供特征工程、标签生成、信号评分和回测的 API。
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.observability import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/signal-lab", tags=["signal-lab"])


# ============ 数据模型 ============


class FeatureComputeRequest(BaseModel):
    """特征计算请求"""

    subject_id: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    groups: Optional[List[str]] = None
    features: Optional[List[str]] = None


class LabelComputeRequest(BaseModel):
    """标签计算请求"""

    subject_id: str
    label_type: str = "relative_return"
    horizon: int = 20
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class BacktestRequest(BaseModel):
    """回测请求"""

    signal_ids: Optional[List[str]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    initial_capital: float = 1000000.0


class ScoreSignalRequest(BaseModel):
    """信号评分请求"""

    signal_id: str
    scorer_types: Optional[List[str]] = None


# ============ 路由 ============


@router.get("/features/groups")
async def list_feature_groups() -> Dict[str, Any]:
    """
    获取所有可用的特征组

    Returns:
        特征组列表
    """
    try:
        from signal_lab.features.groups import (
            FinancialFeatures,
            FundFlowFeatures,
            IndustryFeatures,
            MacroFeatures,
            PriceVolumeFeatures,
            ValuationFeatures,
        )

        groups = {
            "price_volume": {
                "name": "价量特征",
                "description": "价格、成交量相关的技术指标",
                "features": PriceVolumeFeatures().get_feature_names(),
            },
            "valuation": {
                "name": "估值特征",
                "description": "PE、PB、PS等估值指标",
                "features": ValuationFeatures().get_feature_names(),
            },
            "financial": {
                "name": "财务特征",
                "description": "营收、利润、资产负债等财务指标",
                "features": FinancialFeatures().get_feature_names(),
            },
            "fund_flow": {
                "name": "资金流特征",
                "description": "主力资金、北向资金等资金流向指标",
                "features": FundFlowFeatures().get_feature_names(),
            },
            "industry": {
                "name": "行业特征",
                "description": "行业动量、相对强弱等行业相关指标",
                "features": IndustryFeatures().get_feature_names(),
            },
            "macro": {
                "name": "宏观特征",
                "description": "市场环境、利率、通胀等宏观指标",
                "features": MacroFeatures().get_feature_names(),
            },
        }

        return {"success": True, "groups": groups}

    except Exception as e:
        logger.error(f"Failed to list feature groups: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/features/compute")
async def compute_features(request: FeatureComputeRequest) -> Dict[str, Any]:
    """
    计算特征

    Args:
        request: 特征计算请求

    Returns:
        特征计算结果
    """
    try:
        from signal_lab.features.builder import FeatureBuilder
        from signal_lab.features.groups import (
            FinancialFeatures,
            FundFlowFeatures,
            IndustryFeatures,
            MacroFeatures,
            PriceVolumeFeatures,
            ValuationFeatures,
        )

        # 构建特征
        builder = FeatureBuilder()

        # 根据请求添加特征组
        all_groups = {
            "price_volume": PriceVolumeFeatures,
            "valuation": ValuationFeatures,
            "financial": FinancialFeatures,
            "fund_flow": FundFlowFeatures,
            "industry": IndustryFeatures,
            "macro": MacroFeatures,
        }

        groups_to_add = request.groups if request.groups else list(all_groups.keys())

        for group_name in groups_to_add:
            if group_name in all_groups:
                builder.add_group(all_groups[group_name]())

        # 获取价格数据
        try:
            from data_layer.adapters.multi_source_adapter import MultiSourcePriceAdapter

            price_adapter = MultiSourcePriceAdapter()
        except Exception:
            from data_layer.adapters.hybrid_price_adapter import HybridPriceAdapter

            price_adapter = HybridPriceAdapter()

        # 设置日期范围
        end_date = request.end_date or datetime.now().strftime("%Y-%m-%d")
        if not request.start_date:
            from datetime import timedelta

            start_date = (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d")
        else:
            start_date = request.start_date

        # 获取价格数据
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            quotes = loop.run_until_complete(
                price_adapter.fetch_stock_quotes(request.subject_id, start_date, end_date)
            )
        finally:
            loop.close()

        if not quotes:
            raise HTTPException(status_code=404, detail="No price data available")

        # 转换为 DataFrame
        import pandas as pd

        df = pd.DataFrame(quotes)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").set_index("date")

        # 计算特征
        features_df = builder.compute_features(
            df,
            group_names=request.groups,
            feature_names=request.features,
        )

        # 转换为字典格式返回
        result = {
            "success": True,
            "subject_id": request.subject_id,
            "date_range": {
                "start": start_date,
                "end": end_date,
            },
            "features": features_df.reset_index().to_dict("records"),
            "feature_names": list(features_df.columns),
        }

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to compute features: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/labels/types")
async def list_label_types() -> Dict[str, Any]:
    """
    获取所有可用的标签类型

    Returns:
        标签类型列表
    """
    label_types = {
        "relative_return": {
            "name": "相对收益标签",
            "description": "未来一段时间的收益率",
        },
        "event_driven": {
            "name": "事件驱动标签",
            "description": "基于事件的标签生成",
        },
    }

    return {"success": True, "label_types": label_types}


@router.post("/labels/compute")
async def compute_labels(request: LabelComputeRequest) -> Dict[str, Any]:
    """
    计算标签

    Args:
        request: 标签计算请求

    Returns:
        标签计算结果
    """
    try:
        # 获取价格数据
        try:
            from data_layer.adapters.multi_source_adapter import MultiSourcePriceAdapter

            price_adapter = MultiSourcePriceAdapter()
        except Exception:
            from data_layer.adapters.hybrid_price_adapter import HybridPriceAdapter

            price_adapter = HybridPriceAdapter()

        # 设置日期范围
        end_date = request.end_date or datetime.now().strftime("%Y-%m-%d")
        if not request.start_date:
            from datetime import timedelta

            start_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
        else:
            start_date = request.start_date

        # 获取价格数据
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            quotes = loop.run_until_complete(
                price_adapter.fetch_stock_quotes(request.subject_id, start_date, end_date)
            )
        finally:
            loop.close()

        if not quotes:
            raise HTTPException(status_code=404, detail="No price data available")

        # 转换为 DataFrame
        import pandas as pd

        df = pd.DataFrame(quotes)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").set_index("date")

        # 计算标签
        from signal_lab.labels import RelativeReturnLabeler

        labeler = RelativeReturnLabeler(horizon=request.horizon, forward=True)
        labels = labeler.compute(df)

        result = {
            "success": True,
            "subject_id": request.subject_id,
            "label_type": request.label_type,
            "horizon": request.horizon,
            "date_range": {
                "start": start_date,
                "end": end_date,
            },
            "labels": labels.reset_index().to_dict("records"),
        }

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to compute labels: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scorers/types")
async def list_scorer_types() -> Dict[str, Any]:
    """
    获取所有可用的评分器类型

    Returns:
        评分器类型列表
    """
    scorer_types = {
        "confidence": {
            "name": "置信度评分",
            "description": "基于信号置信度的评分",
        },
        "strength": {
            "name": "强度评分",
            "description": "基于信号强度的评分",
        },
        "evidence": {
            "name": "证据评分",
            "description": "基于证据支持度的评分",
        },
        "composite": {
            "name": "组合评分",
            "description": "多个评分器的加权组合",
        },
    }

    return {"success": True, "scorer_types": scorer_types}


@router.get("/backtests/result/{signal_id}")
async def get_backtest_result(signal_id: str) -> Dict[str, Any]:
    """
    获取单个信号的回测结果

    Args:
        signal_id: 信号ID

    Returns:
        回测结果
    """
    try:
        from sqlalchemy import text

        from data_layer.repositories.base import SessionLocal

        db = SessionLocal()
        try:
            result = db.execute(
                text("SELECT * FROM signal_outcome WHERE signal_id = :signal_id"),
                {"signal_id": signal_id},
            ).fetchone()

            if not result:
                raise HTTPException(status_code=404, detail="Backtest result not found")

            # 转换为字典
            import json

            outcome_dict = dict(result._mapping)
            if outcome_dict.get("metadata"):
                outcome_dict["metadata"] = json.loads(outcome_dict["metadata"])

            return {
                "success": True,
                "signal_id": signal_id,
                "backtest": outcome_dict,
            }

        finally:
            db.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get backtest result: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backtests/run")
async def run_backtest(request: BacktestRequest) -> Dict[str, Any]:
    """
    运行回测

    Args:
        request: 回测请求

    Returns:
        回测结果
    """
    try:
        from services.closed_loop_service import ClosedLoopService

        service = ClosedLoopService()
        results = service.backtest_signals(signal_ids=request.signal_ids)

        return {
            "success": True,
            "initial_capital": request.initial_capital,
            "backtested_count": len(results),
            "results": results,
        }

    except Exception as e:
        logger.error(f"Failed to run backtest: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_signal_lab_summary() -> Dict[str, Any]:
    """
    获取Signal Lab摘要信息

    Returns:
        Signal Lab摘要
    """
    try:
        # 获取统计信息
        from sqlalchemy import text

        from data_layer.repositories.base import SessionLocal
        from data_layer.repositories.models import AlphaSignalDB

        db = SessionLocal()
        try:
            # 信号统计
            signal_count = db.query(AlphaSignalDB).count()

            # 回测统计
            result = db.execute(text("SELECT COUNT(*) FROM signal_outcome"))
            backtest_count = result.scalar()

            # 特征统计
            from signal_lab.features.groups import (
                FinancialFeatures,
                FundFlowFeatures,
                IndustryFeatures,
                MacroFeatures,
                PriceVolumeFeatures,
                ValuationFeatures,
            )

            total_features = (
                len(PriceVolumeFeatures().get_feature_names())
                + len(ValuationFeatures().get_feature_names())
                + len(FinancialFeatures().get_feature_names())
                + len(FundFlowFeatures().get_feature_names())
                + len(IndustryFeatures().get_feature_names())
                + len(MacroFeatures().get_feature_names())
            )

            return {
                "success": True,
                "summary": {
                    "signals_count": signal_count,
                    "backtests_count": backtest_count,
                    "features_count": total_features,
                    "feature_groups_count": 6,
                },
            }

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Failed to get signal lab summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dynamic-factors/overview")
async def get_dynamic_factor_overview() -> Dict[str, Any]:
    """获取动态多因子 Alpha Control Room 可视化数据。"""
    try:
        from services.dynamic_factor_visualization_service import DynamicFactorVisualizationService

        return DynamicFactorVisualizationService().build_overview()
    except Exception as e:
        logger.error(f"Failed to get dynamic factor overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))
