import random
import time
from typing import Any, Iterable

import snekrpc
from snekrpc import logs


class Service(snekrpc.Service):
    @snekrpc.command()
    def echo(self, value: Any) -> Any:
        return value

    @snekrpc.command()
    def download(self) -> Iterable[bytes]:
        total = 0
        start_t = time.perf_counter()

        while True:
            chunk = random.randbytes(512)

            total += len(chunk)
            elapsed_t = time.perf_counter() - start_t
            rate = total / elapsed_t
            print(f'\r{rate:,.2f}b/s {total:,}b', end='')

            yield chunk

    @snekrpc.command(data='stream')
    def upload(self, data: Iterable[bytes]) -> None:
        total = 0
        start_t = time.perf_counter()

        for chunk in data:
            total += len(chunk)
            elapsed_t = time.perf_counter() - start_t
            rate = total / elapsed_t
            print(f'\r{rate:,.2f}b/s {total:,}b', end='')


def main():
    logs.init()

    s = snekrpc.Server('tcp://localhost:1234')
    s.add_service(Service(), alias='ex')
    s.serve()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
