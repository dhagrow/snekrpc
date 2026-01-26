from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from . import errors, logs, protocol, registry, utils
from .codec import REGISTRY as CODEC_REGISTRY
from .codec import Codec
from .codec import create as create_codec
from .service import REGISTRY as SERVICE_REGISTRY
from .service import Service, ServiceProxy
from .service import create as create_service
from .transport import REGISTRY as TRANSPORT_REGISTRY
from .transport import Connection, Transport
from .transport import create as create_transport

DEFAULT_CODEC = 'msgpack'

log = logs.get(__name__)


class Interface:
    def __init__(
        self,
        transport: str | Transport | None = None,
        codec: str | Codec | None = None,
    ) -> None:
        registry.init()

        self.transport = (
            transport
            if isinstance(transport, Transport)
            else create_transport(transport or utils.DEFAULT_URL)
        )
        self.codec = codec

    @property
    def url(self) -> str:
        return str(self.transport.url)

    @property
    def transport_name(self) -> str | None:
        return None if self.transport is None else TRANSPORT_REGISTRY.get_name(type(self.transport))

    @property
    def codec_name(self) -> str:
        return '' if self._codec is None else CODEC_REGISTRY.get_name(type(self._codec))

    @property
    def codec(self) -> Codec | None:
        return self._codec

    @codec.setter
    def codec(self, codec: str | Codec | None) -> None:
        self._codec = codec if codec is None or isinstance(codec, Codec) else create_codec(codec)
        log.debug('codec: %s', self.codec_name)


class Client(Interface):
    def __init__(
        self,
        transport: str | Transport | None = None,
        codec: str | Any | None = None,
        retry_count: int | None = None,
        retry_interval: float | None = None,
    ) -> None:
        super().__init__(transport, codec)
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
        super().__init__(transport, codec or DEFAULT_CODEC)
        self._services: dict[str, Service] = {}
        self.add_service(create_service('meta', server=self), name='_meta')
        self.version = version
        self.remote_tracebacks = remote_tracebacks

        log.info('server version: %s', version or '-')

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

    def add_service(self, service: Service, name: str | None = None) -> Server:
        """Register a service with the server.

        You can register a service but keep it hidden from users by prefixing
        the name with an underscore.
        """
        name = name or SERVICE_REGISTRY.get_name(type(service))
        self._services[name] = service
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
