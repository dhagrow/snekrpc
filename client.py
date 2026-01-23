# ruff: noqa

from datetime import datetime, timezone
from typing import Any, Iterable


import msgspec
import snekrpc


class Event(msgspec.Struct):
    name: str
    message: str
    timestamp: datetime = msgspec.field(
        default_factory=lambda: datetime.now().astimezone(timezone.utc)
    )

class Service:
    def __init__(self, proxy: snekrpc.service.ServiceProxy):
        self._proxy = proxy

    def chunk(self) -> 'bytes':
        return self._proxy.chunk()

    def download(self) -> 'Iterable[bytes]':
        return self._proxy.download()

    def echo(self, value: 'Any') -> 'Any':
        return self._proxy.echo(value)

    def event(self) -> 'Event':
        return self._proxy.event()

    def events(self) -> 'Iterable[Event]':
        return self._proxy.events()

    def upload(self, data: 'Iterable[bytes]') -> 'None':
        self._proxy.upload(data)


class Client(snekrpc.Client):
    @property
    def example(self) -> Service:
        proxy = self.service('example')
        return Service(proxy)

