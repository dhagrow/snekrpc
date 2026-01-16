"""Codec base classes and helpers."""

from __future__ import annotations

import abc
from typing import Any

from .. import errors, utils
from ..registry import Registry


class Codec(abc.ABC):
    """Base class for codecs that know how to encode/decode RPC payloads."""

    def __init_subclass__(cls, /, name: str | None = None) -> None:
        REGISTRY.set(cls.__name__ if name is None else name, cls)

    @abc.abstractmethod
    def encode(self, msg: Any) -> bytes:
        """Serialize `msg` into bytes."""
        raise NotImplementedError('abstract')

    @abc.abstractmethod
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


REGISTRY = Registry(__name__, Codec)
get, create = REGISTRY.get, REGISTRY.create
