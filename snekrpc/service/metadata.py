from __future__ import annotations

from typing import Any

from .. import Service, command, param
from ..interface import Server
from ..utils.encoding import to_str
from . import service_to_dict


class MetadataService(Service):
    _name_ = 'meta'

    @param('server', hide=True)
    def __init__(self, server: Server) -> None:
        self._server = server

    @command()
    def status(self) -> dict[str, Any]:
        ifc = self._server
        res = {
            'codec': None if ifc.codec is None else ifc.codec._name_,
            'transport': ifc.transport._name_,
            'version': ifc.version,
        }
        return to_str(res)

    @command()
    def service_names(self) -> list[str]:
        return list(self._server.service_names())

    @command()
    def services(self):
        return to_str([service_to_dict(svc) for svc in self._server.services()])

    @command()
    def service(self, name: str):
        return to_str(service_to_dict(self._server.service(name)))
