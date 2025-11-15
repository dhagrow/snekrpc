from __future__ import annotations

from typing import Any

from .. import Client, logs, param
from . import Service, ServiceProxy

log = logs.get(__name__)


class RemoteService(Service, ServiceProxy):
    _name_ = 'remote'

    @param('transport')
    @param('codec')
    @param('version')
    @param('retry_count', int)
    @param('retry_interval', float)
    @param('kwargs', hide=True)
    def __init__(self, name: str, **kwargs: Any) -> None:
        Service.__init__(self)
        ServiceProxy.__init__(self, name, Client(**kwargs))
        log.info('forwarding (%s): %s', name, self._client.url)
