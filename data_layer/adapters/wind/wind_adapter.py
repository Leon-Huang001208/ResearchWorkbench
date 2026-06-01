"""Wind 数据适配器 —— 通过 Excel 插件获取 Wind 数据"""

from datetime import datetime, timedelta
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

    # 日行情字段定义（_fetch_dq_recent_batch 和 fetch_daily_quotes 共享）
    _DQ_FIELD_KEYS = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "turnover",
        "adj_factor",
        "vwap",
        "pct_change",
        "amplitude",
    ]
    _DQ_FIELD_FNS = [
        wf.daily_open,
        wf.daily_high,
        wf.daily_low,
        wf.daily_close,
        wf.daily_volume,
        wf.daily_amount,
        wf.daily_turnover,
        wf.daily_adj_factor,
        wf.daily_vwap,
        wf.daily_pct_change,
        wf.daily_amplitude,
    ]
    _DQ_ADJ_FIELDS = {0, 1, 2, 3}  # open, high, low, close 需要 adj_type 参数

    def fetch_daily_quotes(
        self, codes: list[str], start_date: str, end_date: str, adj_type: int = 1
    ) -> pd.DataFrame:
        """获取日行情数据

        策略：WSD 获取交易日历日期（date + open 列可靠），
        然后用 execute_batch 批量补齐其余字段。

        Args:
            codes: 证券代码列表
            start_date: 起始日期 "YYYY-MM-DD"
            end_date: 截止日期 "YYYY-MM-DD"
            adj_type: 复权方式 1-不复权 2-后复权 3-前复权

        Returns:
            DataFrame
        """
        client = self._get_client()
        all_rows = []

        for code in codes:
            logger.info(f"获取日行情: {code}, {start_date}~{end_date}")

            # Step 1: WSD 获取交易日历日期（用 open 字段，只取日期列可靠）
            try:
                wsd_raw = client.execute_wsd(
                    code=code,
                    fields="open",
                    start_date=start_date,
                    end_date=end_date,
                    options="",
                )
            except Exception as exc:
                logger.warning(f"WSD 获取交易日历失败: {code}: {exc}")
                wsd_raw = []

            if not wsd_raw or len(wsd_raw) < 2:
                # 回退：生成 weekday 日期并批量获取
                logger.info(f"WSD 返回空，使用批处理回退: {code}")
                batch_raw = self._fetch_dq_recent_batch(
                    client, code, start_date, end_date, adj_type
                )
                if batch_raw and len(batch_raw) > 1:
                    for row in batch_raw[1:]:
                        all_rows.append(self._dq_row_to_dict(code, row))
                continue

            # 从 WSD 提取日期列表（raw_value 返回无表头，直接是数据行）
            # 注意：WSD 返回的矩阵可能有大量空行 padding（由 WSD_MAX_ROWS 导致），
            # 需要在第一个空行处停止以避免处理大量无效行
            trading_dates = []
            for row in wsd_raw:
                if not row or len(row) == 0:
                    continue
                date_val = row[0]
                if date_val is None:
                    # WSD 数据按时间顺序排列，遇到 None 说明后面都是空行
                    break
                if isinstance(date_val, str) and not date_val.strip():
                    # 空字符串 → 已到达数据末尾
                    break
                if isinstance(date_val, (int, float)):
                    # Excel serial number → date string
                    try:
                        excel_epoch = datetime(1899, 12, 30)
                        dt_val = excel_epoch + timedelta(days=int(date_val))
                        trading_dates.append(dt_val.strftime("%Y-%m-%d"))
                    except (ValueError, OverflowError):
                        continue
                elif isinstance(date_val, datetime):
                    trading_dates.append(date_val.strftime("%Y-%m-%d"))
                else:
                    # 字符串日期，尝试解析
                    date_str = str(date_val).strip()
                    if date_str:
                        trading_dates.append(date_str[:10])

            if not trading_dates:
                logger.warning(f"WSD 返回空日期列表: {code}")
                continue

            # Step 2: 批量获取所有日期 × 所有字段的单值公式
            n_dates = len(trading_dates)
            n_fields = len(self._DQ_FIELD_KEYS)
            total_formulas = n_dates * n_fields
            logger.info(f"批量获取 {code}: {n_dates} 天 × {n_fields} 字段 = {total_formulas} 公式")

            formulas = []
            formula_dates = []
            for date_str in trading_dates:
                for f_idx, fn in enumerate(self._DQ_FIELD_FNS):
                    formula_dates.append(date_str)
                    if f_idx in self._DQ_ADJ_FIELDS:
                        formulas.append(fn(code, date_str, adj_type))
                    else:
                        formulas.append(fn(code, date_str))

            # 分批执行（每批最多 200 个公式，避免 Excel 过载）
            BATCH_SIZE = 200
            all_raw = []
            for batch_start in range(0, len(formulas), BATCH_SIZE):
                batch = formulas[batch_start : batch_start + BATCH_SIZE]
                batch_results = client.execute_batch(batch)
                all_raw.extend(batch_results)

            # Step 3: 解析结果并组装为行
            for day_idx, date_str in enumerate(trading_dates):
                base = day_idx * n_fields
                row_data = {"code": code, "date": date_str}
                all_ok = True
                for f_idx in range(n_fields):
                    val = all_raw[base + f_idx]
                    if isinstance(val, Exception):
                        row_data[self._DQ_FIELD_KEYS[f_idx]] = None
                        all_ok = False
                    else:
                        row_data[self._DQ_FIELD_KEYS[f_idx]] = _safe_float_wind(val)
                if all_ok:
                    all_rows.append(row_data)
                else:
                    # 即使部分字段缺失也保留（至少 date + open 会有）
                    all_rows.append(row_data)

        return pd.DataFrame(all_rows)

    def _dq_row_to_dict(self, code: str, row: list) -> dict:
        """将 _fetch_dq_recent_batch 的行转为字典"""
        if len(row) < 2:
            return {}
        result = {"code": code, "date": str(row[0])[:10] if row[0] else None}
        for i, key in enumerate(self._DQ_FIELD_KEYS):
            result[key] = _safe_float_wind(row[i + 1] if len(row) > i + 1 else None)
        return result

    def _fetch_dq_recent_batch(
        self, client, code: str, start_date: str, end_date: str, adj_type: int = 1
    ) -> list[list]:
        """回退方案：生成 weekday 日期列表并批量获取行情"""
        date_range = pd.date_range(start=start_date, end=end_date, freq="B")
        if len(date_range) > 60:
            # 超过 60 个交易日则只取最近 60 天
            date_range = date_range[-60:]
        date_range = date_range.sort_values()

        logger.info(f"批处理获取行情: {code}, {len(date_range)} 天")

        formulas = []
        dates = []
        for dt in date_range:
            date_str = dt.strftime("%Y-%m-%d")
            for f_idx, fn in enumerate(self._DQ_FIELD_FNS):
                dates.append(date_str)
                if f_idx in self._DQ_ADJ_FIELDS:
                    formulas.append(fn(code, date_str, adj_type))
                else:
                    formulas.append(fn(code, date_str))

        raw = client.execute_batch(formulas)

        def _val(idx):
            r = raw[idx]
            return None if isinstance(r, Exception) else r

        header = ["DATE"] + self._DQ_FIELD_KEYS
        result = [header]
        n_fields = len(self._DQ_FIELD_KEYS)
        for day_idx in range(len(date_range)):
            base = day_idx * n_fields
            data_row = [dates[base]]
            for f_idx in range(n_fields):
                data_row.append(_val(base + f_idx))
            result.append(data_row)

        return result

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

        优化：所有日期 × 5 字段一次性写入 Excel 批量执行（而非按日循环），
        将 244 次 Excel 往返减少到 1 次。

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
            logger.info(f"获取资金流向: {code}, {start_date}~{end_date} ({len(date_range)} 个交易日)")
            # 一次性构建所有日期 × 所有字段的公式列表
            dates: list[str] = []
            formulas: list[str] = []
            field_keys = [
                "main_force_inflow",
                "main_force_open",
                "main_force_close",
                "north_bound_shares",
                "north_bound_pct",
            ]
            field_fns = [
                wf.moneyflow_main_force,
                wf.moneyflow_main_force_open,
                wf.moneyflow_main_force_close,
                wf.north_bound_shares,
                wf.north_bound_pct,
            ]

            for dt in date_range:
                date_str = dt.strftime("%Y-%m-%d")
                for fn in field_fns:
                    dates.append(date_str)
                    formulas.append(fn(code, date_str))

            # 一次性批量执行
            raw = client.execute_batch(formulas)

            def _val(idx: int):
                r = raw[idx]
                return None if isinstance(r, Exception) else r

            # 按日期重新分组结果
            n_fields = len(field_keys)
            for day_idx in range(len(date_range)):
                base = day_idx * n_fields
                rows.append(
                    {
                        "code": code,
                        "date": dates[base],
                        "main_force_inflow": _val(base),
                        "main_force_open": _val(base + 1),
                        "main_force_close": _val(base + 2),
                        "north_bound_shares": _val(base + 3),
                        "north_bound_pct": _val(base + 4),
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


def _safe_float_wind(value) -> float | None:
    """Wind 公式返回值转 float，None/非数字返回 None"""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
