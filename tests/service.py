import itertools

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

    @snekrpc.command(stream='stream')
    def upstream(self, stream):
        return list(stream)

    @snekrpc.command(limit='int')
    def downstream(self, limit=None):
        it = iter(range(limit)) if limit else itertools.count(0)
        while True:
            try:
                yield next(it)
            except StopIteration:
                return

    @snekrpc.command(stream='stream')
    def dualstream(self, stream):
        for x in stream:
            yield x
