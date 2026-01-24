"""Service base classes and helpers."""

from __future__ import annotations

import inspect
import itertools
from collections.abc import Callable, Iterator, Sequence
from typing import TYPE_CHECKING, Any, Self

import msgspec

from .. import errors, logs, protocol, utils
from ..registry import Registry

if TYPE_CHECKING:
    from ..interface import Client

log = logs.get(__name__)


class Service:
    def __init_subclass__(cls, /, name: str | None = None) -> None:
        REGISTRY.set(cls.__name__ if name is None else name, cls)


REGISTRY = Registry(__name__, Service)
get, create = REGISTRY.get, REGISTRY.create


class ServiceSpec(msgspec.Struct, frozen=True):
    """Description of a callable signature."""

    name: str
    doc: str | None
    commands: tuple[utils.function.SignatureSpec, ...]

    @classmethod
    def from_service(cls, svc: type[Service], service_name: str | None = None) -> Self:
        """Serialize a service definition for metadata responses."""
        # commands have a `_meta` attribute
        commands = []
        service_name = REGISTRY.get_name(svc) if service_name is None else service_name
        for name in dir(svc):
            if name.startswith('_'):
                continue
            attr = getattr(svc, name)
            if getattr(attr, '_meta', None) is not None:
                commands.append(utils.function.encode(attr, remove_self=True))

        return cls(service_name, svc.__doc__, tuple(commands))


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
        self._svc_name = name
        self._client = client
        self._commands: dict[str, Callable[..., Any]] = {}

        self._retry = utils.retry.Retry(
            client.retry_count, client.retry_interval, errors=[errors.TransportError], logger=log
        )

        if command_metadata is True:
            meta = ServiceProxy('_meta', client, command_metadata=False)
            svc = msgspec.convert(meta.service(self._svc_name), ServiceSpec)
            self._commands.update({c.name: wrap_call(self, c.name, c) for c in svc.commands})
        elif command_metadata:
            self._commands.update({c.name: wrap_call(self, c.name, c) for c in command_metadata})

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


class StreamInitiator:
    """Generator shim that ensures the generator is started."""

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


def wrap_call(
    proxy: ServiceProxy, cmd_name: str, cmd_spec: utils.function.SignatureSpec | None = None
) -> Callable[..., Any]:
    """Wrap a remote call in retry logic, handling stream outputs."""

    def call(*args: Any, **kwargs: Any) -> Any:
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

    def call_value(*args: Any, **kwargs: Any) -> Any:
        gen = call(*args, **kwargs)
        isgen = next(gen)
        if isgen:
            raise errors.ParameterError('did not expect a stream')
        return next(gen)

    def call_stream(*args: Any, **kwargs: Any) -> Any:
        gen = call(*args, **kwargs)
        isgen = next(gen)
        if not isgen:
            raise errors.ParameterError('expected a stream')
        return iter(StreamInitiator(gen))

    if cmd_spec and cmd_spec.is_generator:

        def retry_wrap_gen(*args: Any, **kwargs: Any) -> Any:
            yield from proxy._retry.call_gen(call_stream, *args, **kwargs)

        callback = retry_wrap_gen
    else:

        def retry_wrap(*args: Any, **kwargs: Any) -> Any:
            return proxy._retry.call(call_value, *args, **kwargs)

        callback = retry_wrap

    if not cmd_spec:
        return callback
    return utils.function.decode(cmd_spec, callback)
