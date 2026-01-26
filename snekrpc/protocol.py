"""RPC protocol handling for the built-in transports."""

from __future__ import annotations

import functools
import inspect
import operator
import traceback
from collections.abc import Iterable, MutableMapping
from typing import TYPE_CHECKING, Any, cast

import msgspec

from . import errors, logs, utils

if TYPE_CHECKING:
    from .interface import Client, Server
    from .transport import Connection

log = logs.get(__name__)


HANDSHAKE = b'\0'


class Message(msgspec.Struct, tag=True, array_like=True):
    @classmethod
    def subtypes(cls) -> type:
        return functools.reduce(operator.or_, cls.__subclasses__())


class CommandMessage(Message):
    service_name: str
    command_name: str
    args: tuple[Any, ...]
    kwargs: dict[str, Any]


class DataMessage(Message):
    data: Any

    # def __repr__(self) -> str:
    #     return f'{self.__class__.__name__}()'


class ErrorMessage(Message):
    name: str
    message: str
    traceback: str


class StreamStartMessage(Message):
    pass


class StreamEndMessage(Message):
    pass


class Argument(msgspec.Struct, tag=True, array_like=True):
    value: Any


class StreamArgument(msgspec.Struct, tag=True, array_like=True):
    pass


class Protocol:
    """Handle RPC messages for a single client/server connection."""

    def __init__(
        self,
        interface: Client | Server,
        con: Connection,
        metadata: MutableMapping[str, Any] | None = None,
    ) -> None:
        """Capture interfaces, connections, and any metadata."""
        self._ifc = interface
        self._con = con
        self.metadata: MutableMapping[str, Any] = metadata or {}

    @property
    def local_url(self) -> str:
        """Return the local URL used by this endpoint."""
        return self._ifc.url

    @property
    def remote_url(self) -> str:
        """Return the remote URL for the peer connection."""
        return self._con.url

    def handle(self) -> None:
        """Main loop that receives messages and dispatches commands."""
        while True:
            try:
                self.recv_cmd()
            except (ConnectionError, errors.TransportError) as exc:
                logger = logs.error_logger(log)
                logger('transport error (%s): %s', self.remote_url, utils.format.format_exc(exc))
                break

            except Exception as exc:
                self.send_err(exc)

    def req_handshake(self) -> None:
        """Negotiate codec information as an RPC client."""
        if self._ifc.codec:
            return

        if logs.is_debug(log):
            log.debug('handshake -> %s', self._con._addr)
        self._con.send(HANDSHAKE)

        data = self._con.recv()
        if not data:
            raise errors.ReceiveInterrupted()

        op, codec = data[:1], data[1:].decode()
        if op != HANDSHAKE:
            raise errors.HandshakeError()

        if logs.is_debug(log):
            log.debug('handshake(codec=%s) <- %s', codec, self._con._addr)

        self._ifc.codec = codec

    def res_handshake(self) -> bytes:
        """Respond to handshake requests as an RPC server."""
        data = self._con.recv()
        if data != HANDSHAKE:
            return data

        if logs.is_debug(log):
            log.debug('handshake <- %s', self._con._addr)

        codec_name = self._ifc.codec_name
        data = HANDSHAKE + codec_name.encode()

        self._con.send(data)
        if logs.is_debug(log):
            log.debug('handshake(codec=%s) -> %s', codec_name, self._con._addr)

        return self._con.recv()

    def recv_msg(self) -> Message | None:
        """Receive and decode a complete message."""
        data = self.res_handshake()
        if not data:
            return None

        if (codec := self._ifc.codec) is None:
            raise errors.TransportError('codec is not set')
        msg = cast(Message, msgspec.convert(codec._decode(data), Message.subtypes()))

        if logs.is_debug(log):
            log.debug('msg: %s <- %s', msg, self._con._addr)

        return msg

    def send_msg(self, message: Message) -> None:
        """Encode and send a message (performing the handshake as needed)."""
        self.req_handshake()

        if logs.is_debug(log):
            log.debug('msg: %s -> %s', message, self._con._addr)

        if (codec := self._ifc.codec) is None:
            raise errors.TransportError('codec is not set')
        data = codec._encode(message)

        self._con.send(data)

    def recv_cmd(self) -> None:
        """Decode a command message and execute the requested method."""
        msg = self.recv_msg()
        if msg is None:
            return
        if not isinstance(msg, CommandMessage):
            raise errors.MessageError(msg, CommandMessage)

        svc = self._ifc.service(msg.service_name)
        func = getattr(svc, msg.command_name)

        recv_args = []
        recv_kwargs = {}

        for arg in msg.args:
            arg = msgspec.convert(arg, Argument | StreamArgument)
            if isinstance(arg, StreamArgument):
                recv_args.append(self.recv_stream())
            else:
                recv_args.append(arg.value)
        for name, arg in msg.kwargs.items():
            arg = msgspec.convert(arg, Argument | StreamArgument)
            if isinstance(arg, StreamArgument):
                recv_kwargs[name] = self.recv_stream()
            else:
                recv_kwargs[name] = arg.value

        args = recv_args
        kwargs = recv_kwargs

        if logs.is_debug(log):
            log.debug(
                'cmd: %s <- %s',
                utils.format.format_cmd(msg.service_name, msg.command_name, args, kwargs),
                self.remote_url,
            )

        res = func(*args, **kwargs)

        if inspect.isgenerator(res):
            self.send_stream(res)
        else:
            self.send_msg(DataMessage(res))

    def send_cmd(self, svc_name: str, cmd_name: str, *args: Any, **kwargs: Any) -> Any:
        """Send a command to the remote endpoint and return the response."""
        if logs.is_debug(log):
            log.debug(
                'cmd: %s -> %s',
                utils.format.format_cmd(svc_name, cmd_name, args, kwargs),
                self.remote_url,
            )

        stream = None
        send_args: list[Any] = []
        send_kwargs: dict[str, Any] = {}

        for arg in args:
            if inspect.isgenerator(arg):
                if stream is not None:
                    raise errors.ParameterError('only one stream param is possible')
                stream = arg
                send_args.append(StreamArgument())
            else:
                send_args.append(Argument(arg))
        for name, arg in kwargs.items():
            if inspect.isgenerator(arg):
                if stream is not None:
                    raise errors.ParameterError('only one stream param is possible')
                stream = arg
                send_kwargs[name] = StreamArgument()
            else:
                send_kwargs[name] = Argument(arg)

        self.send_msg(
            CommandMessage(
                svc_name,
                cmd_name,
                tuple(send_args),
                send_kwargs,
            )
        )

        if stream:
            self.send_stream(stream)

        msg = self.recv_msg()
        if msg is None:
            raise errors.ReceiveInterrupted()

        match msg:
            case DataMessage(data):
                return data
            case ErrorMessage(name, message, traceback):
                raise errors.RemoteError(name, message, traceback)
            case StreamStartMessage():
                return self.recv_stream(started=True)
            case _:
                raise errors.MessageError(msg)

    def recv_stream(self, started: bool = False) -> Iterable[Any]:
        """Iterate over stream responses, handling protocol errors."""
        if not started:
            msg = self.recv_msg()
            if not msg:
                raise errors.ReceiveInterrupted()
            if not isinstance(msg, StreamStartMessage):
                raise errors.MessageError(msg, StreamStartMessage)

        while True:
            msg = self.recv_msg()
            if not msg:
                raise errors.ReceiveInterrupted()

            match msg:
                case DataMessage(data):
                    yield data
                case ErrorMessage(name, message, traceback):
                    raise errors.RemoteError(name, message, traceback)
                case StreamEndMessage():
                    return
                case _:
                    raise errors.MessageError(msg)

    def send_stream(self, it: Iterable[Any]) -> None:
        """Send generator output over the wire as stream chunks."""
        self.send_msg(StreamStartMessage())
        for value in it:
            self.send_msg(DataMessage(value))
        self.send_msg(StreamEndMessage())

    def send_err(self, exc: BaseException) -> None:
        """Serialize an exception and send it back to the caller."""
        name = exc.__class__.__name__
        msg = str(exc)
        # this method is only used by servers, so `remote_tracebacks` will exist
        # TODO: split protocol into client/server components?
        assert isinstance(self._ifc, Server)
        tb = traceback.format_exc().rstrip() if self._ifc.remote_tracebacks else ''

        log.exception('%s: %s', name, msg)
        self.send_msg(ErrorMessage(name, msg, tb))
