"""CJPY 0.5.2 adapter: explicit clients, isolated proxies, and lossless source APIs."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from core.contracts import DocumentEnvelope
from core.contracts.datahub import DATASETS, DataHubSyncRequest
from core.observability import get_logger
from data_layer.adapters.base import BaseDataAdapter

logger = get_logger(__name__)


class CjpyAdapter(BaseDataAdapter):
    """Own an SDK client; never change global SDK tokens or proxy environment."""

    def __init__(self, token: str | None = None, *, timeout: float = 30, client: Any = None):
        super().__init__(source_type="vendor_snapshot")
        self._token = token
        self._client = client
        self.timeout = timeout
        self._factor_repo_cache = None
        self._tables_cache = None

    def _get_token(self) -> str | None:
        if self._token:
            return self._token
        from cjpy.base import CjConfigError, get_token

        try:
            return get_token(os.getenv("CJ_KEY"))
        except CjConfigError:
            return None

    def _ensure_token(self) -> str:
        token = self._get_token()
        if not token:
            raise RuntimeError("cjpy token 未配置，请在本机设置 CJ_KEY 或 cjpy.set_token()")
        return token

    def _get_client(self):
        if self._client is None:
            from cjpy.base import CjClient

            class DirectClient(CjClient):
                def _create_session(self):
                    session = super()._create_session()
                    session.trust_env = False
                    return session

            self._client = DirectClient(
                token=self._ensure_token(), timeout=self.timeout, verify=True
            )
        return self._client

    def health(self) -> dict:
        from importlib.metadata import PackageNotFoundError, version

        try:
            installed = version("cjpy")
        except PackageNotFoundError:
            return {"status": "unavailable", "reason": "not_installed", "version": None}
        try:
            if not self._get_token():
                return {"status": "unavailable", "reason": "not_configured", "version": installed}
            self.query("universes")
            return {"status": "healthy", "reason": None, "version": installed}
        except Exception as exc:
            # SDK exceptions may embed upstream bodies or headers: log only the class.
            logger.warning("cjpy health failed", error_type=type(exc).__name__)
            return {"status": "unavailable", "reason": type(exc).__name__, "version": installed}

    def is_available(self) -> bool:
        return self.health()["status"] == "healthy"

    def query(self, dataset: str, **params: Any) -> Any:
        """Only dispatch explicitly listed SDK methods; no arbitrary attribute access."""
        import cjpy

        request = DataHubSyncRequest(dataset=dataset, params=params)
        p = request.params
        args: dict[str, Any] = {"client": self._get_client()}
        if dataset in {"stock_list", "fund_list", "codes", "index_constituents"}:
            args["date"] = p.get("date")
        if dataset == "codes":
            args["universe"] = p["universe"]
        if dataset in {"daily_quotes", "trading_days", "table_data", "macro_data"}:
            args.update(start=p.get("start_date"), end=p.get("end_date"))
        if dataset in {"daily_quotes", "index_constituents"}:
            if len(p["codes"]) != 1:
                raise ValueError("This SDK query requires exactly one code per batch")
            args["code"] = p["codes"][0]
        elif dataset in {"table_data", "factor_data"}:
            args["code"] = p["codes"]
        elif dataset == "trading_days" and p.get("codes"):
            args["code"] = p["codes"][0]
        if dataset == "daily_quotes":
            rates = {"none": "不复权", "forward": "前复权", "backward": "后复权"}
            rate = p.get("rate", "前复权")
            args.update(
                cycle=p.get("cycle", "day"), rate=rates.get(rate, rate), fields=p.get("fields")
            )
        if dataset == "trading_days":
            args["cycle"] = p.get("cycle", "D")
        if dataset in {"table_data", "table_fields"}:
            args["table_name"] = p["table_name"]
        if dataset == "table_data":
            args["fields"] = p.get("fields")
        if dataset == "macro_data":
            args["indicator"] = p["indicator"]
        if dataset == "factor_data":
            args.update(
                date=p.get("dates") or p.get("date"), factors=p["factors"], repo=p.get("repo")
            )
        try:
            result = getattr(cjpy, DATASETS[dataset][1])(**args)
            logger.info(
                "cjpy query completed",
                dataset=dataset,
                count=len(result) if result is not None else 0,
            )
            return result
        except Exception as exc:
            logger.warning("cjpy query failed", dataset=dataset, error_type=type(exc).__name__)
            raise RuntimeError(f"CJPY {dataset} failed ({type(exc).__name__})") from None

    def fetch_stock_list(self, date=None):
        return self.query("stock_list", **({"date": date} if date else {}))

    def fetch_fund_list(self, date=None):
        return self.query("fund_list", **({"date": date} if date else {}))

    def fetch_trading_days(self, start, end, cycle="D", code=None):
        return self.query(
            "trading_days",
            start_date=start,
            end_date=end,
            cycle=cycle,
            **({"codes": [code]} if code else {}),
        )

    def fetch_daily_quotes(self, codes, start_date, end_date, cycle="day", rate="前复权"):
        frames = []
        for code in dict.fromkeys(codes):
            frame = self.query(
                "daily_quotes",
                codes=[code],
                start_date=start_date,
                end_date=end_date,
                cycle=cycle,
                rate=rate,
            )
            if frame is not None and not frame.empty:
                from data_layer.normalizers.cjpy import canonical_code

                for key in ("code", "CODE", "代码", "证券代码"):
                    if key in frame and any(
                        canonical_code(value) != canonical_code(code) for value in frame[key]
                    ):
                        logger.warning("cjpy legacy response identity mismatch")
                        raise ValueError("CJPY returned a different security")
                frames.append(frame if "code" in frame else frame.assign(code=code))
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def fetch_factor_data(self, codes, dates, factors, repo=None):
        params = {"codes": codes, "factors": factors, "repo": repo}
        params["date" if isinstance(dates, str) else "dates"] = dates
        return self.query("factor_data", **params)

    def fetch_table_data(self, codes, table_name, fields=None, start=None, end=None):
        return self.query(
            "table_data",
            codes=[codes] if isinstance(codes, str) else codes,
            table_name=table_name,
            fields=fields,
            start_date=start,
            end_date=end,
        )

    def get_supported_tables(self):
        result = self.query("tables")
        return result["表名"].tolist() if "表名" in result else []

    def get_factor_repo(self):
        import cjpy

        # Compatibility for existing callers. New discovery preserves the full list_factors table.
        return dict(cjpy.get_factor_repo(client=self._get_client()).iloc[:, 0])

    def subscribe(self, ids, fields, on_event=None):
        import cjpy

        logger.info("cjpy subscription starting", count=len(ids))
        return cjpy.subscribe(ids=ids, fields=fields, on_event=on_event, client=self._get_client())

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
