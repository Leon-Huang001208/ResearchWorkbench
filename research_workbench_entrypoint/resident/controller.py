"""Pinned stdlib supervisor; application imports run only in the owned Native venv.

Journal-before-stop, same-root lifecycle lease, fixed dependency envelope. Source
and wheel rollback deliberately never restore research data or credential stores.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import plistlib
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import zipfile
from contextlib import contextmanager
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .admission import MaintenanceBusy, file_lock, private_root
from .evidence import SHA, GitHubEvidence, UpdateBlocked, compatible, read_json, run

log = logging.getLogger(__name__)
LABEL = "com.research-workbench.resident"


def atomic(path: Path, value: dict) -> None:
    private_root(path.parent)
    descriptor, name = tempfile.mkstemp(dir=path.parent, prefix=".resident-")
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        sync_directory(path.parent)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def remove_journal(root: Path) -> None:
    (root / "transaction.json").unlink()
    sync_directory(root)


def digest(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise UpdateBlocked("resident_artifact_invalid")
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def git(root: Path, *args: str) -> str:
    return run(["/usr/bin/git", "-c", "gc.auto=0", "-c", "maintenance.auto=false", *args], cwd=root)


def clean(root: Path, expected: str) -> None:
    if git(root, "rev-parse", "HEAD") != expected or git(root, "status", "--porcelain"):
        raise UpdateBlocked("resident_checkout_changed")


def gateway_relocation_pending(server: Path) -> bool:
    journal = server / "run/gateway-source-rehome.json"
    return journal.exists() or journal.is_symlink()


def configured(home: Path) -> tuple[Path, dict]:
    root = home / "resident"
    private_root(root)
    if gateway_relocation_pending(home / "server"):
        raise UpdateBlocked("gateway_source_recovery_required")
    config = read_json(root / "config.json")
    for field in ("project", "node", "python", "artifact"):
        path = Path(config[field])
        if not path.is_absolute() or path.resolve() != path or not path.exists():
            raise UpdateBlocked("resident_configuration_changed")
    identity = Path(config["project"]).stat()
    if [identity.st_dev, identity.st_ino] != config["project_identity"]:
        raise UpdateBlocked("resident_checkout_identity_changed")
    if digest(Path(config["artifact"])) != config["artifact_sha256"]:
        raise UpdateBlocked("resident_controller_changed")
    return root, config


def record(root: Path, status: str, **fields) -> dict:
    value = {"status": status, "checked_at": datetime.now(UTC).isoformat(), **fields}
    atomic(root / "state.json", value)
    log.info("resident_%s", status)
    return value


def environment(home: Path, config: dict) -> None:
    os.environ["RESEARCH_RESIDENT_HOME"] = str(home / "resident")
    os.environ["RESEARCH_NODE_BINARY"] = config["node"]
    os.environ["RESEARCH_WEB_PRIVATE_ORIGIN"] = config["private_origin"]
    os.environ["RESEARCH_DATA_HOME"] = str(home / "research-web")
    os.environ["RESEARCH_RUN_MODE"] = "web-prod"
    bypass = "127.0.0.1,localhost,::1," + config["private_origin"].split("//")[-1]
    os.environ["NO_PROXY"] = bypass
    os.environ["no_proxy"] = bypass


def bridge(home: Path, config: dict, operation: str) -> dict:
    output = run(
        [
            str(Path(config["project"]) / ".venv/bin/python"),
            config["artifact"],
            "bridge",
            "--home",
            str(home),
            "--operation",
            operation,
        ],
        timeout=600,
    )
    try:
        return json.loads(output.splitlines()[-1])
    except (ValueError, IndexError) as exc:
        raise UpdateBlocked("resident_bridge_invalid") from exc


def build_wheel(project: Path, source: Path, output: Path) -> dict:
    private_root(output)
    sha = git(source, "rev-parse", "HEAD")
    clean(source, sha)
    wheels = list(output.glob("research_workbench-*.whl"))
    binding = output / "binding.json"
    if wheels:
        proof = read_json(binding)
        if len(wheels) != 1 or proof != {"source": sha, "sha256": digest(wheels[0])}:
            raise UpdateBlocked("resident_wheel_source_mismatch")
    if not wheels:
        run(
            [
                str(project / ".venv/bin/python"),
                "-m",
                "pip",
                "wheel",
                "--no-index",
                "--no-deps",
                "--no-build-isolation",
                "--wheel-dir",
                str(output),
                str(source),
            ],
            timeout=300,
        )
        wheels = list(output.glob("research_workbench-*.whl"))
    if len(wheels) != 1:
        raise UpdateBlocked("resident_wheel_ambiguous")
    wheel = wheels[0]
    with zipfile.ZipFile(wheel) as archive:
        if archive.testzip() is not None or "app/research_web/main.py" not in archive.namelist():
            raise UpdateBlocked("resident_wheel_invalid")
    clean(source, sha)
    atomic(binding, {"source": sha, "sha256": digest(wheel)})
    return {"path": str(wheel), "sha256": digest(wheel)}


def stage(
    home: Path, config: dict, target: str, proof: dict, *, compatibility_profile: str | None = None
) -> dict:
    root = home / "resident"
    project = Path(config["project"])
    previous = git(project, "rev-parse", "HEAD")
    manifest = read_json(home / "install/manifest.json")
    if manifest.get("code_commit") != previous or manifest.get("status") != "installed":
        raise UpdateBlocked("resident_installation_mismatch")
    clean(project, previous)
    # Login jobs do not inherit the interactive SSH agent. This public GitHub
    # fetch needs no SSH key and does not change the user's origin configuration.
    git(
        project,
        "fetch",
        "--no-auto-maintenance",
        f"https://github.com/{config['repository']}.git",
        "master",
    )
    if git(project, "rev-parse", "FETCH_HEAD") != target:
        raise UpdateBlocked("resident_master_moved")
    git(project, "merge-base", "--is-ancestor", previous, target)
    paths = git(project, "diff", "--name-only", previous, target).splitlines()
    review = None
    if compatibility_profile is not None:
        from . import host_metadata

        if compatibility_profile != host_metadata.PROFILE:
            raise UpdateBlocked("resident_compatibility_profile_unknown")
        review = host_metadata.review(project, config, previous, target, paths)
    elif not compatible(paths):
        raise UpdateBlocked("resident_compatibility_review_required")
    directory = root / "artifacts" / target
    private_root(directory)
    source = directory / "source"
    if not source.exists():
        git(project, "worktree", "add", "--detach", str(source), target)
    clean(source, target)
    new_wheel = build_wheel(project, source, directory / "new" / target)
    old_wheel = build_wheel(project, project, directory / "old" / previous)
    candidate = {
        "previous": previous,
        "target": target,
        "new_wheel": new_wheel,
        "old_wheel": old_wheel,
        "manifest": manifest,
        "proof": proof,
    }
    if review is not None:
        candidate["compatibility_review"] = review
    atomic(root / "candidate.json", candidate)
    return candidate


def retirement_command(
    config: dict, root: Path, revision: str
) -> tuple[list[str], Path, dict] | None:
    """Run the accepted checkout's code against the enrolled control repository."""
    project = Path(config["project"])
    common = Path(config["source_common"])
    if common.name != ".git" or not common.is_dir() or common.resolve() != common:
        raise UpdateBlocked("resident_retirement_source_unverified")
    source = common.parent
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("GIT_")
        and key not in {"NODE_OPTIONS", "NODE_PATH", "PYTHONHOME", "PYTHONPATH"}
    }
    env.update(GIT_NO_LAZY_FETCH="1", GIT_NO_REPLACE_OBJECTS="1")
    env["PATH"] = os.pathsep.join(
        (
            str(Path(config["gh"]).parent),
            "/opt/homebrew/bin",
            "/usr/local/bin",
            "/usr/bin",
            "/bin",
            "/usr/sbin",
            "/sbin",
        )
    )

    def inspect_git(checkout, *args):
        value = subprocess.run(
            ["/usr/bin/git", "--no-optional-locks", "-c", "core.fsmonitor=false", *args],
            cwd=checkout,
            env=env,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        return value.stdout.strip()

    binding_args = ("rev-parse", "--path-format=absolute", "--show-toplevel")
    if inspect_git(project, *binding_args, "HEAD").splitlines() != [str(project), revision]:
        raise UpdateBlocked("resident_retirement_source_unverified")
    if inspect_git(source, *binding_args, "--git-common-dir").splitlines() != [
        str(source),
        str(common),
    ]:
        raise UpdateBlocked("resident_retirement_source_unverified")
    for checkout in (project, source):
        url = inspect_git(checkout, "remote", "get-url", "origin")
        origin = re.fullmatch(
            r"(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)"
            r"([a-z0-9_.-]+/[a-z0-9_.-]+)/?",
            url,
            re.IGNORECASE,
        )
        if not origin or origin[1].lower().removesuffix(".git") != config["repository"].lower():
            raise UpdateBlocked("resident_retirement_origin_unverified")
    entrypoint = "scripts/git_safety.mjs"
    script = project / entrypoint
    if not script.exists() and not script.is_symlink():
        return None
    if inspect_git(project, "status", "--porcelain", "--untracked-files=all") or any(
        line[0].islower() or line.startswith("S ")
        for line in inspect_git(project, "ls-files", "-v").splitlines()
        if line
    ):
        raise UpdateBlocked("resident_retirement_script_changed")

    def checked_file(relative):
        file = project / relative
        if (
            file.resolve() != file
            or not file.is_file()
            or inspect_git(project, "hash-object", "--no-filters", "--", relative)
            != inspect_git(project, "rev-parse", f"{revision}:{relative}")
        ):
            raise UpdateBlocked("resident_retirement_script_changed")
        return file

    if b"worktree-retirement" not in checked_file(entrypoint).read_bytes():
        return None  # Older accepted releases did not provide this entrypoint.
    for relative in (
        "scripts/native_retirement_acceptance.mjs",
        "scripts/git_deployed_worktree_proof.mjs",
        "scripts/backup_fd_clone.py",
        ".agents/deployed-worktree-retirement.json",
    ):
        checked_file(relative)
    return (
        [
            config["node"],
            str(script),
            "worktree-retirement",
            "--project",
            str(source),
            "--resident-root",
            str(root),
            "--apply",
        ],
        project,
        env,
    )


def retire_accepted_worktrees(home: Path, root: Path, config: dict, state: dict) -> None:
    if state["status"] not in {"ready", "deployed"}:
        return
    revision = state.get("deployed")
    if not isinstance(revision, str) or not SHA.fullmatch(revision):
        return
    accepted = root / "accepted.json"
    if not accepted.exists() and not accepted.is_symlink():
        return
    try:
        # The retirement CLI itself holds a shared admission lease across
        # its live proof and mutation. The supervisor lock is not held here.
        with file_lock(root, "worktree-retirement.lock", exclusive=True):
            if (
                read_json(root / "state.json") != state
                or read_json(accepted).get("target") != revision
                or os.path.lexists(root / "transaction.json")
            ):
                return
            manifest = read_json(home / "install/manifest.json")
            if manifest.get("status") != "installed" or manifest.get("code_commit") != revision:
                return
            quarantine = root / "quarantine.json"
            if os.path.lexists(quarantine) and read_json(quarantine).get("sha") == revision:
                return
            invocation = retirement_command(config, root, revision)
            if invocation is None:
                return
            args, project, env = invocation
            # The worker owns its transaction locks. Do not kill it on a Python timeout.
            completed = subprocess.run(
                args,
                cwd=project,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            response = completed.stdout or completed.stderr
            if len(response) > 65_536:
                raise UpdateBlocked("resident_retirement_response_invalid")
            result = json.loads(response)
            if not isinstance(result, dict):
                raise UpdateBlocked("resident_retirement_response_invalid")
            if result.get("status") == "BLOCKED":
                reason = result.get("code")
                if isinstance(reason, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", reason):
                    raise UpdateBlocked(reason)
            items = result.get("items")
            if result.get("status") not in {"complete", "cleanup_pending"} or not isinstance(
                items, list
            ):
                raise UpdateBlocked("resident_retirement_response_invalid")
            complete = completed.returncode == 0 and result["status"] == "complete"
            details: dict = {"items": len(items)}
            if not complete:
                blockers = []
                for item in items:
                    if not isinstance(item, dict) or item.get("status") not in {
                        "blocked",
                        "pending",
                    }:
                        continue
                    code, task = item.get("code"), item.get("taskId")
                    if not isinstance(code, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", code):
                        continue
                    details.setdefault("reason", code)
                    if isinstance(task, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", task):
                        blockers.append({"taskId": task, "code": code, "status": item["status"]})
                details["blocked"] = blockers
            retirement_receipt(
                root, revision, "complete" if complete else "cleanup_pending", **details
            )
    except MaintenanceBusy:
        return  # Another observer already owns this attempt.
    except (
        OSError,
        RuntimeError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as exc:
        reason = str(exc) if isinstance(exc, UpdateBlocked) else "resident_retirement_failed"
        retirement_receipt(root, revision, "cleanup_pending", reason=reason)


def retirement_receipt(root: Path, revision: str, status: str, **fields) -> None:
    filename = root / "worktree-retirement.json"
    result = {"status": status, "revision": revision, **fields}
    try:
        if filename.is_file():
            previous = read_json(filename)
            previous.pop("checked_at", None)
            if previous == result:
                return
        atomic(
            filename,
            {
                **result,
                "checked_at": datetime.now(UTC).isoformat(),
            },
        )
    except (OSError, RuntimeError, ValueError):
        log.warning("resident_worktree_retirement_receipt_unavailable")
    log.info(
        "resident_worktree_retirement status=%s reason=%s", status, fields.get("reason", "none")
    )


def tick(home: Path) -> dict:
    root, config = configured(home)
    with file_lock(root, "supervisor.lock", exclusive=True):
        state = tick_deployment(home, root, config)
    retire_accepted_worktrees(home, root, config, state)
    return state


def tick_deployment(home: Path, root: Path, config: dict) -> dict:
    environment(home, config)
    if (root / "transaction.json").exists():
        recovery = bridge(home, config, "recover")
        if recovery["status"] != "rolled_back":
            return record(root, "blocked", reason="resident_recovery_failed")
    # Boot/recovery always precedes GitHub network access.
    current = bridge(home, config, "ensure")
    if current["status"] != "ready":
        return record(root, "blocked", reason="resident_service_unavailable")
    try:
        github = GitHubEvidence(
            Path(config["gh"]), config["repository"], Path(config["source_common"])
        )
        target = github.latest()
        if target == current["sha"]:
            return record(
                root, "ready", deployed=target, url=config["private_origin"] + "/#/fingpt"
            )
        quarantine = (
            read_json(root / "quarantine.json") if (root / "quarantine.json").exists() else {}
        )
        if quarantine.get("sha") == target:
            return record(
                root,
                "blocked",
                deployed=current["sha"],
                failed_candidate=target,
                reason="resident_failed_candidate_requires_retry",
            )
        proof = github.qualify(target)
        candidate_path = root / "candidate.json"
        candidate = read_json(candidate_path) if candidate_path.exists() else {}
        if candidate.get("target") != target or candidate.get("previous") != current["sha"]:
            stage(home, config, target, proof)
        # Recheck all remote/review evidence immediately before the stop boundary.
        if github.latest() != target:
            return record(root, "deferred", reason="resident_master_moved")
        github.qualify(target)
        result = bridge(home, config, "deploy")
        fields = {"deployed": result.get("sha", current["sha"]), "candidate": target}
        if result["status"] == "rolled_back":
            fields["failed_candidate"] = target
            atomic(root / "quarantine.json", {"sha": target})
        return record(root, result["status"], **fields)
    except UpdateBlocked as exc:
        return record(root, "waiting", deployed=current["sha"], reason=str(exc))


def wait_ports(ports: tuple[int, int]) -> None:
    for _ in range(120):
        available = True
        for port in ports:
            with socket.socket() as probe:
                try:
                    probe.bind(("127.0.0.1", port))
                except OSError:
                    available = False
        if available:
            return
        time.sleep(0.5)
    raise UpdateBlocked("resident_ports_not_released")


@contextmanager
def fixed_ports(manager, ports):
    # Endpoint selection normally reallocates busy ports. A resident deployment
    # must instead fail, retaining its exact Tailscale Serve upstream contract.
    wait_ports(ports)
    yield


def bridge_main(home: Path, operation: str) -> dict:
    root, config = configured(home)
    environment(home, config)
    project = Path(config["project"])
    sys.path.insert(0, str(project))
    from app.research_web.service_manager import WebServiceManager

    ports = config["web_port"], config["runtime_port"]
    manager = WebServiceManager(
        project_root=project,
        data_root=home / "research-web",
        python=str(project / ".venv/bin/python"),
        node=config["node"],
        web_port=ports[0],
        runtime_port=ports[1],
    )

    def host_snapshot():
        import urllib.request

        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(
            f"http://127.0.0.1:{ports[0]}/api/research/resident", timeout=10
        ) as response:
            actual = json.load(response)
        if not actual.get("enabled") or actual.get("revision") != git(project, "rev-parse", "HEAD"):
            raise UpdateBlocked("resident_process_revision_mismatch")
        return actual

    def health():
        import urllib.request

        status = manager.status()["services"]
        if not all(status[role]["running"] for role in ("web", "runtime")):
            raise UpdateBlocked("resident_health_failed")
        if status["web"]["port"] != ports[0] or status["runtime"]["port"] != ports[1]:
            raise UpdateBlocked("resident_endpoint_changed")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for url in (f"http://127.0.0.1:{ports[0]}/", config["private_origin"] + "/"):
            with opener.open(url, timeout=15) as response:
                if response.status != 200 or b"html" not in response.read(4096).lower():
                    raise UpdateBlocked("resident_http_health_failed")
        host_snapshot()

    if operation == "ensure":
        if (root / "transaction.json").exists():
            raise UpdateBlocked("resident_recovery_required")
        manifest = read_json(home / "install/manifest.json")
        clean(project, manifest["code_commit"])
        os.environ["RESEARCH_RESIDENT_REVISION"] = manifest["code_commit"]
        status = manager.status()["services"]
        if status["runtime"]["running"] and not status["runtime"]["healthy"]:
            raise UpdateBlocked("resident_activity_unverified")
        if not all(item["healthy"] for item in status.values()):
            manager.start(open_browser=False)
        health()
        return {"status": "ready", "sha": manifest["code_commit"]}
    with (
        file_lock(root, "admission.lock", exclusive=True),
        manager._installation_start_scope() as lease,
    ):
        recovering = operation == "recover"
        candidate = read_json(
            root
            / (
                "transaction.json"
                if recovering
                else "accepted.json" if operation == "rollback" else "candidate.json"
            )
        )
        for field in ("previous", "target"):
            if not SHA.fullmatch(candidate[field]):
                raise UpdateBlocked("resident_journal_invalid")
        for field in ("old_wheel", "new_wheel"):
            path = Path(candidate[field]["path"])
            if (
                not path.is_relative_to(root / "artifacts")
                or digest(path) != candidate[field]["sha256"]
            ):
                raise UpdateBlocked("resident_wheel_changed")
        if not recovering:
            clean(
                project, candidate["target"] if operation == "rollback" else candidate["previous"]
            )
            runtime = next(probe for probe in manager._service_probes() if probe.role == "runtime")
            if manager._active_research_read_only(runtime):
                return {"status": "deferred", "sha": git(project, "rev-parse", "HEAD")}
            if host_snapshot().get("active") is not False:
                return {"status": "deferred", "sha": git(project, "rev-parse", "HEAD")}
            index = read_json(home / "research-web/index.json")
            if any(
                row.get("research_status") in {"queued", "running"}
                for row in index.get("automation_runs", {}).values()
            ):
                return {"status": "deferred", "sha": git(project, "rev-parse", "HEAD")}
            atomic(root / "transaction.json", {**candidate, "phase": "switching"})

        def activate(sha: str, wheel: dict, manifest: dict):
            manager._stop_locked()
            actual = git(project, "rev-parse", "HEAD")
            if actual not in {candidate["previous"], candidate["target"]}:
                raise UpdateBlocked("resident_checkout_changed")
            clean(project, actual)
            git(project, "switch", "--detach", sha)
            run(
                [
                    str(project / ".venv/bin/python"),
                    "-m",
                    "pip",
                    "install",
                    "--no-index",
                    "--no-deps",
                    "--force-reinstall",
                    wheel["path"],
                ],
                timeout=180,
            )
            atomic(home / "install/manifest.json", {**manifest, "code_commit": sha})
            os.environ["RESEARCH_RESIDENT_REVISION"] = sha
            with fixed_ports(manager, ports):
                manager._start_installed(lease, open_browser=False)
            health()
            if git(project, "rev-parse", "HEAD") != sha:
                raise UpdateBlocked("resident_version_health_failed")

        if not recovering and operation != "rollback":
            try:
                activate(candidate["target"], candidate["new_wheel"], candidate["manifest"])
                atomic(root / "accepted.json", candidate)
                remove_journal(root)
                return {"status": "deployed", "sha": candidate["target"]}
            except Exception:
                log.exception("resident_candidate_failed_restoring_previous")
        # Also used after interruption at any point. Journal stays on disk
        # throughout recovery; new HTTP writes/research remain fenced.
        activate(candidate["previous"], candidate["old_wheel"], candidate["manifest"])
        atomic(root / "quarantine.json", {"sha": candidate["target"]})
        remove_journal(root)
        return {"status": "rolled_back", "sha": candidate["previous"]}


def install(home: Path, project: Path, source_repository: Path, origin: str) -> dict:
    if sys.platform != "darwin":
        raise UpdateBlocked("resident_macos_only")
    root = home / "resident"
    private_root(root)
    existing = (root / "config.json").exists()
    agents = Path.home() / "Library/LaunchAgents"
    agents.mkdir(parents=True, exist_ok=True)
    plist = agents / f"{LABEL}.plist"
    if not existing and (plist.exists() or plist.is_symlink()):
        raise UpdateBlocked("resident_launchagent_exists")
    if not re.fullmatch(
        r"https://[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.tail[a-z0-9]+\.ts\.net", origin
    ):
        raise UpdateBlocked("resident_origin_invalid")
    sha = git(project, "rev-parse", "HEAD")
    clean(project, sha)
    if read_json(home / "install/manifest.json").get("code_commit") != sha:
        raise UpdateBlocked("resident_installation_mismatch")
    node = home / "toolchain/node-v24.19.0-darwin-arm64/bin/node"
    gh = Path(shutil.which("gh") or "/opt/homebrew/bin/gh")
    if not os.access(node, os.X_OK) or not os.access(gh, os.X_OK):
        raise UpdateBlocked("resident_toolchain_missing")
    source_common = Path(
        git(source_repository, "rev-parse", "--path-format=absolute", "--git-common-dir")
    )
    identity = project.stat()
    artifact = root / "controller.pyz"
    if existing:
        _, config = configured(home)
        if (
            config["project"] != str(project)
            or config["source_common"] != str(source_common)
            or config["private_origin"] != origin
            or config["baseline"] != sha
        ):
            raise UpdateBlocked("resident_install_resume_mismatch")
    else:
        # Create an immutable executable artifact from this approved package. It is
        # independent of the checkout and is never self-updated by the polling loop.
        package = Path(__file__).parent
        with zipfile.ZipFile(artifact, "x", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(package.glob("*.py")):
                archive.write(path, "resident/" + path.name)
            archive.writestr(
                "__main__.py", "from resident.controller import main\nraise SystemExit(main())\n"
            )
        artifact.chmod(0o600)
        config = {
            "schema_version": 1,
            "project": str(project),
            "project_identity": [identity.st_dev, identity.st_ino],
            "source_common": str(source_common),
            "repository": "Leon-Huang001208/ResearchWorkbench",
            "gh": str(gh.resolve()),
            "node": str(node.resolve()),
            "python": str(Path(sys.executable).resolve()),
            "artifact": str(artifact),
            "artifact_sha256": digest(artifact),
            "baseline": sha,
            "private_origin": origin,
            "web_port": 8088,
            "runtime_port": 3081,
        }
        atomic(root / "config.json", config)
    logs = home / "logs"
    logs.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload = {
        "Label": LABEL,
        "ProgramArguments": [config["python"], str(artifact), "tick", "--home", str(home)],
        "RunAtLoad": True,
        "StartInterval": 60,
        "ProcessType": "Background",
        "WorkingDirectory": str(home),
        "StandardOutPath": str(logs / "resident-launchd.log"),
        "StandardErrorPath": str(logs / "resident-launchd-error.log"),
        "EnvironmentVariables": {"PATH": "/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"},
    }
    if plist.exists() or plist.is_symlink():
        if plist.is_symlink() or plistlib.loads(plist.read_bytes()) != payload:
            raise UpdateBlocked("resident_launchagent_changed")
    else:
        descriptor = os.open(plist, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            plistlib.dump(payload, stream)
            stream.flush()
            os.fsync(stream.fileno())
        sync_directory(agents)
    from .volume_launch import register

    try:
        storage = register(home, config, supervisor_locked=True)
    except UpdateBlocked as exc:
        if str(exc) != "resident_volume_not_apfs":
            raise
        log.info("resident_storage_identity_unavailable", extra={"reason": str(exc)})
        storage = {"status": "unavailable", "reason": str(exc)}
    run(["/bin/launchctl", "enable", f"gui/{os.getuid()}/{LABEL}"])
    try:
        run(["/bin/launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist)])
    except UpdateBlocked:
        # A failed/uncertain bootstrap is resumable. Only accept an already
        # registered job whose printed executable artifact matches this config.
        registered = run(["/bin/launchctl", "print", f"gui/{os.getuid()}/{LABEL}"])
        if str(artifact) not in registered or config["python"] not in registered:
            raise UpdateBlocked("resident_registration_unverified") from None
    return record(
        root, "installed", deployed=sha, url=origin + "/#/fingpt", storage_identity=storage
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rwb resident")
    parser.add_argument(
        "command",
        choices=(
            "install",
            "tick",
            "status",
            "disable",
            "rollback",
            "retry",
            "bridge",
            "upgrade-host-metadata",
            "enroll-storage-identity",
            "repair-storage-identity",
            "prepare-gateway-source",
            "plan-gateway-relocation",
            "relocate-gateway",
            "recover-gateway-relocation",
        ),
    )
    parser.add_argument("--home", type=Path, default=Path.home() / ".research-workbench")
    parser.add_argument("--project", type=Path)
    parser.add_argument("--source-repository", type=Path)
    parser.add_argument("--private-origin")
    parser.add_argument("--release", type=Path)
    parser.add_argument("--revision")
    parser.add_argument("--plan-seal")
    parser.add_argument("--expected-previous")
    parser.add_argument("--expected-target")
    parser.add_argument("--operation", choices=("ensure", "deploy", "recover", "rollback"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.command != "upgrade-host-metadata" and (
        args.expected_previous is not None or args.expected_target is not None
    ):
        parser.error("expected revision arguments require upgrade-host-metadata")
    owns_resident_state = args.command in {
        "install",
        "tick",
        "disable",
        "rollback",
        "retry",
        "bridge",
        "upgrade-host-metadata",
    }
    root = args.home / "resident"
    try:
        if args.command == "status":
            value = (
                read_json(root / "state.json")
                if (root / "state.json").exists()
                else {"status": "not_installed"}
            )
        elif args.command == "plan-gateway-relocation":
            from .gateway_source import plan_rehome

            if args.release is None or args.revision is None:
                raise UpdateBlocked("gateway_release_arguments_required")
            value = plan_rehome(args.home, args.release, args.revision)
        else:
            private_root(root)
            log_directory = args.home / "logs"
            log_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            logging.basicConfig(
                handlers=[
                    RotatingFileHandler(
                        log_directory / "resident.log", maxBytes=2_000_000, backupCount=3
                    )
                ],
                level=logging.INFO,
                format="%(asctime)s %(levelname)s %(message)s",
            )
            if args.command == "install":
                if not args.project or not args.source_repository or not args.private_origin:
                    raise UpdateBlocked("resident_install_arguments_required")
                with file_lock(root, "supervisor.lock", exclusive=True):
                    value = install(
                        args.home,
                        args.project.resolve(),
                        args.source_repository.resolve(),
                        args.private_origin,
                    )
            elif args.command == "upgrade-host-metadata":
                from .host_metadata import upgrade

                value = upgrade(args.home, args.expected_previous, args.expected_target)
            elif args.command == "enroll-storage-identity":
                from .volume_launch import register

                _, config = configured(args.home)
                value = register(args.home, config)
            elif args.command == "repair-storage-identity":
                from .volume_identity import rebind

                value = rebind(args.home)
            elif args.command in {
                "prepare-gateway-source",
                "relocate-gateway",
                "recover-gateway-relocation",
            }:
                from . import gateway_source

                if args.command == "recover-gateway-relocation":
                    value = gateway_source.recover_rehome(args.home)
                else:
                    if args.release is None or args.revision is None:
                        raise UpdateBlocked("gateway_release_arguments_required")
                    if args.command == "prepare-gateway-source":
                        value = gateway_source.prepare(args.home, args.release, args.revision)
                    else:
                        if args.plan_seal is None:
                            raise UpdateBlocked("gateway_relocation_seal_required")
                        value = gateway_source.rehome(
                            args.home, args.release, args.revision, expected_seal=args.plan_seal
                        )
            elif args.command == "bridge":
                value = bridge_main(args.home, args.operation)
            elif args.command == "disable":
                with file_lock(root, "supervisor.lock", exclusive=True):
                    if (root / "transaction.json").exists():
                        raise UpdateBlocked("resident_recovery_required")
                    run(["/bin/launchctl", "disable", f"gui/{os.getuid()}/{LABEL}"])
                    run(["/bin/launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}"])
                    value = record(root, "disabled")
            elif args.command == "rollback":
                with file_lock(root, "supervisor.lock", exclusive=True):
                    candidate = read_json(root / "accepted.json")
                    _, config = configured(args.home)
                    environment(args.home, config)
                    value = bridge(args.home, config, "rollback")
                    fields = {"deployed": value["sha"]}
                    if value["status"] == "rolled_back":
                        fields["failed_candidate"] = candidate["target"]
                    record(root, value["status"], **fields)
            else:
                if args.command == "retry":
                    with file_lock(root, "supervisor.lock", exclusive=True):
                        (root / "quarantine.json").unlink(missing_ok=True)
                        sync_directory(root)
                        record(root, "retry_requested")
                value = tick(args.home)
        print(json.dumps(value, ensure_ascii=False))
        return 0
    except MaintenanceBusy:
        print(json.dumps({"status": "deferred", "reason": "resident_busy"}))
        return 0
    except Exception as exc:
        code = str(exc) if isinstance(exc, UpdateBlocked) else "resident_operation_failed"
        log.exception("resident_operation_failed")
        if owns_resident_state and root.exists():
            try:
                record(root, "blocked", reason=code)
            except (OSError, RuntimeError):
                log.error("resident_failure_state_unavailable")
        print(json.dumps({"status": "blocked", "reason": code}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
