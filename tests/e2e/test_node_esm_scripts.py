"""Regression checks for Node scripts executed beneath the ESM package scope."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ESM_NODE_SCRIPTS = (
    PROJECT_ROOT / "scripts/desktop/run_backend.js",
    PROJECT_ROOT / "scripts/desktop/run_preview.js",
    PROJECT_ROOT / "tests/e2e/asset_search_playwright_core.js",
    PROJECT_ROOT / "tests/e2e/verify-placeholder-test.js",
)
REQUIRE_CALL_PATTERN = re.compile(r"\brequire\s*\(")


@pytest.mark.parametrize("script_path", ESM_NODE_SCRIPTS)
def test_executable_node_scripts_are_esm_compatible(script_path: Path, tmp_path: Path) -> None:
    """Ensure package-scoped Node scripts parse as ESM and do not use require."""
    node_path = shutil.which("node")
    if node_path is None:
        pytest.skip("Node.js is required to validate executable JavaScript scripts")

    source = script_path.read_text(encoding="utf-8")
    assert REQUIRE_CALL_PATTERN.search(source) is None

    package_root = tmp_path / "esm-package"
    copied_script = package_root / script_path.relative_to(PROJECT_ROOT)
    copied_script.parent.mkdir(parents=True)
    copied_script.write_text(source, encoding="utf-8")
    (package_root / "package.json").write_text('{"type":"module"}\n', encoding="utf-8")

    result = subprocess.run(
        [node_path, "--check", str(copied_script)],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
