import json
import os
import plistlib
import subprocess
from pathlib import Path

import pytest

from research_workbench_entrypoint.resident import gateway_source as source
from research_workbench_entrypoint.resident.evidence import UpdateBlocked


def git(cwd, *args):
    return subprocess.check_output(["/usr/bin/git", "-C", str(cwd), *args], text=True).strip()


def record(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(0o600)


@pytest.fixture
def installation(tmp_path, monkeypatch):
    user = tmp_path.resolve()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: user))
    monkeypatch.setenv("HOME", str(user))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(user / ".config"))
    home = user / ".research-workbench"
    repository = user / "Developer/project"
    releases = user / ".local/share/research-workbench/server-releases"
    for path in (
        home,
        home / "resident",
        home / "install",
        home / "server",
        home / "server/run",
        repository,
        releases,
        user / "Library/LaunchAgents",
    ):
        path.mkdir(mode=0o700, parents=True)
    git(repository, "init", "--quiet")
    (repository / "example.py").write_text("print('tracked')\n", encoding="utf-8")
    git(repository, "add", "example.py")
    git(
        repository,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.test",
        "commit",
        "--quiet",
        "-m",
        "fixture",
    )
    revision = git(repository, "rev-parse", "HEAD")
    common = repository / ".git"
    primary = user / ".local/share/research-workbench/releases/test-primary"
    primary.mkdir(mode=0o700, parents=True)
    data_root = home / "research-web"
    data_root.mkdir(mode=0o700)
    record(
        home / "resident/config.json",
        {
            "project": str(primary),
            "source_common": str(common),
            "web_port": 8088,
            "runtime_port": 3081,
            "node": "/opt/homebrew/bin/node",
            "private_origin": "https://example.tail.invalid",
        },
    )
    record(home / "install/manifest.json", {"status": "installed", "code_commit": revision})
    old, release = releases / "old", releases / revision
    old.mkdir(mode=0o700)
    # This placeholder only contains the former worktree link. Its target does
    # not exist, so consulting the old repository to infer HEAD cannot work.
    old_gitdir = user / "Desktop/Projects/project/.git/worktrees/old"
    (old / ".git").write_text(f"gitdir: {old_gitdir}\n", encoding="utf-8")
    config = home / "server/resident.json"
    record(
        config,
        {
            "version": 1,
            "project": str(old),
            "revision": revision,
            "port": 8089,
            "source": str(home / "dsh-source"),
            "node": "/opt/homebrew/bin/node",
            "origin": "https://example.tail.invalid",
            "mcp_readonly_enabled": False,
            "binding": {
                "project": str(primary),
                "home": str(home),
                "revision": revision,
                "web_port": 8088,
                "runtime_port": 3081,
                "primary_user_id": "62b89b0f-1e71-4c40-8e5a-53d2fec7e79c",
                "project_identity": [primary.stat().st_dev, primary.stat().st_ino],
                "data_identity": [data_root.stat().st_dev, data_root.stat().st_ino],
            },
        },
    )
    label = "com.research-workbench.multiuser-server"
    plist = user / "Library/LaunchAgents" / f"{label}.plist"
    plist.write_bytes(
        plistlib.dumps(
            {
                "Label": label,
                "WorkingDirectory": str(old),
                "KeepAlive": True,
                "RunAtLoad": True,
                "ProgramArguments": [
                    str(primary / ".venv/bin/python"),
                    "-m",
                    "app.research_web.multiuser.resident",
                    "--root",
                    str(home / "server"),
                ],
            }
        )
    )
    plist.chmod(0o600)
    monkeypatch.setattr(source, "_require_paused_jobs", lambda: None)
    monkeypatch.setattr(source.gateway_upgrade, "job_state", lambda: None)
    monkeypatch.setattr(source.gateway_upgrade, "listener_pids", set)
    monkeypatch.setattr(source.gateway_upgrade, "no_private_processes", lambda _: None)
    return home, common, revision, old, release, config, plist


