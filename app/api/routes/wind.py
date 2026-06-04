"""Wind Excel Data API 路由

通过 xlwings 操控 macOS Excel Wind 插件获取专业数据。
提供一致预期、融资融券、龙虎榜、日行情、财务报表、行业分类、资金流向、持有人数据查询。
"""
from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.observability import get_logger
from data_layer.adapters.wind import WindAdapter

logger = get_logger(__name__)

router = APIRouter(prefix="/api/wind", tags=["wind"])


# ─── 请求模型 ────────────────────────────────────────────


class WindConsensusRequest(BaseModel):
    """一致预期查询请求"""

    codes: list[str] = Field(..., description="证券代码列表，如 ['600519.SH', '000858.SZ']")
    trade_date: str | None = Field(None, description="交易日期 YYYY-MM-DD，默认当日")


class WindDateRangeRequest(BaseModel):
    """带日期范围的查询请求（两融/龙虎榜/日行情/资金流向）"""

    codes: list[str] = Field(..., description="证券代码列表")
    start_date: date = Field(..., description="起始日期")
    end_date: date = Field(..., description="截止日期")


class WindReportDateRequest(BaseModel):
    """带报告期的查询请求（财务/持有人）"""

    codes: list[str] = Field(..., description="证券代码列表")
    report_date: str = Field(..., description="报告期，如 '2024-12-31'")


class WindFinancialsRequest(WindReportDateRequest):
    """财务报表查询请求"""

    statement_type: str = Field("annual", description="报表类型: annual | quarterly")


class WindResponse(BaseModel):
    """Wind 查询响应"""

    success: bool = True
    data: list[dict] = Field(default_factory=list, description="查询结果列表")
    count: int = 0

    model_config = {"json_schema_extra": {"examples": [{"success": True, "data": [], "count": 0}]}}


# ─── 辅助函数 ────────────────────────────────────────────


def _create_adapter() -> WindAdapter:
    """创建 Wind 适配器实例"""
    return WindAdapter()


def _build_response(df) -> WindResponse:
    """将 DataFrame 转为统一响应格式"""
    rows = df.to_dict(orient="records")
    return WindResponse(success=True, data=rows, count=len(rows))


# ─── 健康检查 ────────────────────────────────────────────


@router.get("/health")
def check_health():
    """检查 Wind Excel 插件是否可用

    Returns:
        {"available": true/false, "message": "..."}
    """
    try:
        adapter = _create_adapter()
        available = adapter.is_available()
        return {
            "available": available,
            "message": "Wind Excel 已连接" if available else "Wind Excel 未连接或会话已过期",
        }
    except Exception as e:
        logger.warning(f"Wind 健康检查失败: {e}")
        return {"available": False, "message": f"检查失败: {str(e)}"}


# ─── 一致预期 ────────────────────────────────────────────


@router.post("/consensus", response_model=WindResponse)
def get_consensus(request: WindConsensusRequest):
    """获取一致预期数据

    返回分析师一致预测的净利润、EPS、营收、目标价、综合评级、评级机构数。
    """
    try:
        adapter = _create_adapter()
        df = adapter.fetch_consensus_estimates(request.codes, trade_date=request.trade_date)
        return _build_response(df)
    except Exception as e:
        logger.error(f"获取一致预期失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── 融资融券 ────────────────────────────────────────────


@router.post("/margin-trading", response_model=WindResponse)
def get_margin_trading(request: WindDateRangeRequest):
    """获取融资融券数据

    返回融资余额、融券余量、融资买入额、融资偿还额、融券卖出量、融券偿还量。
    """
    try:
        adapter = _create_adapter()
        df = adapter.fetch_margin_trading(
            request.codes,
            request.start_date.isoformat(),
            request.end_date.isoformat(),
        )
        return _build_response(df)
    except Exception as e:
        logger.error(f"获取融资融券失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── 龙虎榜 ──────────────────────────────────────────────


@router.post("/block-trades", response_model=WindResponse)
def get_block_trades(request: WindDateRangeRequest):
    """获取龙虎榜数据

    返回龙虎榜买入金额、卖出金额、买入席位、卖出席位。
    仅返回有龙虎榜数据的交易日（无数据日期自动跳过）。
    """
    try:
        adapter = _create_adapter()
        df = adapter.fetch_block_trades(
            request.codes,
            request.start_date.isoformat(),
            request.end_date.isoformat(),
        )
        return _build_response(df)
    except Exception as e:
        logger.error(f"获取龙虎榜失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── 日行情 ──────────────────────────────────────────────


@router.post("/prices", response_model=WindResponse)
def get_prices(request: WindDateRangeRequest):
    """获取日行情数据

    返回 OHLCV、成交额、换手率、后复权收盘价、复权因子、VWAP、涨跌幅、振幅。
    """
    try:
        adapter = _create_adapter()
        df = adapter.fetch_daily_quotes(
            request.codes,
            request.start_date.isoformat(),
            request.end_date.isoformat(),
        )
        return _build_response(df)
    except Exception as e:
        logger.error(f"获取日行情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── 财务报表 ────────────────────────────────────────────


@router.post("/financials", response_model=WindResponse)
def get_financials(request: WindFinancialsRequest):
    """获取财务报表数据

    返回营收、营业成本、毛利润、净利润、EPS、ROE、总资产、总负债、
    股东权益、经营现金流、自由现金流。
    """
    try:
        adapter = _create_adapter()
        df = adapter.fetch_financial_statements(
            request.codes,
            request.report_date,
        )
        return _build_response(df)
    except Exception as e:
        logger.error(f"获取财务报表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── 行业数据 ────────────────────────────────────────────


@router.post("/industry", response_model=WindResponse)
def get_industry(request: WindConsensusRequest):
    """获取行业分类数据

    返回申万一级/二级/三级行业分类、行业平均市盈率、行业平均市净率。
    """
    try:
        adapter = _create_adapter()
        df = adapter.fetch_industry_data(request.codes)
        return _build_response(df)
    except Exception as e:
        logger.error(f"获取行业数据失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── 资金流向 ────────────────────────────────────────────


@router.post("/fund-flow", response_model=WindResponse)
def get_fund_flow(request: WindDateRangeRequest):
    """获取资金流向数据

    返回资金净流入、主力资金净流入、散户资金净流入、北向资金净买入。
    """
    try:
        adapter = _create_adapter()
        df = adapter.fetch_fund_flow(
            request.codes,
            request.start_date.isoformat(),
            request.end_date.isoformat(),
        )
        return _build_response(df)
    except Exception as e:
        logger.error(f"获取资金流向失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── 持有人数据 ──────────────────────────────────────────


@router.post("/holders", response_model=WindResponse)
def get_holders(request: WindReportDateRequest):
    """获取股东/持有人结构数据

    返回股东户数、户均持股数、前十大股东持股比例、机构持股比例、基金持股比例。
    """
    try:
        adapter = _create_adapter()
        df = adapter.fetch_holder_data(request.codes, request.report_date)
        return _build_response(df)
    except Exception as e:
        logger.error(f"获取持有人数据失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
