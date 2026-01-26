import os

import pytest

from snekrpc.service.file import FileService


def test_symlink_escape(tmp_path):
    root = tmp_path / 'root'
    root.mkdir()
    outside = tmp_path / 'outside.txt'
    outside.write_text('x')
    link = root / 'escape'

    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f'symlinks not available: {exc}')

    svc = FileService(root_path=str(root), safe_root=True)
    with pytest.raises(OSError):
        svc.check_path('escape')
