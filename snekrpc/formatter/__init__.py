"""Formatter plugin infrastructure."""

from __future__ import annotations

import inspect
from typing import Any

from .. import utils
from ..registry import Registry


def create(name: str | Formatter, **kwargs: Any) -> Formatter:
    """Return a formatter by name or pass through existing instances."""
    if isinstance(name, Formatter):
        return name
    try:
        cls = REGISTRY[name]
    except KeyError:
        cls = utils.path.import_class(Formatter, name)
    return cls(**kwargs)


class Formatter:
    """Base class for converting RPC responses to user output."""

    NAME: str

    def __init_subclass__(cls) -> None:
        REGISTRY[cls.NAME] = cls

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
