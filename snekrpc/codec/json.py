"""JSON codec supporting more complex RPC types."""

from __future__ import annotations

import json
from typing import Any

from . import Codec, decode, encode


class JsonCodec(Codec):
    """Codec that serializes RPC payloads using JSON."""

    _name_ = 'json'

    def __init__(self, encoding: str | None = None) -> None:
        """Store the encoding to apply when serializing bytes."""
        self._encoding = encoding or 'utf8'

    def encode(self, msg: Any) -> bytes:
        """Encode Python objects to JSON bytes."""
        return json.dumps(msg, default=encode).encode(self._encoding)

    def decode(self, data: bytes) -> Any:
        """Decode JSON back into the original object graph."""
        return json.loads(data, object_hook=decode)
