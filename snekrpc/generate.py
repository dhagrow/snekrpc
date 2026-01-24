import inspect
from datetime import datetime
from typing import Iterable

import msgspec
from jinja2 import Environment, PackageLoader

import snekrpc
from snekrpc.service import ServiceSpec


def generate(
    services: Iterable[type[snekrpc.Service]],
    structs: Iterable[type[msgspec.Struct]] | None = None,
    imports: Iterable[str] | None = None,
) -> str:
    env = Environment(loader=PackageLoader('snekrpc'))
    template = env.get_template('client.py.j2')
    return template.render(
        timestamp=datetime.now().astimezone(),
        default_url=':1234',
        specs={service.__name__: ServiceSpec.from_service(service) for service in services},
        structs=[inspect.getsource(struct) for struct in structs] if structs else [],
        imports=imports or [],
    )


def main():
    from examples.server import Command, Event, Service

    client_source = generate(
        [Service],
        [Command, Event],
        imports=[
            'from datetime import datetime, timezone',
            'from typing import Any, Iterable',
        ],
    )
    print(client_source)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
