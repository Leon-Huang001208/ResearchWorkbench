import logging
import sys
from datetime import datetime
from pathlib import Path

from core.settings import settings

# 尝试导入 structlog，如果不可用则回退到标准库
try:
    import structlog

    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False


def configure_logging(level: str = "INFO", log_file: str | None = None) -> None:
    """配置日志（简化版本，供 CLI 使用）"""
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    handlers = [handler]

    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    else:
        file_handler = logging.FileHandler(
            log_dir / f"alphafoundry_{datetime.now().strftime('%Y%m%d')}.log",
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    root_logger = logging.getLogger()
    for h in handlers:
        root_logger.addHandler(h)
    root_logger.setLevel(getattr(logging, level))


def setup_logging() -> None:
    """配置日志"""
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    if HAS_STRUCTLOG:
        _setup_structlog(log_dir)
    else:
        _setup_simple_logging(log_dir)


def _setup_structlog(log_dir: Path):
    """配置结构化日志"""
    # 配置时间戳格式
    timestamper = structlog.processors.TimeStamper(fmt="iso")

    # 共享的处理器
    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
    ]

    # 配置 structlog
    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.render_to_log_kwargs,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 配置标准库 logging
    handler = logging.StreamHandler(sys.stdout)
    file_handler = logging.FileHandler(
        log_dir / f"alphafoundry_{datetime.now().strftime('%Y%m%d')}.log",
        encoding="utf-8",
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer()
        if sys.stdout.isatty()
        else structlog.processors.JSONRenderer(),
        foreign_pre_chain=shared_processors,
    )

    handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL))


def _setup_simple_logging(log_dir: Path):
    """配置简单日志（structlog 不可用时）"""
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    file_handler = logging.FileHandler(
        log_dir / f"alphafoundry_{datetime.now().strftime('%Y%m%d')}.log",
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL))


def get_logger(name: str):
    """获取 logger"""
    if HAS_STRUCTLOG:
        return structlog.get_logger(name)
    else:
        return _SimpleLoggerWrapper(logging.getLogger(name))


class _SimpleLoggerWrapper:
    """简单 logger 包装器，提供类似 structlog 的接口"""

    def __init__(self, logger):
        self._logger = logger
        self._context = {}

    def bind(self, **kwargs):
        new_logger = _SimpleLoggerWrapper(self._logger)
        new_logger._context = {**self._context, **kwargs}
        return new_logger

    def _format_msg(self, msg, **kwargs):
        if kwargs or self._context:
            all_ctx = {**self._context, **kwargs}
            ctx_str = " ".join([f"{k}={v}" for k, v in all_ctx.items()])
            return f"{msg} {ctx_str}"
        return msg

    def debug(self, msg, **kwargs):
        self._logger.debug(self._format_msg(msg, **kwargs))

    def info(self, msg, **kwargs):
        self._logger.info(self._format_msg(msg, **kwargs))

    def warning(self, msg, **kwargs):
        self._logger.warning(self._format_msg(msg, **kwargs))

    def warn(self, msg, **kwargs):
        self._logger.warning(self._format_msg(msg, **kwargs))

    def error(self, msg, **kwargs):
        self._logger.error(self._format_msg(msg, **kwargs), exc_info=kwargs.get("exc_info"))

    def exception(self, msg, **kwargs):
        self._logger.exception(self._format_msg(msg, **kwargs))
