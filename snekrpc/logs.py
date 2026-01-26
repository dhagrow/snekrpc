"""Helpers for configuring and using project logging."""

from __future__ import annotations

import sys
from logging import DEBUG, INFO, Formatter, StreamHandler, getLogger
from logging import Logger as Logger
from types import TracebackType
from typing import Callable

try:
    import colorlog
except ImportError:
    colorlog = None  # type: ignore

get = getLogger
log = get(__name__)


def is_debug(log: Logger) -> bool:
    return log.isEnabledFor(DEBUG)


def error_logger(logger: Logger) -> Callable[..., None]:
    return logger.exception if is_debug(logger) else logger.error


def init(debug_level: int = 0, use_color: bool = True, log_exceptions: bool = True) -> None:
    """Initializes simple logging defaults."""
    root_log = get()
    handler = StreamHandler()

    if not use_color or colorlog is None:
        formatter = Formatter('%(levelname)8s %(asctime)s . %(message)s')
    else:
        formatter = colorlog.ColoredFormatter(
            '%(log_color)s%(levelname)8s %(asctime)s . %(message)s',
            log_colors={
                'DEBUG': 'thin_white',
                'INFO': 'white',
                'WARNING': 'bold_yellow',
                'ERROR': 'bold_red',
                'CRITICAL': 'bold_white,bg_bold_red',
            },
        )

    if root_log.handlers:
        return

    handler.setFormatter(formatter)

    root_log.addHandler(handler)
    root_log.setLevel(DEBUG if debug_level > 0 else INFO)

    transport_log = get('snekrpc.transport')
    transport_log.setLevel(DEBUG if debug_level > 1 else INFO)

    utils_log = get('snekrpc.utils')
    utils_log.setLevel(DEBUG if debug_level > 1 else INFO)

    if log_exceptions:
        sys.excepthook = handle_exception


def handle_exception(
    etype: type[BaseException],
    evalue: BaseException,
    etb: TracebackType | None,
) -> None:
    """Log uncaught exceptions while letting Ctrl+C exit quietly."""
    if issubclass(etype, KeyboardInterrupt):
        sys.__excepthook__(etype, evalue, etb)
        return
    log.error('unhandled exception', exc_info=(etype, evalue, etb))
