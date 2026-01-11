"""Simple health-check/ping service."""

from __future__ import annotations

import itertools
import time
from collections.abc import Iterator

from .. import Service, command


class HealthService(Service, name='health'):
    """Expose a heartbeat for monitoring."""

    @command()
    def ping(self, count: int = 1, interval: float = 1.0) -> Iterator[None]:
        """Respond at regular intervals."""
        iterator = range(count - 1) if count > 0 else itertools.count()
        for _ in iterator:
            yield
            time.sleep(interval)
