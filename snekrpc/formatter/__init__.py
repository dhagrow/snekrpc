"""Formatter plugin infrastructure."""

from __future__ import annotations

import importlib
import inspect
from typing import Any

from .. import registry

FormatterMeta = registry.create_metaclass(__name__)


def create(name: str | Formatter, **kwargs: Any) -> 'Formatter':
    """Return a formatter by name or pass through existing instances."""
    if isinstance(name, Formatter):
        return name
    cls = load(name) if '.' in name else FormatterMeta.get(name)
    return cls(**kwargs)


def load(name: str):
    """Dynamically import a formatter given `module.Class` notation."""
    mod_name, cls_name = name.rsplit('.', 1)
    mod = importlib.import_module(mod_name)
    return getattr(mod, cls_name)


class Formatter(metaclass=FormatterMeta):
    """Base class for converting RPC responses to user output."""

    NAME: str

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
