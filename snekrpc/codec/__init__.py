from __future__ import annotations

import datetime
import inspect
from collections.abc import Generator, Mapping, MutableMapping
from typing import Any

import temporenc

from .. import errors, registry, utils

CodecMeta = registry.create_metaclass(__name__)

Encodable = Any
Encoded = Any


def get(name: str | Codec, codec_args: Mapping[str, Any] | None = None) -> Codec:
    """Return an instance of the Codec matching *name*."""
    if isinstance(name, Codec):
        return name
    cls = CodecMeta.get(name)
    return cls(**(codec_args or {}))


class Codec(metaclass=CodecMeta):
    _name_: str | None = None

    def encode(self, msg: Encodable) -> Encoded:  # pragma: no cover - overridden
        raise NotImplementedError('abstract')

    def decode(self, data: Encoded) -> Encodable:  # pragma: no cover - overridden
        raise NotImplementedError('abstract')

    def _encode(self, msg: Encodable) -> Encoded:
        """Wrapper that provides encoding error context. Used internally."""
        try:
            return self.encode(msg)
        except Exception as exc:
            raise errors.EncodeError(f'{exc}: msg={utils.format.elide(repr(msg))}') from exc

    def _decode(self, data: Encoded) -> Encodable:
        """Wrapper that provides decoding error context. Used internally."""
        try:
            return self.decode(data)
        except Exception as exc:
            raise errors.DecodeError(f'{exc}: data={utils.format.elide(repr(data))!r}') from exc


def encode(obj: Encodable) -> Encodable:
    if isinstance(obj, datetime.datetime):
        return encode_datetime(obj)
    if inspect.isgenerator(obj):
        return encode_generator(obj)
    return obj


def decode(obj: MutableMapping[str, Encodable]) -> Encodable:
    if '__datetime__' in obj:
        return decode_datetime(obj)
    if '__generator__' in obj:
        return decode_generator(obj)
    return obj


def encode_datetime(obj: datetime.datetime) -> dict[str, bytes]:
    return {'__datetime__': temporenc.packb(obj)}


def decode_datetime(obj: Mapping[str, bytes]) -> datetime.datetime:
    return temporenc.unpackb(obj['__datetime__']).datetime()


def encode_generator(obj: Generator[Any, Any, Any]) -> dict[str, None]:
    return {'__generator__': None}


def decode_generator(_: Mapping[str, Any]) -> Generator[Any, None, None]:
    yield from ()
