"""Service base classes and helpers."""

from __future__ import annotations

import inspect
import itertools
from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import TYPE_CHECKING, Any

import msgspec

from .. import errors, logs, protocol, registry, utils
from ..utils.encoding import to_str

if TYPE_CHECKING:
    from ..interface import Client

log = logs.get(__name__)

ServiceMeta = registry.create_metaclass(__name__)


class ServiceSpec(msgspec.Struct, frozen=True):
    """Description of a callable signature."""

    name: str
    doc: str | None
    commands: tuple[utils.function.SignatureSpec, ...]


def parse_alias(name: str) -> tuple[str, str | None]:
    """Split ``name`` into ``module`` and ``alias`` if ``:`` is present."""
    try:
        base, alias = name.split(':')
    except ValueError:
        return name, None
    return base, alias


def get_class(name: str):
    """Return the registered Service subclass for ``name``."""
    return ServiceMeta.get(name)


def get(
    name: str | Service, service_args: Mapping[str, Any] | None = None, alias: str | None = None
):
    """Instantiate (or normalize) a service definition."""
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


def encode(svc: Service) -> ServiceSpec:
    """Serialize a service definition for metadata responses."""
    # commands have a `_meta` attribute
    commands = []
    for name in dir(svc):
        if name.startswith('_'):
            continue
        attr = getattr(svc, name)
        if getattr(attr, '_meta', None) is not None:
            commands.append(utils.function.encode(attr))

    return ServiceSpec(
        svc._name_ or svc.__class__.__name__,
        svc.__doc__,
        tuple(commands),
    )


class Service(metaclass=ServiceMeta):
    """Base class for RPC services."""

    _name_: str | None = None

    def __init__(self) -> None:
        """Primarily intended for subclass initialization."""
        pass


class ServiceProxy:
    """Client-side helper that exposes remote commands as callables."""

    def __init__(
        self,
        name: str,
        client: Client,
        command_metadata: bool | Sequence[utils.function.SignatureSpec] = True,
    ):
        """Cache remote service metadata and wrap remote commands.

        When `command_metadata` is `True`, metadata will be loaded from the
        remote metadata service. When `False`, no metadata will be loaded.
        Otherwise, a sequence of command metadata can be provided directly.
        """
        self._svc_name = to_str(name)
        self._client = client
        self._commands: dict[str, Callable[..., Any]] = {}

        self._retry = utils.retry.Retry(
            client.retry_count, client.retry_interval, errors=[errors.TransportError], logger=log
        )

        def wrap_command(spec: utils.function.SignatureSpec):
            return wrap_call(self, spec.name, spec)

        if command_metadata is True:
            meta = ServiceProxy('_meta', client, command_metadata=False)
            svc = msgspec.convert(meta.service(self._svc_name), ServiceSpec)
            self._commands.update({c.name: wrap_command(c) for c in svc.commands})
        elif command_metadata:
            self._commands.update({c.name: wrap_command(c) for c in command_metadata})

    def __getattr__(self, cmd_name: str) -> Callable[..., Any]:
        """Return a cached callable or lazily wrap the remote command."""
        if self._commands:
            try:
                return self._commands[cmd_name]
            except KeyError as exc:
                raise AttributeError(cmd_name) from exc
        return wrap_call(self, cmd_name)

    def __dir__(self) -> list[str]:
        """Add remote command names to ``dir()`` results."""
        return list(self._commands.keys()) + list(super().__dir__())


def wrap_call(
    proxy: ServiceProxy, cmd_name: str, cmd_spec: utils.function.SignatureSpec | None = None
):
    """Wrap a remote call in retry logic, handling stream outputs."""

    def call(*args: Any, **kwargs: Any):
        con = proxy._client.connect()
        try:
            proto = protocol.Protocol(proxy._client, con, {proxy._svc_name: proxy._commands})

            res = proto.send_cmd(proxy._svc_name, cmd_name, *args, **kwargs)

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

    if cmd_spec and cmd_spec.is_generator:

        def retry_wrap_gen(*args: Any, **kwargs: Any):
            yield from proxy._retry.call_gen(call_stream, *args, **kwargs)

        callback = retry_wrap_gen
    else:

        def retry_wrap(*args: Any, **kwargs: Any):
            return proxy._retry.call(call_value, *args, **kwargs)

        callback = retry_wrap

    if not cmd_spec:
        return callback
    return utils.function.decode(cmd_spec, callback)


class StreamInitiator:
    """Iterator shim that replays the first yielded value."""

    def __init__(self, gen: Iterator[Any]) -> None:
        """Prime the generator while preserving the first item."""
        try:
            gen = itertools.chain([next(gen)], gen)
        except StopIteration:
            pass
        self._gen = gen

    def __iter__(self) -> Iterator[Any]:
        """Yield the cached first item followed by the original stream."""
        yield from self._gen
