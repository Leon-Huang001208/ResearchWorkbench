"""Frozen structured logging adapter, with no Host configuration import."""

import logging


class Logger:
    def __init__(self, name, bound=None):
        self.logger = logging.getLogger(name)
        self.bound = bound or {}

    def bind(self, **values):
        return Logger(self.logger.name, {**self.bound, **values})

    def _emit(self, level, message, args, values):
        exc_info = values.pop("exc_info", False)
        stack_info = values.pop("stack_info", False)
        fields = {**self.bound, **values}
        message = str(message) % args if args else str(message)
        if fields:
            message += " " + " ".join(f"{key}={fields[key]!r}" for key in sorted(fields))
        self.logger.log(level, "%s", message, exc_info=exc_info, stack_info=stack_info)

    def debug(self, message, *args, **values):
        self._emit(logging.DEBUG, message, args, values)

    def info(self, message, *args, **values):
        self._emit(logging.INFO, message, args, values)

    def warning(self, message, *args, **values):
        self._emit(logging.WARNING, message, args, values)

    def error(self, message, *args, **values):
        self._emit(logging.ERROR, message, args, values)

    def exception(self, message, *args, **values):
        self._emit(logging.ERROR, message, args, {**values, "exc_info": True})


def get_logger(name):
    return Logger(name)
