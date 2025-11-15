from __future__ import annotations

import socket
from typing import Any

from .. import logs, param, utils
from . import tcp

ACCEPT_TIMEOUT = 0.1

log = logs.get(__name__)


class UnixConnection(tcp.TcpConnection):
    log = log


class UnixTransport(tcp.TcpTransport):
    _name_ = 'unix'
    log = log
    Connection = UnixConnection

    @param('backlog', int, default=tcp.BACKLOG)
    @param('chunk_size', int, default=tcp.CHUNK_SIZE)
    def __init__(
        self,
        url: str | utils.url.Url,
        timeout: float | None = None,
        backlog: int | None = None,
        chunk_size: int | None = None,
    ) -> None:
        super().__init__(url, timeout, backlog, chunk_size)
        self._path = self._url.path

    def connect(self, client: Any) -> UnixConnection:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect(self._path)
        return self.Connection(client, sock, self._path, self.chunk_size)

    def bind(self) -> None:
        utils.path.discard_file(self._path)

        self._sock = sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(ACCEPT_TIMEOUT)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(self._path)
        sock.listen(self.backlog)

    def serve(self, server: Any) -> None:
        try:
            super().serve(server)
        finally:
            utils.path.discard_file(self._path)

    def handle(self, server: Any, sock: socket.socket, addr: tuple[str, int] | str) -> None:
        with self.Connection(server, sock, self._path, self.chunk_size) as con:
            server.handle(con)
