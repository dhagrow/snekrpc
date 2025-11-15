from __future__ import annotations

import json
from typing import Any

from . import Codec, decode, encode


class JsonCodec(Codec):
    _name_ = 'json'

    def __init__(self, encoding: str | None = None) -> None:
        self._encoding = encoding or 'utf8'

    def encode(self, msg: Any) -> bytes:
        return json.dumps(msg, default=encode).encode(self._encoding)

    def decode(self, data: bytes) -> Any:
        return json.loads(data, object_hook=decode)
