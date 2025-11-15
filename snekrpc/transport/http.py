from __future__ import annotations

import socketserver
from http import client, server
from typing import Any

from .. import __version__, errors, logs, param, utils
from . import Connection, Transport

SERVER_NAME = 'snekrpc'

log = logs.get(__name__)


class HTTPHandler(server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def do_POST(self) -> None:
        ifc = self.server._interface  # type: ignore[attr-defined]
        con = HTTPServerConnection(ifc, utils.url.format_addr(self.client_address), self)
        with con:
            while not con.should_close:
                ifc.handle(con)

    def start_response(self) -> None:
        self.send_response(200)
        self.send_header('Connection', 'keep-alive')
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Transfer-Encoding', 'chunked')

        for key, value in self.server._headers.items():  # type: ignore[attr-defined]
            self.send_header(key, value)
        self.end_headers()

    def version_string(self) -> str:
        interface = self.server._interface  # type: ignore[attr-defined]
        version = self.server._version  # type: ignore[attr-defined]
        return version or f'{SERVER_NAME}/{__version__} {interface.version or ""}'.strip()

    def log_request(self, code: str | int = '-', size: str | int = '-') -> None:
        url = utils.url.format_addr(self.client_address)
        log.debug('%r %s <- %s', self.requestline, code, url)


class HTTPTransport(Transport):
    _name_ = 'http'
    Handler = HTTPHandler

    @param('headers', dict)
    def __init__(
        self,
        url: str | utils.url.Url,
        headers: dict[str, str] | None = None,
        version: str | None = None,
    ):
        super().__init__(url)
        target = self._url
        host = target.host or '127.0.0.1'
        if target.port is None:
            raise ValueError('url must include a port')
        self._addr = (host, target.port)

        self.headers = headers or {}
        self.version = version
        self._server: ThreadingHTTPServer | None = None

    def connect(self, client: Any) -> 'HTTPClientConnection':
        return HTTPClientConnection(client, utils.url.format_addr(self._addr))

    def serve(self, server: Any) -> None:
        self._server = ThreadingHTTPServer(self._addr, self.Handler, self.headers, self.version, server)

        log.info('listening: %s', self.url)
        self._server.serve_forever()

    def stop(self) -> None:
        if not self._server:
            return
        self._server.server_close()
        self._server.shutdown()

    def join(self, timeout: float | None = None) -> None:
        # Blocking handled by HTTPServer internally.
        return


class ThreadingHTTPServer(socketserver.ThreadingMixIn, server.HTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        RequestHandlerClass: type[HTTPHandler],
        headers: dict[str, str],
        version: str | None,
        interface: Any,
    ) -> None:
        super().__init__(server_address, RequestHandlerClass)
        self._headers = headers
        self._version = version
        self._interface = interface

    def handle_error(self, request, client_address) -> None:
        log.exception('request error (%s)', utils.url.format_addr(client_address))


class HTTPClientConnection(Connection):
    def __init__(self, client_ifc: Any, url: str) -> None:
        super().__init__(client_ifc, url)
        self._res: client.HTTPResponse | None = None
        self._con = http = client.HTTPConnection(url)
        http.auto_open = False
        self.connect()

    def connect(self) -> None:
        con = self._con
        con.connect()
        log.debug('connected: %s', self.url)

        con.putrequest('POST', '')
        con.putheader('Connection', 'keep-alive')
        con.putheader('Content-Type', 'application/octet-stream')
        con.putheader('Transfer-Encoding', 'chunked')
        con.endheaders()

    def recv(self) -> bytes:
        try:
            if not self._res:
                self._res = self._con.getresponse()
            rfile = self._res.fp

            line = rfile.readline()
            if not line:
                raise errors.ReceiveInterrupted()
            chunk_len = int(line[:-2], 16)
            return rfile.read(chunk_len + 2)[:-2]
        except errors.ReceiveInterrupted:
            return b''
        except OSError as exc:  # pragma: no cover - network errors
            raise errors.TransportError(exc) from exc

    def send(self, data: bytes) -> None:
        try:
            con = self._con
            con.send(f'{len(data):X}\r\n'.encode('ascii'))
            con.send(data + b'\r\n')
        except OSError as exc:  # pragma: no cover - network errors
            raise errors.TransportError(exc) from exc

    def close(self) -> None:
        log.debug('disconnected: %s', self.url)


class HTTPServerConnection(Connection):
    def __init__(self, server_ifc: Any, url: str, handler: HTTPHandler) -> None:
        super().__init__(server_ifc, url)

        self.handler = handler
        self.response_started = False
        self.should_close = False

        log.debug('connected: %s', self.url)

    def recv(self) -> bytes:
        rfile = self.handler.rfile

        line = rfile.readline()
        if not line:
            self.should_close = True
            return b''
        chunk_len = int(line[:-2], 16)
        return rfile.read(chunk_len + 2)[:-2]

    def send(self, data: bytes) -> None:
        if not self.response_started:
            self.handler.start_response()
            self.response_started = True

        wfile = self.handler.wfile
        wfile.write(f'{len(data):X}\r\n'.encode('ascii'))
        wfile.write(data + b'\r\n')

    def close(self) -> None:
        self.handler.wfile.flush()
        log.debug('disconnected: %s', self.url)
