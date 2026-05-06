
"""AkShare 适配器异常类"""


class AkShareAdapterError(Exception):
    """AkShare 适配器基础异常"""
    pass


class AkShareDataError(AkShareAdapterError):
    """数据获取失败异常"""
    pass


class AkShareRateLimitError(AkShareAdapterError):
    """速率限制异常"""
    pass


class AkShareClientError(AkShareAdapterError):
    """AkShare 客户端调用失败异常"""
    pass

