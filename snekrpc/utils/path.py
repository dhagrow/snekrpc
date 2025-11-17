from __future__ import annotations

import errno
import importlib
import io
import os
import pkgutil
from collections.abc import Generator
from typing import BinaryIO

from .. import logs

log = logs.get(__name__)

BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def base_path(*names: str) -> str:
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


def import_package(pkgname: str) -> dict[str, Exception]:
    """Import all modules in *pkgname* and return any exceptions that occur."""
    exceptions: dict[str, Exception] = {}
    path = base_path(pkgname.replace('.', '/'))
    for _, modname, ispkg in pkgutil.iter_modules([path]):
        if ispkg:
            continue
        exc = import_module(modname, pkgname)
        if exc:
            exceptions[modname] = exc
    return exceptions


def import_module(modname: str, pkgname: str | None = None) -> Exception | None:
    """Import a module, optionally relative to *pkgname*."""
    name = '.'.join(filter(None, [pkgname, modname]))
    try:
        log.debug('loading: %s', name)
        if pkgname:
            importlib.import_module(f'.{modname}', pkgname)
        else:
            importlib.import_module(modname)
    except Exception as exc:
        return exc
    return None
