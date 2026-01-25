import argparse
import inspect
from dataclasses import is_dataclass
from datetime import datetime
from typing import Iterable

import msgspec
from jinja2 import Environment, PackageLoader

import snekrpc
from snekrpc.service import Service, ServiceSpec
from snekrpc.utils.path import import_module


def generate_client(
    services: Iterable[type[snekrpc.Service]],
    data_classes: Iterable[type] | None = None,
    imports: Iterable[str] | None = None,
) -> str:
    env = Environment(loader=PackageLoader('snekrpc'))
    template = env.get_template('client.py.j2')
    return template.render(
        timestamp=datetime.now().astimezone(),
        default_url=':1234',
        specs={service.__name__: ServiceSpec.from_service(service) for service in services},
        classes=[inspect.getsource(struct) for struct in data_classes] if data_classes else [],
        imports=imports or [],
    )


def main():
    parser = argparse.ArgumentParser('snekrpc-pack')
    parser.add_argument(
        '-m',
        '--module',
        action='append',
        dest='modules',
        metavar='MODULE',
        default=[],
        required=True,
        help='a module containing services and data classes to pack',
    )
    parser.add_argument(
        '-i',
        '--import-string',
        action='append',
        dest='imports',
        metavar='IMPORT-STRING',
        default=[],
        help='an import string to prepend to the generated client source',
    )
    parser.add_argument(
        '-o',
        '--output-path',
        help='a file to output to. outputs to STDOUT by default',
    )

    args = parser.parse_args()

    data_classes = []
    services = []

    for module_name in args.modules:
        mod = import_module(module_name)
        for attr in vars(mod).values():
            if is_dataclass(attr) or (inspect.isclass(attr) and issubclass(attr, msgspec.Struct)):
                data_classes.append(attr)
            elif inspect.isclass(attr) and issubclass(attr, Service):
                services.append(attr)

    source = generate_client(services, data_classes, args.imports)
    if args.output_path:
        with open(args.output_path, 'w') as f:
            f.write(source)
    else:
        print(source)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
