"""iFinD 客户端协议定义"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class IFinDClient(Protocol):
    """iFinD 客户端协议 - SDK 和 HTTP 后端必须实现"""

    async def login(self) -> bool:
        """登录认证，返回是否成功"""
        ...

    async def logout(self) -> None:
        """登出并释放资源"""
        ...

    async def is_alive(self) -> bool:
        """健康检查：后端是否可用"""
        ...

    async def history(
        self,
        codes: list[str],
        indicators: list[str],
        start_date: str,
        end_date: str,
        frequency: str = "day",
    ) -> list[dict]:
        """
        历史行情查询

        Args:
            codes: 证券代码列表，如 ["600519.SH"]
            indicators: 指标列表，如 ["ths_open_stock", "ths_close_stock"]
            start_date: 起始日期 "YYYY-MM-DD"
            end_date: 截止日期 "YYYY-MM-DD"
            frequency: "day" | "week" | "month"
        """
        ...

    async def realtime(self, codes: list[str], indicators: list[str]) -> list[dict]:
        """实时行情查询"""
        ...

    async def basic(self, codes: list[str], indicators: list[str]) -> list[dict]:
        """基础数据查询（股票资料、行业分类等）"""
        ...

    async def financial(
        self,
        codes: list[str],
        indicators: list[str],
        report_date: str | None = None,
    ) -> list[dict]:
        """财务数据查询"""
        ...

    async def date_serial(
        self,
        codes: list[str],
        indicators: list[str],
        start_date: str,
        end_date: str,
    ) -> list[dict]:
        """日期序列数据查询（以时间维度提取基本面）"""
        ...

    async def data_pool(
        self,
        report_name: str,
        parameters: dict | None = None,
    ) -> list[dict]:
        """专题报表数据池查询"""
        ...

    async def edb_query(
        self,
        indicators: list[str],
        start_date: str,
        end_date: str,
    ) -> list[dict]:
        """宏观经济数据库查询"""
        ...
