"""iFinD 数据源自定义异常"""
import logging

logger = logging.getLogger(__name__)


class IFinDError(Exception):
    """iFinD 数据源基础异常"""
    pass


class IFinDAuthError(IFinDError):
    """iFinD 认证失败异常"""
    pass


class IFinDQuotaExceededError(IFinDError):
    """iFinD 配额超限异常"""
    pass


class IFinDDatasourceError(IFinDError):
    """iFinD 数据源错误异常"""
    pass


class IFinDSDKNotAvailableError(IFinDError):
    """iFinD Python SDK 不可用异常"""
    pass


class IFinDRateLimitError(IFinDError):
    """iFinD 限流异常"""
    pass
