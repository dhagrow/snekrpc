"""Base transport abstractions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from .. import logs, registry, utils

if TYPE_CHECKING:
    from ..interface import Interface

TransportMeta = registry.create_registry(__name__)

log = logs.get(__name__)


def create(url: str | utils.url.Url | 'Transport', transport_args: Mapping[str, Any] | None = None):
    """Return a `Transport` instance for *url*."""
    if isinstance(url, Transport):
        return url

    scheme = utils.url.Url(url).scheme
    cls = TransportMeta.get(scheme)
    return cls(url, **(transport_args or {}))


class Transport(metaclass=TransportMeta):
    """Base transport class mirrored across clients and servers."""

    NAME: str

    def __init__(self, url: str | utils.url.Url):
        """Store the normalized URL for later use."""
        self._url = utils.url.Url(url)

    @property
    def url(self) -> utils.url.Url:
        """Return the configured transport URL."""
        return self._url

    def connect(self, client: Any) -> Connection:
        """Connect to a remote endpoint and return a Connection."""
        raise NotImplementedError

    def serve(self, server: Any) -> None:
        """Start serving RPC requests."""
        raise NotImplementedError

    def stop(self) -> None:
        """Stop serving and release resources."""
        raise NotImplementedError

    def join(self, timeout: float | None = None) -> None:
        """Block until the server threads exit."""
        raise NotImplementedError


class Connection:
    """Wrap an underlying socket-like object and handle message encoding."""

    def __init__(self, interface: Interface, addr: str) -> None:
        """Bind the connection to an interface instance and address."""
        self._ifc = interface
        self._addr = addr

    @property
    def url(self) -> str:
        """Return a string representation of the connection endpoint."""
        return self._addr

    def send(self, data: bytes) -> None:
        """Send raw bytes."""
        raise NotImplementedError

    def recv(self) -> bytes:
        """Receive raw bytes."""
        raise NotImplementedError

    def close(self) -> None:
        """Close the underlying socket/resource."""
        pass

    def __enter__(self) -> 'Connection':
        """Allow context-manager usage."""
        return self

    def __exit__(self, exc_type: type[Exception], exc: Exception, tb: TracebackType) -> None:
        """Close the connection when leaving a `with` block."""
        self.close()
