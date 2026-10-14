"""Stdlib Hot settings and diagnostic entry; no secrets, Store or research startup."""

from __future__ import annotations

import argparse
import getpass
import json
import logging
import os
import shutil
import stat
import subprocess
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone

log = logging.getLogger(__name__)
MAX_BYTES = 65536


class HotError(RuntimeError):
    """Stable errors never contain input, credential values or subprocess output."""


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "hot_argument_invalid\n")


def _no_alias(path: Path) -> None:
    for parent in reversed((path, *path.parents)):
        try:
            if parent.is_symlink():
                raise HotError("hot_storage_unsafe")
        except OSError:
            raise HotError("hot_storage_unavailable") from None


def _read(path: Path, *, private: bool = False) -> dict:
    _no_alias(path)
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_BYTES:
                raise HotError("hot_config_unsafe")
            if private and (os.name != "posix" or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600):
                raise HotError("hot_config_unsafe")
            value = json.loads(stream.read(MAX_BYTES + 1))
        if not isinstance(value, dict):
            raise HotError("hot_config_invalid")
        return value
    except HotError:
        raise
    except (OSError, ValueError):
        raise HotError("hot_config_unavailable") from None


def _node() -> str:
    explicit = os.environ.get("RESEARCH_NODE_BINARY")
    bundled = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
    value = explicit or (str(bundled) if bundled.is_file() else shutil.which("node"))
    if not value:
        raise HotError("hot_node_missing")
    return value


def normalize(project: Path, value: dict) -> dict:
    try:
        result = subprocess.run(
            [_node(), str(project / "services/hot/scripts/check-config.ts")],
            input=json.dumps(value), capture_output=True, text=True, timeout=10,
            cwd=project,
        )
        if result.returncode or len(result.stdout.encode()) > MAX_BYTES:
            raise HotError("hot_config_invalid")
        normalized = json.loads(result.stdout)
        if not isinstance(normalized, dict) or "error" in normalized:
            raise HotError("hot_config_invalid")
        return normalized
    except HotError:
        raise
    except (OSError, ValueError, subprocess.SubprocessError):
        raise HotError("hot_configuration_bridge_unavailable") from None


def _record_configuration(project: Path, home: Path | None = None) -> None:
    docker_guest = bool(home and os.path.isfile("/.dockerenv") and os.environ.get("RESEARCH_RUN_MODE") == "web-prod"
                        and os.environ.get("RESEARCH_CREDENTIAL_HOME") is not None and os.environ.get("RWB_DATA_ROOT") == str(home))
    path = home / "hot" / "logs" / "configuration.jsonl" if docker_guest else project / "logs" / "hot" / "configuration.jsonl"
    _no_alias(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
                raise HotError("hot_log_unsafe")
            stream.write(json.dumps({"event": "hot_configuration_saved", "time": datetime.now(timezone.utc).isoformat()}) + "\n")
            stream.flush()
    except OSError:
        raise HotError("hot_log_unavailable") from None


def save_settings(project: Path, home: Path, config: dict) -> dict:
    normalized = normalize(project, config)
    target = home / "hot" / "settings.json"
    _no_alias(target)
    parent = target.parent
    try:
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        info = parent.stat()
    except OSError:
        raise HotError("hot_storage_unavailable") from None
    if os.name != "posix" or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise HotError("hot_storage_unsafe")
    if target.exists():
        previous = _read(target, private=True)
        if previous.get("projectRoot") != str(project):
            raise HotError("hot_foreign_config")
    try:
        directory = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError:
        raise HotError("hot_storage_unavailable") from None
    temporary = "settings-" + uuid4().hex + ".tmp"
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=directory)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"schemaVersion": 1, "projectRoot": str(project), "config": normalized}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, "settings.json", src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)
    except OSError:
        raise HotError("hot_config_write_failed") from None
    finally:
        os.close(directory)
    log.info("hot_configuration_saved")
    try:
        _record_configuration(project, home)
    except HotError:
        return {"state": "configured" if normalized["enabled"] else "disabled", "enabled": normalized["enabled"],
                "config_saved": True, "logging": "unavailable", "code": "hot_log_unavailable"}
    return {"state": "configured" if normalized["enabled"] else "disabled", "enabled": normalized["enabled"]}


