"""Explicit, exact-scope Native product upgrades; automatic policy is unchanged."""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import io
import json
import logging
import os
import plistlib
import re
import signal
import socket
import stat
import sys
import time
import urllib.error
import urllib.request
import zipfile
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

from . import controller as c
from . import gateway_upgrade as g
from .admission import MaintenanceBusy, file_lock
from .evidence import GitHubEvidence, UpdateBlocked, read_json
from .gateway_fence import BirthFence

log = logging.getLogger(__name__)
PREVIOUS = "5df8e17e04f1b588f7e742423d81fb8e0ba34cb2"
# PR165 model backend plus already merged PR166 login presentation only.
PAYLOAD = "0d73c0348094f11c3440d8f6893c7a6896a8dbc8"
# PR168's reviewed navigation; all other product files retain PAYLOAD's identity.
NAVIGATION_PAYLOAD = "4e8be6ac7405733755e4a00be10898504e71710a"
NAVIGATION_FILES = frozenset(
    f"app/research_web/ui/{name}.mjs" for name in ("app", "core", "intel", "shell", "workbench")
)
MODULE = "research_workbench_entrypoint/resident/model_provider_upgrade.py"
WORKFLOW = ".github/workflows/research-web-checks.yml"
CONSTRAINTS = ".agents/project-constraints.json"
TEST = "tests/research_web/test_model_provider_upgrade.py"
ENTRY = "from resident.model_provider_upgrade import main\nraise SystemExit(main())\n"
MODE = "reviewed-model-providers-v1"
ASSET_MODE = "reviewed-asset-observation-v1"
ASSET_PREVIOUS = "c68814db170900688d6a799a241efc098eb83f32"
ASSET_PAYLOAD = "54d4c8f9421c568de853a2f93263a2bfcd53422c"
ASSET_V2_MODE = "reviewed-asset-observation-v2"
ASSET_V2_PREVIOUS = "9bc12355c3b80e4e4459f4c250e13fc2634ed23d"
ASSET_V2_PAYLOAD = "93d62be64084a5c92541a4a008216c0b3f56c2f1"
# PR177's reviewed Wind workspace; resident identity is the completed v2 deployment.
ASSET_V3_MODE = "reviewed-asset-observation-v3"
ASSET_V3_PREVIOUS = "5495e64c0be08c9db58e336705db90584f8ba8b5"
ASSET_V3_PAYLOAD = "a0ff3ae2e2ab92bad10ba8547e45027687ec7cc1"
# PR180's reviewed startup-preservation fix; the resident retains its v2 identity.
ASSET_V4_MODE = "reviewed-asset-observation-v4"
ASSET_V4_PREVIOUS = "5495e64c0be08c9db58e336705db90584f8ba8b5"
ASSET_V4_PAYLOAD = "9b436613aad9136f4959c992c89dd72fc7354ed5"
# PR188 includes PR185 assets plus the explicitly authorized DataHub combination.
ASSET_V5_MODE = "reviewed-asset-observation-v5"
ASSET_V5_PREVIOUS = "51f09fa783694aae5234905933948394ca167dcc"
ASSET_V5_PAYLOAD = "88ef3817680ac822e2d7c819db845de4b7275173"
ASSET_V5_WEB_LOCK_SHA256 = "7c631d4fa5354170c622225be129a09f7f5890457aa0521bd5f46cecb6bb7102"
# PR197 is the merged compact workspace, verified turnover chips and magnitude display.
ASSET_V6_MODE = "reviewed-asset-observation-v6"
ASSET_V6_PREVIOUS = "c1a260fa1d8dcf013426aca938d7e46a98aaee28"
ASSET_V6_PAYLOAD = "eac6806822294d75da990c751d88ec156a417f62"
ASSET_V6_WEB_LOCK_SHA256 = "7c631d4fa5354170c622225be129a09f7f5890457aa0521bd5f46cecb6bb7102"
ASSET_V6_EVIDENCE_SHA256 = "5c3077b7fac26f6836384f678514136802bcf2ed03a0a589aaac10e80111eebb"
# Fixed merged asset-panel product; retain all earlier recovery identities.
ASSET_V7_MODE = "reviewed-asset-observation-v7"
ASSET_V7_PREVIOUS = "c4e953c4386c615cde89ad2d014d60c6e2959303"
ASSET_V7_PAYLOAD = "3a62ca1a3bff0927db681322a1ff028f08cf03cd"
ASSET_V7_WEB_LOCK_SHA256 = "7c631d4fa5354170c622225be129a09f7f5890457aa0521bd5f46cecb6bb7102"
ASSET_V7_EVIDENCE_SHA256 = "5c3077b7fac26f6836384f678514136802bcf2ed03a0a589aaac10e80111eebb"
# PR216/217/219 combined product; retain previous recovery identities.
ASSET_V8_MODE = "reviewed-asset-observation-v8"
ASSET_V8_PREVIOUS = "b438447071d08eec38902b2a50610644283885f9"
ASSET_V8_PAYLOAD = "dee0cce4dbc65782dba2c720f33ada683457d72a"
ASSET_V8_WEB_LOCK_SHA256 = ASSET_V7_WEB_LOCK_SHA256
ASSET_V8_EVIDENCE_SHA256 = ASSET_V7_EVIDENCE_SHA256

# V9 admits the reviewed bounded CI reader; V1-V8 evidence identities stay frozen.
ASSET_V9_MODE = "reviewed-asset-observation-v9"
ASSET_V9_PREVIOUS = ASSET_V8_PREVIOUS
ASSET_V9_PAYLOAD = "b500fcbe9b95632667a6194e519f7e8a743c4221"
ASSET_V9_WEB_LOCK_SHA256 = ASSET_V8_WEB_LOCK_SHA256
ASSET_V9_EVIDENCE_SHA256 = "193f4fcc7e27ab1fd9fd87c4d30a0ca200476fe74c6cc4c6c7dad6bb8ce63988"
# PR179's merged market product, starting at the completed v4 resident deployment.
MARKET_MODE = "reviewed-market-overview-v1"
MARKET_PREVIOUS = "4d2e3c408663b64be9e58b03213f4ca8f1152733"
MARKET_PAYLOAD = "5de7e5f2db95b8b501905af9cfdc30e8fe84db0b"
MARKET_GATEWAY = "research_workbench_entrypoint/resident/gateway_upgrade.py"
MARKET_GATEWAY_SHA256 = "a5ebfaee0211403fd12083c61b6eafd6a4e08915af1c3c9c95b34fb4bed7c166"
# Freeze a reviewed product checkpoint; final target still needs merged exact-tree CI.
MARKET_GAPS_MODE = "reviewed-market-gaps-v1"
MARKET_GAPS_PREVIOUS = "99d3ee34977c47189a5638207c109a555f52a687"
MARKET_GAPS_PAYLOAD = "9faeeca3003a912ca75799fb27b635ba1bb87a1a"
MARKET_HISTORY_MODE = "reviewed-market-history-v1"
MARKET_HISTORY_PREVIOUS = "51f09fa783694aae5234905933948394ca167dcc"
MARKET_HISTORY_PAYLOAD = "4f0a248fc87249d41e1c3f75f700c17c8351ad95"
MARKET_HISTORY_WEB_LOCK_SHA256 = "7c631d4fa5354170c622225be129a09f7f5890457aa0521bd5f46cecb6bb7102"
# Full terminal and current asset/DataHub checkpoint; no automatic-policy expansion.
MARKET_TERMINAL_MODE = "reviewed-market-terminal-v1"
MARKET_TERMINAL_PREVIOUS = "0e0022ac792eba88fba0f233524f5c8d66024569"
MARKET_TERMINAL_PAYLOAD = "ca20293b8244bb0644bf2039ddd96ee452a27b0b"
MARKET_TERMINAL_WEB_LOCK_SHA256 = "7c631d4fa5354170c622225be129a09f7f5890457aa0521bd5f46cecb6bb7102"
MARKET_TERMINAL_EVIDENCE_SHA256 = "5c3077b7fac26f6836384f678514136802bcf2ed03a0a589aaac10e80111eebb"
# User-authorized PR223/224 combination: terminal edit and DataHub source fixes.
MARKET_PREVIEW_MODE = "reviewed-market-preview-v1"
MARKET_PREVIEW_PREVIOUS = "36fd990ceed88d2fc595443926105c4b2601fbf6"
MARKET_PREVIEW_PAYLOAD = "e56d9718e12c2252128a6690ca202c7ae21f341e"
MARKET_PREVIEW_WEB_LOCK_SHA256 = ASSET_V9_WEB_LOCK_SHA256
MARKET_PREVIEW_EVIDENCE_SHA256 = ASSET_V9_EVIDENCE_SHA256
# User-approved PR233/235/237/236 product, from the verified b800 resident.
MARKET_BREADTH_MODE = "reviewed-market-breadth-v1"
MARKET_BREADTH_PREVIOUS = "b800e50366d1a0868372bbf173822976066c143f"
MARKET_BREADTH_PAYLOAD = "4c72ed4349c087cf0b7d037d7133b84201a76d5f"
MARKET_BREADTH_WEB_LOCK_SHA256 = ASSET_V9_WEB_LOCK_SHA256
MARKET_BREADTH_EVIDENCE_SHA256 = ASSET_V9_EVIDENCE_SHA256
# PR198's merged Excel-first weekly product; previous is the registered resident.
# This source profile does not authorize a resident switch or arbitrary runtime SHAs.
ETF_WEEKLY_MODE = "reviewed-etf-weekly-v1"
ETF_WEEKLY_PREVIOUS = "5343e18d9f203a87f2d958218e4288afa527711f"
ETF_WEEKLY_PAYLOAD = "988046d23f9951f889a3b9d02e355ed59fd6aa65"
DISCOVERY_MODE = "reviewed-discovery-v1"
DISCOVERY_PREVIOUS = "5343e18d9f203a87f2d958218e4288afa527711f"
# Explicitly authorized combination: discovery, ETF configuration and dossiers.
DISCOVERY_PAYLOAD = "1780064b712afb61ff18f2f1811650fc31fd3038"
# PR209 combined product includes dossier preservation; deployment needs new authorization.
ETF_WEEKLY_V2_MODE = "reviewed-etf-weekly-v2"
ETF_WEEKLY_V2_PREVIOUS = "5343e18d9f203a87f2d958218e4288afa527711f"
ETF_WEEKLY_V2_PAYLOAD = "56709a8dbb6e01d2ab17b64533319e199ebef86f"
# This PR freezes the full historical product before appending its operator.
ETF_HISTORICAL_MODE = "reviewed-etf-historical-v1"
ETF_HISTORICAL_PREVIOUS = "b438447071d08eec38902b2a50610644283885f9"
ETF_HISTORICAL_PAYLOAD = "bb4d2e657872ecb24df5bb0e89f571b4600b84d1"
# Full reviewed product ancestor; no runtime-selected identity is accepted.
ETF_WEEKLY_ADMISSION_MODE = "reviewed-etf-weekly-admission-v1"
ETF_WEEKLY_ADMISSION_PREVIOUS = "36fd990ceed88d2fc595443926105c4b2601fbf6"
ETF_WEEKLY_ADMISSION_PAYLOAD = "bacb423cea203ba0469b5c7f21bfd581408b03ef"
ETF_WEEKLY_ADMISSION_WEB_LOCK_SHA256 = ASSET_V9_WEB_LOCK_SHA256
ETF_WEEKLY_ADMISSION_EVIDENCE_SHA256 = ASSET_V9_EVIDENCE_SHA256
ETF_WEEKLY_ADMISSION_V2_MODE = "reviewed-etf-weekly-admission-v2"
ETF_WEEKLY_ADMISSION_V2_PREVIOUS = "36fd990ceed88d2fc595443926105c4b2601fbf6"
ETF_WEEKLY_ADMISSION_V2_PAYLOAD = "d0e83e438e42e74f606bbd6645ad326db6c5b8a2"
ETF_WEEKLY_ADMISSION_V2_WEB_LOCK_SHA256 = ASSET_V9_WEB_LOCK_SHA256
ETF_WEEKLY_ADMISSION_V2_EVIDENCE_SHA256 = ASSET_V9_EVIDENCE_SHA256
WEEKLY_ACTION_SHA256 = "7cbd0ba4d25c496fe6367c59e2487659e878de0b8b86de5d4b4ac014157ec5af"
WEEKLY_OPERATION_ID = "etf-legacy-monitoring-20261024"
# Historical family name: all these profiles require full business-index preservation.
# Fixed merged dossiers product; retain the registered resident recovery identity.
DOSSIERS_MODE = "reviewed-research-dossiers-v1"
DOSSIERS_PREVIOUS = "5343e18d9f203a87f2d958218e4288afa527711f"
DOSSIERS_PAYLOAD = "1780064b712afb61ff18f2f1811650fc31fd3038"
ASSET_MODES = frozenset(
    (
        ASSET_MODE,
        ASSET_V2_MODE,
        ASSET_V3_MODE,
        ASSET_V4_MODE,
        ASSET_V5_MODE,
        ASSET_V6_MODE,
        ASSET_V7_MODE,
        ASSET_V8_MODE,
        ASSET_V9_MODE,
        MARKET_MODE,
        MARKET_GAPS_MODE,
        MARKET_HISTORY_MODE,
        MARKET_TERMINAL_MODE,
        MARKET_PREVIEW_MODE,
        MARKET_BREADTH_MODE,
        ETF_WEEKLY_MODE,
        DOSSIERS_MODE,
        DISCOVERY_MODE,
        ETF_WEEKLY_V2_MODE,
        ETF_HISTORICAL_MODE,
        ETF_WEEKLY_ADMISSION_MODE,
        ETF_WEEKLY_ADMISSION_V2_MODE,
    )
)
ASSET_EVIDENCE = "research_workbench_entrypoint/resident/evidence.py"
ASSET_EVIDENCE_SHA256 = "ec022e39a89a3dbd021fca26049342ce149077f5beb62a8df2aba7826d016d25"
MAX_ASSET_INDEX_BYTES = 64 * 1024 * 1024
CONTROLLER_SHA256 = "4924299104d5f82a9cc732bb2ca1f811694d14056d58a2762e7c86e40f6665a2"
CONTROLLER_MODULE_SHA256 = "b432f519e14a2e851a7eb39a3de179f99494b9347c857694c4192477a7996846"
TRIAL_MODE = "operator-authorized-trial-retirement-v1"
TRIAL_PREVIOUS = "b800e50366d1a0868372bbf173822976066c143f"
TRIAL_PAYLOAD = "db2ae9a48ceca365852072e622aa6627aa7d0b83"
TAILSCALE = "/Applications/Tailscale.app/Contents/MacOS/Tailscale"
FORWARD = (
    "stop_gateway",
    "stop_primary",
    "activate_sources_and_wheel",
    "start_primary",
    "start_gateway",
    "verify_target",
)
BACKWARD = (
    "rollback_gateway",
    "rollback_primary",
    "restore_sources_and_wheel",
    "start_previous_primary",
    "start_previous_gateway",
    "verify_previous",
)


def execute(ops, state, *, recovering=False):
    """Keep every signal/install behind durable intent; uncertain drains stay fenced."""
    if recovering and state.get("mode") == TRIAL_MODE:
        try:
            terminal = ops.recover_trial_terminal(state)
            if terminal is not None:
                return terminal
        except Exception:
            log.exception("trial_retirement_terminal_recovery_pending")
            return {"status": "recovery_required"}
    if not recovering:
        try:
            idle = ops.idle()
        except (MaintenanceBusy, UpdateBlocked, OSError, ValueError):
            log.warning("model_upgrade_activity_unknown")
            idle = False
        if idle is not True:
            return {"status": "deferred"}
        try:
            ops.checkpoint(state, "prepared")
            for action in FORWARD:
                ops.checkpoint(state, action)
                ops.action(action, state)
        except MaintenanceBusy:
            log.warning("model_upgrade_drain_deferred")
            return {"status": "recovery_required"}
        except Exception:
            log.exception("model_upgrade_candidate_failed")
        else:
            # A finish failure can occur AFTER HTTP admission has reopened.
            # Never signal/reinstall from this stack after that boundary. A new
            # recovery invocation must first reacquire and validate all fences.
            try:
                return ops.finish(state, "deployed")
            except Exception:
                log.exception("model_upgrade_completion_unknown")
                return {"status": "completion_unknown"}
    try:
        if ops.idle() is not True:
            return {"status": "recovery_required"}
        for action in BACKWARD:
            ops.checkpoint(state, action)
            ops.action(action, state)
        return ops.finish(state, "rolled_back")
    except Exception:
        log.exception("model_upgrade_recovery_pending")
        return {"status": "recovery_required"}


