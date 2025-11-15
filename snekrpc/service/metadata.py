from __future__ import annotations

from typing import Any

from .. import Service, command, param
from ..utils.encoding import to_unicode
from . import service_to_dict as s2d


class MetadataService(Service):
    _name_ = 'meta'

    @param('server', hide=True)
    def __init__(self, server: Any) -> None:
        self._server = server

    @command()
    def status(self) -> dict[str, Any]:
        ifc = self._server
        res = {
            'codec': ifc.codec._name_,
            'transport': ifc.transport._name_,
            'version': ifc.version,
        }
        return to_unicode(res)

    @command()
    def service_names(self) -> list[str]:
        return list(self._server.service_names())

    @command()
    def services(self):
        return to_unicode([s2d(svc) for svc in self._server.services()])

    @command()
    def service(self, name: str):
        return to_unicode(s2d(self._server.service(name)))
