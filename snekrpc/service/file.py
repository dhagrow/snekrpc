"""Service for basic filesystem manipulation on the server."""

from __future__ import annotations

import contextlib
import glob
import io
import os
import shutil
from collections.abc import Iterable, Iterator
from typing import Any

from .. import Service, command, logs, param, utils

log = logs.get(__name__)

CHUNK_SIZE = io.DEFAULT_BUFFER_SIZE


class FileService(Service, name='file'):
    """Expose file operations such as listing, uploads, and downloads."""

    @param('root_path', doc='root path for all file operations')
    @param('safe_root', doc='ensures that no file operation escapes the root path')
    @param('chunk_size', doc='size of data to buffer when reading')
    def __init__(
        self, root_path: str | None = None, safe_root: bool = True, chunk_size: int = CHUNK_SIZE
    ) -> None:
        self.root_path = root_path or os.getcwd()
        self.safe_root = safe_root
        self.chunk_size = chunk_size

    @property
    def root_path(self) -> str:
        """Return the normalized root path for operations."""
        return self._root_path

    @root_path.setter
    def root_path(self, root_path: str) -> None:
        """Normalize the supplied root path and store it."""
        path = os.path.expandvars(os.path.expanduser(root_path))
        path = os.path.abspath(os.path.normpath(path))
        self._root_path = os.path.join(path, '')

    @command()
    def paths(self, pattern: str | None = None, with_metadata: bool = False) -> Iterable[str]:
        """Yield file paths (optionally including metadata) matching pattern."""
        pattern = self.check_path(pattern or '*')
        if os.path.isdir(pattern):
            pattern = os.path.join(pattern, '*')

        for name in glob.iglob(pattern):
            if isinstance(name, bytes):
                name = name.decode()

            path = os.path.relpath(name, self.root_path) if self.safe_root else name
            if path == '.':
                continue

            yield path

    @command()
    def path_info(self, pattern: str | None = None) -> Iterable[dict[str, Any]]:
        for path in self.paths(pattern):
            entry: dict[str, Any] = {'path': path}
            try:
                stat = os.stat(path)
                entry.update(size=stat.st_size, mtime=stat.st_mtime, isfile=os.path.isfile(path))
            except OSError as exc:
                log.warning('could not read file: %s', exc)
                entry.update(size=None, mtime=None, isfile=None)

            yield entry

    @command()
    def touch(self, path: str) -> None:
        """Create a file if missing or update its timestamp."""
        path = self.check_path(path)
        with open(path, 'a'):
            os.utime(path, None)

    @command()
    def create_dir(self, path: str, mode: str | None = None, recurse: bool = False) -> None:
        """Create a directory with optional recursion."""
        path = self.check_path(path)
        numeric_mode = 0o755 if mode is None else int(mode, 8)
        if recurse:
            utils.path.ensure_dirs(path, numeric_mode)
        else:
            os.mkdir(path, numeric_mode)

    @command()
    def delete(self, path: str, recurse: bool = False) -> None:
        """Delete a file or directory (optionally recursive)."""
        path = self.check_path(path)
        if os.path.isdir(path):
            if recurse:
                shutil.rmtree(path)
            else:
                os.rmdir(path)
        else:
            os.remove(path)

    @param('src', doc='the data to upload')
    @param('dst_path', doc='the remote path to upload to')
    @command()
    def upload(self, src: Iterable[bytes], dst_path: str) -> str:
        """Write streamed data to the destination path."""
        path = self.check_path(dst_path)

        with open(path, 'wb') as fp:
            for chunk in src:
                fp.write(chunk)
            fp.flush()
            os.fsync(fp.fileno())
            log.info('%s bytes uploaded: %s', fp.tell(), path)

        return self.sanitize_path(path)

    @param('src_path', doc='the remote path to download from')
    @command()
    def download(self, src_path: str) -> Iterator[bytes]:
        """Stream the contents of `src_path` back to the caller."""
        path = self.check_path(src_path)
        with open(path, 'rb') as fp:
            for chunk in utils.path.iter_file(fp, self.chunk_size):
                yield chunk
            log.info('%s bytes downloaded: %s', fp.tell(), path)

    @command()
    def size(self, path: str) -> int:
        """Return the file size for `path`."""
        with self.sanitize_errors():
            path = self.check_path(path)
            return os.stat(path).st_size

    @contextlib.contextmanager
    def sanitize_errors(self) -> Iterator[None]:
        """Ensure error filenames are safe to expose when safe_root is set."""
        try:
            yield
        except OSError as exc:
            exc.filename = self.sanitize_path(exc.filename)
            raise

    def sanitize_path(self, path: str, root_path: str | None = None) -> str:
        """Return a user-safe path when safe_root is enabled."""
        if not self.safe_root:
            return path
        return os.path.relpath(path, root_path or self.root_path)

    def check_path(self, path: str | None, root_path: str | None = None) -> str:
        """Validate and normalize `path` relative to `root_path`."""
        path = path or '.'
        root_path = root_path or self.root_path

        if not self.safe_root:
            path = os.path.expandvars(os.path.expanduser(path))
            return os.path.join(root_path, path)

        if not root_path:
            raise ValueError('safe_root is enabled, but no root_path is set')

        full_path = os.path.join(root_path, path)
        full_path_real = os.path.realpath(full_path)
        root_path_real = os.path.realpath(root_path)

        if os.path.commonpath([root_path_real, full_path_real]) != root_path_real:
            raise OSError(f"Permission denied: '{path}'")

        return full_path_real
