"""Wind 数据适配器 —— 通过 Excel 插件获取 Wind 数据"""

from pathlib import Path
from typing import Any

import pandas as pd

from core.contracts import DocumentEnvelope
from core.observability import get_logger
from data_layer.adapters.base import BaseDataAdapter
from data_layer.adapters.wind import formulas as wf
from data_layer.adapters.wind.client import WindExcelClient

logger = get_logger(__name__)


class WindAdapter(BaseDataAdapter):
    """Wind 数据适配器

    通过 xlwings 操控 macOS Excel 中的 Wind 插件来获取数据。
    使用前需确保 Excel 已启动且 Wind 插件已登录。
    """

    def __init__(self, client: WindExcelClient | None = None):
        super().__init__(source_type="wind")
        self._client = client

    def _get_client(self) -> WindExcelClient:
        if self._client is None:
            self._client = WindExcelClient()
        return self._client

    def is_available(self) -> bool:
        """检查 Wind 是否可用"""
        try:
            client = self._get_client()
            return client.heartbeat()
        except Exception:
            return False

    # ===== 一期接口 =====

    def fetch_consensus_estimates(
        self, codes: list[str], trade_date: str | None = None
    ) -> pd.DataFrame:
        """获取一致预期数据

        Args:
            codes: 证券代码列表，如 ["600519.SH", "000858.SZ"]
            trade_date: 交易日期 "YYYY-MM-DD"，默认当日

        Returns:
            DataFrame，列为: code, trade_date, cons_net_profit, cons_eps,
            cons_revenue, target_price, rating, rating_num
        """
        client = self._get_client()
        rows = []

        for code in codes:
            logger.info(f"获取一致预期: {code}")
            formulas = [
                wf.cons_net_profit(code, trade_date),
                wf.cons_eps(code, trade_date),
                wf.cons_revenue(code, trade_date),
                wf.cons_target_price(code),
                wf.cons_rating(code),
                wf.cons_rating_num(code),
            ]
            raw = client.execute_batch(formulas)

            def _val(idx: int):
                r = raw[idx]
                if isinstance(r, Exception):
                    raise r
                return r

            rows.append(
                {
                    "code": code,
                    "trade_date": trade_date or "today",
                    "cons_net_profit": _val(0),
                    "cons_eps": _val(1),
                    "cons_revenue": _val(2),
                    "target_price": _val(3),
                    "rating": _val(4),
                    "rating_num": _val(5),
                }
            )

        return pd.DataFrame(rows)

    def fetch_margin_trading(
        self, codes: list[str], start_date: str, end_date: str
    ) -> pd.DataFrame:
        """获取融资融券数据

        Args:
            codes: 证券代码列表
            start_date: 起始日期 "YYYY-MM-DD"
            end_date: 截止日期 "YYYY-MM-DD"

        Returns:
            DataFrame，列为: code, date, margin_balance, short_balance,
            margin_buy, margin_repay, short_sell_vol, short_repay_vol
        """
        client = self._get_client()
        date_range = pd.date_range(start_date, end_date, freq="B")
        rows = []

        for code in codes:
            logger.info(f"获取两融数据: {code}, {start_date}~{end_date}")
            for dt in date_range:
                date_str = dt.strftime("%Y-%m-%d")
                formulas = [
                    wf.margin_balance(code, date_str),
                    wf.short_balance(code, date_str),
                    wf.margin_buy(code, date_str),
                    wf.margin_repay(code, date_str),
                    wf.short_sell_vol(code, date_str),
                    wf.short_repay_vol(code, date_str),
                ]
                raw = client.execute_batch(formulas)

                def _val(idx: int):
                    r = raw[idx]
                    if isinstance(r, Exception):
                        return None
                    return r

                rows.append(
                    {
                        "code": code,
                        "date": date_str,
                        "margin_balance": _val(0),
                        "short_balance": _val(1),
                        "margin_buy": _val(2),
                        "margin_repay": _val(3),
                        "short_sell_vol": _val(4),
                        "short_repay_vol": _val(5),
                    }
                )

        return pd.DataFrame(rows)

    def fetch_block_trades(self, codes: list[str], start_date: str, end_date: str) -> pd.DataFrame:
        """获取龙虎榜数据

        Args:
            codes: 证券代码列表
            start_date: 起始日期 "YYYY-MM-DD"
            end_date: 截止日期 "YYYY-MM-DD"

        Returns:
            DataFrame，列为: code, date, lhb_buy_amt, lhb_sell_amt,
            lhb_buy_seat, lhb_sell_seat
        """
        client = self._get_client()
        date_range = pd.date_range(start_date, end_date, freq="B")
        rows = []

        for code in codes:
            logger.info(f"获取龙虎榜: {code}, {start_date}~{end_date}")
            for dt in date_range:
                date_str = dt.strftime("%Y-%m-%d")
                formulas = [
                    wf.lhb_buy_amt(code, date_str),
                    wf.lhb_sell_amt(code, date_str),
                    wf.lhb_buy_seat(code, date_str),
                    wf.lhb_sell_seat(code, date_str),
                ]
                raw = client.execute_batch(formulas)

                def _val(idx: int):
                    r = raw[idx]
                    if isinstance(r, Exception):
                        return None
                    return r

                buy_amt = _val(0)
                sell_amt = _val(1)

                # 如果买卖金额都为 None/0，说明当日无龙虎榜，跳过
                if buy_amt is None and sell_amt is None:
                    continue
                if buy_amt == 0 and sell_amt == 0:
                    continue

                rows.append(
                    {
                        "code": code,
                        "date": date_str,
                        "lhb_buy_amt": buy_amt,
                        "lhb_sell_amt": sell_amt,
                        "lhb_buy_seat": _val(2),
                        "lhb_sell_seat": _val(3),
                    }
                )

        return pd.DataFrame(rows)

    # ===== 基类要求 =====

    def fetch(self, **kwargs: Any) -> list[DocumentEnvelope]:
        """获取 Wind 数据（基类 sync 接口）

        kwargs:
            data_type: str - "consensus", "margin_trading", "block_trades"
            codes: list[str]
            start_date: str (可选)
            end_date: str (可选)
            trade_date: str (可选, 一致预期用)
        """
        data_type = kwargs.get("data_type", "consensus")
        codes = kwargs.get("codes", [])
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")
        trade_date = kwargs.get("trade_date", None)

        if data_type == "consensus":
            df = self.fetch_consensus_estimates(codes, trade_date=trade_date)
        elif data_type == "margin_trading":
            if not start_date or not end_date:
                raise ValueError("两融数据需要 start_date 和 end_date")
            df = self.fetch_margin_trading(codes, start_date, end_date)
        elif data_type == "block_trades":
            if not start_date or not end_date:
                raise ValueError("龙虎榜数据需要 start_date 和 end_date")
            df = self.fetch_block_trades(codes, start_date, end_date)
        else:
            raise ValueError(f"未知数据类型: {data_type}")

        envelopes = []
        for _, row in df.iterrows():
            envelope = self._create_document_envelope(
                content=row.to_json(force_ascii=False),
                metadata={
                    "data_type": data_type,
                    "source": "wind_excel",
                },
            )
            envelopes.append(envelope)
        return envelopes

    def parse(self, source: Path | bytes | str, **kwargs: Any) -> DocumentEnvelope:
        """解析 Wind 原始数据（暂不支持）"""
        raise NotImplementedError("WindAdapter 不支持 parse 方法")
