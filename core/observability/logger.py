"""
Logging utilities with structlog fallback to standard library.

Provides configure_logging (for CLI use), setup_logging (for full app use), and
get_logger, plus _SimpleLoggerWrapper to emulate structlog's interface when
structlog isn't installed.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from core.settings import settings

# Try to import structlog, fall back to standard library if not available
try:
    import structlog

    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False


def configure_logging(level: str = "INFO", log_file: str | None = None) -> None:
    """配置日志（简化版本，供 CLI 使用）.

    Configures simple standard library logging (without structlog) for CLI use. Sets
    up a stream handler (stdout) and a file handler (either the given log_file or a
    daily log in LOG_DIR).

    Args:
        level: Log level (e.g., "DEBUG", "INFO", "WARNING", "ERROR").
        log_file: Optional path to a log file to write to.
    """
    if getattr(configure_logging, "_configured", False):
        return
    configure_logging._configured = True  # type: ignore[attr-defined]

    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Wrap stdout with UTF-8 to prevent UnicodeEncodeError on Windows GBK terminals
    stdout_stream = open(
        sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False, buffering=1
    )
    handler: logging.Handler = logging.StreamHandler(stdout_stream)
    handler.setFormatter(formatter)

    handlers: list[logging.Handler] = [handler]

    if log_file:
        file_handler: logging.Handler = logging.FileHandler(log_file, encoding="utf-8")
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
    """配置日志.

    Full logging setup: uses _setup_structlog if structlog is available, otherwise
    _setup_simple_logging. Sets up both stdout and daily file handlers, using
    settings.LOG_LEVEL and settings.LOG_DIR.
    """
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    if HAS_STRUCTLOG:
        _setup_structlog(log_dir)
    else:
        _setup_simple_logging(log_dir)


def _setup_structlog(log_dir: Path) -> None:
    """配置结构化日志.

    Configures structlog with shared processors (log level, logger name, timestamp),
    then configures both stdout and daily file handlers. Uses ConsoleRenderer for
    TTY (interactive) stdout, JSONRenderer otherwise, and ProcessorFormatter for
    standard library logging integration.

    Args:
        log_dir: Directory to write the daily log file to.
    """
    # Guard against duplicate handler registration when called multiple times
    if getattr(_setup_structlog, "_configured", False):
        return
    _setup_structlog._configured = True  # type: ignore[attr-defined]

    # Configure timestamp format
    timestamper = structlog.processors.TimeStamper(fmt="iso")

    # Shared processors for both structlog and standard library logs
    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
    ]

    # Configure structlog
    structlog.configure(
        processors=shared_processors  # type: ignore[arg-type]
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

    # Configure standard library logging handlers
    # Wrap stdout with UTF-8 to prevent UnicodeEncodeError on Windows GBK terminals
    # when log messages contain non-GBK characters (e.g. Japanese, emoji, etc.)
    stdout_stream = open(
        sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False, buffering=1
    )
    handler = logging.StreamHandler(stdout_stream)
    file_handler = logging.FileHandler(
        log_dir / f"alphafoundry_{datetime.now().strftime('%Y%m%d')}.log",
        encoding="utf-8",
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=(
            structlog.dev.ConsoleRenderer()
            if sys.stdout.isatty()
            else structlog.processors.JSONRenderer()
        ),
        foreign_pre_chain=shared_processors,  # type: ignore[arg-type]
    )

    handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL))


def _setup_simple_logging(log_dir: Path) -> None:
    """配置简单日志（structlog 不可用时）.

    Configures simple standard library logging when structlog is not available. Sets
    up a stream handler (stdout) and a daily file handler in log_dir, using
    settings.LOG_LEVEL.

    Args:
        log_dir: Directory to write the daily log file to.
    """
    if getattr(_setup_simple_logging, "_configured", False):
        return
    _setup_simple_logging._configured = True  # type: ignore[attr-defined]

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Wrap stdout with UTF-8 to prevent UnicodeEncodeError on Windows GBK terminals
    stdout_stream = open(
        sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False, buffering=1
    )
    handler = logging.StreamHandler(stdout_stream)
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


def get_logger(name: str) -> Any:
    """获取 logger.

    Returns a logger instance: structlog.get_logger(name) if structlog is available,
    otherwise a _SimpleLoggerWrapper that emulates structlog's bind and key-value
    message format.

    Args:
        name: Name of the logger (typically __name__).

    Returns:
        Logger: Structlog logger or _SimpleLoggerWrapper instance.
    """
    if HAS_STRUCTLOG:
        return structlog.get_logger(name)
    else:
        return _SimpleLoggerWrapper(logging.getLogger(name))


class _SimpleLoggerWrapper:
    """简单 logger 包装器，提供类似 structlog 的接口.

    Wrapper around a standard library logging.Logger that provides a similar interface
    to structlog: bind() to add context variables, and debug/info/warning/error/
    exception methods that accept **kwargs and format them into the message.
    """

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger
        self._context: dict[str, Any] = {}

    def bind(self, **kwargs: Any) -> "_SimpleLoggerWrapper":
        """绑定上下文变量到 logger.

        Creates a new _SimpleLoggerWrapper with the given kwargs added to the context.

        Args:
            **kwargs: Key-value pairs to add to the logger context.

        Returns:
            _SimpleLoggerWrapper: New wrapper instance with updated context.
        """
        new_logger = _SimpleLoggerWrapper(self._logger)
        new_logger._context = {**self._context, **kwargs}
        return new_logger

    def _format_msg(self, msg: str, **kwargs: Any) -> str:
        """格式化消息，附加上下文变量.

        Formats the message by appending key-value pairs from self._context and kwargs
        as space-separated "key=value" strings.

        Args:
            msg: Base log message.
            **kwargs: Additional key-value pairs to include.

        Returns:
            str: Formatted message string.
        """
        if kwargs or self._context:
            all_ctx = {**self._context, **kwargs}
            ctx_str = " ".join([f"{k}={v}" for k, v in all_ctx.items()])
            return f"{msg} {ctx_str}"
        return msg

    def debug(self, msg: str, **kwargs: Any) -> None:
        self._logger.debug(self._format_msg(msg, **kwargs))

    def info(self, msg: str, **kwargs: Any) -> None:
        self._logger.info(self._format_msg(msg, **kwargs))

    def warning(self, msg: str, **kwargs: Any) -> None:
        self._logger.warning(self._format_msg(msg, **kwargs))

    def warn(self, msg: str, **kwargs: Any) -> None:
        self._logger.warning(self._format_msg(msg, **kwargs))

    def error(self, msg: str, **kwargs: Any) -> None:
        self._logger.error(self._format_msg(msg, **kwargs), exc_info=kwargs.get("exc_info"))

    def exception(self, msg: str, **kwargs: Any) -> None:
        self._logger.exception(self._format_msg(msg, **kwargs))
