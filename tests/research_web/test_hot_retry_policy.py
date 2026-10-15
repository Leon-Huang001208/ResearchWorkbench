"""Hot billing activates zero retries without optional Node/credential probes."""
import json
from pathlib import Path

from app.research_web.launch_runtime import hot_zero_retry


def settings(home, project, enabled=True, model=True):
    home.joinpath("hot").mkdir(exist_ok=True)
    file = home / "hot/settings.json"
    file.write_text(json.dumps({"schemaVersion": 1, "projectRoot": str(project.resolve()), "config": {"enabled": enabled, "model": {"enabled": model, "scopeId": "existing_authorization"}}}))
    file.chmod(0o600)
    return file


def test_absent_disabled_and_enabled_hot_model_policy(tmp_path):
    assert not hot_zero_retry(tmp_path, tmp_path)
    settings(tmp_path, tmp_path, model=False)
    assert not hot_zero_retry(tmp_path, tmp_path)
    settings(tmp_path, tmp_path, enabled=False)
    assert not hot_zero_retry(tmp_path, tmp_path)
    settings(tmp_path, tmp_path)
    assert hot_zero_retry(tmp_path, tmp_path)


def test_unsafe_foreign_or_malformed_hot_policy_does_not_break_base_runtime(tmp_path):
    file = settings(tmp_path, Path("/foreign-worktree"))
    assert not hot_zero_retry(tmp_path, tmp_path)
    settings(tmp_path, tmp_path)
    file.chmod(0o644)
    assert not hot_zero_retry(tmp_path, tmp_path)
    settings(tmp_path, tmp_path, model="true")
    assert not hot_zero_retry(tmp_path, tmp_path)
    file.write_text("not json")
    assert not hot_zero_retry(tmp_path, tmp_path)
