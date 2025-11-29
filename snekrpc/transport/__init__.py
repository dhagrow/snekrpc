"""Base transport abstractions."""

from __future__ import annotations

import struct
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .. import errors, logs, registry, utils
from ..protocol import Op

if TYPE_CHECKING:
    from ..interface import Interface

TransportMeta = registry.create_metaclass(__name__)

log = logs.get(__name__)


def get(url: str | utils.url.Url | 'Transport', transport_args: Mapping[str, Any] | None = None):
    """Return a `Transport` instance for *url*."""
    if isinstance(url, Transport):
        return url

    scheme = utils.url.Url(url).scheme
    cls = TransportMeta.get(scheme)
    return cls(url, **(transport_args or {}))


class Transport(metaclass=TransportMeta):
    """Base transport class mirrored across clients and servers."""

    _name_: str | None = None

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


@dataclass(slots=True)
class Message:
    """Convenience object representing protocol messages."""

    op: int
    data: Any = None

    def __repr__(self) -> str:
        """Return a readable representation for logging."""
        class_name = self.__class__.__name__
        data_str = f', data={utils.format.elide(repr(self.data))}' if self.data is not None else ''
        return f'{class_name}(op=<{self.op}:{Op.to_str(self.op)}>{data_str})'


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

    def req_handshake(self) -> None:
        """Negotiate codec information as an RPC client."""
        if self._ifc.codec:
            return

        if log.isEnabledFor(logs.DEBUG):
            log.debug('msg: %s -> %s', Message(Op.handshake, None), self._addr)

        buf = struct.pack('>B', Op.handshake)
        self.send(buf)

        buf = self.recv()
        if not buf:
            raise errors.TransportError(errors.ReceiveInterrupted())
        op, codec = struct.unpack(f'>B{len(buf) - 1}s', buf)
        if op != Op.handshake:
            raise errors.ProtocolOpError(op)

        if log.isEnabledFor(logs.DEBUG):
            log.debug('msg: %s <- %s', Message(op, codec), self._addr)

        self._ifc.codec = codec.decode('utf8')

    def res_handshake(self, data: bytes) -> bytes:
        """Respond to handshake requests as an RPC server."""
        if data != b'\x00':
            return data

        if log.isEnabledFor(logs.DEBUG):
            log.debug('msg: %s <- %s', Message(Op.handshake, None), self._addr)

        codec_name = None if self._ifc.codec is None else self._ifc.codec._name_.encode('utf8')

        if log.isEnabledFor(logs.DEBUG):
            log.debug('msg: %s -> %s', Message(Op.handshake, codec_name), self._addr)

        buf = struct.pack(
            f'>B{0 if codec_name is None else len(codec_name)}s', Op.handshake, codec_name
        )
        self.send(buf)
        return self.recv()

    def recv_msg(self) -> Message | None:
        """Receive and decode a complete message."""
        data = self.recv()
        data = self.res_handshake(data)

        if not data:
            return None
        if (codec := self._ifc.codec) is None:
            raise errors.TransportError('codec was not set by handshake')

        msg = Message(*codec._decode(data))

        if log.isEnabledFor(logs.DEBUG):
            log.debug('msg: %s <- %s', msg, self._addr)

        return msg

    def send_msg(self, op: int, data: Any = None) -> None:
        """Encode and send a message (performing the handshake as needed)."""
        self.req_handshake()

        if log.isEnabledFor(logs.DEBUG):
            log.debug('msg: %s -> %s', Message(op, data), self._addr)

        if (codec := self._ifc.codec) is None:
            raise errors.TransportError('codec is not set')

        msg = codec._encode((op, data))
        self.send(msg)

    def close(self) -> None:
        """Close the underlying socket/resource."""
        pass

    def __enter__(self) -> 'Connection':
        """Allow context-manager usage."""
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """Close the connection when leaving a `with` block."""
        self.close()
