from __future__ import annotations

import threading
from typing import Any, Callable, TypeVar

from .. import logs

# Imports for convenience
from . import encoding, format, function as _function, path, retry, url

DEFAULT_URL = 'tcp://127.0.0.1:12321'

log = logs.get(__name__)

Func = TypeVar('Func', bound=Callable[..., Any])


def start_thread(func: Func, *args: Any, **kwargs: Any) -> threading.Thread:
    """Start *func* in a daemon thread and return the thread object."""

    def safe(*run_args: Any, **run_kwargs: Any) -> Any:
        tid = threading.current_thread().ident
        log.debug('thread started [%s]: %s', tid, func.__name__)
        try:
            return func(*run_args, **run_kwargs)
        except Exception:  # pragma: no cover - best effort logging
            log.exception('thread error')
        finally:
            log.debug('thread stopped [%s]: %s', tid, func.__name__)

    thread = threading.Thread(target=safe, args=args, kwargs=kwargs)
    thread.daemon = True
    thread.start()
    return thread


function: Any = _function

__all__ = [
    'DEFAULT_URL',
    'encoding',
    'format',
    'function',
    'path',
    'retry',
    'start_thread',
    'url',
]
