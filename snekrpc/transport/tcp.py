"""TCP transport implementation."""

from __future__ import annotations

import errno
import io
import socket
import ssl
import struct
import threading
from typing import Any

from .. import errors, logs, param, utils
from . import Connection, Transport

BACKLOG = socket.SOMAXCONN
CHUNK_SIZE = io.DEFAULT_BUFFER_SIZE
ACCEPT_TIMEOUT = 0.1

log = logs.get(__name__)


class TcpConnection(Connection):
    """Connection implementation backed by a TCP socket."""

    log = log

    def __init__(
        self, interface: Any, sock: socket.socket, url: str, chunk_size: int | None = None
    ) -> None:
        """Wrap a socket for RPC messaging."""
        super().__init__(interface, url)
        self._sock = sock
        self._chunk_size = chunk_size
        self.log.debug('connected: %s', self.url)

    def recv(self) -> bytes:
        """Receive bytes from the socket."""
        return recv(self._sock, self._chunk_size)

    def send(self, data: bytes) -> None:
        """Send bytes through the socket."""
        try:
            send(self._sock, data)
        except OSError as exc:
            raise errors.TransportError(exc) from exc

    def close(self) -> None:
        """Close the socket."""
        close(self._sock)
        self.log.debug('disconnected: %s', self.url)


class TcpTransport(Transport):
    """Expose the transport API over TCP."""

    _name_ = 'tcp'
    log = log
    Connection = TcpConnection

    @param('backlog')
    @param('chunk_size')
    @param('ssl_key', doc='server-side only')
    def __init__(
        self,
        url: str | utils.url.Url,
        timeout: float | None = None,
        backlog: int = BACKLOG,
        chunk_size: int = CHUNK_SIZE,
        ssl_cert: str | None = None,
        ssl_key: str | None = None,
    ) -> None:
        """Store connection parameters and TLS configuration."""
        super().__init__(url)
        target = self._url
        host = target.host or utils.url.DEFAULT_HOST
        port = target.port or utils.url.DEFAULT_PORT
        self._addr = (host, port)
        self._sock: socket.socket | None = None

        self.timeout = timeout
        self.backlog = backlog or BACKLOG
        self.chunk_size = chunk_size

        self._ssl_cert = ssl_cert
        self._ssl_key = ssl_key

        self._stop = threading.Event()
        self._stopped = threading.Event()

    def connect(self, client: Any) -> TcpConnection:
        """Create a connection to the configured host."""
        sock = socket.create_connection(self._addr, self.timeout)

        if self._ssl_cert:
            ctx = ssl.create_default_context()
            ctx.load_verify_locations(self._ssl_cert)
            hostname = socket.gethostbyaddr(self._addr[0])[0]
            sock = ctx.wrap_socket(sock, server_hostname=hostname)

        return self.Connection(client, sock, self._url.netloc, self.chunk_size)

    def bind(self) -> None:
        """Create and bind a listening socket."""
        self._sock = sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(ACCEPT_TIMEOUT)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(self._addr)
        sock.listen(self.backlog)

    def serve(self, server: Any) -> None:
        """Accept incoming connections and handle them in threads."""
        self.bind()
        self.log.info('listening: %s', self.url)

        assert self._sock
        sock = self._sock

        ctx = None
        if self._ssl_cert:
            ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ctx.load_cert_chain(certfile=self._ssl_cert, keyfile=self._ssl_key)

        stop = self._stop
        stopped = self._stopped
        stop.clear()
        stopped.clear()

        try:
            while not stop.is_set():
                try:
                    client_sock, addr = sock.accept()
                except socket.timeout:
                    continue
                client_sock.settimeout(self.timeout)

                try:
                    if ctx:
                        client_sock = ctx.wrap_socket(client_sock, server_side=True)
                except ssl.SSLError:
                    log.exception('ssl error')
                    continue

                utils.start_thread(self.handle, server, client_sock, addr)
        finally:
            stopped.set()

    def handle(self, server: Any, sock: socket.socket, addr: tuple[str, int]) -> None:
        """Wrap `sock` in a Connection and let the server handle requests."""
        addr_str = utils.url.format_addr(addr)
        with self.Connection(server, sock, addr_str, self.chunk_size) as con:
            server.handle(con)

    def stop(self) -> None:
        """Signal the accept loop to exit."""
        self._stop.set()

    def join(self, timeout: float | None = None) -> None:
        """Wait for the accept loop to finish."""
        self._stopped.wait(timeout)


def close(sock: socket.socket) -> None:
    """Shutdown and close a socket, ignoring common errors."""
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except (OSError, socket.error) as exc:
        if exc.errno not in (errno.ENOTCONN,):
            raise
    sock.close()


def recv(sock: socket.socket, chunk_size: int | None = None) -> bytes:
    """Receive a full message including size prefix."""
    try:
        return b''.join(recviter(sock, chunk_size))
    except errors.ReceiveInterrupted:
        return b''
    except OSError as exc:
        raise errors.TransportError(exc) from exc


def recviter(sock: socket.socket, chunk_size: int | None = None):
    """Yield chunks for a single message payload."""
    buf = b''.join(recvsize(sock, 4, chunk_size))
    data_len = struct.unpack('>I', buf)[0]
    for chunk in recvsize(sock, data_len, chunk_size):
        yield chunk


def recvsize(sock: socket.socket, size: int, chunk_size: int | None = None):
    """Yield until `size` bytes have been read."""
    pos = 0
    chunk_size = min(size, chunk_size or CHUNK_SIZE)
    while pos < size:
        chunk = sock.recv(min(size - pos, chunk_size))
        if not chunk:
            raise errors.ReceiveInterrupted()
        pos += len(chunk)
        yield chunk


def send(sock: socket.socket, data: bytes) -> None:
    """Send a length-prefixed payload."""
    data_len = len(data)
    size = struct.pack('>I', data_len)
    sock.sendall(size)
    sock.sendall(data)