def status(project: Path, home: Path) -> dict:
    target = home / "hot" / "settings.json"
    _no_alias(target)
    if not target.exists():
        return {"state": "disabled", "enabled": False, "service": "not_integrated"}
    record = _read(target, private=True)
    if record.get("schemaVersion") != 1 or record.get("projectRoot") != str(project):
        raise HotError("hot_foreign_config")
    config = record.get("config")
    if not isinstance(config, dict) or not isinstance(config.get("enabled"), bool):
        raise HotError("hot_config_invalid")
    return {"state": "configured" if config["enabled"] else "disabled", "enabled": config["enabled"],
            "service": "not_integrated", "lifecycle": "not_integrated"}


def dispatch(argv: list[str], project: Path) -> int:
    parser = SafeParser(prog="rwb hot", description="Hot configuration and diagnostics; lifecycle integration is in progress.")
    parser.add_argument("--data-home", type=Path, default=Path(os.environ.get("RESEARCH_DATA_HOME", str(Path.home() / ".research-workbench/research-web"))))
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("status", "doctor", "start", "stop", "restart", "sources"):
        sub.add_parser(command).add_argument("--json", action="store_true")
    source = sub.add_parser("source-configure")
    source.add_argument("source")
    source.add_argument("--expected-revision", required=True)
    toggles = source.add_mutually_exclusive_group()
    toggles.add_argument("--enable", dest="enabled", action="store_const", const=True)
    toggles.add_argument("--disable", dest="enabled", action="store_const", const=False)
    source.add_argument("--frequency-seconds", type=int)
    source.add_argument("--use-catalog", action="store_true")
    source.add_argument("--reason")
    source.add_argument("--request-id")
    source.add_argument("--json", action="store_true")
    channels = sub.add_parser("channels")
    channels.add_argument("--cutoff")
    channels.add_argument("--json", action="store_true")
    events = sub.add_parser("events")
    for option in ("channel", "cutoff", "query", "topic", "institution", "asset"):
        events.add_argument("--" + option)
    events.add_argument("--from", dest="from_time")
    events.add_argument("--to", dest="to_time")
    events.add_argument("--sort", choices=("recent", "importance", "heat", "increment", "relevance"), default="recent")
    events.add_argument("--limit", type=int, default=20)
    events.add_argument("--offset", type=int, default=0)
    events.add_argument("--min-relevance", type=int)
    events.add_argument("--json", action="store_true")
    event = sub.add_parser("event")
    event.add_argument("event_id")
    event.add_argument("--cutoff")
    event.add_argument("--report-limit", type=int, default=20)
    event.add_argument("--report-offset", type=int, default=0)
    event.add_argument("--json", action="store_true")
    channel_configure = sub.add_parser("channel-configure")
    channel_configure.add_argument("channel")
    channel_configure.add_argument("--expected-version", type=int, required=True)
    channel_configure.add_argument("--file", type=Path, required=True)
    channel_configure.add_argument("--request-id")
    channel_configure.add_argument("--json", action="store_true")
    event_correct = sub.add_parser("event-correct")
    event_correct.add_argument("--file", type=Path, required=True)
    event_correct.add_argument("--reason", required=True)
    event_correct.add_argument("--request-id")
    event_correct.add_argument("--json", action="store_true")
    model_attempts = sub.add_parser("model-attempts")
    model_attempts.add_argument("--scope")
    model_attempts.add_argument("--limit", type=int, default=50)
    model_attempts.add_argument("--offset", type=int, default=0)
    model_attempts.add_argument("--json", action="store_true")
    pricing = sub.add_parser("model-pricing-import")
    pricing.add_argument("--file", type=Path, required=True)
    pricing.add_argument("--verify-official-pricing", action="store_true")
    pricing.add_argument("--reason", required=True)
    pricing.add_argument("--json", action="store_true")
    model_authorize = sub.add_parser("model-authorize")
    model_authorize.add_argument("--file", type=Path, required=True)
    model_authorize.add_argument("--authorize-paid", action="store_true")
    model_amend = sub.add_parser("model-amend-tokens")
    model_amend.add_argument("--scope", required=True)
    model_amend.add_argument("--max-tokens", type=int, required=True)
    model_amend.add_argument("--daily-max-tokens", type=int, required=True)
    model_amend.add_argument("--authorize-paid", action="store_true")
    model_terminate = sub.add_parser("model-terminate")
    model_terminate.add_argument("--attempt", required=True)
    for model_control in (model_authorize, model_terminate, model_amend):
        model_control.add_argument("--reason", required=True)
        model_control.add_argument("--request-id")
        model_control.add_argument("--migration-user", default="postgres")
        model_control.add_argument("--migration-account", default="hot-migration-database")
        model_control.add_argument("--json", action="store_true")
    setup = sub.add_parser("setup")
    setup.add_argument("--migration-user", default="postgres")
    setup.add_argument("--migration-account", default="hot-migration-database")
    setup.add_argument("--json", action="store_true")
    for command in ("backup", "restore"):
        archive = sub.add_parser(command)
        archive.add_argument("--migration-user", default="postgres")
        archive.add_argument("--migration-account", default="hot-migration-database")
        archive.add_argument("--json", action="store_true")
        if command == "backup":
            archive.add_argument("--include-session", action="append", default=[])
        if command == "restore":
            archive.add_argument("--from", dest="archive_directory", type=Path, required=True)
            archive.add_argument("--target-database", required=True)
            archive.add_argument("--research-data-home", type=Path)
    snapshots = sub.add_parser("restore-research-snapshots")
    snapshots.add_argument("--from", dest="archive_directory", type=Path, required=True)
    snapshots.add_argument("--research-data-home", type=Path, required=True)
    snapshots.add_argument("--json", action="store_true")
    configure = sub.add_parser("configure")
    configure.add_argument("--file", type=Path, required=True)
    configure.add_argument("--json", action="store_true")
    credential = sub.add_parser("credential")
    credential.add_argument("kind", choices=("worker", "controller", "migration", "rpc-controller", "rpc-reader"))
    args = parser.parse_args(argv)
    home = args.data_home.absolute()
    try:
        if args.command == "configure":
            value = save_settings(project, home, _read(args.file.absolute()))
        elif args.command in ("setup", "start", "stop", "restart", "credential", "backup", "restore", "restore-research-snapshots", "sources", "source-configure", "channels", "events", "event", "channel-configure", "event-correct", "model-attempts", "model-authorize", "model-terminate", "model-amend-tokens", "model-pricing-import") or (
            args.command in ("status", "doctor") and (home / "hot" / "process.json").exists()
        ):
            from .bootstrap import native_python, native_environment

            python = native_python(project)
            if not python.is_file():
                raise HotError("hot_native_environment_missing")
            if Path(os.path.abspath(os.sys.executable)) != Path(os.path.abspath(python)):
                os.chdir(project)
                os.execve(str(python), [str(python), "-m", "research_workbench_entrypoint", "hot", "--data-home", str(home), *argv[argv.index(args.command):]], native_environment(project))
            from app.research_web.credential_backend import SystemKeyringBackend
            from .hot_manager import HotManager

            manager = HotManager(project, home, SystemKeyringBackend())
            if args.command == "credential":
                if not os.isatty(0) or not os.isatty(2):
                    raise HotError("hot_credential_requires_terminal")
                config = manager._config()
                account = {"worker": config["database"]["secretRef"], "controller": config["database"]["controllerSecretRef"],
                           "migration": "hot-migration-database"}.get(args.kind, args.kind)
                secret = getpass.getpass("Hot credential (stored in system credential store): ")
                try:
                    manager.credentials.set_password(manager.service, account, secret)
                except Exception:
                    raise HotError("hot_credentials_unavailable") from None
                value = {"state": "credential_saved"}
            elif args.command == "setup":
                value = manager.setup(args.migration_user, args.migration_account)
            elif args.command == "model-attempts":
                filters = {"limit": args.limit, "offset": args.offset}
                if args.scope is not None:
                    filters["scopeId"] = args.scope
                value = manager.model_operation("attempts", filters)
            elif args.command == "model-pricing-import":
                value = manager.import_pricing(_read(args.file.absolute()), verified=args.verify_official_pricing, reason=args.reason)
            elif args.command in ("model-authorize", "model-terminate", "model-amend-tokens"):
                operation = args.command.removeprefix("model-")
                if operation == "amend-tokens":
                    parameters = {"scopeId": args.scope, "maxTokens": args.max_tokens,
                                  "dailyMaxTokens": args.daily_max_tokens, "authorizePaid": args.authorize_paid}
                else:
                    parameters = {"policy": _read(args.file.absolute()), "authorizePaid": args.authorize_paid} if operation == "authorize" else {"attemptId": args.attempt}
                value = manager.model_operation(operation, parameters, reason=args.reason, request_id=args.request_id,
                                                migration_user=args.migration_user, migration_account=args.migration_account)
            elif args.command == "source-configure":
                value = manager.configure_source(args.source, args.expected_revision, args.enabled,
                                                 args.frequency_seconds, args.request_id, args.use_catalog, args.reason)
            elif args.command == "channels":
                value = manager.channels(args.cutoff)
            elif args.command == "events":
                filters = {"channelId": args.channel, "cutoff": args.cutoff, "q": args.query, "topic": args.topic,
                           "institution": args.institution, "asset": args.asset, "from": args.from_time, "to": args.to_time,
                           "sort": args.sort, "limit": args.limit, "offset": args.offset, "minRelevance": args.min_relevance}
                value = manager.events({key: item for key, item in filters.items() if item is not None})
            elif args.command == "event":
                value = manager.event_detail(args.event_id, args.cutoff, args.report_offset, args.report_limit)
            elif args.command == "channel-configure":
                config = _read(args.file.absolute())
                if "channels" in config:
                    if set(config) != {"version", "channels"} or type(config["version"]) is not int or config["version"] != 1 or not isinstance(config["channels"], dict) or not isinstance(config["channels"].get(args.channel), dict):
                        raise HotError("hot_channel_request_invalid")
                    config = config["channels"][args.channel]
                value = manager.configure_channel(args.channel, args.expected_version, config, args.request_id)
            elif args.command == "event-correct":
                value = manager.correct_event(_read(args.file.absolute()), args.reason, args.request_id)
            elif args.command == "restore-research-snapshots":
                from .hot_joint_archive import restore_research
                value = restore_research(args.research_data_home.absolute(), args.archive_directory.absolute(), manager._secret("rpc-controller"))
            elif args.command in ("backup", "restore"):
                directory = args.archive_directory.absolute() if args.command == "restore" else None
                research_home = getattr(args, "research_data_home", None)
                research_home = research_home.absolute() if research_home else home
                joint = bool(directory and (directory / "research-manifest.json").exists())
                if joint:
                    from .hot_joint_archive import preflight_research_restore
                    preflight_research_restore(research_home, directory, manager._secret("rpc-controller"))
                value = manager.archive(args.command, directory, getattr(args, "target_database", None),
                                        args.migration_user, args.migration_account)
                if args.command == "backup" and args.include_session:
                    from .hot_joint_archive import backup_research
                    value["researchSnapshots"] = backup_research(home, Path(value["directory"]), args.include_session, manager._secret("rpc-controller"))
                elif joint:
                    from .hot_joint_archive import restore_research
                    value["researchSnapshots"] = restore_research(research_home, directory, manager._secret("rpc-controller"))
            elif args.command == "doctor":
                value = manager.status()
                value["checks"] = {"service": "PASS" if value["state"] == "initialized" else "NOT_RUN",
                                   "source_catalog": value.get("sourceControl", {}).get("catalogActivation", "NOT_RUN"),
                                   "model": "NOT_RUN", "research": "NOT_RUN"}
            else:
                value = getattr(manager, args.command)()
        else:
            value = status(project, home)
            if args.command == "doctor":
                value["checks"] = {"configuration": "configured" if value["enabled"] else "disabled",
                                   "service": "NOT_RUN", "database": "NOT_RUN", "model": "NOT_RUN", "source_catalog": "NOT_RUN"}
        print(json.dumps(value, ensure_ascii=False))
        return 1 if isinstance(value, dict) and (value.get("logging") == "unavailable" or value.get("persistence") == "unavailable" or value.get("durability") == "unavailable" or value.get("state") in ("outcome_unknown","rejected")) else 0
    except HotError as error:
        log.warning("hot_operation_failed code=%s", str(error))
        print(json.dumps({"state": "unavailable", "code": str(error)}))
        return 1
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        log.warning("hot_operation_failed code=hot_lifecycle_unavailable")
        print(json.dumps({"state": "unavailable", "code": "hot_lifecycle_unavailable"}))
        return 1
