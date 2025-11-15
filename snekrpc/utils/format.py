from __future__ import annotations

import traceback
from collections.abc import Iterable, Mapping
from typing import Any


def format_cmd(svc_name: str, cmd_name: str, args: Iterable[Any], kwargs: Mapping[str, Any]) -> str:
    arg_parts: list[str] = []
    if args:
        arg_parts.append(', '.join(f'{value!r}' for value in args))
    if kwargs:
        arg_parts.append(', '.join(f'{key}={value!r}' for key, value in kwargs.items()))
    return f'{svc_name}.{cmd_name}({elide(", ".join(arg_parts))})'


def format_exc(exc: BaseException) -> str:
    return traceback.format_exception_only(exc.__class__, exc)[0].strip()


def elide(value: str, width: int = 100) -> str:
    return value if len(value) <= width else f'{value[: width - 3]}...'
