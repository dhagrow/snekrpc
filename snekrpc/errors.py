from __future__ import annotations

from dataclasses import dataclass


class SnekRPCError(Exception):
    """Base class for all snekrpc exceptions."""


class TransportError(SnekRPCError):
    """Raised for any error in the transport."""


class SendInterrupted(TransportError):
    """Raised when data sent to the remote end is less than expected."""


class ReceiveInterrupted(TransportError):
    """Raised when data received from the remote end is less than expected."""


class ClientError(SnekRPCError):
    """Base class for client exceptions."""


class InvalidService(ClientError):
    """Raised for any attempt to access a service that does not exist."""


class InvalidCommand(ClientError):
    """Raised for any attempt to access a command that does not exist."""


@dataclass(slots=True)
class RemoteError(ClientError):
    """Raised for any exceptions that occur on the RPC server."""

    name: str
    msg: str
    traceback: str

    @property
    def message(self) -> str:
        return f'{self.name}: {self.msg}'

    def __str__(self) -> str:
        return self.traceback or self.message


class ServerError(SnekRPCError):
    """Base class for server exceptions."""


class ParameterError(ServerError):
    """Raised for invalid parameter configurations."""


class ProtocolOpError(SnekRPCError):
    """Raised for protocol errors."""

    def __init__(self, opcode: int) -> None:
        super().__init__(f'invalid opcode: {opcode}')
        self.opcode = opcode


class EncodeError(SnekRPCError):
    """Adds context for errors raised when packing."""


class DecodeError(SnekRPCError):
    """Adds context for errors raised when unpacking."""


class RegistryError(SnekRPCError):
    """Raised when attempting to register a duplicate object."""
