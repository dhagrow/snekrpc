"""Standard formatter implementations."""

from __future__ import annotations

import datetime
import json
import pprint
from typing import Any

from . import Formatter


class RawFormatter(Formatter, name='raw'):
    """Write data exactly as returned by the server."""

    def print(self, res: Any) -> None:
        """Print without adding trailing newlines."""
        print(self.format(res), end='')


class PprintFormatter(Formatter, name='pprint'):
    """Pretty-print results using the stdlib pprint module."""

    def print(self, res: Any) -> None:
        """Pretty-print nested structures."""
        pprint.pprint(res)


class JsonFormatter(Formatter, name='json'):
    """Serialize responses to JSON, encoding datetimes and bytes."""

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
