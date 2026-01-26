"""Filesystem helpers for the utility layer."""

from __future__ import annotations

import errno
import importlib
import io
import os
import pkgutil
from collections.abc import Generator
from types import ModuleType
from typing import BinaryIO, TypeVar, cast

from .. import logs

log = logs.get(__name__)

BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def base_path(*names: str) -> str:
    """Return an absolute path anchored at the repository root."""
    return os.path.join(BASE_PATH, *names)


def ensure_dirs(path: str, mode: int = 0o755) -> None:
    """Create *path* if it does not exist."""
    try:
        os.makedirs(path, mode)
    except OSError:
        pass


def discard_file(path: str) -> None:
    """Remove *path* if it exists."""
    try:
        os.remove(path)
    except OSError as exc:
        if exc.errno != errno.ENOENT:
            raise


def iter_file(fp: BinaryIO, chunk_size: int | None = None) -> Generator[bytes, None, None]:
    """Iterate through a file object in chunks."""
    size = chunk_size or io.DEFAULT_BUFFER_SIZE
    while chunk := fp.read(size):
        yield chunk


def import_package(pkgname: str) -> None:
    """Import all modules in *pkgname*."""
    path = base_path(pkgname.replace('.', '/'))
    for _, modname, ispkg in pkgutil.iter_modules([path]):
        if ispkg:
            continue
        try:
            import_module(modname, pkgname)
        except Exception as e:
            logs.error_logger(log)('import error: %s - %s', modname, e)


def import_module(modname: str, pkgname: str | None = None) -> ModuleType:
    """Import a module, optionally relative to *pkgname*."""
    name = '.'.join(filter(None, [pkgname, modname]))
    log.debug('loading: %s', name)
    return (
        importlib.import_module(f'.{modname}', pkgname)
        if pkgname
        else importlib.import_module(modname)
    )


T = TypeVar('T')


def import_class(BaseType: type[T], name: str) -> type[T]:
    mod_name, cls_name = name.rsplit('.', 1)
    mod = importlib.import_module(mod_name)
    cls = getattr(mod, cls_name)

    if not issubclass(cls, BaseType):
        raise TypeError(f'expected a class of type {BaseType}, got {cls}')

    return cast(type[T], cls)
