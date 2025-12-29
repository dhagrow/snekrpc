"""Msgpack codec with helpers for custom RPC types."""

from __future__ import annotations

from typing import Any

from msgspec import msgpack

from . import Codec


class MsgpackCodec(Codec, name='msgpack'):
    """Codec backed by msgpack for compact binary payloads."""

    def encode(self, msg: Any) -> bytes:
        """Serialize values to msgpack bytes."""
        return msgpack.encode(msg)

    def decode(self, data: bytes) -> Any:
        """Decode msgpack bytes into Python objects."""
        return msgpack.decode(data)
