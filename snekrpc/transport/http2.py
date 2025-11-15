from __future__ import absolute_import

import collections
import errno
import io
import socket
import ssl
import threading

from h2 import events as ev
from h2.config import H2Configuration
from h2.connection import H2Connection

from .. import __version__, logs, param, utils
from . import Connection, Transport

BACKLOG = socket.SOMAXCONN
CHUNK_SIZE = io.DEFAULT_BUFFER_SIZE
ACCEPT_TIMEOUT = 0.1
SERVER_NAME = 'snekrpc'

log = logs.get(__name__)

Request = collections.namedtuple('Request', 'headers data')


class HTTP2Connection(Connection):
    def __init__(self, interface, sock, url, chunk_size=None, client_side=True):
        super(HTTP2Connection, self).__init__(interface, url)
        self._sock = sock
        self._chunk_size = chunk_size

        cfg = H2Configuration(client_side=client_side)
        self._con = con = H2Connection(config=cfg)
        con.initiate_connection()
        sock.sendall(con.data_to_send())

        # the server needs to keep track of the request's stream_id
        self._stream_id = None
        self._events = []

        log.debug('connected: %s', self.url)

    def recv(self):
        """Reads from the socket and processes all HTTP/2 events.

        Returns only on EOF or DataRecieved events.
        """
        con = self._con
        sock = self._sock
        events = self._events

        while True:
            if not events:
                # recieve new events
                data = sock.recv(CHUNK_SIZE)
                if not data:
                    return
                events.extend(con.receive_data(data))

            # process current events
            while True:
                try:
                    event = events.pop(0)
                except IndexError:
                    break

                if isinstance(event, ev.DataReceived):
                    return event.data
                elif isinstance(event, ev.RequestReceived):
                    log.debug('%s', event)
                    self._stream_id = event.stream_id
                elif isinstance(event, ev.ResponseReceived):
                    log.debug('%s', event)
                elif isinstance(event, ev.StreamEnded):
                    log.debug('%s', event)
                    self._stream_id = None
                elif isinstance(event, ev.RemoteSettingsChanged):
                    pass
                elif isinstance(event, ev.SettingsAcknowledged):
                    pass
                else:
                    log.warning('unhandled event: %s', event)

    def close(self):
        sock = self._sock
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except (OSError, socket.error) as e:
            # ignore if not connected
            if e.errno not in (errno.ENOTCONN,):  # errno.EBADF):
                raise
        sock.close()
        log.debug('disconnected: %s', self.url)


class HTTP2ServerConnection(HTTP2Connection):
    def __init__(self, interface, sock, url, chunk_size=None):
        super(HTTP2ServerConnection, self).__init__(
            interface, sock, url, chunk_size, client_side=False
        )

        self._initiated = False

    def initiate(self):
        stream_id = self._stream_id
        if self._initiated == stream_id:
            return

        headers = [
            (':status', '200'),
            ('server', self.version()),
        ]

        con = self._con
        con.send_headers(stream_id, headers)
        self._sock.sendall(con.data_to_send())

        self._initiated = stream_id

    def send(self, data):
        self.initiate()

        stream_id = self._stream_id
        con = self._con
        con.send_data(stream_id, data)

        self._sock.sendall(con.data_to_send())

    def version(self):
        return '{}/{} {}'.format(SERVER_NAME, __version__, self._ifc.version)

    def close(self):
        con = self._con
        con.end_stream(self._stream_id)
        self._sock.sendall(con.data_to_send())
        super(HTTP2ServerConnection, self).close()


class HTTP2ClientConnection(HTTP2Connection):
    def __init__(self, interface, sock, url, chunk_size=None):
        super(HTTP2ClientConnection, self).__init__(interface, sock, url, chunk_size)

    def send(self, data):
        headers = [
            (':method', 'POST'),
            (':authority', 'localhost'),
            (':scheme', 'http'),
            (':path', '/'),
        ]

        con = self._con
        stream_id = con.get_next_available_stream_id()
        con.send_headers(stream_id, headers)
        con.send_data(stream_id, data)

        self._sock.sendall(con.data_to_send())


class HTTP2Transport(Transport):
    _name_ = 'http2'

    @param('backlog', int, default=BACKLOG)
    @param('chunk_size', int, default=CHUNK_SIZE)
    @param('ssl_key', doc='server-side only')
    def __init__(
        self, url, timeout=None, backlog=None, chunk_size=None, ssl_cert=None, ssl_key=None
    ):
        super(HTTP2Transport, self).__init__(url)
        url = self._url

        self._addr = (url.host, url.port)
        self._sock = None

        self.timeout = timeout
        self.backlog = backlog or BACKLOG
        self.chunk_size = chunk_size

        self._ssl_cert = ssl_cert
        self._ssl_key = ssl_key

        self._stop = threading.Event()
        self._stopped = threading.Event()

    def connect(self, client):
        s = socket.create_connection(self._addr, self.timeout)

        if self._ssl_cert:
            ctx = ssl.create_default_context()
            ctx.load_verify_locations(self._ssl_cert)
            hostname = socket.gethostbyaddr(self._addr[0])[0]
            s = ctx.wrap_socket(s, server_hostname=hostname)

        return HTTP2ClientConnection(client, s, self._url.netloc, self.chunk_size)

    def bind(self):
        self._sock = s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(ACCEPT_TIMEOUT)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(self._addr)
        s.listen(self.backlog)

    def serve(self, server):
        self.bind()
        log.info('listening: %s', self.url)

        s = self._sock

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
                    sock, addr = s.accept()
                except socket.timeout:
                    continue
                sock.settimeout(self.timeout)

                try:
                    if ctx:
                        sock = ctx.wrap_socket(sock, server_side=True)
                except ssl.SSLError:
                    log.exception('ssl error')
                    continue

                utils.start_thread(self.handle, server, sock, addr)
        finally:
            stopped.set()

    def handle(self, server, sock, addr):
        addr = utils.url.format_addr(addr)
        con = HTTP2ServerConnection(server, sock, addr, self.chunk_size)
        with con:
            server.handle(con)

    def stop(self):
        self._stop.set()

    def join(self, timeout=None):
        self._stopped.wait(timeout)
