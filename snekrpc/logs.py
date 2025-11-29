"""Helpers for configuring and using project logging."""

from __future__ import annotations

import sys
from logging import DEBUG, INFO, Formatter, StreamHandler, getLogger
from types import TracebackType

get = getLogger
log = get(__name__)


def init(debug_level: int = 0, log_exceptions: bool = True) -> None:
    """Initializes simple logging defaults."""
    root_log = get()

    if root_log.handlers:
        return

    fmt = '%(levelname).1s %(asctime)s . %(message)s'
    formatter = Formatter(fmt)

    handler = StreamHandler()
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
