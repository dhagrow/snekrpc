from __future__ import annotations

import datetime
import inspect
from collections.abc import Generator, Mapping, MutableMapping
from typing import Any

import temporenc

from .. import errors, registry, utils

CodecMeta = registry.create_metaclass(__name__)


def get(name: str | Codec, codec_args: Mapping[str, Any] | None = None) -> Codec:
    """Return an instance of the Codec matching *name*."""
    if isinstance(name, Codec):
        return name
    cls = CodecMeta.get(name)
    return cls(**(codec_args or {}))


class Codec(metaclass=CodecMeta):
    _name_: str | None = None

    def encode(self, msg: Any) -> bytes:
        raise NotImplementedError('abstract')

    def decode(self, data: bytes) -> Any:
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


def encode(obj: Any) -> Any:
    if isinstance(obj, datetime.datetime):
        return encode_datetime(obj)
    if inspect.isgenerator(obj):
        return encode_generator(obj)
    return obj


def decode(obj: MutableMapping[str, Any]) -> Any:
    if '__datetime__' in obj:
        return decode_datetime(obj)
    if '__generator__' in obj:
        return decode_generator(obj)
    return obj


def encode_datetime(obj: datetime.datetime) -> dict[str, bytes]:
    data = temporenc.packb(obj)
    if data is None:
        raise ValueError('temporenc.packb returned None')
    if isinstance(data, bytes):
        return {'__datetime__': data}
    if isinstance(data, bytearray):
        return {'__datetime__': bytes(data)}
    raise TypeError(f'unsupported temporenc result: {type(data).__name__}')


def decode_datetime(obj: Mapping[str, bytes]) -> datetime.datetime:
    return temporenc.unpackb(obj['__datetime__']).datetime()


def encode_generator(obj: Generator[Any, Any, Any]) -> dict[str, None]:
    return {'__generator__': None}


def decode_generator(_: Mapping[str, Any]) -> Generator[Any, None, None]:
    yield from ()
