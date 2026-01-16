"""Base transport abstractions."""

from __future__ import annotations

import abc
from types import TracebackType
from typing import TYPE_CHECKING, Any

from .. import logs, utils
from ..registry import Registry

if TYPE_CHECKING:
    from ..interface import Interface

log = logs.get(__name__)


class Transport(abc.ABC):
    """Base transport class mirrored across clients and servers."""

    def __init_subclass__(cls, /, name: str | None = None) -> None:
        REGISTRY.set(cls.__name__ if name is None else name, cls)

    def __init__(self, url: str | utils.url.Url):
        """Store the normalized URL for later use."""
        self._url = utils.url.Url(url)

    @property
    def url(self) -> utils.url.Url:
        """Return the configured transport URL."""
        return self._url

    @abc.abstractmethod
    def connect(self, client: Any) -> Connection:
        """Connect to a remote endpoint and return a Connection."""
        raise NotImplementedError

    @abc.abstractmethod
    def serve(self, server: Any) -> None:
        """Start serving RPC requests."""
        raise NotImplementedError

    @abc.abstractmethod
    def stop(self) -> None:
        """Stop serving and release resources."""
        raise NotImplementedError

    @abc.abstractmethod
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


REGISTRY = Registry(__name__, Transport)


def get(url: str | utils.url.Url) -> type[Transport]:
    return REGISTRY.get(utils.url.Url(url).scheme)


def create(url: str | utils.url.Url, *args: Any, **kwargs: Any) -> Transport:
    """Create a `Transport` instance for *url*."""
    return REGISTRY.create(utils.url.Url(url).scheme, url, *args, **kwargs)
