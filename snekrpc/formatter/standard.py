"""Standard formatter implementations."""

from __future__ import annotations

import datetime
import json
import pprint
from typing import Any

from . import Formatter


class RawFormatter(Formatter):
    """Write data exactly as returned by the server."""

    NAME = 'raw'

    def print(self, res: Any) -> None:
        """Print without adding trailing newlines."""
        print(self.format(res), end='')


class PprintFormatter(Formatter):
    """Pretty-print results using the stdlib pprint module."""

    NAME = 'pprint'

    def print(self, res: Any) -> None:
        """Pretty-print nested structures."""
        pprint.pprint(res)


class JsonFormatter(Formatter):
    """Serialize responses to JSON, encoding datetimes and bytes."""

    NAME = 'json'

    def format(self, res: Any) -> str:
        """Return a JSON string."""
        return json.dumps(res, default=self.encode)

    def encode(self, obj: Any) -> str:
        """Handle bytes and datetimes in a JSON-friendly way."""
        if isinstance(obj, bytes):
            try:
                return obj.decode()
            except UnicodeDecodeError:
                return '<binary data>'
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        raise TypeError(f'unsupported type: {type(obj)}')
