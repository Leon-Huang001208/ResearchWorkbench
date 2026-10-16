"""One reviewed Host metadata upgrade; never expands automatic compatibility."""

from __future__ import annotations

import logging
from pathlib import Path

from .evidence import SHA, GitHubEvidence, UpdateBlocked, compatible, read_json

log = logging.getLogger(__name__)
PROFILE = "host-navigation-v1"
PREVIOUS = "02c086b168e62723887c7a778f716f6146595b6d"
REVIEWED_HOST = "5ba7578afcf3cb58d9fbbe4716b75b971d6a87a7"
HOST_BLOBS = {
    "app/research_web/claw_projects.py": "b06a6f60a1c8925adca4bc7f6b68acbb4e1dce71",
    "app/research_web/claw_routes.py": "aa6e28c0c7efe1af5c6ad4d380fcd4119e43ee76",
    "app/research_web/navigation.py": "dec1d4d53fd23a957edadd9c3e2f5fc0c74864d9",
    "app/research_web/service.py": "160972c71cb7a3e973be2ec866bdbe3e9ab03360",
}
# These files belong to the exact CI/review-qualified candidate, not a wildcard.
CONTROL_FILES = {
    "research_workbench_entrypoint/resident/controller.py",
    "research_workbench_entrypoint/resident/host_metadata.py",
}
GENERATED_FILES = {
    "outputs/research-web-architecture/api-atlas.html",
    "outputs/research-web-architecture/index.html",
}


def review(project: Path, config: dict, previous: str, target: str, paths: list[str]) -> dict:
    from . import controller as c

    source = Path(__file__).resolve().parents[2]
    c.clean(source, target)
    common = c.git(source, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if previous != PREVIOUS or Path(common) != Path(config["source_common"]):
        raise UpdateBlocked("resident_host_metadata_base_mismatch")
    c.git(project, "merge-base", "--is-ancestor", REVIEWED_HOST, target)
    unknown = [path for path in paths if not compatible([path])]
    if not set(unknown) <= HOST_BLOBS.keys() | CONTROL_FILES | GENERATED_FILES:
        raise UpdateBlocked("resident_host_metadata_scope_changed")
    blobs = {path: c.git(project, "rev-parse", f"{target}:{path}") for path in unknown}
    for path, expected in HOST_BLOBS.items():
        if c.git(project, "rev-parse", f"{target}:{path}") != expected:
            raise UpdateBlocked("resident_host_metadata_content_changed")
    log.info("resident_host_metadata_review_verified", extra={"sha": target})
    return {"profile": PROFILE, "previous": previous, "target": target, "blobs": blobs}


def metadata_shape(home: Path) -> dict:
    index = read_json(home / "research-web/index.json")
    if not isinstance(index.get("sessions"), dict):
        raise UpdateBlocked("resident_host_metadata_shape_changed")
    counts = {}
    for key in ("sessions", "claw_projects", "fingpt_projects", "session_navigation"):
        value = index.get(key, {})
        if not isinstance(value, dict):
            raise UpdateBlocked("resident_host_metadata_shape_changed")
        counts[key] = len(value)
    for mode, value in index.get("session_navigation", {}).items():
        if (
            mode not in {"claw", "fingpt"}
            or not isinstance(value, dict)
            or type(value.get("revision")) is not int
            or value["revision"] < 0
            or not isinstance(value.get("pinned"), list)
            or not isinstance(value.get("project_order"), list)
        ):
            raise UpdateBlocked("resident_host_metadata_shape_changed")
    log.info("resident_host_metadata_shape_verified", extra={"counts": counts})
    return counts


def upgrade(home: Path, previous: str, target: str) -> dict:
    from . import controller as c

    if c.sys.platform != "darwin" or not SHA.fullmatch(target or "") or previous != PREVIOUS:
        raise UpdateBlocked("resident_host_metadata_arguments_invalid")
    root, config = c.configured(home)
    with c.file_lock(root, "supervisor.lock", exclusive=True):
        c.environment(home, config)
        if (root / "transaction.json").exists():
            raise UpdateBlocked("resident_recovery_required")
        current = c.bridge(home, config, "ensure")
        if current.get("status") != "ready" or current.get("sha") not in {previous, target}:
            raise UpdateBlocked("resident_host_metadata_base_mismatch")
        github = GitHubEvidence(
            Path(config["gh"]), config["repository"], Path(config["source_common"])
        )
        if github.latest() != target:
            raise UpdateBlocked("resident_master_moved")
        proof = github.qualify(target)
        project = Path(config["project"])
        c.git(
            project,
            "fetch",
            "--no-auto-maintenance",
            f"https://github.com/{config['repository']}.git",
            "master",
        )
        if c.git(project, "rev-parse", "FETCH_HEAD") != target:
            raise UpdateBlocked("resident_master_moved")
        c.git(project, "merge-base", "--is-ancestor", previous, target)
        paths = c.git(project, "diff", "--name-only", previous, target).splitlines()
        reviewed = review(project, config, previous, target, paths)
        metadata_shape(home)
        if current["sha"] != target:
            if (root / "quarantine.json").exists() and read_json(root / "quarantine.json").get(
                "sha"
            ) == target:
                raise UpdateBlocked("resident_failed_candidate_requires_retry")
            c.stage(home, config, target, proof, compatibility_profile=PROFILE)
            if github.latest() != target:
                raise UpdateBlocked("resident_master_moved")
            github.qualify(target)
            result = c.bridge(home, config, "deploy")
            if result.get("status") != "deployed":
                fields = {"deployed": result.get("sha"), "candidate": target}
                if result["status"] == "deferred":
                    fields["deployed"] = result.get("sha", current["sha"])
                if result.get("reason"):
                    fields["reason"] = result["reason"]
                return c.record(root, result["status"], **fields)
        accepted = read_json(root / "accepted.json")
        if accepted.get("target") != target or accepted.get("previous") != previous:
            raise UpdateBlocked("resident_host_metadata_acceptance_missing")
        if accepted.get("compatibility_review") != reviewed:
            raise UpdateBlocked("resident_host_metadata_acceptance_changed")
        # Refresh only after the original transaction has confirmed health.
        if c.bridge(home, config, "ensure") != {"status": "ready", "sha": target}:
            raise UpdateBlocked("resident_version_health_failed")
        counts = metadata_shape(home)
        if c.configured(home)[1] != config:
            raise UpdateBlocked("resident_configuration_changed")
        if config["baseline"] != target:
            c.atomic(
                root / "baseline-reviews" / f"{target}.json",
                {
                    **reviewed,
                    "previous_baseline": config["baseline"],
                    "proof": proof,
                    "metadata_counts": counts,
                },
            )
            c.atomic(root / "config.json", {**config, "baseline": target})
        return c.record(root, "deployed", deployed=target, profile=PROFILE)
