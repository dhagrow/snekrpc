"""Service proxy that forwards calls to another endpoint."""

from __future__ import annotations

from typing import Any

from .. import Client, logs
from ..transport import Transport
from . import Service, ServiceProxy

log = logs.get(__name__)


class RemoteService(Service, ServiceProxy, name='remote'):
    """Expose another RPC service through the current server."""

    def __init__(
        self,
        name: str,
        transport: str | Transport | None = None,
        codec: str | Any | None = None,
        retry_count: int | None = None,
        retry_interval: float | None = None,
    ) -> None:
        """Initialize a nested client and expose it under ``name``."""
        Service.__init__(self)
        ServiceProxy.__init__(self, name, Client(transport, codec, retry_count, retry_interval))
        log.info('forwarding (%s): %s', name, self._client.url)
