"""日志配置工具模块"""
from typing import Optional

from core.observability import get_logger


def setup_logging(
    logger_name: str,
    verbose: bool = True,
    log_to_file: bool = True,
    log_filename: Optional[str] = None,
    log_dir: str = "logs",
):
    """通用日志配置函数"""
    logger = get_logger(logger_name)
    return logger
