"""Formatter plugin infrastructure."""

from __future__ import annotations

import inspect
from typing import Any

from ..registry import Registry


class Formatter:
    """Base class for converting RPC responses to user output."""

    def __init_subclass__(cls, /, name: str | None = None) -> None:
        REGISTRY.set(cls.__name__ if name is None else name, cls)

    def process(self, res: Any) -> None:
        """Automatically iterate through generators and print results."""
        if inspect.isgenerator(res):
            for value in res:
                self.print(value)
        else:
            self.print(res)

    def print(self, res: Any) -> None:
        """Print a formatted representation of `res`."""
        print(self.format(res))

    def format(self, res: Any) -> Any:
        """Return the raw value by default; subclasses can override."""
        return res


REGISTRY = Registry(__name__, Formatter)
get, create = REGISTRY.get, REGISTRY.create
