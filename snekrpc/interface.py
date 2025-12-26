from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, cast

from . import errors, logs, protocol, registry, utils
from .codec import Codec
from .codec import create as create_codec
from .service import ServiceProxy
from .service import create as create_service
from .transport import Connection, Transport
from .transport import create as create_transport

if TYPE_CHECKING:
    from .service import Service

DEFAULT_CODEC = 'msgpack'

log = logs.get(__name__)


class Interface:
    def __init__(
        self,
        transport: str | Transport | None = None,
        codec: str | Codec | None = None,
        version: str | None = None,
    ) -> None:
        registry.init()

        self.transport = create_transport(transport or utils.DEFAULT_URL)
        self.codec = codec
        self.version = version

    @property
    def url(self) -> str:
        return str(self.transport.url)

    @property
    def codec(self) -> Codec | None:
        return self._codec

    @codec.setter
    def codec(self, codec: str | Codec | None) -> None:
        self._codec = codec if codec is None else create_codec(codec)
        log.debug('codec: %s', self._codec and self._codec.NAME)


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
        # TODO replace this with a proper connection pool
        self._con: Connection | None = None
        self.retry_count = retry_count
        self.retry_interval = retry_interval

    def connect(self) -> Connection:
        if not self._con:
            try:
                self._con = self.transport.connect(self)
            except Exception as exc:
                raise errors.TransportError(exc) from exc
        assert self._con
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
        return cast(list[str], meta.service_names())


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
    ) -> Server:
        svc = create_service(service, **(service_args or {}))
        name = svc.NAME if alias is None else alias
        self._services[name] = svc
        log.debug('service added: %s', name)
        return self

    def remove_service(self, name: str) -> Server:
        del self._services[name]
        return self

    def service(self, name: str) -> Service:
        return self._services[name]

    def services(self) -> list[tuple[str, Service]]:
        return [(name, self.service(name)) for name in self.service_names()]

    def service_names(self) -> list[str]:
        return [name for name in self._services if name and not name.startswith('_')]
