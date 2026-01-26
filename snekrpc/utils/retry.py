"""Generic retry helper for client calls."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from typing import Any, Sequence, TypeVar

from .. import logs
from .format import format_exc

RETRY_COUNT = 0
RETRY_INTERVAL = 1.0
RETRY_ERRORS = (Exception,)
RETRY_LOG_TEMPLATE = '{error} (retrying: {retries})'

log = logs.get(__name__)

T_Result = TypeVar('T_Result')
T_Generator = TypeVar('T_Generator')


class Retry:
    """Call functions with configurable retry/backoff support."""

    def __init__(
        self,
        count: int | None = None,
        interval: float | None = None,
        errors: Sequence[type[BaseException]] | None = None,
        logger: logs.Logger = log,
        log_template: str | None = None,
    ) -> None:
        """Configure retry counts, intervals, and error classes."""
        self.count = RETRY_COUNT if count is None else count
        self.interval = RETRY_INTERVAL if interval is None else interval
        self.errors = tuple(errors or RETRY_ERRORS)

        self.log = logs.error_logger(logger)
        self.log_template = log_template or RETRY_LOG_TEMPLATE

    def call(self, func: Callable[..., T_Result], *args: Any, **kwargs: Any) -> T_Result:
        """Invoke `func` with retries applied to non-streaming results."""
        retries = 0
        while True:
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                if not isinstance(exc, self.errors):
                    raise
                if retries >= self.count >= 0:
                    raise
                time.sleep(self.interval)
                retries += 1
                self._log(retries, exc)

    def call_gen(
        self, func: Callable[..., Iterable[T_Generator]], *args: Any, **kwargs: Any
    ) -> Iterable[T_Generator]:
        """Invoke `func` expecting an iterator while handling retries."""
        retries = 0
        while True:
            try:
                for value in func(*args, **kwargs):
                    yield value
                return
            except Exception as exc:
                if not isinstance(exc, self.errors):
                    raise
                if retries >= self.count >= 0:
                    raise
                time.sleep(self.interval)
                retries += 1
                self._log(retries, exc)

    def _log(self, retries: int, exc: BaseException) -> None:
        """Emit a log message describing a retry attempt."""
        self.log(
            self.log_template.format(
                error=format_exc(exc),
                retries=retries,
                count=self.count,
                interval=self.interval,
            )
        )
