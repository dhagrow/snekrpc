from __future__ import annotations

import importlib
import inspect
from typing import Any

from .. import registry

FormatterMeta = registry.create_metaclass(__name__)


def get(name: str | 'Formatter', **kwargs: Any) -> 'Formatter':
    if isinstance(name, Formatter):
        return name
    cls = load(name) if '.' in name else FormatterMeta.get(name)
    return cls(**kwargs)


def load(name: str):
    mod_name, cls_name = name.rsplit('.', 1)
    mod = importlib.import_module(mod_name)
    return getattr(mod, cls_name)


class Formatter(metaclass=FormatterMeta):
    _name_: str | None = None

    def process(self, res: Any) -> None:
        if inspect.isgenerator(res):
            for value in res:
                self.print(value)
        else:
            self.print(res)

    def print(self, res: Any) -> None:
        print(self.format(res))

    def format(self, res: Any) -> Any:
        return res
