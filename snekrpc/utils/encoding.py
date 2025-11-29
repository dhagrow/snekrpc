"""Helpers for recursively converting between str and bytes."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def to_bytes(value: Any, encoding: str = 'utf8') -> Any:
    """Encode strings (and nested structures) to bytes."""
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode(encoding)
    if isinstance(value, Mapping):
        return {to_bytes(k, encoding): to_bytes(v, encoding) for k, v in value.items()}
    if isinstance(value, Iterable):
        return [to_bytes(item, encoding) for item in value]
    return value


def to_str(value: Any, encoding: str = 'utf8', dict_keys_only: bool = False) -> Any:
    """Decode bytes within complex data structures to Python strings."""
    if isinstance(value, bytes):
        return value.decode(encoding)
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return {
            to_str(k, encoding): (v if dict_keys_only else to_str(v, encoding))
            for k, v in value.items()
        }
    if isinstance(value, Iterable):
        return tuple(to_str(item, encoding) for item in value)
    return value
