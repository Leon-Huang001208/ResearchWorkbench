"""Pure-data tests for the optional descriptor-only Darwin bridge."""

from __future__ import annotations

import ctypes
import errno
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import backup_fd_clone as clone

LOG_ROOT = Path(__file__).resolve().parents[2] / "logs/backup-cow-admission/fd-primitive"


class CloneBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        LOG_ROOT.mkdir(parents=True, exist_ok=True)
        space = os.statvfs(LOG_ROOT)
        self.assertGreaterEqual(space.f_bavail * space.f_frsize, 2 * 1024**3)

    def test_names_are_single_components(self) -> None:
        expected = dict.fromkeys(clone.FACT_KEYS, "1")
        for name in ("", ".", "..", "a/b", "a\x00b"):
            with self.subTest(name=repr(name)), self.assertRaises(clone.Refusal):
                clone.validate_request({"name": name, "expectedSource": expected})
        self.assertEqual(
            clone.validate_request({"name": "sample.data", "expectedSource": expected}),
            ("sample.data", expected),
        )

    def test_unknown_request_fields_are_refused(self) -> None:
        result = clone.clone({"sourcePath": "/unread", "name": "sample.data"})
        self.assertEqual(result, {"status": "error", "code": "CLONE_REQUEST_INVALID"})

    def test_state_numbers_are_lossless_strings(self) -> None:
        with tempfile.TemporaryDirectory(dir=LOG_ROOT) as directory:
            source = Path(directory) / "plain.data"
            source.write_bytes(b"ordinary synthetic data")
            actual = clone.facts(source.stat())
            self.assertEqual(actual["mtimeNs"], str(source.stat().st_mtime_ns))
            self.assertEqual(set(actual), set(clone.FACT_KEYS))

    @unittest.skipUnless(sys.platform == "darwin", "Darwin metadata only")
    def test_plain_file_metadata_is_supported(self) -> None:
        with tempfile.TemporaryDirectory(dir=LOG_ROOT) as directory:
            source = Path(directory) / "plain.data"
            source.write_bytes(b"ordinary synthetic data")
            fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                clone.require_plain_metadata(clone.system_library(), fd)
            finally:
                os.close(fd)

    @unittest.skipUnless(sys.platform == "darwin", "Darwin metadata only")
    def test_xattr_is_refused_without_mutating_sample(self) -> None:
        with tempfile.TemporaryDirectory(dir=LOG_ROOT) as directory:
            source = Path(directory) / "plain.data"
            source.write_bytes(b"ordinary synthetic data")
            fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
            library = clone.system_library()
            library.fsetxattr.argtypes = [
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_void_p,
                ctypes.c_size_t,
                ctypes.c_uint32,
                ctypes.c_int,
            ]
            library.fsetxattr.restype = ctypes.c_int
            try:
                self.assertEqual(library.fsetxattr(fd, b"com.rwb.synthetic", b"data", 4, 0, 0), 0)
                with self.assertRaises(clone.Refusal) as caught:
                    clone.require_plain_metadata(library, fd)
                self.assertEqual(caught.exception.status, "unsupported")
                self.assertEqual(caught.exception.code, "CLONE_XATTR_UNSUPPORTED")
                self.assertEqual(source.read_bytes(), b"ordinary synthetic data")
            finally:
                os.close(fd)

    @unittest.skipUnless(sys.platform == "darwin", "Darwin metadata only")
    def test_file_flags_are_refused_without_mutating_bytes(self) -> None:
        with tempfile.TemporaryDirectory(dir=LOG_ROOT) as directory:
            source = Path(directory) / "plain.data"
            source.write_bytes(b"ordinary synthetic data")
            fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
            library = clone.system_library()
            library.fchflags.argtypes = [ctypes.c_int, ctypes.c_uint]
            library.fchflags.restype = ctypes.c_int
            try:
                self.assertEqual(library.fchflags(fd, 1), 0)  # UF_NODUMP, own sample.
                with self.assertRaises(clone.Refusal) as caught:
                    clone.require_plain_metadata(library, fd)
                self.assertEqual(caught.exception.code, "CLONE_FLAGS_UNSUPPORTED")
                self.assertEqual(source.read_bytes(), b"ordinary synthetic data")
            finally:
                self.assertEqual(library.fchflags(fd, 0), 0)
                os.close(fd)

    @unittest.skipUnless(sys.platform == "darwin", "Darwin syscall only")
    def test_stale_absence_then_real_eexist_preserves_unknown_target(self) -> None:
        with tempfile.TemporaryDirectory(dir=LOG_ROOT) as directory:
            root = Path(directory)
            source = root / "plain.data"
            target_directory = root / "private"
            target_directory.mkdir(mode=0o700)
            target = target_directory / "copy.data"
            source.write_bytes(b"ordinary synthetic source")
            target.write_bytes(b"existing ordinary target")
            before = target.stat()
            source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
            directory_fd = os.open(target_directory, os.O_RDONLY | os.O_NOFOLLOW)
            library = clone.system_library()
            real_syscall = library.fclonefileat
            observed_errno = []

            def record_syscall(*arguments: object) -> int:
                result = real_syscall(*arguments)
                observed_errno.append(ctypes.get_errno())
                return int(result)

            try:
                # Only the initial existence observation is stale. The actual
                # system call uses real sample FDs and encounters EEXIST once.
                with (
                    patch.object(clone, "SOURCE_FD", source_fd),
                    patch.object(clone, "DIRECTORY_FD", directory_fd),
                    patch.object(clone, "system_library", return_value=library),
                    patch.object(clone, "destination_present", side_effect=[False, True]),
                    patch.object(library, "fclonefileat", side_effect=record_syscall) as syscall,
                ):
                    result = clone.clone(
                        {"name": "copy.data", "expectedSource": clone.facts(os.fstat(source_fd))}
                    )
                    self.assertEqual(syscall.call_count, 1)
                self.assertEqual(observed_errno, [errno.EEXIST])
                self.assertEqual(result, {"status": "unknown", "code": "CLONE_EFFECT_UNVERIFIED"})
                self.assertEqual(target.stat().st_ino, before.st_ino)
                self.assertEqual(target.read_bytes(), b"existing ordinary target")
            finally:
                os.close(directory_fd)
                os.close(source_fd)


if __name__ == "__main__":
    unittest.main()
