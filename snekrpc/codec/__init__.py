"""Codec base classes and helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .. import errors, registry, utils

CodecMeta = registry.create_metaclass(__name__)


def create(name: str | Codec, codec_args: Mapping[str, Any] | None = None) -> Codec:
    """Return an instance of the Codec matching *name*."""
    if isinstance(name, Codec):
        return name
    cls = CodecMeta.get(name)
    return cls(**(codec_args or {}))


class Codec(metaclass=CodecMeta):
    """Base class for codecs that know how to encode/decode RPC payloads."""

    _name_: str

    def encode(self, msg: Any) -> bytes:
        """Serialize `msg` into bytes."""
        raise NotImplementedError('abstract')

    def decode(self, data: bytes) -> Any:
        """Deserialize bytes into Python objects."""
        raise NotImplementedError('abstract')

    def _encode(self, msg: Any) -> bytes:
        """Wrapper that provides encoding error context. Used internally."""
        try:
            return self.encode(msg)
        except Exception as exc:
            raise errors.EncodeError(f'{exc}: msg={utils.format.elide(repr(msg))}') from exc

    def _decode(self, data: bytes) -> Any:
        """Wrapper that provides decoding error context. Used internally."""
        try:
            return self.decode(data)
        except Exception as exc:
            raise errors.DecodeError(f'{exc}: data={utils.format.elide(repr(data))!r}') from exc
