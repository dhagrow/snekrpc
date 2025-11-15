from __future__ import annotations

import pprint
from typing import Any

from . import Formatter


class PrettyFormatter(Formatter):
    _name_ = 'pretty'

    def print(self, res: Any) -> None:
        text = self.format(res)
        if text is not None:
            print(text)

    def format(self, res: Any) -> str | None:
        if res is None:
            return None
        if isinstance(res, str):
            return res
        if isinstance(res, (list, tuple)):
            return '\n'.join(str(value) for value in res)
        return pprint.pformat(res)
