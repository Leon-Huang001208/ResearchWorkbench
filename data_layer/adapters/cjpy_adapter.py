"""天软 (Tinysoft) 数据适配器 —— 通过 cjpy 包获取天软行情、因子、表格数据"""

import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from core.contracts import DocumentEnvelope
from core.observability import get_logger
from data_layer.adapters.base import BaseDataAdapter

logger = get_logger(__name__)

_MARKET_CYCLE_MAP = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "60m": "60m",
    "day": "day",
    "D": "day",
    "W": "W",
    "M": "M",
}

_RATE_MAP = {
    "不复权": "不复权",
    "前复权": "前复权",
    "后复权": "后复权",
    "none": "不复权",
    "forward": "前复权",
    "backward": "后复权",
}
# Module-level Cjpy availability cache — cjpy.get_stocks() 网络调用较慢
_cjpy_available_cache: Optional[bool] = None
_PROXY_ENV_KEYS = (
    "http_proxy",
    "https_proxy",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "all_proxy",
    "ALL_PROXY",
)


@contextmanager
def _without_proxy_env():
    """cjpy 访问天软服务时绕开本机代理环境变量。"""
    saved = {key: os.environ.get(key) for key in _PROXY_ENV_KEYS}
    for key in _PROXY_ENV_KEYS:
        os.environ.pop(key, None)
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class CjpyAdapter(BaseDataAdapter):
    """天软 (Tinysoft) 数据适配器

    封装 cjpy 包的同步查询接口，提供行情、因子、表格、股票列表、
    交易日等数据获取能力。

    token 查找优先级:
        1. 构造参数 ``token``
        2. 已调用 ``cjpy.set_token()`` 的进程内 token
        3. ``~/.cjpy/config.json`` 持久化 token
        4. 环境变量 ``CJ_KEY``

    使用前确保 token 已配置（通常只需在首次使用时调用
    ``import cjpy; cjpy.set_token("your-token")``）。
    """

    def __init__(self, token: str | None = None):
        super().__init__(source_type="vendor_snapshot")
        self._token = token
        self._factor_repo_cache: dict[str, str] | None = None
        self._tables_cache: list[str] | None = None

    def _get_token(self) -> str | None:
        """按优先级获取 token"""
        import cjpy

        if self._token:
            return self._token
        try:
            return cjpy.get_saved_token()  # type: ignore[no-any-return, attr-defined]
        except Exception:
            pass
        return os.getenv("CJ_KEY")

    def _ensure_token(self) -> str:
        """确保 token 可用并返回"""
        import cjpy

        token = self._get_token()
        if token:
            return token

        env_token = os.getenv("CJ_KEY")
        if env_token:
            cjpy.set_token(env_token, persist=True)
            return env_token

        raise RuntimeError("cjpy token 未配置。请调用 cjpy.set_token('your-token') 或设置环境变量 CJ_KEY")

    def is_available(self) -> bool:
        """检查天软服务是否可用（模块级缓存，避免每次请求都做网络调用）"""
        global _cjpy_available_cache

        if _cjpy_available_cache is not None:
            return _cjpy_available_cache

        try:
            import cjpy

            self._ensure_token()
            with _without_proxy_env():
                cjpy.get_stocks()
            _cjpy_available_cache = True
            return True
        except Exception:
            _cjpy_available_cache = False
            return False

    # ===== 证券/基金列表 =====

    def fetch_stock_list(self, date: str | None = None) -> list[str]:
        """获取 A 股代码列表

        Args:
            date: 查询日期 "YYYYMMDD"，默认当日

        Returns:
            股票代码列表（Wind 格式，如 "000001.SZ"）
        """
        import cjpy

        self._ensure_token()
        with _without_proxy_env():
            stocks = cjpy.get_stocks(date=date)
        logger.info(f"获取股票列表: {len(stocks) if isinstance(stocks, list) else 'unknown'} 条")
        return stocks if isinstance(stocks, list) else []

    def fetch_fund_list(self) -> list[str]:
        """获取全部基金代码列表"""
        import cjpy

        self._ensure_token()
        with _without_proxy_env():
            funds = cjpy.get_funds()
        logger.info(f"获取基金列表: {len(funds) if isinstance(funds, list) else 'unknown'} 条")
        return funds if isinstance(funds, list) else []

    # ===== 交易日 =====

    def fetch_trading_days(
        self,
        start: str,
        end: str,
        cycle: str = "D",
        code: str | None = None,
    ) -> list[str]:
        """获取交易日序列

        Args:
            start: 起始日期 "YYYYMMDD" 或 "YYYY-MM-DD"
            end: 截止日期 "YYYYMMDD" 或 "YYYY-MM-DD"
            cycle: 周期 D/W/M/Q/H/Y，默认 D
            code: 证券代码（默认 SH000001 上证指数）

        Returns:
            "YYYYMMDD" 格式的交易日列表
        """
        import cjpy

        self._ensure_token()
        with _without_proxy_env():
            days = cjpy.get_trading_days(start=start, end=end, cycle=cycle, code=code)
        return days  # type: ignore[no-any-return]

    # ===== 行情数据 =====

    def fetch_daily_quotes(
        self,
        codes: list[str],
        start_date: str,
        end_date: str,
        cycle: str = "day",
        rate: str = "前复权",
    ) -> pd.DataFrame:
        """批量获取日行情数据

        Args:
            codes: 证券代码列表（Wind 格式如 "000001.SZ" 或天软格式 "SZ000001"）
            start_date: 起始日期 "YYYYMMDD" 或 "YYYY-MM-DD"
            end_date: 截止日期 "YYYYMMDD" 或 "YYYY-MM-DD"
            cycle: 周期 1m/5m/15m/30m/60m/day，默认 day
            rate: 复权方式 不复权/前复权/后复权，默认前复权

        Returns:
            DataFrame，合并所有代码的行情数据
        """
        import cjpy

        self._ensure_token()
        cycle = _MARKET_CYCLE_MAP.get(cycle, cycle)
        rate = _RATE_MAP.get(rate, rate)

        frames: list[pd.DataFrame] = []
        for code in codes:
            try:
                with _without_proxy_env():
                    df = cjpy.get_market_data(
                        code=code,
                        start=start_date,
                        end=end_date,
                        cycle=cycle,
                        rate=rate,
                    )
                if not df.empty:
                    df["code"] = code
                    frames.append(df)
                logger.debug(f"获取行情: {code} → {len(df)} 行")
            except Exception as e:
                logger.warning(f"获取行情失败 {code}: {e}")

        if not frames:
            return pd.DataFrame()

        result = pd.concat(frames, ignore_index=True)
        logger.info(
            f"批量获取行情完成: {len(codes)} 代码, {len(result)} 行, "
            f"{start_date}~{end_date}, cycle={cycle}"
        )
        return result

    # ===== 因子数据 =====

    def fetch_factor_data(
        self,
        codes: list[str],
        dates: str | list[str],
        factors: list[str],
        repo: dict[str, str] | None = None,
    ) -> pd.DataFrame:
        """获取因子指标数据

        Args:
            codes: 证券代码列表
            dates: 单个日期或日期列表 "YYYYMMDD"
            factors: 因子名称列表
            repo: 自定义因子公式字典，不传则使用系统因子库

        Returns:
            DataFrame，列包含 截止日、代码 及各因子列
        """
        import cjpy

        self._ensure_token()
        with _without_proxy_env():
            df = cjpy.get_factor_data(code=codes, date=dates, factors=factors, repo=repo)
        if df is None:
            logger.warning(f"因子数据为空: {factors}, codes={len(codes)}")
            return pd.DataFrame()
        logger.info(f"获取因子数据: {len(df)} 行, factors={factors}")
        return df  # type: ignore[no-any-return]

    def get_factor_repo(self) -> dict[str, str]:
        """获取系统默认因子库

        Returns:
            dict: {因子名称: 因子公式} 的映射

        示例:
            >>> adapter.get_factor_repo()
            {'收盘价': 'Close()', '市盈率': 'PE()', ...}
        """
        import cjpy

        if self._factor_repo_cache is not None:
            return self._factor_repo_cache

        self._ensure_token()
        with _without_proxy_env():
            repo_df = cjpy.get_factor_repo()
        if repo_df.empty:
            self._factor_repo_cache = {}
            return {}

        self._factor_repo_cache = dict(zip(repo_df.index, repo_df.iloc[:, 0]))
        logger.info(f"加载因子库: {len(self._factor_repo_cache)} 个因子")
        return self._factor_repo_cache

    # ===== 表格数据 =====

    def fetch_table_data(
        self,
        codes: str | list[str],
        table_name: str,
        fields: str | list[str] | None = None,
    ) -> pd.DataFrame:
        """获取天软表格数据

        Args:
            codes: 单个或多个证券代码
            table_name: 表格名称（如 "股本结构"、"财务摘要" 等）
            fields: 字段列表或 "*"，默认全部字段

        Returns:
            DataFrame
        """
        import cjpy

        self._ensure_token()
        with _without_proxy_env():
            df = cjpy.get_table_data(code=codes, table_name=table_name, fields=fields)
        logger.info(
            f"获取表格数据: table={table_name}, codes={len(codes) if isinstance(codes, list) else 1}, rows={len(df)}"
        )
        return df  # type: ignore[no-any-return]

    def get_supported_tables(self) -> list[str]:
        """获取当前支持的表格名称列表

        Returns:
            表格名称列表
        """
        import cjpy

        if self._tables_cache is not None:
            return self._tables_cache

        self._ensure_token()
        with _without_proxy_env():
            tables = cjpy.get_supported_tables()
        self._tables_cache = tables if isinstance(tables, list) else []
        logger.info(f"支持表格: {len(self._tables_cache)} 张")
        return self._tables_cache

    # ===== 实时订阅 =====

    def subscribe(
        self,
        ids: list[str],
        fields: list[str],
        on_event: Any = None,
    ) -> Any:
        """启动实时行情订阅

        Args:
            ids: 订阅标的列表，如 ["SZ000001", "SH000001"]
            fields: 订阅字段列表，如 ["StockName", "price"]
            on_event: 可选回调函数

        Returns:
            Subscription 对象，通过 get() / stop() 消费事件

        示例:
            >>> sub = adapter.subscribe(["SZ000001"], ["StockName", "price"])
            >>> event = sub.get(timeout=5)
            >>> sub.stop()
        """
        import cjpy

        self._ensure_token()
        with _without_proxy_env():
            sub = cjpy.subscribe(ids=ids, fields=fields, on_event=on_event)
        logger.info(f"启动订阅: ids={ids}, fields={fields}")
        return sub

    # ===== DataAdapter 抽象方法 =====

    def fetch(self, **kwargs: Any) -> list[DocumentEnvelope]:
        """获取天软数据（基类统一接口）

        kwargs:
            data_type: str -
                "stock_list" / "fund_list" / "trading_days" /
                "daily_quotes" / "factor_data" / "table_data"
            codes: list[str] - 证券代码列表
            start_date: str (行情/交易日)
            end_date: str (行情/交易日)
            date: str (股票列表/因子)
            dates: list[str] (因子)
            factors: list[str] (因子)
            table_name: str (表格)
            fields: list[str] (表格/订阅)
            repo: dict (因子自定义公式)
        """
        data_type = kwargs.get("data_type", "stock_list")

        if data_type == "stock_list":
            stocks = self.fetch_stock_list(date=kwargs.get("date"))
            content = "\n".join(stocks)
            title = f"天软 A 股列表 ({len(stocks)} 只)"
            metadata = {"data_type": "stock_list", "count": len(stocks)}

        elif data_type == "fund_list":
            funds = self.fetch_fund_list()
            content = "\n".join(funds)
            title = f"天软基金列表 ({len(funds)} 只)"
            metadata = {"data_type": "fund_list", "count": len(funds)}

        elif data_type == "trading_days":
            start_date = kwargs.get("start_date")
            end_date = kwargs.get("end_date")
            if not start_date or not end_date:
                raise ValueError("交易日查询需要 start_date 和 end_date")
            days = self.fetch_trading_days(
                start=start_date,
                end=end_date,
                cycle=kwargs.get("cycle", "D"),
                code=kwargs.get("code"),
            )
            content = "\n".join(days)
            title = f"交易日 ({start_date}~{end_date}, {len(days)} 天)"
            metadata = {
                "data_type": "trading_days",
                "start_date": start_date,
                "end_date": end_date,
                "count": len(days),
            }

        elif data_type == "daily_quotes":
            codes = kwargs.get("codes", [])
            start_date = kwargs.get("start_date")
            end_date = kwargs.get("end_date")
            if not start_date or not end_date:
                raise ValueError("行情数据需要 start_date 和 end_date")
            df = self.fetch_daily_quotes(
                codes=codes,
                start_date=start_date,
                end_date=end_date,
                cycle=kwargs.get("cycle", "day"),
                rate=kwargs.get("rate", "前复权"),
            )
            content = df.to_json(orient="records", force_ascii=False)
            title = f"天软行情 ({start_date}~{end_date}, {len(codes)} 代码)"
            metadata = {
                "data_type": "daily_quotes",
                "codes": codes,
                "start_date": start_date,
                "end_date": end_date,
                "row_count": len(df),
            }

        elif data_type == "factor_data":
            codes = kwargs.get("codes", [])
            dates = kwargs.get("dates") or kwargs.get("date", [])
            factors = kwargs.get("factors", [])
            if not factors:
                raise ValueError("因子数据需要 factors 参数")
            df = self.fetch_factor_data(
                codes=codes,
                dates=dates,
                factors=factors,
                repo=kwargs.get("repo"),
            )
            content = df.to_json(orient="records", force_ascii=False) if not df.empty else "{}"
            title = f"天软因子 ({', '.join(factors)})"
            metadata = {
                "data_type": "factor_data",
                "codes": codes,
                "factors": factors,
                "row_count": len(df),
            }

        elif data_type == "table_data":
            codes = kwargs.get("codes", [])
            table_name = kwargs.get("table_name", "")
            if not table_name:
                raise ValueError("表格数据需要 table_name 参数")
            df = self.fetch_table_data(
                codes=codes,
                table_name=table_name,
                fields=kwargs.get("fields"),
            )
            content = df.to_json(orient="records", force_ascii=False) if not df.empty else "{}"
            title = f"天软表格: {table_name}"
            metadata = {
                "data_type": "table_data",
                "table_name": table_name,
                "codes": codes if isinstance(codes, list) else [codes],
                "row_count": len(df),
            }

        else:
            raise ValueError(f"未知 data_type: {data_type}")

        envelope = DocumentEnvelope(
            doc_id=self._generate_idempotency_key(content),
            source_type=self.source_type,  # type: ignore[arg-type]
            title=title,
            published_at=datetime.utcnow(),
            source_name="Tinysoft (天软)",
            language="zh",
            metadata=metadata,
            raw_text=content,
            canonical_text=content,
        )

        return [envelope]

    def parse(self, source: Path | bytes | str, **kwargs: Any) -> DocumentEnvelope:
        """解析天软原始数据

        支持从文件路径、字节串或字符串反序列化为 DocumentEnvelope。

        Args:
            source: Path (读取文件), bytes/str (JSON 内容)
            **kwargs:
                data_type: str - 数据类型标识
                title: str - 可选标题
        """
        if isinstance(source, Path):
            content = source.read_text(encoding="utf-8")
        elif isinstance(source, bytes):
            content = source.decode("utf-8")
        else:
            content = source

        data_type = kwargs.get("data_type", "unknown")
        title = kwargs.get("title", f"天软数据 ({data_type})")

        return self._create_document_envelope(
            content=content,
            title=title,
            metadata={
                "data_type": data_type,
                "source": "tinysoft_cjpy",
            },
        )

    # ===== 自省辅助 =====

    def info(self) -> dict[str, Any]:
        """返回适配器信息摘要（供 AI / REPL 使用）"""
        import cjpy

        repo = self.get_factor_repo()
        tables = self.get_supported_tables()
        return {
            "package_version": cjpy.__version__,
            "token_configured": bool(self._get_token()),
            "factor_count": len(repo),
            "table_count": len(tables),
            "tables": tables[:20],
            "sample_factors": dict(list(repo.items())[:10]),
        }
