"""Installed-wheel lock projection and byte-level runtime binding."""

import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from app.research_web.capabilities.models import CapabilityError


def test_packaged_lock_projection_matches_the_actual_web_lock():
    from app.research_web.capabilities.pack_dependencies import LOCK_PROJECTION, runtime_identity

    projection = json.loads(LOCK_PROJECTION.read_bytes())
    lock = Path(__file__).parents[2] / "requirements/web.lock"
    assert projection["lock_sha256"] == hashlib.sha256(lock.read_bytes()).hexdigest()
    runtime = runtime_identity()
    assert runtime["lock_sha256"] == projection["lock_sha256"]
    assert {item["name"]: item["version"] for item in runtime["dependencies"]} == projection[
        "versions"
    ]
    assert all(
        item["file_count"] > 0 and len(item["closure_sha256"]) == 64
        for item in runtime["dependencies"]
    )


def test_changed_packaged_lock_identity_is_rejected(tmp_path, monkeypatch):
    from app.research_web.capabilities import pack_dependencies

    projection = tmp_path / "bad-lock.json"
    projection.write_text('{"schema":"invalid"}')
    monkeypatch.setattr(pack_dependencies, "LOCK_PROJECTION", projection)
    with pytest.raises(CapabilityError) as error:
        pack_dependencies.runtime_identity()
    assert error.value.code == "pack_runtime_unverified"


@pytest.mark.skipif(
    not os.environ.get("RWB_TEST_WHEEL"), reason="An actual locally built wheel is required"
)
def test_actual_wheel_contains_lock_and_builds_packs_without_a_checkout(tmp_path):
    wheel = Path(os.environ["RWB_TEST_WHEEL"])
    installed = tmp_path / "site-packages"
    installed.mkdir()
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        assert "app/research_web/capabilities/pack-runtime-lock.json" in names
        assert "app/research_web/scenarios/packs/record_contracts.py" in names
        for name in names:
            parts = Path(name).parts
            if parts[0] not in {"app", "core", "runtimes"} or name.endswith("/"):
                continue
            assert not Path(name).is_absolute() and ".." not in parts
            target = installed / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
    code = f"import sys,json\nassert 'app' not in sys.modules\nsys.path.insert(0,{str(installed)!r})\nfrom app.research_web.capabilities.pack_dependencies import runtime_identity,LOCK_PROJECTION\nfrom app.research_web.capabilities.pack_resources import pack_packages\nfrom pathlib import Path\nassert not Path({str(installed / 'requirements/web.lock')!r}).exists()\nvalue=runtime_identity()\nassert LOCK_PROJECTION.is_file() and str(LOCK_PROJECTION).startswith({str(installed)!r})\nassert len(dict(pack_packages()))==9\nprint(json.dumps({{'lock_sha256':value['lock_sha256'],'dependencies':len(value['dependencies']),'packs':9}}))\n"
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", code],
        cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8"},
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["packs"] == 9
