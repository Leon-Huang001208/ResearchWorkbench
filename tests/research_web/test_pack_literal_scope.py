"""Exact sealed-input grants and protected artifact output roots."""

import hashlib
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from app.research_web.sandbox import SandboxConfig, SandboxError, run_script

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS Native sandbox")


def session(tmp_path):
    root = tmp_path / "research"
    sid = root / "sessions" / str(uuid4())
    for name in ("inputs", "resources", "outputs", "tmp"):
        (sid / name).mkdir(parents=True)
    return SandboxConfig(root, Path(sys.executable)), sid


def test_generic_code_cannot_prewrite_managed_pack_outputs(tmp_path):
    config, sid = session(tmp_path)
    target = sid / "outputs" / "scenario-results"
    target.mkdir()
    result = run_script(config, sid, "open('outputs/scenario-results/forged.json','w').write('{}')")
    assert result.status == "failed"
    assert "PermissionError" in result.stderr
    assert not (target / "forged.json").exists()


def test_scenario_policy_checks_exact_file_hash_and_rejects_hardlinks(tmp_path):
    config, sid = session(tmp_path)
    path = sid / "inputs" / "scenarios" / ("a" * 32) / "input.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}")
    relative = path.relative_to(sid).as_posix()
    info = path.stat()
    bindings = [
        {
            "path": relative,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": info.st_size,
            "device": info.st_dev,
            "inode": info.st_ino,
        }
    ]
    output = "outputs/scenario-results/" + "b" * 32
    (sid / output).mkdir(parents=True)
    result = run_script(
        config,
        sid,
        f"print(open({relative!r}).read())",
        read_paths=[relative],
        input_policy="scenario-frozen-inputs-v1",
        file_bindings=bindings,
        output_root=output,
    )
    assert result.status == "completed", result.stderr
    assert result.stdout.strip() == "{}"
    generic = run_script(config, sid, f"print(open({relative!r}).read())")
    assert generic.status == "failed" and "PermissionError" in generic.stderr
    sibling = path.parent / "unlisted.json"
    sibling.write_text("private")
    denied = run_script(
        config,
        sid,
        f"print(open({sibling.relative_to(sid).as_posix()!r}).read())",
        read_paths=[relative],
        input_policy="scenario-frozen-inputs-v1",
        file_bindings=bindings,
        output_root=output,
    )
    assert denied.status == "failed" and "PermissionError" in denied.stderr
    path.write_text("[]")
    with pytest.raises(SandboxError):
        run_script(
            config,
            sid,
            "print(1)",
            read_paths=[relative],
            input_policy="scenario-frozen-inputs-v1",
            file_bindings=bindings,
            output_root=output,
        )
