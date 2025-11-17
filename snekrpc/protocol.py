from __future__ import annotations

import inspect
import traceback
from collections.abc import Iterable, MutableMapping
from typing import TYPE_CHECKING, Any

from . import errors, logs, utils

if TYPE_CHECKING:
    from .interface import Client, Server
    from .transport import Connection, Message

log = logs.get(__name__)


class Op:
    # fmt: off
    handshake    = 0  # <raw> initial handshake (codec)
    command      = 1  # call a command (svc_name, cmd_name, args, kwargs)
    data         = 2  # return data (data)
    error        = 3  # return error (name, msg, tb)
    stream_start = 4  # start of stream ([name])
    stream_end   = 5  # end of stream
    # fmt: on

    @classmethod
    def to_str(cls, op: int) -> str:
        for name, value in vars(cls).items():
            if value == op:
                return name
        raise ValueError(f'invalid op code: {op}')


class Protocol:
    def __init__(
        self,
        interface: Client | Server,
        con: Connection,
        metadata: MutableMapping[str, Any] | None = None,
    ) -> None:
        self._ifc = interface
        self._con = con
        self.metadata: MutableMapping[str, Any] = metadata or {}

    @property
    def local_url(self):
        return self._ifc.url

    @property
    def remote_url(self):
        return self._con.url

    def handle(self) -> None:
        recv = self._con.recv_msg

        while True:
            try:
                msg = recv()

                if msg is None:
                    return
                if msg.op == Op.command:
                    self.recv_cmd(msg)
                else:
                    raise errors.ProtocolOpError(msg.op)

            except errors.TransportError as exc:
                logger = log.exception if log.isEnabledFor(logs.DEBUG) else log.error
                logger('transport error (%s): %s', self.remote_url, utils.format.format_exc(exc))

            except Exception as exc:
                self.send_err(exc)

    def recv_cmd(self, msg: 'Message') -> None:
        svc_name, cmd_name, args, kwargs = msg.data

        svc = self._ifc.service(svc_name)
        func = getattr(svc, cmd_name)

        recv_args = []
        recv_kwargs = {}

        for arg in args:
            if inspect.isgenerator(arg):
                arg = self.recv_stream()
            recv_args.append(arg)
        for name, arg in kwargs.items():
            if inspect.isgenerator(arg):
                arg = self.recv_stream()
            recv_kwargs[name] = arg

        args = recv_args
        kwargs = recv_kwargs

        if log.isEnabledFor(logs.DEBUG):
            log.debug(
                'cmd: %s <- %s',
                utils.format.format_cmd(svc_name, cmd_name, args, kwargs),
                self.remote_url,
            )

        res = func(*args, **kwargs)

        if inspect.isgenerator(res):
            self.send_stream(res)
        else:
            self._con.send_msg(Op.data, res)

    def send_cmd(self, svc_name: str, cmd_name: str, *args: Any, **kwargs: Any) -> Any:
        if log.isEnabledFor(logs.DEBUG):
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
            send_args.append(arg)
        for name, arg in kwargs.items():
            if inspect.isgenerator(arg):
                if stream is not None:
                    raise errors.ParameterError('only one stream param is possible')
                stream = arg
            send_kwargs[name] = arg

        args = tuple(send_args)
        kwargs = send_kwargs

        self._con.send_msg(Op.command, (svc_name, cmd_name, args, kwargs))

        if stream:
            self.send_stream(stream)

        msg = self._con.recv_msg()
        if msg is None:
            raise errors.ReceiveInterrupted()

        if msg.op == Op.data:
            return msg.data
        if msg.op == Op.error:
            raise errors.RemoteError(*msg.data)
        if msg.op == Op.stream_start:
            return self.recv_stream(started=True)
        raise errors.ProtocolOpError(msg.op)

    def recv_stream(self, started: bool = False):
        recv = self._con.recv_msg

        if not started:
            msg = recv()
            if not msg:
                raise errors.ReceiveInterrupted()
            if msg.op != Op.stream_start:
                raise errors.ProtocolOpError(msg.op)

        while True:
            msg = recv()
            if not msg:
                raise errors.ReceiveInterrupted()
            if msg.op == Op.data:
                yield msg.data
            elif msg.op == Op.error:
                raise errors.RemoteError(*msg.data)
            elif msg.op == Op.stream_end:
                return
            else:
                raise errors.ProtocolOpError(msg.op)

    def send_stream(self, it: Iterable[Any]) -> None:
        send = self._con.send_msg
        send(Op.stream_start)
        for value in it:
            send(Op.data, value)
        send(Op.stream_end)

    def send_err(self, exc: BaseException) -> None:
        name = exc.__class__.__name__
        msg = str(exc)
        tb = traceback.format_exc().rstrip() if self._ifc.remote_tracebacks else ''

        log.exception('%s: %s', name, msg)
        self._con.send_msg(Op.error, utils.encoding.to_str((name, msg, tb)))