def test_prepare_uses_verified_local_common_and_leaves_live_records_alone(installation):
    home, common, commit, old, release, config, plist = installation
    before = config.read_bytes(), plist.read_bytes(), (old / ".git").read_bytes()
    source.prepare(home, release, commit)
    source.verify_local_checkout(release, common, commit)
    assert git(release, "rev-parse", "--path-format=absolute", "--git-common-dir") == str(common)
    assert (release / "example.py").is_file()
    assert before == (config.read_bytes(), plist.read_bytes(), (old / ".git").read_bytes())
    source.prepare(home, release, commit)
    (release / "untracked").touch()
    with pytest.raises(UpdateBlocked, match="gateway_source_checkout_dirty"):
        source.verify_local_checkout(release, common, commit)


def test_checkout_guard_rejects_cloud_alias_and_redirected_objects(installation):
    home, common, commit, _, release, _, _ = installation
    cloud = home.parent / "Desktop/cloud-release"
    cloud.parent.mkdir()
    with pytest.raises(UpdateBlocked, match="gateway_source_cloud_path"):
        source.prepare(home, cloud, commit)
    source.prepare(home, release, commit)
    alias = release.parent / "alias"
    alias.symlink_to(release, target_is_directory=True)
    with pytest.raises(UpdateBlocked, match="gateway_source_path_unsafe"):
        source.verify_local_checkout(alias, common, commit)
    (common / "objects/info/alternates").touch()
    with pytest.raises(UpdateBlocked, match="gateway_source_external_objects"):
        source.verify_local_checkout(release, common, commit)


def test_checkout_guard_handles_a_local_standalone_clone(installation, monkeypatch):
    _, common, commit, _, _, _, _ = installation
    monkeypatch.setenv("GIT_DIR", str(common.parent / "foreign"))
    monkeypatch.setenv("GIT_ALTERNATE_OBJECT_DIRECTORIES", "/wrong/objects")
    source.verify_local_checkout(common.parent, None, commit)
    with pytest.raises(UpdateBlocked, match="gateway_source_revision_mismatch"):
        source.verify_local_checkout(common.parent, None, "a" * 40)


@pytest.mark.parametrize(
    "key,value,code",
    [
        ("include.path", "/unavailable/cloud/gitconfig", "gateway_source_git_config_include"),
        ("remote.fixture.promisor", "true", "gateway_source_external_objects"),
        ("core.hooksPath", "~/Desktop/unavailable", "gateway_source_cloud_path"),
    ],
)
def test_prepare_blocks_redirected_git_configuration(installation, key, value, code):
    home, common, commit, _, release, _, _ = installation
    git(common.parent, "config", key, value)
    with pytest.raises(UpdateBlocked, match=code):
        source.prepare(home, release, commit)
    assert not release.exists()


def test_checkout_guard_rejects_symlinked_loose_head_ref(installation):
    _, common, commit, _, _, _, _ = installation
    reference = common / git(common.parent, "symbolic-ref", "HEAD")
    original = reference.with_suffix(".old")
    reference.rename(original)
    reference.symlink_to(original)
    with pytest.raises(UpdateBlocked, match="gateway_source_record_unsafe"):
        source.verify_local_checkout(common.parent, None, commit)


@pytest.mark.parametrize("loaded,listening", [(True, False), (False, True)])
def test_loaded_or_listening_gateway_is_not_offline(installation, monkeypatch, loaded, listening):
    home, _, _, _, _, _, _ = installation
    monkeypatch.setattr(source.gateway_upgrade, "job_state", lambda: "loaded" if loaded else None)
    monkeypatch.setattr(
        source.gateway_upgrade, "listener_pids", lambda: {8089} if listening else set()
    )
    with pytest.raises(UpdateBlocked, match="gateway_source_gateway_must_be_unloaded"):
        source._require_offline(home)


