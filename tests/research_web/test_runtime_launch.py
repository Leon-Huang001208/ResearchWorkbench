from pathlib import Path
from types import SimpleNamespace

import pytest

from app.research_web import launch_runtime


def make_source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    (source / "packages/boot/app-boot/lib").mkdir(parents=True)
    (source / "packages/boot/app-boot/lib/index.js").write_text("// built")
    (source / "apps/cli").mkdir(parents=True)
    (source / "apps/cli/package.json").write_text("{}")
    return source


def test_runtime_module_fallback_is_healed_inside_private_source(tmp_path, monkeypatch):
    source = make_source(tmp_path)
    home = tmp_path / "home"
    target = source / "packages/example"
    target.mkdir(parents=True)

    def run(*args, **kwargs):
        modules = home / "profiles/node_modules/@deepseek-ai"
        modules.mkdir(parents=True)
        (modules / "dsh-example").symlink_to(target)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(launch_runtime.subprocess, "run", run)
    assert launch_runtime.prepare_runtime_module_fallback(source, home, "/node") == 1


def test_runtime_module_fallback_rejects_external_target(tmp_path, monkeypatch):
    source = make_source(tmp_path)
    home = tmp_path / "home"
    external = tmp_path / "external"
    external.mkdir()

    def run(*args, **kwargs):
        modules = home / "profiles/node_modules"
        modules.mkdir(parents=True)
        (modules / "external").symlink_to(external)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(launch_runtime.subprocess, "run", run)
    with pytest.raises(RuntimeError, match="越出项目私有源码目录"):
        launch_runtime.prepare_runtime_module_fallback(source, home, "/node")
