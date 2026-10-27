"""Regenerated dependency adoption remains derived, journaled and fail closed."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_workbench_entrypoint.iteration_resources import (
    ResourceError,
    clean_dependencies,
    regenerated_directory,
    register_directory,
)


class RegenerationTests(unittest.TestCase):
    def test_function_scoped_real_bytecode_encodings_can_rebind(self):
        import py_compile

        from research_workbench_entrypoint.docker_resources import write_receipt

        for mode in (
            py_compile.PycInvalidationMode.TIMESTAMP,
            py_compile.PycInvalidationMode.CHECKED_HASH,
        ):
            for optimization in (0, 1, 2):
                with (
                    self.subTest(mode=mode.name, optimization=optimization),
                    tempfile.TemporaryDirectory() as directory,
                ):
                    root = Path(directory).resolve()
                    state = root / "state"
                    state.mkdir(mode=0o700)
                    source = root / "example.py"
                    source.write_text("def f(x):\n    return x + 1\nvalue=f(2)\n")
                    cache = Path(
                        py_compile.compile(
                            str(source),
                            doraise=True,
                            optimize=optimization,
                            invalidation_mode=mode,
                        )
                    ).parent
                    row = register_directory(root, cache, "dependency")
                    write_receipt(
                        state / "dependencies.json",
                        {"ok": True, "items": [{"path": str(cache), "status": "reclaimed"}]},
                    )
                    with (
                        patch(
                            "research_workbench_entrypoint.iteration_resources.occupied",
                            return_value=False,
                        ),
                        patch(
                            "research_workbench_entrypoint.iteration_resources.git",
                            side_effect=lambda _, *args: (
                                "example.py" if args[0] == "ls-files" else ""
                            ),
                        ),
                    ):
                        proof = regenerated_directory(row, row, state)
                    self.assertEqual(len(proof["manifest"]), 1)

    def test_missing_standard_bytecode_encoder_remains_blocked(self):
        import importlib._bootstrap_external
        import py_compile

        from research_workbench_entrypoint.docker_resources import write_receipt

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            state = root / "state"
            state.mkdir(mode=0o700)
            source = root / "example.py"
            source.write_text("value=1\n")
            filename = Path(py_compile.compile(str(source), doraise=True))
            row = register_directory(root, filename.parent, "dependency")
            write_receipt(
                state / "dependencies.json",
                {"ok": True, "items": [{"path": str(filename.parent), "status": "reclaimed"}]},
            )
            with (
                patch(
                    "research_workbench_entrypoint.iteration_resources.occupied", return_value=False
                ),
                patch(
                    "research_workbench_entrypoint.iteration_resources.git",
                    side_effect=lambda _, *args: "example.py" if args[0] == "ls-files" else "",
                ),
                patch.object(importlib._bootstrap_external, "_code_to_timestamp_pyc", None),
                self.assertRaisesRegex(ResourceError, "bytecode_encoder_unavailable"),
            ):
                regenerated_directory(row, row, state)
            self.assertTrue(filename.exists())

    def test_reclaimed_bytecode_can_rebind_but_new_contents_are_rechecked(self):
        import py_compile

        from research_workbench_entrypoint.docker_resources import write_receipt

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            state = root / "state"
            state.mkdir(mode=0o700)
            source = root / "example.py"
            source.write_text("value=1\n")
            py_compile.compile(str(source), doraise=True)
            cache = root / "__pycache__"
            before = register_directory(root, cache, "dependency")
            clean_dependencies(
                [before],
                occupied=lambda _: False,
                tracked=lambda _: False,
                journal=lambda result: write_receipt(state / "dependencies.json", result),
            )
            py_compile.compile(str(source), doraise=True)
            current = register_directory(root, cache, "dependency")
            with (
                patch(
                    "research_workbench_entrypoint.iteration_resources.occupied", return_value=False
                ),
                patch(
                    "research_workbench_entrypoint.iteration_resources.git",
                    side_effect=lambda _, *args: "example.py" if args[0] == "ls-files" else "",
                ),
            ):
                proof = regenerated_directory(before, current, state)
            self.assertTrue(Path(proof["proof"]).is_file())
            (cache / "business.txt").write_text("must keep")
            result = clean_dependencies(
                [current],
                occupied=lambda _: False,
                tracked=lambda _: False,
                regenerations={str(cache): proof},
            )
            self.assertFalse(result["ok"])
            self.assertTrue((cache / "business.txt").exists())

    def test_rebinding_unknown_or_unreclaimed_dependency_remains_blocked(self):
        from research_workbench_entrypoint.docker_resources import write_receipt

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            state = root / "state"
            state.mkdir(mode=0o700)
            dep = root / "node_modules"
            dep.mkdir()
            row = register_directory(root, dep, "dependency")
            write_receipt(
                state / "dependencies.json",
                {"ok": True, "items": [{"path": str(dep), "status": "reclaimed"}]},
            )
            with (
                patch(
                    "research_workbench_entrypoint.iteration_resources.occupied", return_value=False
                ),
                patch("research_workbench_entrypoint.iteration_resources.git", return_value=""),
                self.assertRaises(ResourceError),
            ):
                regenerated_directory(row, row, state)

    def test_forged_bytecode_payload_is_preserved(self):
        import py_compile

        from research_workbench_entrypoint.docker_resources import write_receipt

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            state = root / "state"
            state.mkdir(mode=0o700)
            source = root / "example.py"
            source.write_text("value=1\n")
            filename = Path(py_compile.compile(str(source), doraise=True))
            filename.write_bytes(filename.read_bytes()[:16] + b"not a derived bytecode payload")
            cache = root / "__pycache__"
            row = register_directory(root, cache, "dependency")
            write_receipt(
                state / "dependencies.json",
                {"ok": True, "items": [{"path": str(cache), "status": "reclaimed"}]},
            )
            with (
                patch(
                    "research_workbench_entrypoint.iteration_resources.occupied", return_value=False
                ),
                patch(
                    "research_workbench_entrypoint.iteration_resources.git",
                    side_effect=lambda _, *args: "example.py" if args[0] == "ls-files" else "",
                ),
                self.assertRaisesRegex(ResourceError, "bytecode_unknown"),
            ):
                regenerated_directory(row, row, state)
            self.assertTrue(filename.exists())

    def test_new_unknown_file_cannot_enter_verified_regeneration_manifest(self):
        import py_compile

        from research_workbench_entrypoint.docker_resources import write_receipt
        from research_workbench_entrypoint.iteration_resources import file_manifest

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            state = root / "state"
            state.mkdir(mode=0o700)
            source = root / "example.py"
            source.write_text("value=1\n")
            py_compile.compile(str(source), doraise=True)
            cache = root / "__pycache__"
            row = register_directory(root, cache, "dependency")
            write_receipt(
                state / "dependencies.json",
                {"ok": True, "items": [{"path": str(cache), "status": "reclaimed"}]},
            )

            def raced_manifest(path):
                if Path(path) == cache:
                    (cache / "business.txt").write_text("must keep")
                return file_manifest(path)

            with (
                patch(
                    "research_workbench_entrypoint.iteration_resources.occupied", return_value=False
                ),
                patch(
                    "research_workbench_entrypoint.iteration_resources.git",
                    side_effect=lambda _, *args: "example.py" if args[0] == "ls-files" else "",
                ),
                patch(
                    "research_workbench_entrypoint.iteration_resources.file_manifest",
                    side_effect=raced_manifest,
                ),
                self.assertRaisesRegex(ResourceError, "contents_changed"),
            ):
                regenerated_directory(row, row, state)
            self.assertTrue((cache / "business.txt").exists())

    def test_real_compiled_other_source_and_trailing_payload_are_preserved(self):
        import py_compile

        from research_workbench_entrypoint.docker_resources import write_receipt

        for alteration in ("other-source", "trailing"):
            with self.subTest(alteration=alteration), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                state = root / "state"
                state.mkdir(mode=0o700)
                source = root / "example.py"
                source.write_text("value=1\n")
                filename = Path(py_compile.compile(str(source), doraise=True))
                original = filename.read_bytes()
                if alteration == "other-source":
                    other = root / "other.py"
                    other.write_text("value=2\n")
                    other_cache = Path(
                        py_compile.compile(str(other), dfile=str(source), doraise=True)
                    )
                    filename.write_bytes(original[:16] + other_cache.read_bytes()[16:])
                    other_cache.unlink()
                else:
                    filename.write_bytes(original + b"business data must not be deleted")
                row = register_directory(root, filename.parent, "dependency")
                write_receipt(
                    state / "dependencies.json",
                    {"ok": True, "items": [{"path": str(filename.parent), "status": "reclaimed"}]},
                )
                with (
                    patch(
                        "research_workbench_entrypoint.iteration_resources.occupied",
                        return_value=False,
                    ),
                    patch(
                        "research_workbench_entrypoint.iteration_resources.git",
                        side_effect=lambda _, *args: "example.py" if args[0] == "ls-files" else "",
                    ),
                    self.assertRaisesRegex(ResourceError, "bytecode_unknown"),
                ):
                    regenerated_directory(row, row, state)
                self.assertTrue(filename.exists())