def test_rehome_preserves_binding_and_legacy_checkout(installation):
    home, _, commit, old, release, config, plist = installation
    source.prepare(home, release, commit)
    original = json.loads(config.read_bytes())
    launch = plistlib.loads(plist.read_bytes())
    legacy_git = (old / ".git").read_bytes()
    plan = source.plan_rehome(home, release, commit)
    assert config.read_bytes() == json.dumps(original).encode()
    assert plistlib.loads(plist.read_bytes()) == launch
    result = source.rehome(home, release, commit, expected_seal=plan["seal"])
    assert result["status"] == "rehomed"
    assert json.loads(config.read_bytes()) == {**original, "project": str(release)}
    assert plistlib.loads(plist.read_bytes()) == {**launch, "WorkingDirectory": str(release)}
    assert (old / ".git").read_bytes() == legacy_git
    assert Path(result["receipt"]).is_file()


def test_rehome_rejects_plan_drift_and_pending_deployment(installation):
    home, _, commit, _, release, config, plist = installation
    source.prepare(home, release, commit)
    before = plist.read_bytes()
    plan = source.plan_rehome(home, release, commit)
    record(config, {**json.loads(config.read_bytes()), "mcp_readonly_enabled": True})
    with pytest.raises(UpdateBlocked, match="gateway_source_plan_changed"):
        source.rehome(home, release, commit, expected_seal=plan["seal"])
    assert plist.read_bytes() == before
    for filename in ("gateway-upgrade.json", "birth-fence.json"):
        journal = home / "server/run" / filename
        journal.touch()
        with pytest.raises(UpdateBlocked, match="gateway_source_maintenance_pending"):
            source.plan_rehome(home, release, commit)
        journal.unlink()


@pytest.mark.parametrize("native_loaded", [False, True])
def test_durable_pause_requires_both_labels_and_native_unloaded(monkeypatch, native_loaded):
    disabled = [
        '"com.research-workbench.multiuser-server" => disabled',
        '"com.research-workbench.resident" => true',
    ]
    monkeypatch.setattr(source, "run", lambda *args, **kwargs: "\n".join(disabled))
    monkeypatch.setattr(
        source.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            [],
            0 if native_loaded else 113,
            "",
            f'Bad request.\nCould not find service "{source.NATIVE_LABEL}" '
            f"in domain for user gui: {os.getuid()}\n",
        ),
    )
    if native_loaded:
        with pytest.raises(UpdateBlocked, match="gateway_source_native_job_must_be_unloaded"):
            source._require_paused_jobs()
    else:
        source._require_paused_jobs()
    disabled.pop()
    with pytest.raises(UpdateBlocked, match="gateway_source_launchagents_must_be_disabled"):
        source._require_paused_jobs()


def test_partial_rehome_rolls_back_matching_records(installation, monkeypatch):
    home, _, commit, _, release, config, plist = installation
    source.prepare(home, release, commit)
    before = config.read_bytes(), plist.read_bytes()
    plan = source.plan_rehome(home, release, commit)
    replace = source._replace

    def fail_plist(path, value):
        if path == plist:
            raise OSError("interrupt after gateway configuration")
        return replace(path, value)

    with monkeypatch.context() as fault:
        fault.setattr(source, "_replace", fail_plist)
        with pytest.raises(UpdateBlocked, match="gateway_source_recovery_required"):
            source.rehome(home, release, commit, expected_seal=plan["seal"])
    assert json.loads(config.read_bytes())["project"] == str(release)
    assert plist.read_bytes() == before[1]
    # Restoring the backed-up metadata must still work when the staged source
    # becomes unusable. It does not need to boot the old cloud-linked copy.
    (release / "unexpected").touch()
    result = source.recover_rehome(home)
    assert result["status"] == "rolled_back"
    assert (config.read_bytes(), plist.read_bytes()) == before
    assert Path(result["receipt"]).is_file()
    assert source.recover_rehome(home)["status"] == "not_required"