def previous_for(mode):
    if mode == TRIAL_MODE:
        return TRIAL_PREVIOUS
    if mode == MODE:
        return PREVIOUS
    if mode == ASSET_MODE:
        return ASSET_PREVIOUS
    if mode == ASSET_V2_MODE:
        return ASSET_V2_PREVIOUS
    if mode == ASSET_V3_MODE:
        return ASSET_V3_PREVIOUS
    if mode == ASSET_V4_MODE:
        return ASSET_V4_PREVIOUS
    if mode == ASSET_V5_MODE:
        return ASSET_V5_PREVIOUS
    if mode == ASSET_V6_MODE:
        return ASSET_V6_PREVIOUS
    if mode == ASSET_V7_MODE:
        return ASSET_V7_PREVIOUS
    if mode == ASSET_V9_MODE:
        return ASSET_V9_PREVIOUS
    if mode == ASSET_V8_MODE:
        return ASSET_V8_PREVIOUS
    if mode == MARKET_MODE:
        return MARKET_PREVIOUS
    if mode == MARKET_GAPS_MODE:
        return MARKET_GAPS_PREVIOUS
    if mode == MARKET_HISTORY_MODE:
        return MARKET_HISTORY_PREVIOUS
    if mode == MARKET_TERMINAL_MODE:
        return MARKET_TERMINAL_PREVIOUS
    if mode == MARKET_PREVIEW_MODE:
        return MARKET_PREVIEW_PREVIOUS
    if mode == MARKET_BREADTH_MODE:
        return MARKET_BREADTH_PREVIOUS
    if mode == DOSSIERS_MODE:
        return DOSSIERS_PREVIOUS
    if mode == ETF_WEEKLY_MODE:
        return ETF_WEEKLY_PREVIOUS
    if mode == DISCOVERY_MODE:
        return DISCOVERY_PREVIOUS
    if mode == ETF_WEEKLY_V2_MODE:
        return ETF_WEEKLY_V2_PREVIOUS
    if mode == ETF_WEEKLY_ADMISSION_MODE:
        return ETF_WEEKLY_ADMISSION_PREVIOUS
    if mode == ETF_WEEKLY_ADMISSION_V2_MODE:
        return ETF_WEEKLY_ADMISSION_V2_PREVIOUS
    if mode == ETF_HISTORICAL_MODE:
        return ETF_HISTORICAL_PREVIOUS
    raise UpdateBlocked("model_upgrade_profile_unknown")


def asset_queries_idle(index):
    """A Native-idle response does not prove pending DataHub work has finished."""
    observations, queries = index.get("asset_observations", {}), index.get("data_queries", {})
    if not isinstance(observations, dict) or not isinstance(queries, dict):
        return False
    history_jobs = index.get("asset_history_jobs", {})
    if not isinstance(history_jobs, dict):
        return False
    for job in history_jobs.values():
        if not isinstance(job, dict):
            return False
        state = job.get("state", job.get("status"))
        if state not in {"completed", "failed", "cancelled", "interrupted"}:
            return False
        if "state" in job and "status" in job and job["state"] != job["status"]:
            return False
    for row in observations.values():
        if not isinstance(row, dict) or row.get("status") not in {"complete", "partial", "failed"}:
            return False
        blocks = row.get("blocks", {})
        if not isinstance(blocks, dict) or any(
            not isinstance(block, dict)
            or block.get("status") not in {"complete", "partial", "empty", "unavailable", "error"}
            for block in blocks.values()
        ):
            return False
    return all(
        isinstance(row, dict) and row.get("status") in {"completed", "failed", "cancelled"}
        for row in queries.values()
    )


def read_business_index(path: Path):
    """Read bounded business data without relaxing deployment metadata limits."""
    try:
        if path.resolve() != path.absolute():
            raise ValueError("index_path_unsafe")
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_ASSET_INDEX_BYTES:
                raise ValueError("index_file_invalid")
            raw = stream.read(MAX_ASSET_INDEX_BYTES + 1)
        if len(raw) > MAX_ASSET_INDEX_BYTES:
            raise ValueError("index_size_invalid")
        index = json.loads(raw)
        if not isinstance(index, dict):
            raise TypeError("index_object_required")
    except (OSError, ValueError, TypeError) as exc:
        log.error("asset_upgrade_index_read_failed", extra={"error_type": type(exc).__name__})
        raise UpdateBlocked("asset_upgrade_index_invalid") from exc
    return index


def discovery_background_idle(home):
    """Recheck persisted work without starting a backend or changing consent."""
    try:
        users = home / "server/users"
        if users.is_symlink() or not users.is_dir():
            return False
        roots = [home / "research-web"]
        for folder in sorted(users.iterdir()):
            if folder.is_symlink() or not folder.is_dir():
                return False
            roots.append(folder / "research-web")
        for root in roots:
            if root.is_symlink():
                return False
            if not root.exists() and root != home / "research-web":
                # Registered primary/uninitialized accounts can have state only.
                continue
            if not root.is_dir():
                return False
            index_path = root / "index.json"
            index = (
                read_business_index(index_path)
                if index_path.exists() or index_path.is_symlink()
                else {}
            )
            for name in ("automations", "automation_runs", "discovery_tracks"):
                table = index.get(name, {})
                if not isinstance(table, dict) or any(
                    not isinstance(row, dict) for row in table.values()
                ):
                    return False
            for row in index.get("automations", {}).values():
                if type(row.get("enabled")) is not bool or row["enabled"]:
                    return False
            if any(
                row.get("research_status")
                not in {
                    "completed",
                    "failed",
                    "cancelled",
                    "canceled",
                    "interrupted",
                    "skipped_overlap",
                    "blocked_version",
                }
                for row in index.get("automation_runs", {}).values()
            ):
                return False
            workflows = root / "report-workflows"
            if workflows.is_symlink() or (workflows.exists() and not workflows.is_dir()):
                return False
            catalog_path = workflows / "catalog.json"
            if not catalog_path.exists() and not catalog_path.is_symlink():
                # The existing runtime treats a missing catalog as no plans.
                continue
            catalog = read_business_index(catalog_path)
            if any(not isinstance(catalog.get(name), dict) for name in ("workflows", "runs")):
                return False
            for row in catalog["workflows"].values():
                if not isinstance(row, dict):
                    return False
                schedule = row.get("schedule")
                if schedule is not None and (
                    not isinstance(schedule, dict)
                    or type(schedule.get("enabled", False)) is not bool
                    or schedule.get("enabled", False)
                ):
                    return False
            if any(
                not isinstance(row, dict)
                or row.get("status")
                not in {
                    "completed",
                    "failed",
                    "cancelled",
                    "canceled",
                    "blocked_data",
                    "delivery_incomplete",
                }
                for row in catalog["runs"].values()
            ):
                return False
        return True
    except (OSError, ValueError, TypeError, UpdateBlocked) as exc:
        log.warning(
            "discovery_deploy_background_unverified", extra={"error_type": type(exc).__name__}
        )
        return False


def verify_primary(home, expected, mode):
    if mode in {
        MARKET_MODE,
        MARKET_GAPS_MODE,
        MARKET_HISTORY_MODE,
        MARKET_TERMINAL_MODE,
        MARKET_PREVIEW_MODE,
        MARKET_BREADTH_MODE,
        ASSET_V5_MODE,
        ASSET_V6_MODE,
        ASSET_V7_MODE,
        ASSET_V8_MODE,
        ASSET_V9_MODE,
        ETF_WEEKLY_MODE,
        DOSSIERS_MODE,
        DISCOVERY_MODE,
        ETF_WEEKLY_V2_MODE,
        ETF_HISTORICAL_MODE,
        ETF_WEEKLY_ADMISSION_MODE,
        ETF_WEEKLY_ADMISSION_V2_MODE,
    }:
        return g.verify_primary(home, expected, index_reader=read_business_index)
    return g.verify_primary(home, expected)


def weekly_primary_identity_precheck(home, expected):
    """V2 only: original primary identity, explicit activity observation, Native idle.

    Host active=True is observed, never certified idle. The sealed bridge may
    end its approved legacy control wait; the original full verifier must still
    pass afterwards. Keep every non-Host-activity check from g.verify_primary.
    """
    from app.research_web.multiuser.resident_binding import LegacyBinding
    from app.research_web.service_manager import WebServiceManager

    _, config = g.configured(home)
    g.clean(Path(config["project"]), expected)
    server = read_json(home / "server/resident.json")
    binding = LegacyBinding.discover(home, server["binding"]["primary_user_id"])
    state = binding.verify()
    manager = WebServiceManager(
        project_root=binding.project,
        data_root=binding.data_root,
        python=str(binding.project / ".venv/bin/python"),
        node=config["node"],
        web_port=binding.web_port,
        runtime_port=binding.runtime_port,
    )
    probes = [probe for probe in manager._service_probes() if probe.role == "runtime"]
    native = manager._active_research_read_only(probes[0]) if len(probes) == 1 else None
    if type(state.get("active")) is not bool or type(native) is not list or native:
        raise MaintenanceBusy("research_active_or_unknown")
    index = read_business_index(binding.data_root / "index.json")
    rows = index.get("automation_runs", {})
    if not isinstance(rows, dict) or any(
        not isinstance(row, dict) or row.get("research_status") in {"queued", "running"}
        for row in rows.values()
    ):
        raise MaintenanceBusy("research_active_or_unknown")
    log.info(
        "weekly_primary_identity_verified host_active=%s idle_certified=false", state["active"]
    )
    return state


def asset_index_snapshot(home: Path):
    """Hash every business-index value, preserving scope and missing/empty distinctions."""

    def snapshot(path):
        index = read_business_index(path)
        from app.research_web.dossier_preservation import snapshot_dossiers

        try:
            dossier_state = snapshot_dossiers(path.parent)
        except RuntimeError as exc:
            raise UpdateBlocked("dossier_preservation_failed") from exc
        if dossier_state is not None:
            if "@dossiers" in index:
                raise UpdateBlocked("dossier_preservation_key_conflict")
            index = {**index, "@dossiers": dossier_state}
        return {
            key: hashlib.sha256(
                json.dumps(
                    value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
                ).encode()
            ).hexdigest()
            for key, value in index.items()
        }

    users = home / "server/users"
    if users.is_symlink() or not users.is_dir():
        raise UpdateBlocked("asset_upgrade_index_scope_invalid")
    private = {}
    for folder in sorted(users.iterdir()):
        if folder.is_symlink() or (folder / "research-web").is_symlink():
            raise UpdateBlocked("asset_upgrade_index_scope_invalid")
        path = folder / "research-web/index.json"
        if path.exists() or path.is_symlink():
            private[folder.name] = snapshot(path)
    return {"primary": snapshot(home / "research-web/index.json"), "private": private}


def validate_asset_snapshot(state):
    if state.get("mode") not in ASSET_MODES:
        return
    value = state.get("asset_index_before")
    if (
        not isinstance(value, dict)
        or set(value) != {"primary", "private"}
        or not isinstance(value["private"], dict)
    ):
        raise UpdateBlocked("asset_upgrade_index_snapshot_invalid")
    for scope in [value["primary"], *value["private"].values()]:
        if not isinstance(scope, dict) or any(
            not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
            for digest in scope.values()
        ):
            raise UpdateBlocked("asset_upgrade_index_snapshot_invalid")


def verify_asset_index(home: Path, state):
    if state.get("mode") in ASSET_MODES:
        validate_asset_snapshot(state)
        if asset_index_snapshot(home) != state["asset_index_before"]:
            log.error("asset_upgrade_business_index_changed")
            raise UpdateBlocked("asset_upgrade_business_index_changed")


def review_assets(source: Path, target: str, mode=ASSET_MODE):
    """Freeze the selected reviewed product, including paths reverted from the diff."""
    if mode not in ASSET_MODES:
        raise UpdateBlocked("model_upgrade_profile_unknown")
    previous = previous_for(mode)
    payload = {
        ASSET_MODE: ASSET_PAYLOAD,
        ASSET_V2_MODE: ASSET_V2_PAYLOAD,
        ASSET_V3_MODE: ASSET_V3_PAYLOAD,
        ASSET_V4_MODE: ASSET_V4_PAYLOAD,
        ASSET_V5_MODE: ASSET_V5_PAYLOAD,
        ASSET_V6_MODE: ASSET_V6_PAYLOAD,
        ASSET_V7_MODE: ASSET_V7_PAYLOAD,
        ASSET_V8_MODE: ASSET_V8_PAYLOAD,
        ASSET_V9_MODE: ASSET_V9_PAYLOAD,
        MARKET_MODE: MARKET_PAYLOAD,
        MARKET_GAPS_MODE: MARKET_GAPS_PAYLOAD,
        MARKET_HISTORY_MODE: MARKET_HISTORY_PAYLOAD,
        MARKET_TERMINAL_MODE: MARKET_TERMINAL_PAYLOAD,
        MARKET_PREVIEW_MODE: MARKET_PREVIEW_PAYLOAD,
        MARKET_BREADTH_MODE: MARKET_BREADTH_PAYLOAD,
        ETF_WEEKLY_MODE: ETF_WEEKLY_PAYLOAD,
        DOSSIERS_MODE: DOSSIERS_PAYLOAD,
        DISCOVERY_MODE: DISCOVERY_PAYLOAD,
        ETF_WEEKLY_V2_MODE: ETF_WEEKLY_V2_PAYLOAD,
        ETF_HISTORICAL_MODE: ETF_HISTORICAL_PAYLOAD,
        ETF_WEEKLY_ADMISSION_MODE: ETF_WEEKLY_ADMISSION_PAYLOAD,
        ETF_WEEKLY_ADMISSION_V2_MODE: ETF_WEEKLY_ADMISSION_V2_PAYLOAD,
    }[mode]
    c.clean(source, target)
    c.git(source, "merge-base", "--is-ancestor", payload, target)
    paths = {MODULE, TEST, ASSET_EVIDENCE}
    if mode == MARKET_MODE:
        paths.add(MARKET_GATEWAY)
    for revision in (payload, target):
        paths.update(
            c.git(source, "diff", "--no-renames", "--name-only", previous, revision).splitlines()
        )
    result = {}
    for name in sorted(paths):
        blob = c.git(source, "rev-parse", f"{target}:{name}")
        actual_mode = c.git(source, "ls-tree", target, "--", name).split()[0]
        if actual_mode not in {"100644", "100755"}:
            raise UpdateBlocked("asset_upgrade_payload_changed")
        if name == ASSET_EVIDENCE:
            if actual_mode != "100644" or hashlib.sha256(
                g.git_bytes(source, target, "evidence.py")
            ).hexdigest() != (
                {
                    ASSET_V9_MODE: ASSET_V9_EVIDENCE_SHA256,
                    MARKET_PREVIEW_MODE: MARKET_PREVIEW_EVIDENCE_SHA256,
                    MARKET_BREADTH_MODE: MARKET_BREADTH_EVIDENCE_SHA256,
                    ETF_WEEKLY_ADMISSION_MODE: ETF_WEEKLY_ADMISSION_EVIDENCE_SHA256,
                    ETF_WEEKLY_ADMISSION_V2_MODE: ETF_WEEKLY_ADMISSION_V2_EVIDENCE_SHA256,
                }[mode]
                if mode
                in {
                    ASSET_V9_MODE,
                    MARKET_PREVIEW_MODE,
                    MARKET_BREADTH_MODE,
                    ETF_WEEKLY_ADMISSION_MODE,
                    ETF_WEEKLY_ADMISSION_V2_MODE,
                }
                else (
                    MARKET_TERMINAL_EVIDENCE_SHA256
                    if mode == MARKET_TERMINAL_MODE
                    else (
                        (
                            ASSET_V8_EVIDENCE_SHA256
                            if mode == ASSET_V8_MODE
                            else ASSET_V7_EVIDENCE_SHA256
                        )
                        if mode in {ASSET_V7_MODE, ASSET_V8_MODE}
                        else (
                            ASSET_V6_EVIDENCE_SHA256
                            if mode
                            in {
                                ASSET_V6_MODE,
                                ETF_WEEKLY_MODE,
                                DOSSIERS_MODE,
                                DISCOVERY_MODE,
                                ETF_WEEKLY_V2_MODE,
                                ETF_HISTORICAL_MODE,
                                ETF_WEEKLY_ADMISSION_MODE,
                                ETF_WEEKLY_ADMISSION_V2_MODE,
                            }
                            else ASSET_EVIDENCE_SHA256
                        )
                    )
                )
            ):
                raise UpdateBlocked("asset_upgrade_evidence_changed")
        elif mode == MARKET_MODE and name == MARKET_GATEWAY:
            if (
                actual_mode != "100644"
                or hashlib.sha256(g.git_bytes(source, target, "gateway_upgrade.py")).hexdigest()
                != MARKET_GATEWAY_SHA256
            ):
                raise UpdateBlocked("market_upgrade_gateway_changed")
        elif mode in {ETF_WEEKLY_ADMISSION_MODE, ETF_WEEKLY_ADMISSION_V2_MODE} and name in {
            "outputs/research-web-architecture/index.html",
            "outputs/research-web-architecture/api-atlas.html",
        }:
            if actual_mode != "100644":
                raise UpdateBlocked("asset_upgrade_payload_changed")
        elif (
            mode in {ETF_WEEKLY_ADMISSION_MODE, ETF_WEEKLY_ADMISSION_V2_MODE}
            and name not in {MODULE, TEST}
            and not name.startswith(("docs/", ".ai/reports/"))
        ):
            if (
                blob != c.git(source, "rev-parse", f"{payload}:{name}")
                or actual_mode != c.git(source, "ls-tree", payload, "--", name).split()[0]
            ):
                raise UpdateBlocked("asset_upgrade_payload_changed")
        elif name.startswith(("docs/", "tests/", ".ai/reports/")) or name in {
            MODULE,
            "README.md",
            "outputs/research-web-architecture/index.html",
            "outputs/research-web-architecture/api-atlas.html",
        }:
            pass
        elif (
            blob != c.git(source, "rev-parse", f"{payload}:{name}")
            or actual_mode != c.git(source, "ls-tree", payload, "--", name).split()[0]
        ):
            raise UpdateBlocked("asset_upgrade_payload_changed")
        result[name] = blob
    log.info("asset_upgrade_payload_reviewed profile=%s files=%s", mode, len(result))
    return result


