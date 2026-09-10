import json
import stat
from types import SimpleNamespace

import pytest

from app.research_web import runtime_auth


def write_record(path, *, mode=0o600):
    path.write_text(json.dumps({"cookie": "dsh-auth-test=value"}), encoding="utf-8")
    path.chmod(mode)
    return path


def test_windows_ignores_posix_mode_bits_but_posix_rejects_them(tmp_path):
    path = write_record(tmp_path / "auth.json", mode=0o644)

    assert runtime_auth.read_runtime_auth_record(path, platform_name="nt")["cookie"]
    with pytest.raises(runtime_auth.RuntimeAuthFileError):
        runtime_auth.read_runtime_auth_record(path, platform_name="posix")


@pytest.mark.parametrize(
    ("is_symlink", "file_attributes"),
    [(True, 0), (False, getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))],
)
def test_aliases_are_rejected_on_every_platform(tmp_path, is_symlink, file_attributes):
    path = write_record(tmp_path / "auth.json")
    identity = SimpleNamespace(
        st_mode=path.stat().st_mode,
        st_nlink=1,
        st_size=path.stat().st_size,
        st_file_attributes=file_attributes,
    )
    candidate = SimpleNamespace(is_symlink=lambda: is_symlink)

    assert runtime_auth._is_unsafe_identity(candidate, identity, platform_name="nt") is True


def test_directory_and_oversized_control_are_rejected(tmp_path):
    directory = tmp_path / "runtime"
    directory.mkdir()
    oversized = write_record(tmp_path / "auth.json")
    oversized.write_bytes(b"x" * (runtime_auth.MAX_RUNTIME_AUTH_BYTES + 1))
    oversized.chmod(0o600)

    with pytest.raises(runtime_auth.RuntimeAuthFileError):
        runtime_auth.read_runtime_auth_record(directory)
    with pytest.raises(runtime_auth.RuntimeAuthFileError):
        runtime_auth.read_runtime_auth_record(oversized)


def test_control_replaced_between_lstat_and_open_is_rejected(tmp_path, monkeypatch):
    path = write_record(tmp_path / "auth.json")
    before = path.stat()
    replaced = SimpleNamespace(
        st_mode=before.st_mode,
        st_nlink=before.st_nlink,
        st_size=before.st_size,
        st_dev=before.st_dev + 1,
        st_ino=before.st_ino,
        st_file_attributes=0,
    )

    with monkeypatch.context() as patcher:
        patcher.setattr(runtime_auth.os, "fstat", lambda _fd: replaced)
        with pytest.raises(runtime_auth.RuntimeAuthFileError):
            runtime_auth.read_runtime_auth_record(path)
