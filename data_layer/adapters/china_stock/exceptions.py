"""China Stock 适配器异常类"""


class ChinaStockAdapterError(Exception):
    """China Stock 适配器基础异常"""

    pass


class ChinaStockDataError(ChinaStockAdapterError):
    """数据获取失败异常"""

    pass


class ChinaStockRateLimitError(ChinaStockAdapterError):
    """速率限制异常"""

    pass


class ChinaStockPluginError(ChinaStockAdapterError):
    """插件调用失败异常"""

    pass