def review(source: Path, target: str, mode=MODE):
    """Only the reviewed model payload plus this operator, its test and documentation."""
    previous_for(mode)
    if mode == TRIAL_MODE:
        if target != TRIAL_PAYLOAD:
            raise UpdateBlocked("trial_retirement_product_changed")
        c.clean(source, target)
        return {"product_tree": c.git(source, "rev-parse", f"{target}^{{tree}}")}
    if mode in ASSET_MODES:
        return review_assets(source, target, mode)
    c.clean(source, target)
    c.git(source, "merge-base", "--is-ancestor", PAYLOAD, target)
    c.git(source, "merge-base", "--is-ancestor", NAVIGATION_PAYLOAD, target)
    paths = c.git(source, "diff", "--no-renames", "--name-only", PREVIOUS, target).splitlines()
    # A reverted file disappears from PREVIOUS..target; still require every
    # reviewed navigation file so the deployed product cannot silently regress.
    paths = sorted(set(paths) | NAVIGATION_FILES)
    result = {}
    for name in paths:
        blob = c.git(source, "rev-parse", f"{target}:{name}")
        if name.startswith(("docs/", "tests/", ".ai/reports/")) or name in {
            MODULE,
            "README.md",
            "outputs/research-web-architecture/index.html",
            "outputs/research-web-architecture/api-atlas.html",
        }:
            pass
        elif name in (WORKFLOW, CONSTRAINTS):
            original = c.git(source, "show", f"{PAYLOAD}:{name}")
            expected = original
            if name == WORKFLOW and TEST not in original:
                expected = original.replace(
                    "tests/research_web/test_gateway_upgrade.py",
                    "tests/research_web/test_gateway_upgrade.py " + TEST,
                    1,
                )
            expected = expected.replace("timeout-minutes: 20", "timeout-minutes: 30", 1)
            if c.git(source, "show", f"{target}:{name}") != expected:
                raise UpdateBlocked("model_upgrade_workflow_scope_changed")
        else:
            expected = NAVIGATION_PAYLOAD if name in NAVIGATION_FILES else PAYLOAD
            expected_blob = c.git(source, "rev-parse", f"{expected}:{name}")
            expected_mode = c.git(source, "ls-tree", expected, "--", name).split()[0]
            actual_mode = c.git(source, "ls-tree", target, "--", name).split()[0]
            if blob != expected_blob or expected_mode != actual_mode:
                raise UpdateBlocked("model_upgrade_payload_changed")
        result[name] = blob
    if MODULE not in result or TEST not in result:
        raise UpdateBlocked("model_upgrade_operator_missing")
    log.info(
        "model_upgrade_payload_reviewed files=%s navigation_files=%s",
        len(result),
        len(NAVIGATION_FILES.intersection(result)),
    )
    return result


def request_json(url):
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(url, timeout=15) as r:
        return json.load(r)


def ports_are_free(ports):
    for port in ports:
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                return False
    return True


def model_metadata(config):
    value = request_json(f"http://127.0.0.1:{config['web_port']}/api/research/runtime")
    if (
        value.get("connected") is not True
        or value.get("health_check_passed") is not True
        or (
            type(value.get("credential_configured")) is not bool
            and value.get("credential_storage") != "not_required"
        )
    ):
        raise MaintenanceBusy("model_upgrade_credential_state_unknown")
    return {
        key: value.get(key)
        for key in ("provider", "model", "credential_configured", "credential_storage")
    }


def verify_retention(home):
    index = read_business_index(home / "research-web/index.json")
    sessions = index.get("sessions")
    if not isinstance(sessions, dict):
        raise UpdateBlocked("model_upgrade_session_state_unknown")
    cutoff = time.time() - 30 * 86400 + 3600
    if any(
        not isinstance(row, dict)
        or (isinstance(row.get("deleted_at"), (int, float)) and row["deleted_at"] <= cutoff)
        for row in sessions.values()
    ):
        raise UpdateBlocked("model_upgrade_retention_due")


def verify_serve(origin):
    from urllib.parse import urlsplit

    value = json.loads(g.run([TAILSCALE, "serve", "status", "--json"]))
    authority = urlsplit(origin).netloc + ":443"
    web = value.get("Web", {})
    handlers = web.get(authority, {}).get("Handlers", {})
    # Existing /collections is a separate private service and is never changed.
    if (
        value.get("AllowFunnel")
        or set(web) != {authority}
        or set(handlers) - {"/", "/collections"}
        or handlers.get("/") != {"Proxy": "http://127.0.0.1:8089"}
        or value.get("TCP") != {"443": {"HTTPS": True}}
    ):
        raise UpdateBlocked("model_upgrade_private_route_unknown")


def verify_private_fence(origin):
    """No redirect or primary HTML may make the old controller clear its journal."""

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *_args, **_kwargs):
            return None

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(origin + "/", timeout=15):
            pass
    except urllib.error.HTTPError as error:
        if error.code == 503:
            return
    raise UpdateBlocked("model_upgrade_private_fence_unverified")


def reserved_owners(server, transaction):
    """Validate only this fence's directory reservations; never mistake one for work."""
    owners = set((server / "users").glob("*/state/owner.json"))
    journal = server / "run/birth-fence.json"
    if not journal.exists():
        return not owners
    value = read_json(journal)
    if value.get("version") != 1 or value.get("transaction") != transaction:
        return False
    expected = set()
    for slot in value["slots"]:
        user = slot["user"]
        if str(UUID(user)) != user:
            return False
        p = server / "users" / user / "state/owner.json"
        info = p.lstat()
        marker = p / "reservation"
        token_info = marker.lstat()
        if (
            p.resolve() != p
            or not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
            or [info.st_dev, info.st_ino] != slot["identity"]
            or sorted(x.name for x in p.iterdir()) != ["reservation"]
            or not stat.S_ISREG(token_info.st_mode)
            or token_info.st_uid != os.getuid()
            or token_info.st_mode & 0o077
            or token_info.st_nlink != 1
            or token_info.st_size != len(transaction)
            or marker.is_symlink()
            or marker.read_text() != transaction
        ):
            return False
        expected.add(p)
    return owners == expected


def validate_executor(source, target, state=None):
    actual = Path(__file__)
    if state is not None and ".pyz/" in str(actual):
        artifact = Path(state["recovery"]["artifact"])
        if (
            Path(sys.argv[0]).absolute() != artifact
            or str(actual) != str(artifact) + "/resident/model_provider_upgrade.py"
            or c.digest(artifact) != state["recovery"]["sha256"]
        ):
            raise UpdateBlocked("other_model_recovery_version")
    elif actual.resolve() != source / MODULE or actual.read_bytes() != g.git_bytes(
        source, target, Path(MODULE).name
    ):
        raise UpdateBlocked("model_upgrade_executor_unverified")


def verify_supervisor(home, config):
    """The known immutable recovery peer must remain installed and scheduled."""
    plist = Path.home() / "Library/LaunchAgents" / (c.LABEL + ".plist")
    payload = plistlib.loads(plist.read_bytes())
    expected = [
        config["python"],
        str(home / "resident/controller.pyz"),
        "tick",
        "--home",
        str(home),
    ]
    if (
        payload.get("ProgramArguments") != expected
        or payload.get("Label") != c.LABEL
        or payload.get("WorkingDirectory") != str(home)
        or payload.get("StartInterval") != 60
        or payload.get("RunAtLoad") is not True
    ):
        raise UpdateBlocked("model_upgrade_supervisor_unknown")
    loaded = g.run(["/bin/launchctl", "print", f"gui/{os.getuid()}/{c.LABEL}"])
    if str(plist) not in loaded or str(home / "resident/controller.pyz") not in loaded:
        raise UpdateBlocked("model_upgrade_supervisor_unknown")
    return c.digest(plist)


def private_artifact(path):
    info = path.lstat()
    if (
        path.resolve() != path
        or not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_nlink != 1
        or info.st_mode & 0o077
    ):
        raise UpdateBlocked("model_upgrade_artifact_unsafe")


def activate_recovery_source(home: Path) -> None:
    """Bind app dependencies to the preserved Git source, never the replaced wheel."""
    if ".pyz/" not in str(__file__):
        return
    journal = home / "server/run/gateway-upgrade.json"
    if not journal.exists() and not journal.is_symlink():
        return
    try:
        state = g.read_upgrade_journal(journal)
        artifact = Path(sys.argv[0]).absolute()
        private_artifact(artifact)
        if (
            state.get("version") != 4
            or state.get("mode") not in {MODE, TRIAL_MODE, *ASSET_MODES}
            or str(artifact) != state["recovery"]["artifact"]
            or c.digest(artifact) != state["recovery"]["sha256"]
            or not re.fullmatch(r"[a-f0-9]{40}", state["target"])
        ):
            raise ValueError("recovery identity")
        with zipfile.ZipFile(artifact) as archive:
            if archive.getinfo("manifest.json").file_size > 65536:
                raise ValueError("manifest budget")
            manifest = json.loads(archive.read("manifest.json"))
        source = Path(state.get("executor_source", state["source"]))
        expected_source = (
            home
            / "resident/artifacts"
            / state["target"]
            / ("executor" if state.get("mode") == TRIAL_MODE else "source")
        )
        if (
            source != expected_source
            or Path(state["source"]) != home / "resident/artifacts" / state["target"] / "source"
            or not isinstance(manifest, dict)
            or set(manifest)
            != (
                {"target", "modules", "source", "executor_revision"}
                if state.get("mode") == TRIAL_MODE
                else {"target", "modules", "source"}
            )
            or manifest.get("target") != state["target"]
            or manifest.get("source") != str(source)
            or manifest.get("executor_revision", state["target"])
            != state.get("executor_revision", state["target"])
            or source.resolve(strict=True) != source
            or source.stat().st_uid != os.getuid()
        ):
            raise ValueError("source identity")
        c.clean(source, state.get("executor_revision", state["target"]))
        # Parent-only import path: child services must still load their installed wheel.
        product_source = Path(state["source"])
        c.clean(product_source, state["target"])
        sys.path.insert(0, str(product_source))
        log.info("model_recovery_source_verified target=%s", state["target"])
    except Exception as error:
        log.error("model_recovery_source_unavailable error_type=%s", type(error).__name__)
        raise UpdateBlocked("model_upgrade_recovery_source_unavailable") from error


