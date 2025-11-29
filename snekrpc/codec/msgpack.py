"""Msgpack codec with helpers for custom RPC types."""

from __future__ import annotations

from typing import Any

import msgpack

from . import Codec, decode, encode


class MsgpackCodec(Codec):
    """Codec backed by msgpack for compact binary payloads."""

    _name_ = 'msgpack'

    def encode(self, msg: Any) -> bytes:
        """Serialize values to msgpack bytes."""
        data = msgpack.packb(msg, use_bin_type=True, default=encode)
        if isinstance(data, bytes):
            return data
        if isinstance(data, bytearray):
            return bytes(data)
        raise TypeError(f'unsupported msgpack result: {type(data).__name__}')

    def decode(self, data: bytes) -> Any:
        """Decode msgpack bytes into Python objects."""
        return msgpack.unpackb(data, use_list=True, raw=False, object_hook=decode)
