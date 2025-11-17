from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from . import errors, logs, protocol, registry, utils
from .codec import Codec
from .codec import get as get_codec
from .service import ServiceProxy
from .service import get as get_service
from .transport import Connection, Transport
from .transport import get as get_transport

if TYPE_CHECKING:
    from .service import Service

DEFAULT_CODEC = 'msgpack'

log = logs.get(__name__)


class Interface:
    def __init__(
        self,
        transport: str | Transport | None = None,
        codec: str | Any | None = None,
        version: str | None = None,
    ) -> None:
        registry.init()

        self.transport = get_transport(transport or utils.DEFAULT_URL)
        self.codec = codec
        self.version = version

    @property
    def url(self) -> utils.url.Url:
        return self.transport.url

    @property
    def codec(self) -> Codec | None:
        return self._codec

    @codec.setter
    def codec(self, codec: str | Any | None) -> None:
        self._codec = codec if codec is None else get_codec(codec)
        log.debug('codec: %s', self._codec and self._codec._name_)


class Client(Interface):
    def __init__(
        self,
        transport: str | Transport | None = None,
        codec: str | Any | None = None,
        version: str | None = None,
        retry_count: int | None = None,
        retry_interval: float | None = None,
    ) -> None:
        super().__init__(transport, codec, version)
        self._con: Connection | None = None
        self.retry_count = retry_count
        self.retry_interval = retry_interval

    def connect(self) -> Connection:
        if not self._con:
            try:
                self._con = self.transport.connect(self)
            except Exception as exc:
                raise errors.TransportError(exc) from exc
        return self._con

    def close(self) -> None:
        if self._con:
            self._con.close()
        self._con = None

    def __getitem__(self, name: str) -> ServiceProxy:
        return self.service(name)

    def __getattr__(self, name: str) -> ServiceProxy:
        try:
            return self.service(name)
        except errors.RemoteError as exc:
            if exc.name != 'KeyError':
                raise
            raise AttributeError(name) from exc

    def service(
        self, name: str, metadata: bool | Sequence[utils.function.SignatureSpec] = True
    ) -> ServiceProxy:
        return ServiceProxy(name, self, metadata)

    def service_names(self) -> list[str]:
        meta = self.service('_meta')
        return meta.service_names()


class Server(Interface):
    def __init__(
        self,
        transport: str | Transport | None = None,
        codec: str | Any | None = None,
        version: str | None = None,
        remote_tracebacks: bool = False,
    ) -> None:
        super().__init__(transport, codec or DEFAULT_CODEC, version)
        self._services: dict[str, Service] = {}
        self.add_service('meta', {'server': self}, '_meta')
        self.remote_tracebacks = remote_tracebacks

    def serve(self) -> None:
        try:
            self.transport.serve(self)
        except Exception as exc:
            raise errors.TransportError(exc) from exc

    def handle(self, con: Connection) -> None:
        protocol.Protocol(self, con).handle()

    def stop(self) -> None:
        self.transport.stop()

    def join(self, timeout: float | None = None) -> None:
        self.transport.join(timeout)

    def add_service(
        self,
        service: str | Service,
        service_args: Mapping[str, Any] | None = None,
        alias: str | None = None,
    ) -> 'Server':
        if service == 'meta':
            service_args = {'server': self}

        svc = get_service(service, service_args, alias)
        if not svc._name_:
            raise ValueError('service must define a name')
        self._services[svc._name_] = svc
        log.debug('service added: %s', svc._name_)
        return self

    def remove_service(self, name: str) -> 'Server':
        del self._services[name]
        return self

    def service(self, name: str) -> Service:
        return self._services[name]

    def services(self) -> list[Service]:
        return [self.service(name) for name in self.service_names()]

    def service_names(self) -> list[str]:
        return [name for name in self._services if name and not name.startswith('_')]
