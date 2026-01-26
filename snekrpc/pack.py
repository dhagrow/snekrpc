import argparse
import inspect
from dataclasses import is_dataclass
from datetime import datetime
from typing import Iterable, cast

import msgspec

import snekrpc
from snekrpc.service import Service, ServiceSpec
from snekrpc.utils.path import import_module

try:
    import jinja2
except ImportError as e:
    jinja2 = e  # type: ignore


log = snekrpc.logs.get(__name__)


def generate_client(
    services: Iterable[type[snekrpc.Service]],
    data_classes: Iterable[type] | None = None,
    imports: Iterable[str] | None = None,
) -> str:
    if isinstance(jinja2, Exception):
        raise jinja2

    env = jinja2.Environment(loader=jinja2.PackageLoader('snekrpc'))
    template = env.get_template('client.py.j2')
    return template.render(
        timestamp=datetime.now().astimezone(),
        default_url=':1234',
        specs={service.__name__: ServiceSpec.from_service(service) for service in services},
        classes=[inspect.getsource(struct) for struct in data_classes] if data_classes else [],
        imports=imports or [],
    )


def main() -> None:
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

    data_classes: list[type] = []
    services = []

    for module_name in args.modules:
        mod = import_module(module_name)
        for attr in vars(mod).values():
            if is_dataclass(attr) or (inspect.isclass(attr) and issubclass(attr, msgspec.Struct)):
                data_classes.append(cast(type, attr))
            elif inspect.isclass(attr) and issubclass(attr, Service):
                services.append(attr)

    try:
        source = generate_client(services, data_classes, args.imports)
    except ImportError as e:
        parser.error(
            f'jinja2 is required. enable client generation with `pip install snekrpc[pack]`: {e}'
        )
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
