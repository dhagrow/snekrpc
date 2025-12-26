"""Registry helpers that auto-import packages and expose named lookups."""

from __future__ import annotations

from threading import Event, Lock
from typing import Any, Generic, TypeVar

from . import logs
from .utils.path import import_class, import_package

log = logs.get(__name__)

_init_lock = Lock()
_initialized = Event()
_registries: dict[str, Registry[Any]] = {}


def init() -> None:
    """Import and register modules for all known metaclass registries."""
    with _init_lock:
        if _initialized.is_set():
            return

        for meta_name, meta in _registries.items():
            meta.init(meta_name)

        _initialized.set()


T = TypeVar('T')


class Registry(Generic[T]):
    """Keeps a registry of subclasses by name."""

    def __init__(self, name: str, base_type: type[T]) -> None:
        self._base_type = base_type
        self._registry: dict[str, type[T]] = {}

        _registries[name] = self

    def __getitem__(self, name: str) -> type[T]:
        try:
            cls = self._registry[name]
        except KeyError:
            cls = import_class(self._base_type, name)
        return cls

    def __setitem__(self, name: str, cls: type[T]) -> None:
        self._registry[name] = cls

    def names(self) -> tuple[str, ...]:
        """Return all registered names in insertion order."""
        return tuple(self._registry.keys())

    def init(self, name: str) -> None:
        """Eagerly import `name` to populate the registry with entry points."""
        import_package(name)
