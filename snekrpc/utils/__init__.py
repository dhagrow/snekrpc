"""Utility helpers and convenience imports used throughout the codebase."""

from __future__ import annotations

import threading
from typing import Any, Callable

from .. import logs

# Imports for convenience
from . import format, function, path, retry, url

DEFAULT_URL = 'tcp://127.0.0.1:12321'

log = logs.get(__name__)


def start_thread(func: Callable[..., Any], *args: Any, **kwargs: Any) -> threading.Thread:
    """Start *func* in a daemon thread and return the thread object."""

    def safe(*run_args: Any, **run_kwargs: Any) -> Any:
        tid = threading.current_thread().ident
        log.debug('thread started [%s]: %s', tid, func.__name__)
        try:
            return func(*run_args, **run_kwargs)
        except Exception:
            log.exception('thread error')
        finally:
            log.debug('thread stopped [%s]: %s', tid, func.__name__)

    thread = threading.Thread(target=safe, args=args, kwargs=kwargs, daemon=True)
    thread.start()
    return thread


__all__ = [
    'DEFAULT_URL',
    'format',
    'function',
    'path',
    'retry',
    'start_thread',
    'url',
]
