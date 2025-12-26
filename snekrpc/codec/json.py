"""JSON codec supporting more complex RPC types."""

from __future__ import annotations

from typing import Any

from msgspec import json

from . import Codec


class JsonCodec(Codec):
    """Codec that serializes RPC payloads using JSON."""

    NAME = 'json'

    def encode(self, msg: Any) -> bytes:
        """Encode Python objects to JSON bytes."""
        return json.encode(msg)

    def decode(self, data: bytes) -> Any:
        """Decode JSON back into the original object graph."""
        return json.decode(data)
