import random
from typing import Any, Iterable

import snekrpc
from snekrpc import logs


class Service(snekrpc.Service):
    """Example service"""

    @snekrpc.command()
    @snekrpc.param('value', 'The value to echo back')
    def echo(self, value: Any) -> Any:
        """Echo back the input value."""
        return value

    @snekrpc.command()
    def download(self) -> Iterable[bytes]:
        """Start a download of an infinite amount of data.

        To test and measure throughput, try:
        $ snekrpc -u :1234 -f raw ex download | pv > /dev/null
        """
        while True:
            yield random.randbytes(512)

    @snekrpc.command()
    def upload(self, data: Iterable[bytes]) -> None:
        """Accept an upload of an infinite amount of data.

        To test and measure throughput, try:
        $ cat /dev/urandom | pv | snekrpc -u :1234 ex upload -
        """
        for _chunk in data:
            pass


def main():
    logs.init()

    s = snekrpc.Server('tcp://localhost:1234')
    s.add_service(Service(), alias='ex')
    s.add_service('meta')
    s.serve()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
