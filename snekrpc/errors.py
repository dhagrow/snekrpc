"""Exception hierarchy used throughout the project."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class SnekRPCError(Exception):
    """Base class for package-specific exceptions."""


class TransportError(SnekRPCError):
    """Raised for any error in the transport."""


class SendInterrupted(TransportError):
    """Raised when data sent to the remote end is less than expected."""

    def __init__(self, msg: str = 'send interrupted'):
        super().__init__(msg)


class ReceiveInterrupted(TransportError):
    """Raised when data received from the remote end is less than expected."""

    def __init__(self, msg: str = 'receive interrupted'):
        super().__init__(msg)


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
        """Return the formatted error message provided by the server."""
        return f'{self.name}: {self.msg}'

    def __str__(self) -> str:
        """Prefer the server-side traceback when rendering the error."""
        return self.traceback or self.message


class ServerError(SnekRPCError):
    """Base class for server exceptions."""


class ParameterError(ServerError):
    """Raised for invalid parameter configurations."""


class HandshakeError(SnekRPCError):
    """Raised for protocol handshake errors."""


class MessageError(SnekRPCError):
    """Raised for protocol message errors."""

    def __init__(self, message: Any, expected: Any = None) -> None:
        """Store the invalid opcode so callers can inspect it."""
        super().__init__(f'invalid protocol message: {message} (expected: {expected or "Any"})')


class EncodeError(SnekRPCError):
    """Adds context for errors raised when packing."""


class DecodeError(SnekRPCError):
    """Adds context for errors raised when unpacking."""


class RegistryError(SnekRPCError):
    """Raised when attempting to register a duplicate object."""
