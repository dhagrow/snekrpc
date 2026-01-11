"""Registry helpers that auto-import packages and expose named lookups."""

from __future__ import annotations

from threading import Event, Lock
from typing import Any, Generic, TypeVar

from . import logs
from .utils.path import import_package

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
        self._name = name
        self._base_type = base_type
        self._registry: dict[str, type[T]] = {}
        self._names: dict[type[T], str] = {}

        _registries[name] = self

    def create(self, name: str, *args: Any, **kwargs: Any) -> T:
        """Create a registered instance."""
        return self.get(name)(*args, **kwargs)

    def get(self, name: str) -> type[T]:
        try:
            return self._registry[name]
        except KeyError as e:
            raise RegistryError(f'{name!r} has not been registered as a {self._name!r}') from e

    def get_name(self, cls: type[T]) -> str:
        return self._names[cls]

    def set(self, name: str, cls: type[T]) -> None:
        if name in self._registry:
            raise ValueError(f'{name} has already been registered in the {self._name} registry')
        self._registry[name] = cls
        self._names[cls] = name

    def names(self) -> tuple[str, ...]:
        """Return all registered names in insertion order."""
        return tuple(self._registry.keys())

    def init(self, name: str) -> None:
        """Eagerly import `name` to populate the registry with entry points."""
        import_package(name)


class RegistryError(Exception):
    pass
