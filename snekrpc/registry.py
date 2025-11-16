from __future__ import annotations

from threading import Event, Lock
from typing import Any, ClassVar

from . import errors, logs
from .utils.path import import_package

log = logs.get(__name__)

_metaclasses: dict[str, type['RegistryMeta']] = {}
_init_lock = Lock()
_initialized = Event()


def init() -> None:
    """Import and register modules for all known metaclass registries."""
    with _init_lock:
        if _initialized.is_set():
            return

        for meta_name, meta in _metaclasses.items():
            meta.init(meta_name)

        _initialized.set()


class RegistryMeta(type):
    registry: ClassVar[dict[str, type[Any] | Exception]] = {}

    def __init__(cls, name: str, bases: tuple[type, ...], namespace: dict[str, Any]) -> None:
        super().__init__(name, bases, namespace)
        if bases and bases[0] is not object:
            cls._name_ = reg_name = namespace.get('_name_', name)  # type: ignore[attr-defined]
            if reg_name in cls.registry:
                raise errors.RegistryError(f'already registered: {reg_name}')
            cls.registry[reg_name] = cls
            log.debug('registered %s: %s', f'{cls.__module__}.{name}', reg_name)

    @classmethod
    def get(cls, name: str) -> type[Any]:
        _initialized.wait()
        entry = cls.registry[name]
        if isinstance(entry, Exception):
            raise entry
        return entry

    @classmethod
    def names(cls) -> tuple[str, ...]:
        _initialized.wait()
        return tuple(cls.registry.keys())

    @classmethod
    def init(cls, name: str) -> None:
        exceptions = import_package(name)
        for modname, exc in exceptions.items():
            cls.registry[modname] = exc


def create_metaclass(meta_name: str) -> type[RegistryMeta]:
    class Meta(RegistryMeta):
        registry: ClassVar[dict[str, type[Any] | Exception]] = {}

    _metaclasses[meta_name] = Meta
    return Meta
