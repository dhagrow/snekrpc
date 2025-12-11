"""URL parsing helpers tailored for the built-in transports."""

from __future__ import annotations

import posixpath
from dataclasses import dataclass
from urllib.parse import urlparse

DEFAULT_SCHEME = 'tcp'
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 12321


def format_addr(addr: tuple[str, int]) -> str:
    """Return `host:port` string."""
    return f'{addr[0]}:{addr[1]}'


@dataclass(slots=True)
class Url:
    """Parse and normalize transport URLs (tcp/unix)."""

    _scheme: str
    _host: str | None
    _port: int | None
    _path: str | None
    _address: tuple[str, int] | str
    _netloc: str

    def __init__(self, url: str | Url) -> None:
        """Normalize `url` and copy fields when already parsed."""
        if isinstance(url, Url):
            self._scheme = url._scheme
            self._host = url._host
            self._port = url._port
            self._path = url._path
            self._address = url._address
            self._netloc = url._netloc
            return

        parsed = urlparse(url if ':/' in url else f'{DEFAULT_SCHEME}://{url}')
        self._scheme = parsed.scheme

        if self._scheme == 'unix':
            path = posixpath.join(
                parsed.hostname or posixpath.sep, parsed.path.lstrip(posixpath.sep)
            ).rstrip(posixpath.sep)
            self._host = None
            self._port = None
            self._path = path
            self._address = path
            self._netloc = path
        else:
            if parsed.path.strip(posixpath.sep):
                raise ValueError(f'invalid URL: {url}')
            host = (parsed.hostname or DEFAULT_HOST).replace('*', '0.0.0.0')
            port = parsed.port or DEFAULT_PORT
            self._host = host
            self._port = port
            self._path = None
            self._address = (host, port)
            self._netloc = format_addr(self._address)

    @property
    def scheme(self) -> str:
        """Return the scheme (tcp/unix)."""
        return self._scheme

    @property
    def host(self) -> str | None:
        """Return the parsed hostname."""
        return self._host

    @property
    def port(self) -> int | None:
        """Return the parsed port."""
        return self._port

    @property
    def path(self) -> str | None:
        """Return the parsed path (for unix sockets)."""
        return self._path

    @property
    def address(self) -> tuple[str, int] | str:
        """Return a tuple address for tcp or str path for unix."""
        return self._address

    @property
    def netloc(self) -> str:
        """Return `host:port` or unix path string."""
        return self._netloc

    def __eq__(self, other: object) -> bool:
        """Compare equality against strings or other Url objects."""
        if isinstance(other, Url):
            return str(self) == str(other)
        if isinstance(other, str):
            return str(self) == other
        return NotImplemented

    def __str__(self) -> str:
        """Return the canonical `scheme://netloc` string."""
        return f'{self.scheme}://{self.netloc}'

    def __repr__(self) -> str:
        """Return a helpful representation for debugging."""
        return f'{self.__class__.__name__}({str(self)!r})'