def install_recovery(home, source, target, python, *, executor_revision=None):
    """Freeze all operator modules from Git, before either journal or service mutation."""
    g.run(["/usr/bin/env", "PATH=" + g.RECOVERY_PATH, "/usr/bin/git", "lfs", "version"])
    revision = executor_revision or target
    modules = g.module_blobs(source, revision)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(modules):
            z.writestr("resident/" + name, g.git_bytes(source, revision, name))
        z.writestr("__main__.py", ENTRY)
        z.writestr(
            "manifest.json",
            json.dumps(
                {
                    "target": target,
                    "modules": modules,
                    "source": str(source),
                    **({"executor_revision": executor_revision} if executor_revision else {}),
                },
                sort_keys=True,
            ),
        )
    raw = buffer.getvalue()
    checksum = hashlib.sha256(raw).hexdigest()
    label = "com.research-workbench.model-recovery." + checksum[:16]
    artifact = home / "server/run" / (label + ".pyz")
    if artifact.exists():
        private_artifact(artifact)
        if c.digest(artifact) != checksum:
            raise UpdateBlocked("model_upgrade_artifact_changed")
    else:
        with os.fdopen(
            os.open(artifact, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb"
        ) as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
    plist = Path.home() / "Library/LaunchAgents" / (label + ".plist")
    payload = {
        "Label": label,
        "ProgramArguments": [python, str(artifact), "recover", "--home", str(home)],
        "RunAtLoad": True,
        "StartInterval": 30,
        "WorkingDirectory": str(home),
        "StandardOutPath": str(home / "logs/model-recovery.log"),
        "StandardErrorPath": str(home / "logs/model-recovery-error.log"),
        "EnvironmentVariables": {"PATH": g.RECOVERY_PATH, "PYTHONDONTWRITEBYTECODE": "1"},
    }
    raw_plist = plistlib.dumps(payload)
    if plist.exists():
        private_artifact(plist)
        if plist.is_symlink() or plist.read_bytes() != raw_plist:
            raise UpdateBlocked("model_upgrade_recovery_job_changed")
    else:
        with os.fdopen(
            os.open(plist, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb"
        ) as f:
            f.write(raw_plist)
            f.flush()
            os.fsync(f.fileno())
    c.sync_directory(plist.parent)
    c.sync_directory(artifact.parent)
    try:
        g.run(["/bin/launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist)])
    except UpdateBlocked:
        loaded = g.run(["/bin/launchctl", "print", f"gui/{os.getuid()}/{label}"])
        if str(artifact) not in loaded or python not in loaded:
            raise UpdateBlocked("model_upgrade_recovery_job_unknown") from None
    return {
        "artifact": str(artifact),
        "sha256": checksum,
        "plist": str(plist),
        "plist_sha256": c.digest(plist),
        "modules": modules,
    }


def validate_state(home, state, *, executor_source=None):
    if str(UUID(state.get("transaction", ""))) != state.get("transaction"):
        raise UpdateBlocked("model_upgrade_journal_invalid")
    metadata = state.get("model_before")
    if not isinstance(metadata, dict) or set(metadata) != {
        "provider",
        "model",
        "credential_configured",
        "credential_storage",
    }:
        raise UpdateBlocked("model_upgrade_journal_invalid")
    if (
        state.get("version") != 4
        or state.get("mode") not in {MODE, TRIAL_MODE, *ASSET_MODES}
        or state.get("previous") != previous_for(state["mode"])
    ):
        raise UpdateBlocked("model_upgrade_journal_invalid")
    if not g.SHA.fullmatch(state.get("target", "")) or state.get("phase") not in (
        "prepared",
        "preparing",
        *FORWARD,
        *BACKWARD,
    ):
        raise UpdateBlocked("model_upgrade_journal_invalid")
    validate_asset_snapshot(state)
    source = Path(state["source"])
    validate_executor(
        (
            executor_source
            if executor_source is not None
            else Path(state.get("executor_source", source))
        ),
        state.get("executor_revision", state["target"]),
        state,
    )
    expected = home / "resident/artifacts" / state["target"] / "source"
    if (
        source != expected
        or source.resolve() != source
        or review(source, state["target"], state["mode"]) != state["reviewed"]
    ):
        raise UpdateBlocked("model_upgrade_source_changed")
    if c.git(source, "rev-parse", "--path-format=absolute", "--git-common-dir") != (
        validate_trial_rebind(state)["source_common"]
        if state.get("mode") == TRIAL_MODE
        else state["config"]["source_common"]
    ):
        raise UpdateBlocked("model_upgrade_source_changed")
    if (
        state["controller_sha256"] != CONTROLLER_SHA256
        or c.digest(home / "resident/controller.pyz") != CONTROLLER_SHA256
    ):
        raise UpdateBlocked("model_upgrade_controller_changed")
    if verify_supervisor(home, state["config"]) != state["supervisor_plist_sha256"]:
        raise UpdateBlocked("model_upgrade_supervisor_changed")
    recovery = state["recovery"]
    artifact = Path(recovery["artifact"])
    private_artifact(artifact)
    if artifact.parent != home / "server/run" or c.digest(artifact) != recovery["sha256"]:
        raise UpdateBlocked("model_upgrade_artifact_changed")
    module_source = Path(state.get("executor_source", source))
    module_revision = state.get("executor_revision", state["target"])
    if state.get("mode") == TRIAL_MODE:
        c.clean(module_source, module_revision)
        if (
            module_source != home / "resident/artifacts" / state["target"] / "executor"
            or c.git(module_source, "rev-parse", "--path-format=absolute", "--git-common-dir")
            != validate_trial_rebind(state)["source_common"]
        ):
            raise UpdateBlocked("trial_retirement_executor_changed")
        if not g.SHA.fullmatch(module_revision):
            raise UpdateBlocked("trial_retirement_executor_changed")
    with zipfile.ZipFile(artifact) as z:
        manifest = json.loads(z.read("manifest.json"))
        expected_manifest = {"target": state["target"], "modules": recovery["modules"]}
        if "source" in manifest or state["mode"] in {
            DOSSIERS_MODE,
            DISCOVERY_MODE,
            ETF_WEEKLY_V2_MODE,
            ETF_HISTORICAL_MODE,
            ETF_WEEKLY_ADMISSION_MODE,
            ETF_WEEKLY_ADMISSION_V2_MODE,
        }:
            expected_manifest["source"] = str(module_source)
        if state.get("mode") == TRIAL_MODE:
            expected_manifest["executor_revision"] = module_revision
        if manifest != expected_manifest or z.read("__main__.py").decode() != ENTRY:
            raise UpdateBlocked("model_upgrade_artifact_changed")
        if recovery["modules"] != g.module_blobs(module_source, module_revision):
            raise UpdateBlocked("model_upgrade_artifact_changed")
        for name in recovery["modules"]:
            if z.read("resident/" + name) != g.git_bytes(module_source, module_revision, name):
                raise UpdateBlocked("model_upgrade_artifact_changed")
    if c.digest(Path(recovery["plist"])) != recovery["plist_sha256"]:
        raise UpdateBlocked("model_upgrade_recovery_job_changed")
    for key in ("new_wheel", "old_wheel"):
        wheel = state[key]
        p = Path(wheel["path"])
        if not p.is_relative_to(home / "resident/artifacts") or c.digest(p) != wheel["sha256"]:
            raise UpdateBlocked("model_upgrade_wheel_changed")
    for role in ("primary", "gateway"):
        p = Path(state[role + "_project"])
        expected_project = (
            state["config"]["project"] if role == "primary" else state["gateway_config"]["project"]
        )
        if str(p) != expected_project:
            raise UpdateBlocked("model_upgrade_project_changed")
        if p.resolve() != p or [p.stat().st_dev, p.stat().st_ino] != state[role + "_identity"]:
            raise UpdateBlocked("model_upgrade_project_changed")
        verify_release_repository(state, role)
        actual = c.git(p, "rev-parse", "HEAD")
        if actual not in (previous_for(state["mode"]), state["target"]):
            raise UpdateBlocked("model_upgrade_revision_unknown")
        c.clean(p, actual)
    if c.digest(Path(state["gateway_plist"])) != state["gateway_plist_sha256"]:
        raise UpdateBlocked("model_upgrade_job_changed")
    if state.get("mode") == TRIAL_MODE and "trial_retirement" in state:
        from . import trial_retirement as trial

        trial.validate_record(state["trial_retirement"])
    validate_configuration(home, state)


def repository_identity(project, repository):
    """Release clones need not share the development checkout's Git directory."""
    common = Path(c.git(project, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    info = common.lstat()
    if common.resolve() != common or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise UpdateBlocked("model_upgrade_repository_unknown")
    origin = c.git(project, "remote", "get-url", "origin")
    if origin not in {
        f"git@github.com:{repository}.git",
        f"https://github.com/{repository}.git",
        f"https://github.com/{repository}",
    }:
        raise UpdateBlocked("model_upgrade_repository_unknown")
    after = common.lstat()
    if (info.st_dev, info.st_ino) != (after.st_dev, after.st_ino):
        raise UpdateBlocked("model_upgrade_repository_changed")
    return {"common": str(common), "identity": [info.st_dev, info.st_ino]}


def verify_release_repository(state, role):
    if (
        repository_identity(Path(state[role + "_project"]), state["config"]["repository"])
        != state[role + "_repository"]
    ):
        raise UpdateBlocked("model_upgrade_repository_changed")


def gateway_configuration(state, previous=False):
    old = state["gateway_config"]
    if previous:
        return old
    return {
        **old,
        "revision": state["target"],
        "binding": {**old["binding"], "revision": state["target"]},
    }


def target_manifest(state):
    manifest = {**state["manifest"], "code_commit": state["target"]}
    if state.get("mode") == ASSET_V5_MODE:
        manifest["web_lock_sha256"] = ASSET_V5_WEB_LOCK_SHA256
    elif state.get("mode") == ASSET_V6_MODE:
        manifest["web_lock_sha256"] = ASSET_V6_WEB_LOCK_SHA256
    elif state.get("mode") == ASSET_V7_MODE:
        manifest["web_lock_sha256"] = ASSET_V7_WEB_LOCK_SHA256
    elif state.get("mode") == ASSET_V9_MODE:
        manifest["web_lock_sha256"] = ASSET_V9_WEB_LOCK_SHA256
    elif state.get("mode") == ASSET_V8_MODE:
        manifest["web_lock_sha256"] = ASSET_V8_WEB_LOCK_SHA256
    elif state.get("mode") == MARKET_HISTORY_MODE:
        manifest["web_lock_sha256"] = MARKET_HISTORY_WEB_LOCK_SHA256
    elif state.get("mode") == MARKET_TERMINAL_MODE:
        manifest["web_lock_sha256"] = MARKET_TERMINAL_WEB_LOCK_SHA256
    elif state.get("mode") == MARKET_PREVIEW_MODE:
        manifest["web_lock_sha256"] = MARKET_PREVIEW_WEB_LOCK_SHA256
    elif state.get("mode") == MARKET_BREADTH_MODE:
        manifest["web_lock_sha256"] = MARKET_BREADTH_WEB_LOCK_SHA256
    if state.get("mode") == ETF_WEEKLY_ADMISSION_MODE:
        manifest["web_lock_sha256"] = ETF_WEEKLY_ADMISSION_WEB_LOCK_SHA256
    elif state.get("mode") == ETF_WEEKLY_ADMISSION_V2_MODE:
        manifest["web_lock_sha256"] = ETF_WEEKLY_ADMISSION_V2_WEB_LOCK_SHA256
    return manifest


def validate_configuration(home, state):
    actual = read_json(home / "resident/config.json")
    next_config = (
        validate_trial_rebind(state) if state.get("mode") == TRIAL_MODE else state["config"]
    )
    if actual not in (state["config"], next_config, {**next_config, "baseline": state["target"]}):
        raise UpdateBlocked("model_upgrade_configuration_changed")
    manifest = read_json(home / "install/manifest.json")
    if manifest not in (state["manifest"], target_manifest(state)):
        raise UpdateBlocked("model_upgrade_manifest_changed")
    gateway = read_json(home / "server/resident.json")
    if gateway not in (gateway_configuration(state, True), gateway_configuration(state)):
        raise UpdateBlocked("model_upgrade_gateway_configuration_changed")
    pending = home / "resident/transaction.json"
    if pending.exists():
        expected = {
            k: state[k]
            for k in ("previous", "target", "new_wheel", "old_wheel", "manifest", "proof")
        }
        if read_json(pending) != {**expected, "phase": "switching"}:
            raise UpdateBlocked("model_upgrade_primary_journal_changed")


def trial_primary_identity(home, expected, state):
    """Observe identity and readiness, preserving unknown trial activity as unknown."""
    c.clean(Path(state["primary_project"]), expected)
    observed = request_json(f"http://127.0.0.1:{state['config']['web_port']}/api/research/resident")
    if observed.get("enabled") is not True or observed.get("revision") != expected:
        raise UpdateBlocked("trial_retirement_primary_identity_unknown")
    return observed


def trial_rebind(source, config):
    """Only the explicitly authorized old Desktop to new Main Git identity pair."""
    old = Path("/Users/leon/Desktop/Projects/ResearchWorkbench/.git")
    new = Path("/Users/leon/Developer/ResearchWorkbench-main/.git")
    if config["source_common"] != str(old):
        raise UpdateBlocked("trial_retirement_source_transition_unknown")
    before = repository_identity(old.parent, config["repository"])
    after = repository_identity(source, config["repository"])
    if before["common"] != str(old) or after["common"] != str(new):
        raise UpdateBlocked("trial_retirement_source_transition_unknown")
    return {"before": before, "after": after}


def validate_trial_rebind(state):
    transition = state["source_transition"]
    if transition != trial_rebind(Path(transition["after"]["common"]).parent, state["config"]):
        raise UpdateBlocked("trial_retirement_source_transition_changed")
    for role, expected in transition.items():
        if (
            role not in {"before", "after"}
            or repository_identity(Path(expected["common"]).parent, state["config"]["repository"])
            != expected
        ):
            raise UpdateBlocked("trial_retirement_source_transition_changed")
    if (
        set(transition) != {"before", "after"}
        or transition["before"]["common"] != state["config"]["source_common"]
    ):
        raise UpdateBlocked("trial_retirement_source_transition_changed")
    return {**state["config"], "source_common": transition["after"]["common"]}


class Operations:
    def __init__(self, home, state, manager, lease, fence):
        self.home, self.state, self.manager, self.lease, self.fence = (
            home,
            state,
            manager,
            lease,
            fence,
        )
        self.root, self.server = home / "resident", home / "server"
        self._trial_owned_birth_journal = (
            copy.deepcopy(read_json(fence.journal))
            if state.get("mode") == TRIAL_MODE
            and isinstance(fence, BirthFence)
            and fence.owns_journal
            else None
        )
        self._trial_terminal_resume = False

    def capture_trial_processes(self, roles=("web", "runtime", "gateway")):
        from research_workbench_entrypoint.web_contract import probe_process, signature_matches_argv

        identities = dict(self.state.get("trial_processes", {}))
        original_identities = copy.deepcopy(identities)
        processes = {p.role: p for p in self.manager._processes()}
        probes = list(self.manager._service_probes())
        if {p.role for p in probes} != {"web", "runtime"}:
            raise UpdateBlocked("trial_retirement_process_unknown")
        for probe in probes:
            if probe.role not in roles:
                continue
            if (
                probe.process != "alive"
                or probe.ownership != "owned"
                or probe.port_state != "listening"
            ):
                raise UpdateBlocked("trial_retirement_process_unknown")
            original = self.manager._probe_state(processes[probe.role])
            observed = probe_process(probe.pid)
            if (
                original.state != "valid"
                or original.pid != probe.pid
                or observed.state != "alive"
                or observed.issue is not None
                or observed.started_at is None
                or not signature_matches_argv(original.signature, observed.argv)
            ):
                raise UpdateBlocked("trial_retirement_process_unknown")
            identities[probe.role] = self.trial_process_identity(probe.pid, observed)
        if "gateway" in roles:
            pid = g.job_pid()
            if (
                pid is None
                or not self.loaded_job_matches(g.job_state() or "")
                or g.listener_pids() != {pid}
            ):
                raise UpdateBlocked("trial_retirement_gateway_unknown")
            observed = probe_process(pid)
            expected = plistlib.loads(Path(self.state["gateway_plist"]).read_bytes())[
                "ProgramArguments"
            ]
            if tuple(expected[1:]) != (observed.argv or ())[1:] or g.native_image(
                pid
            ) != g.native_image(os.getpid()):
                raise UpdateBlocked("trial_retirement_gateway_argv_unknown")
            identities["gateway"] = self.trial_process_identity(pid, observed)
        changed_roles = {
            role for role in roles if identities.get(role) != original_identities.get(role)
        }
        self.state["trial_signal_intents"] = [
            value
            for value in self.state.get("trial_signal_intents", [])
            if value.split(":", 1)[0] not in changed_roles
        ]
        self.state["trial_processes"] = identities
        if self.lease is not None:
            self.checkpoint(self.state, self.state["phase"])

    def trial_process_identity(self, pid, observed):
        if (
            observed.state != "alive"
            or observed.issue is not None
            or observed.started_at is None
            or not observed.argv
            or int(g.run(["/bin/ps", "-p", str(pid), "-o", "uid="]).strip()) != os.getuid()
        ):
            raise UpdateBlocked("trial_retirement_process_unknown")
        full_signature = g.process(pid)
        if not full_signature:
            raise UpdateBlocked("trial_retirement_process_signature_unknown")
        return {
            "pid": pid,
            "birth": observed.started_at,
            "argv": list(observed.argv),
            "signature": full_signature,
            "image": str(g.native_image(pid)),
            "uid": os.getuid(),
        }

    def trial_unknown(self, role, observed, *, observed_pids=()):
        """Keep the original start intent and identity; never adopt a crash-window PID."""
        phase = self.state.get("phase", "unprepared")
        identity = self.state.get("trial_processes", {}).get(role, {})
        self.state["trial_unknown_observation"] = {
            "role": role,
            "phase": phase,
            "expected_pid": identity.get("pid"),
            "observed_pids": list(observed_pids),
            "observed_state": observed.state,
            "observed_birth": getattr(observed, "started_at", None),
            "observed_argv_sha256": hashlib.sha256(
                json.dumps(
                    list(getattr(observed, "argv", None) or ()), separators=(",", ":")
                ).encode()
            ).hexdigest(),
            "disposition": "UNKNOWN_MANUAL_RECONCILIATION_REQUIRED",
        }
        if self.fence is not None:
            self.fence.retain = True
        journal = self.server / "run/gateway-upgrade.json"
        if journal.is_file() and not journal.is_symlink():
            from . import trial_retirement as trial

            for path in (
                self.root / "supervisor.lock",
                self.root / "admission.lock",
                self.server / "run/operator.lock",
            ):
                trial._held(path)
            g.write_upgrade_journal(journal, self.state)
        log.error(
            "trial_retirement_process_unknown role=%s phase=%s manual_reconciliation_required=true",
            role,
            phase,
        )
        raise UpdateBlocked("trial_retirement_unknown:" + role + ":" + phase)

    def check_trial_processes(self):
        from research_workbench_entrypoint.web_contract import (
            PROCESS_START_TOLERANCE_SECONDS,
            listener_pids,
            probe_process,
            signature_matches_argv,
        )

        state = self.state
        if state.get("mode") != TRIAL_MODE or state.get("target") != TRIAL_PAYLOAD:
            raise UpdateBlocked("trial_retirement_profile_changed")
        validate_trial_rebind(state)
        home_info = self.home.lstat()
        if [home_info.st_dev, home_info.st_ino] != state["trial_authorization"]["home_identity"]:
            raise UpdateBlocked("trial_retirement_home_changed")
        g.no_private_processes(self.server)
        for role in ("primary", "gateway"):
            project = Path(state[role + "_project"])
            if [project.stat().st_dev, project.stat().st_ino] != state[role + "_identity"]:
                raise UpdateBlocked("trial_retirement_root_changed")
            verify_release_repository(state, role)
        if c.digest(Path(state["gateway_plist"])) != state["gateway_plist_sha256"]:
            raise UpdateBlocked("trial_retirement_gateway_job_changed")
        identities = state.get("trial_processes", {})
        if set(identities) != {"web", "runtime", "gateway"}:
            raise UpdateBlocked("trial_retirement_process_unknown")
        processes = {p.role: p for p in self.manager._processes()}
        for role, identity in identities.items():
            pid = identity["pid"]
            observed = probe_process(pid)
            if observed.state != "missing":
                try:
                    matches = self.trial_process_identity(pid, observed) == identity
                except (UpdateBlocked, OSError, ValueError):
                    matches = False
                if not matches:
                    self.trial_unknown(role, observed)
            if role == "gateway":
                listeners = g.listener_pids()
                loaded = g.job_state()
                if (
                    listeners - {pid}
                    or (observed.state != "missing" and (loaded is None or g.job_pid() != pid))
                    or (loaded is not None and not self.loaded_job_matches(loaded))
                    or g.job_pid() not in (None, pid)
                ):
                    self.trial_unknown(role, observed)
            else:
                process = processes[role]
                listeners = listener_pids(process.port)
                if listeners.state not in {"closed", "listening"} or set(listeners.pids) - {pid}:
                    self.trial_unknown(role, observed, observed_pids=listeners.pids)
                original = self.manager._probe_state(process)
                if original.pid not in (None, pid) or (
                    observed.state != "missing"
                    and (
                        original.state != "valid"
                        or original.started_at is None
                        or abs(original.started_at - identity["birth"])
                        > PROCESS_START_TOLERANCE_SECONDS
                        or not signature_matches_argv(original.signature, tuple(identity["argv"]))
                    )
                ):
                    self.trial_unknown(
                        role,
                        observed,
                        observed_pids=(() if original.pid is None else (original.pid,)),
                    )

    def assert_trial_control_scope(self):
        from . import trial_retirement as trial

        for path in (
            self.root / "supervisor.lock",
            self.root / "admission.lock",
            self.server / "run/operator.lock",
        ):
            trial._held(path)
        self.manager._assert_installation_scope(self.lease)
        if (
            self.fence is None
            or self.fence.retain is not True
            or not (self.root / "transaction.json").is_file()
        ):
            raise UpdateBlocked("trial_retirement_control_scope_required")
        validate_configuration(self.home, self.state)

    def trial_signal(self, role, number):
        from research_workbench_entrypoint.web_contract import probe_process

        self.assert_trial_control_scope()
        if number not in (signal.SIGTERM, signal.SIGKILL) or (
            number == signal.SIGKILL
            and role + ":" + str(signal.SIGTERM) not in self.state.get("trial_signal_intents", [])
        ):
            raise UpdateBlocked("trial_retirement_signal_sequence_invalid")
        self.check_trial_processes()
        identity = self.state["trial_processes"][role]
        if probe_process(identity["pid"]).state == "missing":
            return
        g.no_children(identity["pid"])
        key = role + ":" + str(number)
        attempted = self.state.setdefault("trial_signal_intents", [])
        if key in attempted:
            raise MaintenanceBusy("trial_retirement_signal_outcome_unknown")
        attempted.append(key)
        self.state["trial_outcome"] = "USER_AUTHORIZED_TRIAL_ABORT"
        self.checkpoint(self.state, self.state["phase"])
        self.assert_trial_control_scope()
        self.check_trial_processes()
        g.no_children(identity["pid"])
        os.kill(identity["pid"], number)
        log.warning("trial_retirement_authorized_abort role=%s signal=%s", role, number)

    def retire_trial_process(self, role):
        from research_workbench_entrypoint.web_contract import probe_process

        pid = self.state["trial_processes"][role]["pid"]
        if probe_process(pid).state == "missing":
            return
        if role + ":" + str(signal.SIGTERM) not in self.state.get("trial_signal_intents", []):
            self.trial_signal(role, signal.SIGTERM)
        for number, seconds in ((signal.SIGTERM, 10), (signal.SIGKILL, 5)):
            deadline = time.monotonic() + seconds
            while probe_process(pid).state != "missing":
                self.check_trial_processes()
                if time.monotonic() >= deadline:
                    break
                time.sleep(0.1)
            if probe_process(pid).state == "missing":
                return
            if number == signal.SIGTERM and role + ":" + str(signal.SIGKILL) not in self.state.get(
                "trial_signal_intents", []
            ):
                self.trial_signal(role, signal.SIGKILL)
        raise MaintenanceBusy("trial_retirement_process_not_retired")

    def stop_trial_gateway(self):
        self.assert_trial_control_scope()
        self.retire_trial_process("gateway")
        self.check_trial_processes()
        if g.job_state() is not None:
            self.assert_trial_control_scope()
            self.check_trial_processes()
            g.bootout_after_drain(Path(self.state["gateway_plist"]))
        if g.job_state() is not None or g.listener_pids():
            raise MaintenanceBusy("trial_retirement_gateway_not_retired")

    def stop_trial_primary(self):
        for role in ("web", "runtime"):
            self.retire_trial_process(role)
        from . import trial_retirement as trial

        trial.stopped(self)

    def verify_preservation(self, previous):
        if self.state.get("mode") != TRIAL_MODE:
            g.preserved(self.home, self.state["before"])
            return
        from . import trial_retirement as trial

        before = self.state["before"]
        record = self.state.get("trial_retirement")
        if record is not None:
            before = trial.preservation_baseline(before, record)
        discarded = record is not None and record.get("data_retirement_committed") is True
        expected = trial.preservation_delta(before) if discarded or not previous else before
        g.preserved(self.home, expected)
        asset = (
            record["stopped_asset_index"]
            if record is not None
            else self.state["asset_index_before"]
        )
        if asset_index_snapshot(self.home) != (
            trial.asset_delta(asset, record) if discarded or not previous else asset
        ):
            raise UpdateBlocked("trial_retirement_non_session_data_changed")

    def prepare_fence(self, state):
        """Publish recoverable ownership before any reservation side effects."""
        state["before"] = g.preservation(self.home)
        if state.get("mode") in ASSET_MODES or state.get("mode") == TRIAL_MODE:
            state["asset_index_before"] = asset_index_snapshot(self.home)
        state["phase"] = "preparing"
        verify_serve(state["config"]["private_origin"])
        g.write_upgrade_journal(self.server / "run/gateway-upgrade.json", state)
        verify_private_fence(state["config"]["private_origin"])

    def idle(self):
        """A proved stopped role is safe; any live/unknown native or Host work is not."""
        if self.state.get("mode") == TRIAL_MODE:
            self.check_trial_processes()
            return True  # Authorization to abort; never an assertion of idle.
        if self.state.get("mode") in {
            DISCOVERY_MODE,
            ASSET_V8_MODE,
            ASSET_V9_MODE,
            MARKET_PREVIEW_MODE,
            MARKET_BREADTH_MODE,
            ETF_HISTORICAL_MODE,
            ETF_WEEKLY_ADMISSION_MODE,
            ETF_WEEKLY_ADMISSION_V2_MODE,
        } and not discovery_background_idle(self.home):
            log.warning("discovery_deploy_background_not_quiet")
            return False
        g.no_private_processes(self.server)
        if not reserved_owners(self.server, self.state["transaction"]):
            return False
        probes = list(self.manager._service_probes())
        runtime = next(p for p in probes if p.role == "runtime")
        running = self.manager.status()["services"]
        if any(
            type(running[role][key]) is not bool
            for role in ("web", "runtime")
            for key in ("running", "healthy")
        ):
            return False
        if running["runtime"]["running"]:
            if not running["runtime"]["healthy"] or self.manager._active_research_read_only(
                runtime
            ):
                return False
        elif running["web"]["running"]:
            return False
        else:
            # No Host response is not an idle response. Only a journal already
            # fencing primary admission proves our own stopped role boundary.
            if not (self.root / "transaction.json").exists():
                return False
            if not ports_are_free(
                (self.state["config"]["web_port"], self.state["config"]["runtime_port"])
            ):
                return False
        if running["web"]["running"]:
            data = request_json(
                f"http://127.0.0.1:{self.state['config']['web_port']}/api/research/resident"
            )
            if (
                data.get("enabled") is not True
                or data.get("active") is not False
                or data.get("revision")
                not in (previous_for(self.state.get("mode", MODE)), self.state["target"])
            ):
                return False
        if running["web"]["running"] and self.state.get("mode") in {
            MARKET_GAPS_MODE,
            MARKET_HISTORY_MODE,
            MARKET_TERMINAL_MODE,
            MARKET_PREVIEW_MODE,
            MARKET_BREADTH_MODE,
            ASSET_V7_MODE,
            ASSET_V8_MODE,
            ASSET_V9_MODE,
            ETF_WEEKLY_MODE,
            DOSSIERS_MODE,
            DISCOVERY_MODE,
            ETF_WEEKLY_V2_MODE,
            ETF_HISTORICAL_MODE,
            ETF_WEEKLY_ADMISSION_MODE,
            ETF_WEEKLY_ADMISSION_V2_MODE,
        }:
            market = request_json(
                f"http://127.0.0.1:{self.state['config']['web_port']}/api/research/market"
            )
            if (
                not isinstance(market, dict)
                or not isinstance(market.get("inflight"), list)
                or market["inflight"]
            ):
                log.info("market_upgrade_collectors_active_or_unknown")
                return False
        index = read_business_index(self.home / "research-web/index.json")
        if self.state.get("mode") in ASSET_MODES and not asset_queries_idle(index):
            log.info("asset_upgrade_queries_active_or_unknown")
            return False
        rows = index.get("automation_runs")
        return isinstance(rows, dict) and all(
            isinstance(v, dict) and v.get("research_status") not in ("queued", "running")
            for v in rows.values()
        )

    def checkpoint(self, state, phase):
        state["phase"] = phase
        candidate = {
            k: state[k]
            for k in ("previous", "target", "new_wheel", "old_wheel", "manifest", "proof")
        }
        verify_serve(state["config"]["private_origin"])
        # The old controller may recover only the known previous primary. Its
        # private '/' health cannot pass or remove the root journal under this gate.
        g.write_upgrade_journal(self.server / "run/gateway-upgrade.json", state)
        self.fence.retain = True
        if phase == "prepared" or (
            not (self.root / "transaction.json").exists() and g.job_pid() is not None
        ):
            verify_private_fence(state["config"]["private_origin"])
        c.atomic(self.root / "transaction.json", {**candidate, "phase": "switching"})
        log.info("model_upgrade_checkpoint", extra={"phase": phase})

    def stop_gateway(self):
        if self.state.get("mode") == TRIAL_MODE:
            self.stop_trial_gateway()
            return
        if c.digest(Path(self.state["gateway_plist"])) != self.state["gateway_plist_sha256"]:
            raise UpdateBlocked("model_upgrade_job_changed")
        loaded = g.job_state()
        current = g.job_pid()
        if current is None:
            if g.listener_pids():
                raise MaintenanceBusy("model_upgrade_listener_unknown")
            if loaded is None:
                return
        if loaded is None or not self.loaded_job_matches(loaded):
            raise MaintenanceBusy("model_upgrade_process_unknown")
        g.no_private_processes(self.server)
        if current is not None:
            signature = g.process(current)
            if (
                signature is None
                or signature.split(maxsplit=5)[-1] != self.state["gateway_command"]
                or g.listener_pids() != {current}
                or g.native_image(current) != g.native_image(os.getpid())
            ):
                raise MaintenanceBusy("model_upgrade_process_unknown")
            g.no_children(current)
            g.graceful_drain(current, signature, self.state["gateway_command"])
        g.bootout_after_drain(Path(self.state["gateway_plist"]))
        deadline = time.monotonic() + 15
        while g.job_state() is not None or g.listener_pids():
            if time.monotonic() >= deadline:
                raise MaintenanceBusy("model_upgrade_gateway_not_retired")
            time.sleep(0.1)

    def loaded_job_matches(self, raw):
        fields = dict(
            re.findall(r"^\s*(path|program|working directory) = (.+)$", raw, re.MULTILINE)
        )
        payload = plistlib.loads(Path(self.state["gateway_plist"]).read_bytes())
        return (
            fields.get("path") == self.state["gateway_plist"]
            and fields.get("program") == payload["ProgramArguments"][0]
            and fields.get("working directory") == self.state["gateway_project"]
        )

    def install(self, previous):
        sha = previous_for(self.state.get("mode", MODE)) if previous else self.state["target"]
        for role in ("primary", "gateway"):
            p = Path(self.state[role + "_project"])
            verify_release_repository(self.state, role)
            actual = c.git(p, "rev-parse", "HEAD")
            if actual not in (previous_for(self.state.get("mode", MODE)), self.state["target"]):
                raise UpdateBlocked("model_upgrade_revision_unknown")
            c.clean(p, actual)
            c.git(p, "switch", "--detach", sha)
        wheel = self.state["old_wheel" if previous else "new_wheel"]
        c.run(
            [
                str(Path(self.state["primary_project"]) / ".venv/bin/python"),
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
        c.atomic(
            self.home / "install/manifest.json",
            (
                {**self.state["manifest"], "code_commit": sha}
                if previous
                else target_manifest(self.state)
            ),
        )

    def start_primary(self, previous):
        if self.state.get("mode") == TRIAL_MODE:
            from . import trial_retirement as trial

            trial.validate_retired(
                self.home, self.state["trial_retirement"], transaction=self.state["transaction"]
            )
        os.environ["RESEARCH_RESIDENT_REVISION"] = (
            previous_for(self.state.get("mode", MODE)) if previous else self.state["target"]
        )
        ports = self.state["config"]["web_port"], self.state["config"]["runtime_port"]
        with c.fixed_ports(self.manager, ports):
            self.manager._start_installed(self.lease, open_browser=False)
        if self.state.get("mode") == TRIAL_MODE:
            self.capture_trial_processes(("web", "runtime"))

    def start_gateway(self, previous):
        from app.research_web.multiuser.resident_binding import LegacyBinding

        config = dict(self.state["gateway_config"])
        if not previous:
            binding = LegacyBinding.discover(self.home, config["binding"]["primary_user_id"])
            if binding.verify().get("revision") != self.state["target"]:
                raise UpdateBlocked("model_upgrade_binding_unverified")
            config.update(
                revision=self.state["target"],
                binding=json.loads(json.dumps(binding.public_config())),
            )
        if config != gateway_configuration(self.state, previous):
            raise UpdateBlocked("model_upgrade_binding_changed")
        c.atomic(self.server / "resident.json", config)
        if self.state.get("mode") == TRIAL_MODE:
            from . import trial_retirement as trial

            trial.validate_retired(
                self.home, self.state["trial_retirement"], transaction=self.state["transaction"]
            )
        self.fence.release_database()
        BirthFence.recover(self.server, expected=self.state["transaction"])
        g.bootstrap(Path(self.state["gateway_plist"]))
        g.wait_health(config, fenced=True)
        if self.state.get("mode") == TRIAL_MODE:
            self.capture_trial_processes(("gateway",))

    def verify(self, previous):
        sha = previous_for(self.state.get("mode", MODE)) if previous else self.state["target"]
        if self.state.get("mode") == TRIAL_MODE:
            trial_primary_identity(self.home, sha, self.state)
        else:
            verify_primary(self.home, sha, self.state.get("mode", MODE))
        g.health(read_json(self.server / "resident.json"), fenced=True)
        remote = request_json(self.state["config"]["private_origin"] + "/api/server/health")
        if remote.get("revision") != sha or remote.get("deployment_fenced") is not True:
            raise UpdateBlocked("model_upgrade_private_health_failed")
        self.verify_preservation(previous)
        verify_asset_index(self.home, self.state)
        if model_metadata(self.state["config"]) != self.state["model_before"]:
            raise UpdateBlocked("model_upgrade_credential_metadata_changed")
        if not previous:
            profiles = request_json(
                f"http://127.0.0.1:{self.state['config']['web_port']}/api/research/model-profiles"
            )
            active = [v for v in profiles.get("items", []) if v.get("active") is True]
            if (
                len(active) != 1
                or active[0].get("provider") != self.state["model_before"]["provider"]
                or active[0].get("model") != self.state["model_before"]["model"]
                or active[0].get("credential_configured")
                != self.state["model_before"]["credential_configured"]
            ):
                raise UpdateBlocked("model_upgrade_profile_projection_failed")

    def action(self, name, state):
        if name in ("stop_gateway", "rollback_gateway"):
            self.stop_gateway()
        elif name in ("stop_primary", "rollback_primary"):
            if self.idle() is not True:
                raise MaintenanceBusy("research_active_or_unknown")
            if state.get("mode") == TRIAL_MODE:
                self.stop_trial_primary()
            else:
                self.manager._stop_locked()
        elif name in ("activate_sources_and_wheel", "restore_sources_and_wheel"):
            if state.get("mode") == TRIAL_MODE:
                from . import trial_retirement as trial

                # Code rollback retains the user's committed discard intent.
                # Manual original-byte data restore is a separate offline action.
                if "trial_retirement" not in state:
                    trial.prepare(
                        self,
                        state["trial_authorization"],
                        state["trial_authorization_sha256"],
                        Path(state["trial_backup_parent"]),
                    )
                trial.apply(self)
                trial.validate_retired(
                    self.home, state["trial_retirement"], transaction=state["transaction"]
                )
            self.install(name.startswith("restore"))
            if state.get("mode") == TRIAL_MODE:
                c.atomic(
                    self.root / "config.json",
                    state["config"] if name.startswith("restore") else validate_trial_rebind(state),
                )
        elif name in ("start_primary", "start_previous_primary"):
            self.start_primary("previous" in name)
        elif name in ("start_gateway", "start_previous_gateway"):
            self.start_gateway("previous" in name)
        elif name in ("verify_target", "verify_previous"):
            self.verify(name.endswith("previous"))
        else:
            raise UpdateBlocked("model_upgrade_action_unknown")

    def archive_trial_completion(self, state, result):
        """Publish an immutable full receipt before removing recoverable ownership."""
        from . import trial_discard_backup as backup
        from . import trial_retirement as trial

        if state.get("mode") != TRIAL_MODE or result["status"] not in {"deployed", "rolled_back"}:
            raise UpdateBlocked("trial_retirement_completion_scope_invalid")
        transaction = state["transaction"]
        if str(UUID(transaction)) != transaction:
            raise UpdateBlocked("trial_retirement_completion_transaction_invalid")
        trial.validate_retired(self.home, state["trial_retirement"], transaction=transaction)
        self.verify_preservation(result["status"] == "rolled_back")
        retirement = state["trial_retirement"]
        point = Path(retirement["backup"]["backup"])
        if point.parent != Path(state["trial_backup_parent"]) or not re.fullmatch(
            r"[a-f0-9]{32}", point.name
        ):
            raise UpdateBlocked("trial_retirement_completion_backup_scope_invalid")
        saved_raw, _ = backup._read(point / "manifest.json", backup.RECORD_LIMIT)
        if hashlib.sha256(saved_raw).hexdigest() != retirement["backup"]["manifest_sha256"]:
            raise UpdateBlocked("trial_retirement_completion_backup_changed")
        saved = json.loads(saved_raw)
        allowed = {"server/accounts.sqlite3", "server/resident.json"}
        for row in retirement["plan"]:
            if row["index_present"]:
                allowed.add(row["index"])
            if row["catalog_present"]:
                allowed.add(str(Path(row["index"]).parent / "report-workflows/catalog.json"))
        if set(saved["files"]) != allowed:
            raise UpdateBlocked("trial_retirement_completion_backup_changed")
        total = 0
        for relative, expected in saved["files"].items():
            path = Path(relative)
            if path.is_absolute() or ".." in path.parts:
                raise UpdateBlocked("trial_retirement_completion_backup_scope_invalid")
            data, actual = backup._read(point / path, backup.MAX_ASSET_INDEX_BYTES)
            total += len(data)
            if total > backup.MAX_TOTAL_BYTES or any(
                actual[key] != expected[key] for key in ("sha256", "size", "mode")
            ):
                raise UpdateBlocked("trial_retirement_completion_backup_changed")
        receipt = {
            "version": 1,
            "kind": "completed-trial-retirement",
            "mode": TRIAL_MODE,
            "transaction": transaction,
            "previous": state["previous"],
            "payload": state["target"],
            "executor_revision": state["executor_revision"],
            "result": result,
            "manual_data_restore": "OFFLINE_FENCED_ONLY_NO_SERVICE_START",
            "journal": {
                key: value for key, value in state.items() if key != "trial_terminal_intent"
            },
        }
        raw = json.dumps(
            receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode()
        if len(raw) > g.JOURNAL_MAX_BYTES + 65536:
            raise UpdateBlocked("trial_retirement_completion_oversized")
        name = transaction + ".json"
        intent = {"result": result["status"], "sha256": hashlib.sha256(raw).hexdigest()}
        previous_intent = state.get("trial_terminal_intent")
        if previous_intent is not None and previous_intent != intent:
            raise UpdateBlocked("trial_retirement_terminal_intent_conflict")
        if previous_intent is None:
            state["trial_terminal_intent"] = intent
            # This immutable-byte commitment precedes publishing the receipt.
            g.write_upgrade_journal(self.server / "run/gateway-upgrade.json", state)
        try:
            with backup._anchored_parent(self.root) as (parent, _chain):
                try:
                    os.mkdir("trial-retirements", mode=0o700, dir_fd=parent)
                    os.fsync(parent)
                except FileExistsError:
                    pass
                directory = backup._open_child(parent, "trial-retirements", create=False)
                temporary, fd = ".receipt-" + uuid4().hex, None
                identity = None
                try:
                    try:
                        existing, mode = backup._read_at(directory, name, len(raw) + 1)
                    except FileNotFoundError:
                        fd = os.open(
                            temporary,
                            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                            0o600,
                            dir_fd=directory,
                        )
                        opened = os.fstat(fd)
                        identity = (opened.st_dev, opened.st_ino)
                        view = memoryview(raw)
                        while view:
                            count = os.write(fd, view)
                            if count <= 0:
                                raise UpdateBlocked("trial_retirement_completion_write_failed")
                            view = view[count:]
                        os.fchmod(fd, 0o600)
                        os.fsync(fd)
                        try:
                            os.link(
                                temporary,
                                name,
                                src_dir_fd=directory,
                                dst_dir_fd=directory,
                                follow_symlinks=False,
                            )
                        except FileExistsError:
                            pass
                        info = os.stat(temporary, dir_fd=directory, follow_symlinks=False)
                        if (info.st_dev, info.st_ino) != identity:
                            raise UpdateBlocked("trial_retirement_completion_changed")
                        os.unlink(temporary, dir_fd=directory)
                        identity = None
                        os.fsync(directory)
                        existing, mode = backup._read_at(directory, name, len(raw) + 1)
                    info = os.stat(name, dir_fd=directory, follow_symlinks=False)
                    if (
                        existing != raw
                        or mode != 0o600
                        or info.st_uid != os.getuid()
                        or info.st_nlink != 1
                    ):
                        raise UpdateBlocked("trial_retirement_completion_conflict")
                    final_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
                    try:
                        final_info = os.fstat(final_fd)
                        if (final_info.st_dev, final_info.st_ino) != (info.st_dev, info.st_ino):
                            raise UpdateBlocked("trial_retirement_completion_changed")
                        os.fsync(final_fd)
                    finally:
                        os.close(final_fd)
                    os.fsync(directory)
                    os.fsync(parent)
                    linked = os.stat("trial-retirements", dir_fd=parent, follow_symlinks=False)
                    opened = os.fstat(directory)
                    if (linked.st_dev, linked.st_ino) != (opened.st_dev, opened.st_ino):
                        raise UpdateBlocked("trial_retirement_completion_directory_changed")
                finally:
                    if fd is not None:
                        os.close(fd)
                    if identity is not None:
                        current = os.stat(temporary, dir_fd=directory, follow_symlinks=False)
                        if (current.st_dev, current.st_ino) == identity:
                            os.unlink(temporary, dir_fd=directory)
                            os.fsync(directory)
                    os.close(directory)
        except (OSError, backup.TrialBackupBlocked) as error:
            log.error(
                "trial_retirement_completion_archive_failed error_type=%s", type(error).__name__
            )
            raise UpdateBlocked("trial_retirement_completion_archive_failed") from error
        log.info("trial_retirement_completion_archived transaction=%s", transaction)
        return {
            "path": str(self.root / "trial-retirements" / name),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }

    def release_trial_terminal_fence(self, state):
        """Release only the exact BirthFence acquired by this controlled invocation."""
        fence = self.fence
        expected = self._trial_owned_birth_journal
        if (
            not isinstance(fence, BirthFence)
            or not fence.owns_journal
            or fence.root != self.server
            or fence.transaction != state["transaction"]
            or expected is None
            or read_json(fence.journal) != expected
        ):
            raise UpdateBlocked("trial_retirement_terminal_fence_changed")
        try:
            fence.release_database()
            fence.retain = False
            fence.__exit__(None, None, None)
            if fence.journal.exists() or fence.journal.is_symlink():
                raise UpdateBlocked("trial_retirement_terminal_fence_not_released")
            for slot in expected["slots"]:
                for path in (
                    self.server / "run" / slot["stage"],
                    self.server / "users" / slot["user"] / "state/owner.json",
                ):
                    if path.exists() or path.is_symlink():
                        raise UpdateBlocked("trial_retirement_terminal_fence_not_released")
            fence.owns_journal = False
        except Exception:
            fence.retain = True
            log.exception("trial_retirement_terminal_fence_release_failed")
            raise

    def recover_trial_terminal(self, state):
        """An intended terminal result resumes finalization, never reverse actions."""
        from . import trial_discard_backup as backup

        transaction = state.get("transaction")
        if not isinstance(transaction, str):
            return None
        if str(UUID(transaction)) != transaction:
            raise UpdateBlocked("trial_retirement_completion_transaction_invalid")
        path = self.root / "trial-retirements" / (transaction + ".json")
        intent = state.get("trial_terminal_intent")
        present = path.exists() or path.is_symlink()
        if intent is None and not present:
            return None
        if (
            not isinstance(intent, dict)
            or set(intent) != {"result", "sha256"}
            or intent["result"] not in {"deployed", "rolled_back"}
            or not re.fullmatch(r"[a-f0-9]{64}", intent["sha256"])
        ):
            raise UpdateBlocked("trial_retirement_terminal_intent_invalid")
        if self.fence is not None:
            self.fence.retain = True
        if present:
            raw, identity = backup._read(path, g.JOURNAL_MAX_BYTES + 65536)
            if (
                identity["mode"] != 0o600
                or path.lstat().st_nlink != 1
                or hashlib.sha256(raw).hexdigest() != intent["sha256"]
            ):
                raise UpdateBlocked("trial_retirement_terminal_receipt_changed")
            receipt = json.loads(raw)
            expected_state = {
                key: value for key, value in state.items() if key != "trial_terminal_intent"
            }
            if (
                receipt.get("mode") != TRIAL_MODE
                or receipt.get("transaction") != transaction
                or receipt.get("journal") != expected_state
                or receipt.get("executor_revision") != state["executor_revision"]
                or receipt.get("payload") != state["target"]
                or receipt.get("previous") != state["previous"]
                or receipt.get("result", {}).get("status") != intent["result"]
            ):
                raise UpdateBlocked("trial_retirement_terminal_receipt_changed")
        # Re-verify the exact running revision and fenced private health before
        # touching final records. This performs no stop, spawn, model or restore.
        self.verify(intent["result"] == "rolled_back")
        self._trial_terminal_resume = True
        try:
            return self.finish(state, intent["result"])
        finally:
            self._trial_terminal_resume = False

    def finish(self, state, result):
        validate_configuration(self.home, state)
        verify_asset_index(self.home, state)
        if result == "deployed":
            candidate = {
                k: state[k]
                for k in ("previous", "target", "new_wheel", "old_wheel", "manifest", "proof")
            }
            candidate["compatibility_review"] = {
                "profile": state.get("mode", MODE),
                "blobs": state["reviewed"],
            }
            c.atomic(self.root / "accepted.json", candidate)
            c.atomic(self.root / "candidate.json", candidate)
            c.atomic(
                self.root / "baseline-reviews" / (state["target"] + ".json"),
                candidate["compatibility_review"],
            )
            next_config = (
                validate_trial_rebind(state) if state.get("mode") == TRIAL_MODE else state["config"]
            )
            c.atomic(self.root / "config.json", {**next_config, "baseline": state["target"]})
        else:
            c.atomic(self.root / "config.json", state["config"])
            c.atomic(self.root / "accepted.json", state["accepted"])
            c.atomic(self.root / "candidate.json", state["candidate_before"])
            c.atomic(self.root / "quarantine.json", {"sha": state["target"]})
        record = {
            "status": result,
            "target": state["target"],
            "revision": (
                state["target"] if result == "deployed" else previous_for(state.get("mode", MODE))
            ),
            "preserved": state.get("mode") != TRIAL_MODE,
            **(
                {
                    "manual_reconciliation_limit": "crash_after_spawn_before_durable_pid",
                    "preservation": "accounts_models_non_session_data",
                    "trial_outcome": "USER_AUTHORIZED_TRIAL_ABORT",
                    "native_cleanup": "UNKNOWN",
                }
                if state.get("mode") == TRIAL_MODE
                else {}
            ),
        }
        if state.get("mode") == TRIAL_MODE:
            record["trial_completion_receipt"] = self.archive_trial_completion(state, record.copy())
            if self._trial_terminal_resume:
                self.release_trial_terminal_fence(state)
        c.atomic(self.server / "run/model-upgrade-result.json", record)
        c.record(self.root, result, deployed=record["revision"])
        log.info("model_upgrade_finished", extra={"result": result})
        if state.get("mode") == TRIAL_MODE:
            (self.root / "transaction.json").unlink(missing_ok=True)
        else:
            (self.root / "transaction.json").unlink()
        c.sync_directory(self.root)
        if state.get("mode") == TRIAL_MODE:
            (self.server / "run/gateway-upgrade.json").unlink(missing_ok=True)
        else:
            (self.server / "run/gateway-upgrade.json").unlink()
        c.sync_directory(self.server / "run")
        return record


def _weekly_digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def _weekly_private_json(path):
    """Bind a bounded private single-link file to its checked inode, without following links."""
    from app.research_web.report_workflows.legacy_monitoring import validate_existing_path

    path = validate_existing_path(path, private=True)
    before = path.stat(follow_symlinks=False)
    if stat.S_IMODE(before.st_mode) != 0o600 or before.st_size > 256 * 1024:
        raise UpdateBlocked("weekly_monitoring_file_unsafe")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(descriptor)
        raw = os.read(descriptor, 256 * 1024 + 1)
        after = path.stat(follow_symlinks=False)
        identity = lambda item: (
            item.st_dev,
            item.st_ino,
            item.st_size,
            item.st_mtime_ns,
            item.st_ctime_ns,
            item.st_uid,
            item.st_mode,
            item.st_nlink,
        )
        if (
            identity(before) != identity(opened)
            or identity(opened) != identity(after)
            or len(raw) != before.st_size
        ):
            raise UpdateBlocked("weekly_monitoring_file_changed")

        def unique(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError("duplicate JSON field")
                value[key] = item
            return value

        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
        if not isinstance(value, dict):
            raise UpdateBlocked("weekly_monitoring_file_invalid")
        return value
    finally:
        os.close(descriptor)


def _weekly_publish(path, value):
    """Publish an immutable decision record under the operator lock, then fsync its directory."""
    from app.research_web.report_workflows.legacy_monitoring import validate_existing_path

    validate_existing_path(path.parent, directory=True, private=True)
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    if len(raw) > 256 * 1024:
        raise UpdateBlocked("weekly_monitoring_record_oversize")
    if path.exists() or path.is_symlink():
        if _weekly_private_json(path) != value:
            raise UpdateBlocked("weekly_monitoring_record_changed")
        c.sync_directory(path.parent)
        return
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        # The original operator EX lock serializes publication in this private directory.
        if path.exists() or path.is_symlink():
            raise UpdateBlocked("weekly_monitoring_record_changed")
        os.replace(temporary, path)
        c.sync_directory(path.parent)
        if _weekly_private_json(path) != value:
            raise UpdateBlocked("weekly_monitoring_record_changed")
    finally:
        if temporary.exists() or temporary.is_symlink():
            temporary.unlink()


def _weekly_action(path):
    from app.research_web.report_workflows.legacy_monitoring import LegacyMonitoringExpectation

    value = _weekly_private_json(path)
    keys = {
        "run_id",
        "session_id",
        "version",
        "owner_id",
        "run_sha256",
        "context_sha256",
        "snapshot_sha256",
        "contract_sha256",
    }
    expected = value.get("expected_identity")
    if (
        set(value) != {"schema_version", "profile", "operation_id", "expected_identity"}
        or type(value.get("schema_version")) is not int
        or value["schema_version"] != 1
        or value.get("profile") != "weekly-legacy-monitoring-v1"
        or value.get("operation_id") != WEEKLY_OPERATION_ID
        or not isinstance(expected, dict)
        or set(expected) != keys
        or type(expected.get("version")) is not int
        or expected["version"] < 1
        or any(not isinstance(expected[key], str) for key in keys - {"version"})
        or not re.fullmatch(r"[a-f0-9]{32}", expected["run_id"])
        or any(
            not re.fullmatch(r"[a-f0-9]{64}", expected[key])
            for key in keys
            if key.endswith("sha256")
        )
    ):
        raise UpdateBlocked("weekly_monitoring_action_invalid")
    try:
        if any(str(UUID(expected[key])) != expected[key] for key in ("owner_id", "session_id")):
            raise ValueError("UUID")
    except ValueError as error:
        raise UpdateBlocked("weekly_monitoring_action_invalid") from error
    if _weekly_digest(value) != WEEKLY_ACTION_SHA256:
        raise UpdateBlocked("weekly_monitoring_action_unreviewed")
    return value, LegacyMonitoringExpectation(**expected)


async def _weekly_native_catalog_idle(manager):
    """Read every Native parent and its catalog; reject missing, duplicate and orphan children."""
    from app.research_web.client import DSHClient

    async with DSHClient(
        f"http://127.0.0.1:{manager.runtime_port}", auth_path=manager._runtime_auth_path()
    ) as client:
        native = await client.rpc("session.list", {})
        items = native.get("items")
        if not isinstance(items, list):
            raise UpdateBlocked("weekly_monitoring_native_unknown")
        rows = {}
        for row in items:
            if (
                not isinstance(row, dict)
                or not isinstance(row.get("sessionId"), str)
                or not row["sessionId"]
                or row["sessionId"] in rows
                or row.get("running") is not False
            ):
                raise UpdateBlocked("weekly_monitoring_native_unknown")
            rows[row["sessionId"]] = row
        linked = set()
        for sid, row in rows.items():
            if row.get("origin") == "subagent":
                continue
            children = await client.rpc(
                "subagent.list", {"parentSessionId": sid, "activityOnly": True}
            )
            entries = children.get("entries")
            if not isinstance(entries, list):
                raise UpdateBlocked("weekly_monitoring_native_unknown")
            for child in entries:
                if (
                    not isinstance(child, dict)
                    or child.get("kind") != "child"
                    or child.get("activity") != "inactive"
                    or child.get("mode") not in {"one-shot", "continuable", "unknown"}
                ):
                    raise UpdateBlocked("weekly_monitoring_native_unknown")
                cid = child.get("id")
                live = rows.get(cid) if isinstance(cid, str) else None
                if (
                    cid in linked
                    or not live
                    or cid == sid
                    or live.get("parentSessionId") != sid
                    or live.get("origin") != "subagent"
                ):
                    raise UpdateBlocked("weekly_monitoring_native_unknown")
                linked.add(cid)
        for sid, row in rows.items():
            if (row.get("origin") == "subagent" or row.get("parentSessionId")) and (
                sid not in linked
                or row.get("parentSessionId") not in rows
                or row.get("origin") != "subagent"
            ):
                raise UpdateBlocked("weekly_monitoring_native_unknown")


def _weekly_native_idle(manager):
    probes = [probe for probe in manager._service_probes() if probe.role == "runtime"]
    if len(probes) != 1 or manager._active_research_read_only(probes[0]) != []:
        raise UpdateBlocked("weekly_monitoring_native_unknown")
    asyncio.run(asyncio.wait_for(_weekly_native_catalog_idle(manager), timeout=60))


def _weekly_record_presence(intent_path, receipt_path):
    """Reject linked or orphan records before any domain action or intent publication."""
    intent_present = intent_path.exists() or intent_path.is_symlink()
    receipt_present = receipt_path.exists() or receipt_path.is_symlink()
    if intent_path.is_symlink() or receipt_path.is_symlink():
        raise UpdateBlocked("weekly_monitoring_record_unsafe")
    if receipt_present and not intent_present:
        raise UpdateBlocked("weekly_monitoring_intent_missing")
    return intent_present, receipt_present


def weekly_monitoring_bridge(home, state, manager, action_path=None, *, recovering=False):
    """End only the sealed legacy wait, retaining its unknown outcome across code rollback.

    Called under supervisor, admission and operator EX locks, before the original
    Operations.idle. Catalog locks are released before any Host GET.
    """
    from app.research_web.report_workflows.catalog import ReportWorkflowService
    from app.research_web.report_workflows.owner import resolve_primary_owner

    root = home / "research-web"
    folder = home / "server/run"
    intent_path = folder / "weekly-monitoring-intent.json"
    receipt_path = folder / "weekly-monitoring-receipt.json"
    intent_present, receipt_present = _weekly_record_presence(intent_path, receipt_path)
    existing_receipt = _weekly_private_json(receipt_path) if receipt_present else None
    if recovering:
        intent = _weekly_private_json(intent_path)
        action_path = Path(intent["action_path"])
    action, expected = _weekly_action(action_path)
    action_info = Path(action_path).stat(follow_symlinks=False)
    identity = root.stat(follow_symlinks=False)
    binding = {
        "schema_version": 1,
        "profile": ETF_WEEKLY_ADMISSION_MODE,
        "operation_id": WEEKLY_OPERATION_ID,
        "action_sha256": WEEKLY_ACTION_SHA256,
        "action_path": str(Path(action_path).absolute()),
        "action_identity": [
            action_info.st_dev,
            action_info.st_ino,
            action_info.st_size,
            action_info.st_mtime_ns,
        ],
        "root": str(root),
        "root_identity": [identity.st_dev, identity.st_ino],
        "expected_identity": action["expected_identity"],
    }
    owner_service = SimpleNamespace(
        store=SimpleNamespace(root=root), report_primary_owner_root=home / "server"
    )
    owner_check = lambda owner: resolve_primary_owner(owner_service, owner)
    owner_check(expected.owner_id)
    if not reserved_owners(home / "server", state["transaction"]):
        raise UpdateBlocked("weekly_monitoring_owner_unknown")
    catalog = ReportWorkflowService.open_for_maintenance(root)
    with catalog._exclusive():
        row = copy.deepcopy(catalog.data["runs"].get(expected.run_id))
    if existing_receipt is not None:
        # A receipt can only describe an already committed after-state. Validate
        # it before the before-state CAS; malformed records cannot authorize it.
        observed_receipt = {
            **binding,
            "before_sha256": expected.run_sha256,
            "after_sha256": _weekly_digest(row),
            "domain_receipt": row.get("monitoring_end_receipt") if isinstance(row, dict) else None,
            "preserve_unknown": True,
            "native_cancelled": False,
        }
        if (
            existing_receipt != observed_receipt
            or row.get("status") != "cancelled"
            or row.get("monitoring_disposition") != "ended_by_user"
            or row.get("research_submission_state") != "unknown"
        ):
            raise UpdateBlocked("weekly_monitoring_receipt_changed")
    if intent_present:
        intent = _weekly_private_json(intent_path)
        if (
            set(intent) != set(binding) | {"before"}
            or any(intent.get(key) != value for key, value in binding.items())
            or _weekly_digest(intent["before"]) != expected.run_sha256
        ):
            raise UpdateBlocked("weekly_monitoring_intent_changed")
        if not recovering:
            # A prior rename may have committed before its directory fsync
            # returned. Confirm durable intent before permitting the CAS.
            _weekly_publish(intent_path, intent)
    else:
        if recovering or receipt_present or _weekly_digest(row) != expected.run_sha256:
            raise UpdateBlocked("weekly_monitoring_intent_missing")
        # Validate domain contract and Native before publishing any intent.
        catalog.end_legacy_monitoring(
            expected, operation_id=WEEKLY_OPERATION_ID, owner_check=owner_check, apply=False
        )
        _weekly_native_idle(manager)
        intent = {**binding, "before": row}
        _weekly_publish(intent_path, intent)
    if recovering:
        if not receipt_present:
            raise UpdateBlocked("weekly_monitoring_receipt_missing")
        domain_receipt = catalog.end_legacy_monitoring(
            expected, operation_id=WEEKLY_OPERATION_ID, owner_check=owner_check, apply=False
        )
        if domain_receipt.get("status") == "dry_run":
            raise UpdateBlocked("weekly_monitoring_recovery_before_action")
    else:
        _weekly_native_idle(manager)
        again, _ = _weekly_action(action_path)
        current_action = Path(action_path).stat(follow_symlinks=False)
        current_root = root.stat(follow_symlinks=False)
        if (
            again != action
            or [
                current_action.st_dev,
                current_action.st_ino,
                current_action.st_size,
                current_action.st_mtime_ns,
            ]
            != binding["action_identity"]
            or [current_root.st_dev, current_root.st_ino] != binding["root_identity"]
        ):
            raise UpdateBlocked("weekly_monitoring_identity_changed")
        domain_receipt = catalog.end_legacy_monitoring(
            expected,
            operation_id=WEEKLY_OPERATION_ID,
            owner_check=owner_check,
            apply=_weekly_digest(row) == expected.run_sha256,
        )
        c.sync_directory(catalog.root)
    with catalog._exclusive():
        after = copy.deepcopy(catalog.data["runs"].get(expected.run_id))
    wanted = {
        **intent["before"],
        "status": "cancelled",
        "monitoring_disposition": "ended_by_user",
        "monitoring_end_receipt": domain_receipt,
    }
    if (
        after != wanted
        or after.get("research_submission_state") != "unknown"
        or domain_receipt.get("native_cancelled") is not False
    ):
        raise UpdateBlocked("weekly_monitoring_after_changed")
    receipt = {
        **binding,
        "before_sha256": expected.run_sha256,
        "after_sha256": _weekly_digest(after),
        "domain_receipt": domain_receipt,
        "preserve_unknown": True,
        "native_cancelled": False,
    }
    if recovering:
        if _weekly_private_json(receipt_path) != receipt:
            raise UpdateBlocked("weekly_monitoring_receipt_changed")
        # Recovery may own a deliberately stopped Host. Disk validation must
        # not require HTTP or replay the independently committed decision.
        return
    else:
        try:
            _weekly_publish(receipt_path, receipt)
        except OSError as error:
            raise UpdateBlocked("weekly_monitoring_action_committed_receipt_pending") from error
    # The catalog lock is no longer held. GET refreshes the old Host's cached row.
    observed = request_json(
        f"http://127.0.0.1:{state['config']['web_port']}/api/research/report-runs/{expected.run_id}"
    )
    from app.research_web.report_workflows.runtime import _public_metadata

    public_after = _public_metadata({key: value for key, value in after.items() if key != "path"})
    if observed != public_after:
        raise UpdateBlocked("weekly_monitoring_host_refresh_unknown")
    log.info("weekly_monitoring_bridge_verified preserve_unknown=true native_cancelled=false")


def operate(
    home,
    source=None,
    *,
    recovering=False,
    mode=MODE,
    end_weekly_waiting=False,
    weekly_monitoring_action=None,
    trial_manifest=None,
    trial_manifest_sha256=None,
    trial_backup_parent=None,
):
    if (end_weekly_waiting or weekly_monitoring_action is not None) and (
        recovering or mode not in {ETF_WEEKLY_ADMISSION_MODE, ETF_WEEKLY_ADMISSION_V2_MODE}
    ):
        raise UpdateBlocked("weekly_monitoring_flags_forbidden")
    if (
        not recovering
        and mode in {ETF_WEEKLY_ADMISSION_MODE, ETF_WEEKLY_ADMISSION_V2_MODE}
        and (end_weekly_waiting is not True or weekly_monitoring_action is None)
    ):
        raise UpdateBlocked("weekly_monitoring_authorization_required")
    trial_flags = (trial_manifest, trial_manifest_sha256, trial_backup_parent)
    if any(value is not None for value in trial_flags) and (recovering or mode != TRIAL_MODE):
        raise UpdateBlocked("trial_retirement_flags_forbidden")
    if not recovering and mode == TRIAL_MODE and any(value is None for value in trial_flags):
        raise UpdateBlocked("trial_retirement_authorization_required")
    previous = previous_for(mode)
    if sys.platform != "darwin":
        raise UpdateBlocked("model_upgrade_macos_only")
    root, config = c.configured(home)
    if (
        config.get("artifact") != str(root / "controller.pyz")
        or config.get("artifact_sha256") != CONTROLLER_SHA256
    ):
        raise UpdateBlocked("model_upgrade_controller_unreviewed")
    c.environment(home, config)
    server = home / "server"
    g.private_root(server / "run")
    journal = server / "run/gateway-upgrade.json"
    with ExitStack() as stack:
        stack.enter_context(file_lock(root, "supervisor.lock", exclusive=True))
        stack.enter_context(file_lock(root, "admission.lock", exclusive=True))
        stack.enter_context(file_lock(server / "run", "operator.lock", exclusive=True))
        if recovering:
            if not journal.exists():
                weekly_intent = server / "run/weekly-monitoring-intent.json"
                weekly_receipt = server / "run/weekly-monitoring-receipt.json"
                intent_present, receipt_present = _weekly_record_presence(
                    weekly_intent, weekly_receipt
                )
                if intent_present and not receipt_present:
                    raise UpdateBlocked("weekly_monitoring_action_receipt_pending")
                if intent_present and receipt_present:
                    weekly_monitoring_bridge(
                        home, {"transaction": "no-upgrade-journal"}, None, recovering=True
                    )
                    return {"status": "not_required", "weekly_monitoring": "verified"}
                return {"status": "not_required"}
            state = g.read_upgrade_journal(journal)
            validate_state(home, state)
            previous = previous_for(state["mode"])
            # BirthFence journals describe both staged and releasing slots.
            # Its own identity-checked recovery handles these intermediate
            # states, before the activity probe interprets owner records.
            BirthFence.recover(server, expected=state["transaction"])
        else:
            if journal.exists() or (root / "transaction.json").exists():
                raise UpdateBlocked("model_upgrade_recovery_required")
            if source is None:
                raise UpdateBlocked("model_upgrade_source_required")
            executor_revision = c.git(source, "rev-parse", "HEAD")
            target = TRIAL_PAYLOAD if mode == TRIAL_MODE else executor_revision
            validate_executor(source, executor_revision)
            source_transition = trial_rebind(source, config) if mode == TRIAL_MODE else None
            if c.git(source, "rev-parse", "--path-format=absolute", "--git-common-dir") != (
                source_transition["after"]["common"]
                if source_transition
                else config["source_common"]
            ):
                raise UpdateBlocked("model_upgrade_source_changed")
            reviewed = review(source, target, mode) if mode != TRIAL_MODE else None
            if c.digest(root / "controller.pyz") != CONTROLLER_SHA256:
                raise UpdateBlocked("model_upgrade_controller_unreviewed")
            with zipfile.ZipFile(root / "controller.pyz") as original:
                if (
                    hashlib.sha256(original.read("resident/controller.py")).hexdigest()
                    != CONTROLLER_MODULE_SHA256
                ):
                    raise UpdateBlocked("model_upgrade_controller_unreviewed")
            verify_serve(config["private_origin"])
            verify_retention(home)
            supervisor_hash = verify_supervisor(home, config)
            github = GitHubEvidence(
                Path(config["gh"]),
                config["repository"],
                Path(
                    source_transition["after"]["common"]
                    if source_transition
                    else config["source_common"]
                ),
            )
            if github.latest() != (executor_revision if mode == TRIAL_MODE else target):
                raise UpdateBlocked("resident_master_moved")
            proof = github.qualify(target)
            executor_proof = github.qualify(executor_revision) if mode == TRIAL_MODE else proof
            if (root / "quarantine.json").exists() and read_json(root / "quarantine.json").get(
                "sha"
            ) == target:
                raise UpdateBlocked("resident_failed_candidate_requires_retry")
            primary, gateway = Path(config["project"]), read_json(server / "resident.json")
            for project in (primary, Path(gateway["project"])):
                c.clean(project, previous)
            if (
                gateway["revision"] != previous
                or read_json(home / "install/manifest.json").get("status") != "installed"
                or read_json(home / "install/manifest.json").get("code_commit") != previous
                or read_json(root / "accepted.json").get("target") != previous
            ):
                raise UpdateBlocked("model_upgrade_previous_changed")
            if mode == ETF_WEEKLY_ADMISSION_V2_MODE:
                weekly_primary_identity_precheck(home, previous)
            elif mode != TRIAL_MODE:
                verify_primary(home, previous, mode)
            g.no_private_processes(server)
            directory = root / "artifacts" / target
            g.private_root(directory)
            artifact_source = directory / "source"
            if not artifact_source.exists():
                c.git(source, "worktree", "add", "--detach", str(artifact_source), target)
            c.clean(artifact_source, target)
            if mode == TRIAL_MODE:
                reviewed = review(artifact_source, target, mode)
            old_wheel = c.build_wheel(primary, primary, directory / "old" / previous)
            new_wheel = c.build_wheel(primary, artifact_source, directory / "new" / target)
            plist = Path.home() / "Library/LaunchAgents" / (g.LABEL + ".plist")
            pid = g.job_pid()
            signature = g.process(pid) if pid else None
            payload = plistlib.loads(plist.read_bytes())
            python = str(primary / ".venv/bin/python")
            expected_argv = [
                python,
                "-m",
                "app.research_web.multiuser.resident",
                "--root",
                str(server),
            ]
            if (
                payload.get("ProgramArguments") != expected_argv
                or payload.get("WorkingDirectory") != gateway["project"]
                or payload.get("Label") != g.LABEL
                or not signature
                or g.listener_pids() != {pid}
                or g.native_image(pid) != g.native_image(os.getpid())
            ):
                raise UpdateBlocked("model_upgrade_gateway_identity_unknown")
            if Path(sys.prefix).resolve() != (primary / ".venv").resolve():
                raise UpdateBlocked("model_upgrade_interpreter_unknown")
            g.verify_signal_contract()
            g.no_children(pid)
            state = {
                "version": 4,
                "mode": mode,
                "previous": previous,
                "target": target,
                "source": str(artifact_source),
                "reviewed": reviewed,
                "proof": proof,
                "phase": "prepared",
                "transaction": str(uuid4()),
                "config": config,
                "gateway_config": gateway,
                "gateway_command": signature.split(maxsplit=5)[-1],
                "gateway_plist": str(plist),
                "gateway_plist_sha256": c.digest(plist),
                "primary_project": str(primary),
                "gateway_project": gateway["project"],
                "manifest": read_json(home / "install/manifest.json"),
                "model_before": model_metadata(config),
                "accepted": read_json(root / "accepted.json"),
                "candidate_before": read_json(root / "candidate.json"),
                "new_wheel": new_wheel,
                "old_wheel": old_wheel,
                "controller_sha256": c.digest(root / "controller.pyz"),
                "supervisor_plist_sha256": supervisor_hash,
            }
            if mode in ASSET_MODES:
                state["asset_index_before"] = asset_index_snapshot(home)
            for role in ("primary", "gateway"):
                project = Path(state[role + "_project"])
                info = project.stat()
                state[role + "_identity"] = [info.st_dev, info.st_ino]
                state[role + "_repository"] = repository_identity(project, config["repository"])
                c.git(project, "cat-file", "-e", f"{target}^{{commit}}")
            if mode == TRIAL_MODE:
                from . import trial_retirement as trial

                manifest_value = read_json(trial_manifest)
                trial.authorize(home, manifest_value, trial_manifest_sha256)
                executor_path = directory / "executor"
                if not executor_path.exists():
                    c.git(
                        source, "worktree", "add", "--detach", str(executor_path), executor_revision
                    )
                c.clean(executor_path, executor_revision)
                state.update(
                    executor_revision=executor_revision,
                    executor_proof=executor_proof,
                    executor_source=str(executor_path),
                    source_transition=source_transition,
                    trial_authorization=manifest_value,
                    trial_authorization_sha256=trial_manifest_sha256,
                    trial_backup_parent=str(trial_backup_parent),
                )
            state["recovery"] = install_recovery(
                home,
                Path(state.get("executor_source", artifact_source)),
                target,
                python,
                **({"executor_revision": executor_revision} if mode == TRIAL_MODE else {}),
            )
            # Exercise the exact recovery identity contract before any fence
            # publication or stop; an apply-only proof cannot protect rollback.
            validate_state(home, state, executor_source=source)
        from app.research_web.service_manager import WebServiceManager

        manager = WebServiceManager(
            project_root=Path(state["primary_project"]),
            data_root=home / "research-web",
            python=str(Path(state["primary_project"]) / ".venv/bin/python"),
            node=config["node"],
            web_port=config["web_port"],
            runtime_port=config["runtime_port"],
        )
        if state["mode"] in {ETF_WEEKLY_ADMISSION_MODE, ETF_WEEKLY_ADMISSION_V2_MODE}:
            try:
                weekly_monitoring_bridge(
                    home, state, manager, weekly_monitoring_action, recovering=recovering
                )
            except Exception as error:
                log.warning("weekly_monitoring_bridge_deferred error_type=%s", type(error).__name__)
                if (
                    isinstance(error, UpdateBlocked)
                    and str(error) != "weekly_monitoring_native_unknown"
                ):
                    raise
                return {
                    "status": "recovery_required" if recovering else "deferred",
                    "reason": "weekly_monitoring_unverified",
                }
        if not recovering and state["mode"] == ETF_WEEKLY_ADMISSION_V2_MODE:
            # Refresh completed with catalog locks released; the original full
            # verifier now proves Host and Native idle before any service fence.
            verify_primary(home, previous, state["mode"])
            # The historical verifier uses truthiness for Native activity. V2
            # additionally requires a fresh explicit empty list and Host false;
            # neither an unknown falsey value nor a new Host activity is idle.
            observed = weekly_primary_identity_precheck(home, previous)
            if observed.get("active") is not False:
                raise MaintenanceBusy("research_active_or_unknown")
        # In the gateway-only crash window a local primary caller could have
        # started work before a durable primary journal existed. Do not create
        # that journal or reservations until this real activity check is idle.
        if not recovering and state["mode"] == TRIAL_MODE:
            Operations(home, state, manager, None, None).capture_trial_processes()
        terminal_pending = (
            recovering
            and state["mode"] == TRIAL_MODE
            and state.get("trial_terminal_intent") is not None
        )
        if not terminal_pending and Operations(home, state, manager, None, None).idle() is not True:
            return {"status": "recovery_required" if recovering else "deferred"}
        if not recovering:
            # Establish recovery ownership BEFORE BirthFence publishes any
            # durable slot. A crash in __enter__ must never orphan reservations.
            Operations(home, state, manager, None, None).prepare_fence(state)
        elif state["phase"] == "preparing":
            # No service/source effect is possible before checkpoint prepared.
            validate_configuration(home, state)
            if state["mode"] != TRIAL_MODE:
                verify_primary(home, previous, state["mode"] if recovering else mode)
            g.preserved(home, state["before"])
            verify_asset_index(home, state)
            journal.unlink()
            c.sync_directory(journal.parent)
            return {"status": "aborted_before_signal"}
        fence = stack.enter_context(
            BirthFence(
                server,
                state["gateway_config"]["binding"]["primary_user_id"],
                resume=(server / "run/birth-fence.json").exists(),
                transaction=state["transaction"],
            )
        )
        lease = stack.enter_context(manager._installation_start_scope())
        ops = Operations(home, state, manager, lease, fence)
        if not recovering:
            latest_expected = executor_revision if mode == TRIAL_MODE else target
            if github.latest() != latest_expected or github.qualify(target) != proof:
                raise UpdateBlocked("resident_master_or_evidence_moved")
            if mode == TRIAL_MODE and github.qualify(executor_revision) != executor_proof:
                raise UpdateBlocked("resident_executor_evidence_moved")
        return execute(ops, state, recovering=recovering)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "apply",
            "apply-assets",
            "apply-assets-v2",
            "apply-assets-v3",
            "apply-assets-v4",
            "apply-assets-v5",
            "apply-assets-v6",
            "apply-assets-v7",
            "apply-assets-v8",
            "apply-assets-v9",
            "apply-market",
            "apply-market-gaps",
            "apply-market-history",
            "apply-market-terminal",
            "apply-market-preview",
            "apply-market-breadth",
            "apply-trial-retirement",
            "apply-etf-weekly",
            "apply-dossiers",
            "apply-discovery",
            "apply-etf-weekly-v2",
            "apply-etf-historical",
            "apply-etf-weekly-admission",
            "apply-etf-weekly-admission-v2",
            "recover",
        ),
    )
    parser.add_argument("--home", type=Path, default=Path.home() / ".research-workbench")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--end-weekly-waiting", action="store_true")
    parser.add_argument("--weekly-monitoring-action", type=Path)
    parser.add_argument("--trial-manifest", type=Path)
    parser.add_argument("--trial-manifest-sha256")
    parser.add_argument("--trial-backup-parent", type=Path)
    args = parser.parse_args(argv)
    logging.basicConfig(filename=args.home / "logs/model-upgrade.log", level=logging.INFO)
    try:
        if (
            args.end_weekly_waiting or args.weekly_monitoring_action is not None
        ) and args.command not in {"apply-etf-weekly-admission", "apply-etf-weekly-admission-v2"}:
            raise UpdateBlocked("weekly_monitoring_flags_forbidden")
        if args.command in {"apply-etf-weekly-admission", "apply-etf-weekly-admission-v2"} and (
            not args.end_weekly_waiting or args.weekly_monitoring_action is None
        ):
            raise UpdateBlocked("weekly_monitoring_authorization_required")
        if args.command == "recover":
            activate_recovery_source(args.home)
        result = operate(
            args.home,
            args.source,
            recovering=args.command == "recover",
            mode={
                "apply-assets": ASSET_MODE,
                "apply-assets-v2": ASSET_V2_MODE,
                "apply-assets-v3": ASSET_V3_MODE,
                "apply-assets-v4": ASSET_V4_MODE,
                "apply-assets-v5": ASSET_V5_MODE,
                "apply-assets-v6": ASSET_V6_MODE,
                "apply-assets-v7": ASSET_V7_MODE,
                "apply-assets-v8": ASSET_V8_MODE,
                "apply-assets-v9": ASSET_V9_MODE,
                "apply-market": MARKET_MODE,
                "apply-market-gaps": MARKET_GAPS_MODE,
                "apply-market-history": MARKET_HISTORY_MODE,
                "apply-market-terminal": MARKET_TERMINAL_MODE,
                "apply-market-preview": MARKET_PREVIEW_MODE,
                "apply-market-breadth": MARKET_BREADTH_MODE,
                "apply-trial-retirement": TRIAL_MODE,
                "apply-etf-weekly": ETF_WEEKLY_MODE,
                "apply-dossiers": DOSSIERS_MODE,
                "apply-discovery": DISCOVERY_MODE,
                "apply-etf-weekly-v2": ETF_WEEKLY_V2_MODE,
                "apply-etf-historical": ETF_HISTORICAL_MODE,
                "apply-etf-weekly-admission": ETF_WEEKLY_ADMISSION_MODE,
                "apply-etf-weekly-admission-v2": ETF_WEEKLY_ADMISSION_V2_MODE,
            }.get(args.command, MODE),
            **(
                {
                    "trial_manifest": args.trial_manifest,
                    "trial_manifest_sha256": args.trial_manifest_sha256,
                    "trial_backup_parent": args.trial_backup_parent,
                }
                if any(
                    v is not None
                    for v in (
                        args.trial_manifest,
                        args.trial_manifest_sha256,
                        args.trial_backup_parent,
                    )
                )
                else {}
            ),
            **(
                {
                    "end_weekly_waiting": True,
                    "weekly_monitoring_action": args.weekly_monitoring_action,
                }
                if args.command in {"apply-etf-weekly-admission", "apply-etf-weekly-admission-v2"}
                else {}
            ),
        )
        print(json.dumps(result))
        return 0 if result["status"] in {"deployed", "not_required"} else 2
    except MaintenanceBusy:
        print(json.dumps({"status": "deferred", "reason": "research_or_maintenance_busy"}))
        return 2
    except Exception as error:
        log.exception("model_upgrade_blocked")
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "reason": (
                        str(error) if isinstance(error, UpdateBlocked) else type(error).__name__
                    ),
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
