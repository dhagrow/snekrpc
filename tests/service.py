import itertools
from collections.abc import Iterable
from typing import Any

import snekrpc


class TestService(snekrpc.Service):
    _name_ = 'test'

    @snekrpc.command()
    def null(self):
        return None

    @snekrpc.command()
    def echo(self, s):
        return s

    @snekrpc.command()
    def params(self, a, b=None, c=True, d=False, *e, **f):
        return a, b, c, d, e, f

    @snekrpc.command()
    def upstream(self, stream: Iterable[Any]) -> list[Any]:
        return list(stream)

    @snekrpc.command()
    def downstream(self, limit: int | None = None):
        it = iter(range(limit)) if limit else itertools.count(0)
        while True:
            try:
                yield next(it)
            except StopIteration:
                return

    @snekrpc.command()
    def dualstream(self, stream: Iterable[Any]) -> Iterable[Any]:
        for x in stream:
            yield x
