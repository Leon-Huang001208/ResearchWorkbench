"""Import only the source inputs actually selected for the container image."""

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]


def test_final_image_python_source_closure_imports_without_checkout_fallback(tmp_path):
    stage = tmp_path / "image"
    stage.mkdir()
    builder = (PROJECT / "Dockerfile").read_text().split("FROM python-builder AS dsh-builder")[0]
    for line in builder.splitlines():
        if not line.startswith("COPY "):
            continue
        parts = shlex.split(line)[1:]
        for name in parts[:-1]:
            if not name.startswith(("app/", "core/", "data_layer/", "runtimes/", "research_workbench_entrypoint")):
                continue
            source = PROJECT / name
            target = stage / (parts[-1] if len(parts) == 2 else str(Path(parts[-1]) / source.name))
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))
            else:
                shutil.copy2(source, target)
    code = """
import importlib.abc, importlib.machinery, pathlib, sys
root = pathlib.Path(sys.argv[1])
class ImageOnly(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'app', 'core', 'data_layer', 'runtimes', 'research_workbench_entrypoint'}:
            spec = importlib.machinery.PathFinder.find_spec(fullname, path or [str(root)])
            if spec is None or (spec.origin and not pathlib.Path(spec.origin).is_relative_to(root)):
                raise ModuleNotFoundError('image_module_missing: ' + fullname)
            return spec
sys.meta_path.insert(0, ImageOnly())
import app.research_web.main
import app.research_web.launch_runtime
import app.cli.main
from data_layer.adapters.ifind.http_client import IFinDHTTPClient
print('image_import_smoke_passed')
"""
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "RESEARCH_RUN_MODE": "web-prod",
        "LOG_DIR": str(tmp_path / "logs"),
        "OBJECT_STORAGE_PATH": str(tmp_path / "objects"),
        "PDF_MARKDOWN_DIR": str(tmp_path / "markdown"),
        "PDF_RAW_TEXT_DIR": str(tmp_path / "raw"),
    }
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", code, str(stage)],
        cwd=stage, env=environment, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "image_import_smoke_passed" in result.stdout
