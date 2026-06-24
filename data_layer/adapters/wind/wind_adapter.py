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
        super().__init__(source_type="vendor_snapshot")
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

    # ===== 二期接口 =====

    def fetch_daily_quotes(
        self, codes: list[str], start_date: str, end_date: str, adj_type: int = 1
    ) -> pd.DataFrame:
        """获取日行情数据

        Args:
            codes: 证券代码列表
            start_date: 起始日期 "YYYY-MM-DD"
            end_date: 截止日期 "YYYY-MM-DD"
            adj_type: 复权方式 1-不复权 2-后复权 3-前复权

        Returns:
            DataFrame，列为: code, date, open, high, low, close, volume,
            amount, turnover, adj_factor, vwap, pct_change, amplitude
        """
        client = self._get_client()
        date_range = pd.date_range(start_date, end_date, freq="B")
        rows = []

        for code in codes:
            logger.info(f"获取日行情: {code}, {start_date}~{end_date}")
            for dt in date_range:
                date_str = dt.strftime("%Y-%m-%d")
                formulas = [
                    wf.daily_open(code, date_str, adj_type=adj_type),
                    wf.daily_high(code, date_str, adj_type=adj_type),
                    wf.daily_low(code, date_str, adj_type=adj_type),
                    wf.daily_close(code, date_str, adj_type=adj_type),
                    wf.daily_volume(code, date_str),
                    wf.daily_amount(code, date_str),
                    wf.daily_turnover(code, date_str),
                    wf.daily_adj_factor(code, date_str),
                    wf.daily_vwap(code, date_str),
                    wf.daily_pct_change(code, date_str),
                    wf.daily_amplitude(code, date_str),
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
                        "open": _val(0),
                        "high": _val(1),
                        "low": _val(2),
                        "close": _val(3),
                        "volume": _val(4),
                        "amount": _val(5),
                        "turnover": _val(6),
                        "adj_factor": _val(7),
                        "vwap": _val(8),
                        "pct_change": _val(9),
                        "amplitude": _val(10),
                    }
                )

        return pd.DataFrame(rows)

    def fetch_market_snapshot(
        self, codes: list[str], trade_date: str | None = None
    ) -> pd.DataFrame:
        """获取资产分析页需要的轻量市场快照。

        只拉取估值、换手率和总股本等少数字段，避免调用完整日行情
        接口时按日期循环导致页面请求过慢。
        """
        client = self._get_client()
        td = trade_date or wf._td(None)
        rows = []

        for code in codes:
            logger.info(f"获取市场快照: {code}, {td}")
            formulas = [
                wf.daily_close(code, td),
                wf.daily_turnover(code, td),
                wf.val_pe_ttm(code, td),
                wf.val_pb_lf(code, td),
                wf.val_pcf_ocf_ttm(code, td),
                wf.s_info_shares(code),
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
                    "trade_date": td,
                    "close": _val(0),
                    "turnover": _val(1),
                    "pe_ttm": _val(2),
                    "pb": _val(3),
                    "pcf_ocf_ttm": _val(4),
                    "total_shares": _val(5),
                }
            )

        return pd.DataFrame(rows)

    def fetch_realtime_quotes(self, codes: list[str], timeout: float | None = 2.0) -> pd.DataFrame:
        """获取 Wind Excel 实时行情快照。

        使用 WSS `rt_*` 字段，返回列与日 K 线转换逻辑兼容的一行实时价格数据。
        """
        client = self._get_client()
        rows = []
        trade_date = pd.Timestamp.now().date()

        for code in codes:
            logger.info(f"获取 Wind 实时行情: {code}")
            formulas = [
                wf.rt_open(code),
                wf.rt_high(code),
                wf.rt_low(code),
                wf.rt_last(code),
                wf.rt_volume(code),
                wf.rt_amount(code),
                wf.rt_turnover(code),
                wf.rt_pct_change(code),
            ]
            raw = client.execute_batch(formulas, timeout=timeout)

            def _val(idx: int):
                r = raw[idx]
                if isinstance(r, Exception):
                    return None
                return r

            rows.append(
                {
                    "code": code,
                    "date": trade_date,
                    "open": _val(0),
                    "high": _val(1),
                    "low": _val(2),
                    "close": _val(3),
                    "volume": _val(4),
                    "amount": _val(5),
                    "turnover": _val(6),
                    "pct_change": _val(7),
                }
            )

        return pd.DataFrame(rows)

    def fetch_index_quotes(self, codes: list[str], trade_date: str | None = None) -> pd.DataFrame:
        """获取 Wind 指数名称、实时最新价和实时涨跌幅。

        用于首页市场概览的核心指数、Wind 行业指数和热门概念指数。
        trade_date 保留用于兼容旧调用方；实时口径直接使用 WSS rt_* 字段。
        """
        client = self._get_client()
        td = trade_date or wf._td(None)
        formulas: list[str] = []
        for code in codes:
            logger.info(f"获取 Wind 指数实时行情: {code}, {td}")
            formulas.extend(
                [
                    wf.s_info_name(code),
                    wf.index_rt_last(code),
                    wf.index_rt_pct_change(code),
                ]
            )

        raw = client.execute_batch(formulas, timeout=4.0) if formulas else []
        rows = []

        def _safe(idx: int):
            if idx >= len(raw):
                return None
            value = raw[idx]
            if isinstance(value, Exception):
                logger.warning("Wind index formula failed: %s", value)
                return None
            return value

        def _number_value(value: Any):
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        for offset, code in enumerate(codes):
            base = offset * 3
            name = _safe(base)
            close = _number_value(_safe(base + 1))
            pct_change = _number_value(_safe(base + 2))
            rows.append(
                {
                    "code": code,
                    "trade_date": td,
                    "name": name,
                    "close": close,
                    "pct_change": pct_change,
                }
            )

        return pd.DataFrame(rows)

    def fetch_financial_statements(
        self,
        codes: list[str],
        trade_date: str | None = None,
        report_date: str | None = None,
    ) -> pd.DataFrame:
        """获取财务报表数据

        Wind TTM/MRQ 公式参数不统一，分三组执行：
        - trade_date 组: revenue, net_profit, eps (TTM, 自动匹配最新报告期)
        - report_date 组: operating_cost, gross_profit, gross_profit_ttm,
          gross_profit_margin, roe, total_assets, free_cf, free_cf_per_share
        - 无日期组: equity (MRQ, 自动取最新报告期)

        Args:
            codes: 证券代码列表
            trade_date: 交易日期，用于 TTM 类公式，默认系统日期
            report_date: 报告期，如 "2024/12/31"，默认空则跳过该组

        Returns:
            DataFrame
        """
        client = self._get_client()
        td = trade_date or wf._td(None)
        rd = report_date or ""
        rows = []

        for code in codes:
            logger.info(f"获取财务报表: {code}, trade={td}, report={rd}")

            # 三组公式按参数类型分别执行
            td_keys = ["revenue", "net_profit", "eps"]
            td_formulas = [
                wf.fin_revenue(code, td),
                wf.fin_net_profit(code, td),
                wf.fin_eps(code, td),
            ]

            rd_keys = [
                "operating_cost",
                "gross_profit",
                "gross_profit_ttm",
                "gross_profit_margin",
                "roe",
                "total_assets",
                "free_cf",
                "free_cf_per_share",
            ]
            rd_formulas = [
                wf.fin_operating_cost(code, rd),
                wf.fin_gross_profit(code, rd),
                wf.fin_gross_profit_ttm(code, rd),
                wf.fin_gross_profit_margin(code, rd),
                wf.fin_roe(code, rd),
                wf.fin_total_assets(code, rd),
                wf.fin_free_cf(code, rd),
                wf.fin_free_cf_per_share(code, rd),
            ]

            nd_keys = ["equity"]
            nd_formulas = [wf.fin_equity(code)]

            # 合并执行
            all_keys = td_keys + rd_keys + nd_keys
            all_formulas = td_formulas + rd_formulas + nd_formulas
            raw = client.execute_batch(all_formulas)

            def _safe(idx):
                r = raw[idx]
                return None if isinstance(r, Exception) else r

            row = {"code": code, "trade_date": td}
            if rd:
                row["report_date"] = rd
            for i, key in enumerate(all_keys):
                row[key] = _safe(i)

            rows.append(row)

        return pd.DataFrame(rows)

    def fetch_industry_data(self, codes: list[str], trade_date: str | None = None) -> pd.DataFrame:
        """获取行业/指数分类数据

        Args:
            codes: 证券代码列表
            trade_date: 交易日期，默认系统日期

        Returns:
            DataFrame，列为: code, industry_sw, industry_sw_l2, industry_sw_l3
        """
        client = self._get_client()
        rows = []

        for code in codes:
            logger.info(f"获取行业数据: {code}")
            formulas = [
                wf.industry_sw(code, trade_date=trade_date),
                wf.industry_sw_level2(code, trade_date=trade_date),
                wf.industry_sw_level3(code, trade_date=trade_date),
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
                    "industry_sw": _val(0),
                    "industry_sw_l2": _val(1),
                    "industry_sw_l3": _val(2),
                }
            )

        return pd.DataFrame(rows)

    def fetch_fund_flow(self, codes: list[str], start_date: str, end_date: str) -> pd.DataFrame:
        """获取资金流向 + 北向持股数据

        Args:
            codes: 证券代码列表
            start_date: 起始日期 "YYYY-MM-DD"
            end_date: 截止日期 "YYYY-MM-DD"

        Returns:
            DataFrame，列为: code, date, main_force_inflow,
            main_force_open, main_force_close, north_bound_shares, north_bound_pct
        """
        client = self._get_client()
        date_range = pd.date_range(start_date, end_date, freq="B")
        rows = []

        for code in codes:
            logger.info(f"获取资金流向: {code}, {start_date}~{end_date}")
            for dt in date_range:
                date_str = dt.strftime("%Y-%m-%d")
                formulas = [
                    wf.moneyflow_main_force(code, date_str),
                    wf.moneyflow_main_force_open(code, date_str),
                    wf.moneyflow_main_force_close(code, date_str),
                    wf.north_bound_shares(code, date_str),
                    wf.north_bound_pct(code, date_str),
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
                        "main_force_inflow": _val(0),
                        "main_force_open": _val(1),
                        "main_force_close": _val(2),
                        "north_bound_shares": _val(3),
                        "north_bound_pct": _val(4),
                    }
                )

        return pd.DataFrame(rows)

    def fetch_holder_data(self, codes: list[str], report_date: str) -> pd.DataFrame:
        """获取股东/持有人结构数据

        Args:
            codes: 证券代码列表
            report_date: 报告期 "YYYY-MM-DD"（或 "2024/12/31" 格式）

        Returns:
            DataFrame，列为: code, report_date, holder_num, holder_avg_hold,
            holder_avg_pct, top10_pct, top10_quantity, institutional_hold,
            institutional_pct
        """
        client = self._get_client()
        rows = []

        for code in codes:
            logger.info(f"获取持有人数据: {code}, {report_date}")
            formulas = [
                wf.holder_num(code, report_date),
                wf.holder_avg_hold(code, report_date),
                wf.holder_avg_pct(code, report_date),
                wf.top10_holder_pct(code, report_date),
                wf.top10_holder_quantity(code, report_date),
                wf.institutional_hold(code, report_date),
                wf.institutional_hold_pct(code, report_date),
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
                    "report_date": report_date,
                    "holder_num": _val(0),
                    "holder_avg_hold": _val(1),
                    "holder_avg_pct": _val(2),
                    "top10_pct": _val(3),
                    "top10_quantity": _val(4),
                    "institutional_hold": _val(5),
                    "institutional_pct": _val(6),
                }
            )

        return pd.DataFrame(rows)

    # ===== 前十大股东逐项数据 =====

    def fetch_top10_holder_details(self, codes: list[str], report_date: str) -> pd.DataFrame:
        """获取前十大股东逐项数据（名称、持股比例、持股数量）

        将所有公式批量写入 Excel，一次等待全部返回，避免逐 rank 轮询的 COM 开销。

        Args:
            codes: 证券代码列表
            report_date: 报告期 "YYYY/MM/DD"（或 "2024/12/31" 格式）

        Returns:
            DataFrame，列为: code, report_date, rank, name, ratio, quantity
        """
        client = self._get_client()
        rows = []

        for code in codes:
            logger.info(f"获取前十大股东逐项: {code}, {report_date}")

            # 批量构建所有公式: 10 ranks × 3 fields = 30 公式
            formulas: list[str] = []
            formula_meta: list[tuple[int, str]] = []  # (rank, field)
            for rank in range(1, 11):
                for field, formula in [
                    ("name", wf.s_info_top10_holdername(code, report_date, rank)),
                    ("ratio", wf.s_info_top10_holderratio(code, report_date, rank)),
                    ("quantity", wf.s_info_top10_holderquantity(code, report_date, rank)),
                ]:
                    formulas.append(formula)
                    formula_meta.append((rank, field))

            raw = client.execute_batch(formulas)

            # 按 rank 聚合结果
            rank_data: dict[int, dict[str, Any]] = {}
            for idx, (rank, field) in enumerate(formula_meta):
                val = raw[idx]
                if isinstance(val, Exception):
                    continue
                rank_data.setdefault(rank, {})[field] = val

            for rank, data in sorted(rank_data.items()):
                name = data.get("name")
                if not name:
                    continue
                rows.append(
                    {
                        "code": code,
                        "report_date": report_date,
                        "rank": rank,
                        "name": str(name),
                        "ratio": data.get("ratio"),
                        "quantity": data.get("quantity"),
                    }
                )

        return pd.DataFrame(rows)

    # ===== 基类要求 =====

    def fetch(self, **kwargs: Any) -> list[DocumentEnvelope]:
        """获取 Wind 数据（基类 sync 接口）

        kwargs:
            data_type: str - "consensus", "margin_trading", "block_trades",
                       "daily_quotes", "financials", "industry", "fund_flow", "holders"
            codes: list[str]
            start_date: str (可选)
            end_date: str (可选)
            trade_date: str (可选, 一致预期用)
            report_date: str (可选, 财务/持有人用)
        """
        data_type = kwargs.get("data_type", "consensus")
        codes = kwargs.get("codes", [])
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")
        trade_date = kwargs.get("trade_date", None)
        report_date = kwargs.get("report_date", None)

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
        elif data_type == "daily_quotes":
            if not start_date or not end_date:
                raise ValueError("日行情数据需要 start_date 和 end_date")
            df = self.fetch_daily_quotes(codes, start_date, end_date)
        elif data_type == "financials":
            df = self.fetch_financial_statements(
                codes, trade_date=trade_date, report_date=report_date
            )
        elif data_type == "industry":
            df = self.fetch_industry_data(codes, trade_date=trade_date)
        elif data_type == "fund_flow":
            if not start_date or not end_date:
                raise ValueError("资金流向数据需要 start_date 和 end_date")
            df = self.fetch_fund_flow(codes, start_date, end_date)
        elif data_type == "holders":
            if not report_date:
                raise ValueError("持有人数据需要 report_date")
            df = self.fetch_holder_data(codes, report_date)
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
        """解析 Wind 原始数据

        支持从文件路径、字节串或字符串反序列化为 DocumentEnvelope。
        适用于从文件或缓存中恢复之前获取的 Wind 数据。

        Args:
            source: Path (读取文件), bytes/str (JSON 或 CSV 内容)
            **kwargs:
                data_type: str - 数据类型标识
                code: str - 证券代码
        """
        if isinstance(source, Path):
            content = source.read_text(encoding="utf-8")
        elif isinstance(source, bytes):
            content = source.decode("utf-8")
        else:
            content = source

        data_type = kwargs.get("data_type", "unknown")
        code = kwargs.get("code", "unknown")

        return self._create_document_envelope(
            content=content,
            metadata={
                "data_type": data_type,
                "code": code,
                "source": "wind_excel",
            },
        )
