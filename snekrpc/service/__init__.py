from __future__ import annotations

import inspect
import itertools
from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..interface import Client

from .. import errors, logs, registry, utils
from ..utils.encoding import to_unicode

log = logs.get(__name__)

ServiceMeta = registry.create_metaclass(__name__)


def parse_alias(name: str) -> tuple[str, str | None]:
    try:
        base, alias = name.split(':')
    except ValueError:
        return name, None
    return base, alias


def get_class(name: str):
    return ServiceMeta.get(name)


def get(
    name: str | Service, service_args: Mapping[str, Any] | None = None, alias: str | None = None
):
    if isinstance(name, Service):
        obj = name
    elif inspect.isclass(name) and issubclass(name, Service):
        obj = name(**(service_args or {}))
    else:
        cls = get_class(name)
        obj = cls(**(service_args or {}))

    if alias:
        obj._name_ = alias

    return obj


def service_to_dict(svc: Service) -> dict[str, Any]:
    f2d = utils.function.func_to_dict

    data: dict[str, Any] = {'name': svc._name_, 'doc': svc.__doc__}
    data['commands'] = commands = []

    for name in dir(svc):
        if name.startswith('_'):
            continue
        attr = getattr(svc, name)
        meta = getattr(attr, '_meta', None)
        if meta is not None:
            commands.append(f2d(attr))

    return data


class Service(metaclass=ServiceMeta):
    _name_: str | None = None

    def __init__(self) -> None:
        pass


class ServiceProxy:
    def __init__(
        self, name: str, client: 'Client', metadata: bool | Sequence[dict[str, Any]] = True
    ):
        self._svc_name = to_unicode(name)
        self._client = client
        self._commands: dict[str, Callable[..., Any]] = {}

        self._retry = utils.retry.Retry(
            client.retry_count, client.retry_interval, errors=[errors.TransportError], logger=log
        )

        def wrap_command(cmd_def: dict[str, Any]):
            return wrap_call(self, cmd_def['name'], cmd_def)

        if metadata is True:
            meta = ServiceProxy('_meta', client, metadata=False)
            svc = meta.service(self._svc_name)
            self._commands.update({c['name']: wrap_command(c) for c in svc['commands']})
        elif metadata:
            self._commands.update({c['name']: wrap_command(c) for c in metadata})

    def __getattr__(self, cmd_name: str) -> Callable[..., Any]:
        if self._commands:
            try:
                return self._commands[cmd_name]
            except KeyError as exc:
                raise AttributeError(cmd_name) from exc
        return wrap_call(self, cmd_name)

    def __dir__(self) -> list[str]:
        return list(self._commands.keys()) + list(super().__dir__())


def wrap_call(proxy: ServiceProxy, cmd_name: str, cmd_def: dict[str, Any] | None = None):
    def call(*args: Any, **kwargs: Any):
        con = proxy._client.connect()
        try:
            proto = con.get_protocol({proxy._svc_name: proxy._commands})

            res = proto.send_cmd(
                proxy._svc_name,
                to_unicode(cmd_name),
                *args,
                **to_unicode(kwargs, dict_keys_only=True),
            )

            isgen = inspect.isgenerator(res)
            yield isgen

            if isgen:
                for r in res:
                    yield r
            else:
                yield res
        except errors.TransportError:
            proxy._client.close()
            raise

    def call_value(*args: Any, **kwargs: Any):
        gen = call(*args, **kwargs)
        isgen = next(gen)
        if isgen:
            raise errors.ParameterError('unexpected stream result')
        return next(gen)

    def call_stream(*args: Any, **kwargs: Any):
        gen = call(*args, **kwargs)
        isgen = next(gen)
        if not isgen:
            raise errors.ParameterError('expected stream result')
        return iter(StreamInitiator(gen))

    if cmd_def and cmd_def.get('isgen'):
        def retry_wrap(*args: Any, **kwargs: Any):
            return proxy._retry.call_gen(call_stream, *args, **kwargs)
        callback = call_stream
    else:
        def retry_wrap(*args: Any, **kwargs: Any):
            return proxy._retry.call(call_value, *args, **kwargs)
        callback = call_value

    if not cmd_def:
        return retry_wrap
    return utils.function.dict_to_func(cmd_def, callback)


class StreamInitiator:
    def __init__(self, gen: Iterator[Any]) -> None:
        try:
            gen = itertools.chain([next(gen)], gen)
        except StopIteration:
            pass
        self._gen = gen

    def __iter__(self) -> Iterator[Any]:
        yield from self._gen
