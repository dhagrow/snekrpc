from __future__ import annotations

import datetime
import json
import pprint
from typing import Any

from . import Formatter


class RawFormatter(Formatter):
    _name_ = 'raw'

    def print(self, res: Any) -> None:
        print(self.format(res), end='')


class PprintFormatter(Formatter):
    _name_ = 'pprint'

    def print(self, res: Any) -> None:
        pprint.pprint(res)


class JsonFormatter(Formatter):
    _name_ = 'json'

    def format(self, res: Any) -> str:
        return json.dumps(res, default=self.encode)

    def encode(self, obj: Any) -> Any:
        if isinstance(obj, bytes):
            try:
                return obj.decode('utf8')
            except UnicodeDecodeError:
                return '<binary data>'
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        raise TypeError(f'unsupported type: {type(obj)}')
