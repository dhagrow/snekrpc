"""Metadata service that introspects registered services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..utils.function import command, param
from . import Service, ServiceSpec

if TYPE_CHECKING:
    from ..interface import Server


class MetadataService(Service, name='meta'):
    """Expose codec/version info and service definitions."""

    @param('server', hide=True)
    def __init__(self, server: Server) -> None:
        """Store the server instance for later inspection."""
        self._server = server

    @command()
    def status(self) -> dict[str, Any]:
        """Return codec, transport, and version information."""
        ifc = self._server
        return {
            'codec': ifc.codec_name,
            'transport': ifc.transport_name,
            'version': ifc.version,
        }

    @command()
    def service_names(self) -> list[str]:
        """Return the exported service names."""
        return list(self._server.service_names())

    @command()
    def services(self) -> list[ServiceSpec]:
        """Return metadata for every service."""
        return [ServiceSpec.from_service(type(svc), name) for name, svc in self._server.services()]

    @command()
    def service(self, name: str) -> ServiceSpec:
        """Return metadata for an individual service."""
        return ServiceSpec.from_service(type(self._server.service(name)), name)
