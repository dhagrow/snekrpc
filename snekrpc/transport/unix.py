"""Unix domain socket transport built atop the TCP transport."""

from __future__ import annotations

import socket
from typing import Any

from .. import logs, param, utils
from . import tcp

ACCEPT_TIMEOUT = 0.1

log = logs.get(__name__)


class UnixConnection(tcp.TcpConnection):
    """Connection wrapper customized for Unix sockets."""

    log = log


class UnixTransport(tcp.TcpTransport, name='unix'):
    """Transport that communicates over Unix domain sockets."""

    log = log
    Connection: type[tcp.TcpConnection] = UnixConnection

    @param('backlog')
    @param('chunk_size')
    def __init__(
        self,
        url: str | utils.url.Url,
        timeout: float | None = None,
        backlog: int = tcp.BACKLOG,
        chunk_size: int = tcp.CHUNK_SIZE,
    ) -> None:
        """Interpret the filesystem path from the URL."""
        super().__init__(url, timeout, backlog, chunk_size)
        path = self._url.path
        if path is None:
            raise ValueError('unix url must include a path')
        self._path: str = path

    def connect(self, client: Any) -> tcp.TcpConnection:
        """Connect to the server's Unix socket."""
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect(self._path)
        return self.Connection(client, sock, self._path, self.chunk_size)

    def bind(self) -> None:
        """Bind and listen on the configured Unix socket path."""
        utils.path.discard_file(self._path)

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(ACCEPT_TIMEOUT)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(self._path)
        sock.listen(self.backlog)
        self._sock = sock

    def serve(self, server: Any) -> None:
        """Serve requests and clean up socket files afterward."""
        try:
            super().serve(server)
        finally:
            utils.path.discard_file(self._path)

    def handle(self, server: Any, sock: socket.socket, addr: tuple[str, int] | str) -> None:
        """Handle an accepted Unix socket connection."""
        with self.Connection(server, sock, self._path, self.chunk_size) as con:
            server.handle(con)
