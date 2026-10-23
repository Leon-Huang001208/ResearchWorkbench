"""Read macOS Excel instance identities without starting another application."""

from __future__ import annotations

import importlib
import re
import sys
import threading
from typing import Any

from core.observability import get_logger

from .exceptions import WindNotConnectedError

log = get_logger(__name__)
_COMPAT_LOCK = threading.Lock()


class _ProcessOutputCompat:
    """Normalize only xlwings' PID reads; leave the subprocess module untouched.

    xlwings repeats the same legacy parser when activating a workbook. Keeping
    the wrapper on its private module also covers that path and exit cleanup,
    without editing installed packages or caching process identities.
    """

    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    def check_output(self, arguments: Any, *args: Any, **kwargs: Any) -> Any:
        pid_query = (
            isinstance(arguments, (list, tuple))
            and len(arguments) == 5
            and arguments[0] in {"lsappinfo", "/usr/bin/lsappinfo"}
            and list(arguments[1:4]) == ["info", "-only", "pid"]
        )
        if pid_query:
            kwargs.setdefault("timeout", 5)
        result = self._delegate.check_output(arguments, *args, **kwargs)
        if not pid_query:
            return result
        record = result.decode("utf-8") if isinstance(result, bytes) else result
        assignments = re.findall(r'(?:"pid"|\bpid)\s*=', record)
        identity = re.search(
            r'(?m)^[ \t]*(?:"pid"|pid)[ \t]*=[ \t]*([1-9][0-9]*)'
            r"(?:[ \t]+!cgsConnection(?:[ \t]+[^\r\n]*)?)?[ \t]*$",
            record,
        )
        if len(assignments) != 1:
            raise ValueError("excel_pid_record_invalid")
        if identity is not None:
            normalized = f'"pid"={identity[1]}\n'
        elif re.fullmatch(r'\s*"pid"\s*=\s*\[ NULL \]\s*', record):
            normalized = '"pid"=[ NULL ] \n'
        else:
            raise ValueError("excel_pid_record_invalid")
        return normalized.encode("utf-8") if isinstance(result, bytes) else normalized


def prepare_macos_excel_compat() -> None:
    """Prepare a loaded native bridge without inspecting any user's instances.

    An explicitly isolated client must not enumerate existing applications, but
    its first workbook activation can still use the same legacy PID parser.
    Importing xlwings loads this bridge on supported Mac installations.
    """
    if sys.platform != "darwin":
        return
    native = sys.modules.get("xlwings._xlmac")
    if native is None or not hasattr(native, "subprocess"):
        return
    with _COMPAT_LOCK:
        if not isinstance(native.subprocess, _ProcessOutputCompat):
            native.subprocess = _ProcessOutputCompat(native.subprocess)
            log.info("wind_excel_pid_output_compat_prepared")


def running_excel_apps(xw: Any) -> list[Any]:
    """Recover the known xlwings parser failure; refuse other inventory errors."""
    try:
        return list(xw.apps)
    except ValueError as exc:
        if sys.platform != "darwin" or "invalid literal for int()" not in str(exc):
            log.warning("wind_excel_inventory_failed", error_type=type(exc).__name__)
            raise WindNotConnectedError("Excel 实例身份无法确认，未启动新实例") from exc
        try:
            native = importlib.import_module("xlwings._xlmac")
            with _COMPAT_LOCK:
                if not isinstance(native.subprocess, _ProcessOutputCompat):
                    native.subprocess = _ProcessOutputCompat(native.subprocess)
            apps = list(xw.apps)
        except Exception as recovery_error:
            log.warning(
                "wind_excel_inventory_recovery_failed",
                error_type=type(recovery_error).__name__,
            )
            raise WindNotConnectedError("Excel 实例身份无法确认，未启动新实例") from recovery_error
        log.info("wind_excel_inventory_recovered", instance_count=len(apps))
        return apps
    except Exception as exc:
        log.warning("wind_excel_inventory_failed", error_type=type(exc).__name__)
        raise WindNotConnectedError("Excel 实例身份无法确认，未启动新实例") from exc
