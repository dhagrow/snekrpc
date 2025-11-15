from __future__ import annotations

from typing import Any

import msgpack

from . import Codec, decode, encode


class MsgpackCodec(Codec):
    _name_ = 'msgpack'

    def encode(self, msg: Any) -> bytes:
        return msgpack.packb(msg, use_bin_type=True, default=encode)

    def decode(self, data: bytes) -> Any:
        return msgpack.unpackb(data, use_list=True, raw=False, object_hook=decode)
