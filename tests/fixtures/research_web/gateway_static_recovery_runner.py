"""Fault fixture: execute frozen recovery code against an isolated local Git repo."""

import json
import logging
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)


def main():
    os.umask(0o077)
    artifact, source, home = map(Path, sys.argv[1:4])
    previous, payload, tool, phase = sys.argv[4:8]
    if subprocess.check_output(["/usr/bin/git", "-C", str(source), "remote"], text=True).strip():
        raise RuntimeError("fixture_repository_has_remote")
    home.mkdir(mode=0o700)
    for folder in [
        "server/run",
        "server/users",
        "resident",
        "research-web/sessions/fixture",
        "logs",
        "Library/LaunchAgents",
    ]:
        (home / folder).mkdir(parents=True, mode=0o700)
    logging.basicConfig(filename=home / "logs/recovery-fixture.log", level=logging.INFO)
    gateway = home / "gateway"
    checkout = payload if phase in {"starting", "rolling_back"} else previous
    subprocess.run(
        ["/usr/bin/git", "-C", str(source), "worktree", "add", "--detach", str(gateway), checkout],
        check=True,
        capture_output=True,
    )
    sys.path.insert(0, str(artifact))
    from resident import gateway_upgrade as g

    assert str(artifact) in g.__file__
    assert g.PRODUCT != payload
    primary = "11111111-1111-4111-8111-111111111111"
    database = home / "server/accounts.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE accounts(id TEXT PRIMARY KEY)")
        connection.execute("INSERT INTO accounts VALUES (?)", (primary,))
    database.chmod(0o600)
    index = home / "research-web/index.json"
    index.write_text(
        json.dumps({"sessions": {"fixture": {"status": "completed"}}, "model": "fixture-model"})
    )
    attachment = home / "research-web/sessions/fixture/keep.txt"
    attachment.write_bytes(b"preserved fixture attachment")
    original = {
        "revision": previous,
        "project": str(gateway),
        "binding": {"primary_user_id": primary},
    }
    updated = {**original, "revision": payload}
    current = updated if phase in {"starting", "rolling_back"} else original
    g.atomic(home / "server/resident.json", current)
    plist = home / "Library/LaunchAgents" / (g.LABEL + ".plist")
    plist.write_bytes(b"fixture job identity")
    raw = artifact.read_bytes()
    checksum = g.hashlib.sha256(raw).hexdigest()
    owned_artifact = home / "server/run" / artifact.name
    owned_artifact.write_bytes(raw)
    common = subprocess.check_output(
        [
            "/usr/bin/git",
            "-C",
            str(source),
            "rev-parse",
            "--path-format=absolute",
            "--git-common-dir",
        ],
        text=True,
    ).strip()
    before = g.preservation(home)
    state = {
        "version": 2,
        "mode": "static-ui",
        "phase": phase,
        "primary": payload,
        "target": payload,
        "previous": previous,
        "tool_revision": tool,
        "project": str(gateway),
        "project_identity": [gateway.stat().st_dev, gateway.stat().st_ino],
        "old_pid": 111,
        "old_signature": "fixture retired",
        "command": "fixture command",
        "transaction": "22222222-2222-4222-8222-222222222222",
        "original_config": original,
        "fallback": original,
        "updated": updated,
        "before": before,
        "plist_sha256": g.digest(plist),
        "recovery": {"artifact_sha256": checksum, "tool_revision": tool},
        "reviewed": g.static_scopes(gateway, previous, payload, tool),
    }
    g.write_upgrade_journal(home / "server/run/gateway-upgrade.json", state)
    events = []
    # Native service/identity probes are the fault boundary. Contract, Git objects,
    # artifact verification, file locks, fences, journals and preservation stay real.
    g.configured = lambda _: (home / "resident", {"project": str(source), "source_common": common})
    Path.home = classmethod(lambda cls: home)

    def primary_idle(_home, revision):
        assert revision == payload
        events.append("primary_idle")

    def no_signal(*_a, **_k):
        raise AssertionError("retired fixture process was signalled")

    def health(config, **_):
        assert config["revision"] == previous
        events.append("fallback_health")

    g.verify_primary = primary_idle
    g.process = lambda _: None
    g.job_pid = lambda: None
    g.job_state = lambda: None
    g.no_private_processes = lambda _: None
    g.os.kill = no_signal
    g.bootstrap = lambda _: events.append("fallback_start")
    g.wait_health = health
    sys.argv = [str(owned_artifact)]
    assert g.main(["recover", "--home", str(home)]) == 0
    result = json.loads((home / "server/run/gateway-upgrade-result.json").read_text())
    assert result["status"] == ("aborted_before_signal" if phase == "preparing" else "rolled_back")
    assert g.preserved(home, before) is None
    assert attachment.read_bytes() == b"preserved fixture attachment"
    assert (
        subprocess.check_output(
            ["/usr/bin/git", "-C", str(gateway), "rev-parse", "HEAD"], text=True
        ).strip()
        == previous
    )
    assert json.loads((home / "server/resident.json").read_text()) == original
    assert not (home / "server/run/gateway-upgrade.json").exists()
    assert "primary_idle" in events
    (home / "logs/events.json").write_text(json.dumps(events))
    print("frozen_recovery_phase_passed")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log.exception("frozen_recovery_fixture_failed")
        raise
