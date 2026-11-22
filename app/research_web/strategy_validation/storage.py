"""Bounded archive parsing and account-local immutable inputs and run results."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import sqlite3
import stat
import tempfile
import zipfile
import zlib
from collections import Counter
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from core.observability import get_logger
from research_workbench_entrypoint.resident.admission import MaintenanceBusy, admission

from ..datahub.security import directory, write_new
from ..store import StoreError
from .models import ValidationConfig

log = get_logger(__name__)
MAX_ZIP_BYTES = 16 * 1024 * 1024
MAX_EXPANDED_BYTES = 48 * 1024 * 1024
MAX_MEMBERS = 256
MAX_MEMBER_BYTES = 2 * 1024 * 1024
MAX_DATASETS = 4
MAX_RUNS = 20
MAX_KEYS = 200
MAX_EVENTS = 160_000
MAX_STORAGE_BYTES = 384 * 1024 * 1024
FOLDER = "strategy-validation"
DATABASE = "research.sqlite3"
SPEC_DIGEST = "89d3b7ebc5cca48e72be01fbab5343e7bf91e2cbd5eed33943040aca4ac68909"
ENGINE_FILES = ("analysis.py", "engine.py", "market.py", "rules.py")
REFERENCES = {
    "stock-basic.csv",
    "calendar.csv",
    "universe.csv",
    "hs300-membership.csv",
    "zz500-membership.csv",
    "bars-receipts.json",
}
SHA = re.compile(r"[a-f0-9]{64}\Z")
TICKER = re.compile(r"(?:sh\.60[0135][0-9]{3}|sz\.00[0123][0-9]{3})\Z")
BAR = re.compile(r"bars/((?:sh|sz)\.[0-9]{6})\.csv\Z")
RUN_FIELDS = ("id", "dataset_id", "horizon", "created_at")
OPERATION_LOCK = Lock()
SCHEMA = """
    CREATE TABLE IF NOT EXISTS datasets (id TEXT PRIMARY KEY, summary TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS dataset_files (
        id TEXT NOT NULL REFERENCES datasets(id), name TEXT NOT NULL, bytes BLOB NOT NULL,
        PRIMARY KEY (id, name)
    );
    CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, detail TEXT NOT NULL, summary TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS events (
        id TEXT NOT NULL REFERENCES runs(id), rule TEXT NOT NULL, ordinal INTEGER NOT NULL,
        row TEXT NOT NULL, PRIMARY KEY (id, rule, ordinal)
    );
    CREATE TABLE IF NOT EXISTS requests (
        key_hash TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, run_id TEXT NOT NULL REFERENCES runs(id)
    );
"""


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def serialized(value) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def reject(code: str, status: int = 422) -> StoreError:
    log.warning("strategy_validation_rejected", code=code)
    return StoreError("策略验证操作未完成", code, status)


def active() -> bool:
    return OPERATION_LOCK.locked()


@contextmanager
def activity():
    if not OPERATION_LOCK.acquire(blocking=False):
        raise reject("strategy_validation_busy", 409)
    try:
        with admission():
            yield
    except MaintenanceBusy as exc:
        raise reject("strategy_validation_maintenance", 503) from exc
    finally:
        OPERATION_LOCK.release()


def _archive_member(info: zipfile.ZipInfo) -> str | None:
    name = info.orig_filename.rstrip("/")
    attributes = info.external_attr >> 16
    mode = stat.S_IFMT(attributes)
    if (
        not name
        or len(name) > 256
        or "\x00" in name
        or "\\" in name
        or any(part in {"", ".", ".."} or ":" in part for part in name.split("/"))
        or info.flag_bits & 1
        or info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
        or mode not in {0, stat.S_IFDIR if info.is_dir() else stat.S_IFREG}
    ):
        raise reject("strategy_archive_member_invalid")
    if info.is_dir():
        return None
    relative = name.removeprefix("exit-backtest/")
    if relative == "data-spec.json":
        return relative
    if relative.startswith("data/"):
        candidate = relative.removeprefix("data/")
        if candidate in {*REFERENCES, "source.json"} or BAR.fullmatch(candidate):
            return candidate
    # Code, prior results, and documenting files are not retained or extracted.
    return None


def _decode_archive(raw: bytes) -> dict[str, bytes]:
    if len(raw) > MAX_ZIP_BYTES:
        raise reject("strategy_archive_too_large", 413)
    files: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members = archive.infolist()
            if (
                len(members) > MAX_MEMBERS
                or sum(info.file_size for info in members) > MAX_EXPANDED_BYTES
            ):
                raise reject("strategy_archive_too_large", 413)
            names = [info.orig_filename.rstrip("/") for info in members]
            if len(names) != len(set(names)):
                raise reject("strategy_archive_duplicate_member")
            for info in members:
                filename = _archive_member(info)
                if filename is None:
                    continue
                if filename in files:
                    raise reject("strategy_archive_duplicate_member")
                if not 0 < info.file_size <= MAX_MEMBER_BYTES:
                    raise reject("strategy_archive_member_too_large", 413)
                with archive.open(info) as stream:
                    value = stream.read(MAX_MEMBER_BYTES + 1)
                if len(value) != info.file_size:
                    raise reject("strategy_archive_member_invalid")
                files[filename] = value
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, zlib.error) as exc:
        raise reject("strategy_archive_invalid") from exc
    return files


def _csv(raw: bytes) -> list[dict]:
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8"), newline=""), strict=True))


def _verify_frozen_files(files: dict[str, bytes]) -> None:
    try:
        spec = files["data-spec.json"]
        source = json.loads(files["source.json"])
        if digest(spec) != SPEC_DIGEST:
            raise reject("strategy_market_spec_unsupported")
        if (
            source["spec_sha256"] != SPEC_DIGEST
            or source["source"] != "BaoStock SDK"
            or source["source_doc"] != "https://baostock.com/baostock/index.php/Python_API文档"
            or set(source["files"]) != REFERENCES
        ):
            raise reject("strategy_source_receipt_invalid")
        if any(digest(files[name]) != value for name, value in source["files"].items()):
            raise reject("strategy_input_digest_mismatch")
        receipts = json.loads(files["bars-receipts.json"])
        universe = [row["code"] for row in _csv(files["universe.csv"])]
        calendar = _csv(files["calendar.csv"])
        listings = _csv(files["stock-basic.csv"])
        basics = [row["code"] for row in listings]
        if (
            len(universe) != 160
            or len(set(universe)) != len(universe)
            or len(basics) != len(universe)
            or set(basics) != set(universe)
            or set(receipts) != set(universe)
            or not 1 <= len(calendar) <= 2_000
            or any(row.get("type") != "1" for row in listings)
        ):
            raise reject("strategy_frozen_scope_invalid")
        expected = {"data-spec.json", "source.json", *REFERENCES}
        for ticker in universe:
            if not TICKER.fullmatch(ticker):
                raise reject("strategy_frozen_scope_invalid")
            name = f"bars/{ticker}.csv"
            row = receipts[ticker]
            if (
                type(row["rows"]) is not int
                or not 1 <= row["rows"] <= 2_000
                or files[name].count(b"\n") != row["rows"] + 1
                or digest(files[name]) != row["sha256"]
            ):
                raise reject("strategy_input_digest_mismatch")
            expected.add(name)
        if set(files) != expected:
            raise reject("strategy_frozen_scope_invalid")
    except (ValueError, TypeError, KeyError, AttributeError, csv.Error) as exc:
        raise reject("strategy_source_receipt_invalid") from exc


def _identity(value: str) -> str:
    if not SHA.fullmatch(value):
        raise reject("strategy_record_not_found", 404)
    return value


def _summary(detail: dict) -> dict:
    return {key: detail[key] for key in RUN_FIELDS}


def _engine_identity() -> str:
    root = Path(__file__).parent
    return digest(
        serialized([digest((root / entry).read_bytes()) for entry in ENGINE_FILES]).encode()
    )


def _check_database_file(path: Path) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or getattr(info, "st_file_attributes", 0) & 0x400
        or os.name == "posix"
        and (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077)
    ):
        raise reject("strategy_storage_unsafe", 503)


class StrategyStore:
    def __init__(self, root: Path):
        self.root = root
        self.path = root / FOLDER / DATABASE

    @property
    def exists(self) -> bool:
        folder = self.path.parent
        return (
            folder.is_symlink()
            or (folder.exists() and not folder.is_dir())
            or (self.path.exists() or self.path.is_symlink())
        )

    @contextmanager
    def _db(self, *, write: bool = False):
        connection = None
        try:
            with directory(self.root, (FOLDER,), create=write, private=True) as fd:
                for suffix in ["", "-journal", "-wal", "-shm"]:
                    _check_database_file(self.path.with_name(DATABASE + suffix))
                if write and not self.path.exists():
                    write_new(fd, DATABASE, b"")
                mode = "rw" if write else "ro"
                connection = sqlite3.connect(
                    f"{self.path.as_uri()}?mode={mode}", timeout=2, uri=True
                )
                connection.execute("PRAGMA foreign_keys=ON")
                if write:
                    page_size = connection.execute("PRAGMA page_size").fetchone()[0]
                    connection.execute(f"PRAGMA max_page_count={MAX_STORAGE_BYTES // page_size}")
                    connection.executescript(SCHEMA)
                    connection.execute("BEGIN IMMEDIATE")
                yield connection
                connection.commit()
        except sqlite3.Error as exc:
            if connection is not None:
                connection.rollback()
            log.error("strategy_validation_sqlite_failed", error_type=type(exc).__name__)
            if getattr(exc, "sqlite_errorcode", None) == sqlite3.SQLITE_FULL:
                raise reject("strategy_storage_full", 409) from exc
            raise reject("strategy_storage_unavailable", 503) from exc
        finally:
            if connection is not None:
                connection.close()

    def list(self) -> dict:
        if not self.exists:
            return {"datasets": [], "runs": []}
        with self._db() as db:
            datasets = db.execute("SELECT summary FROM datasets ORDER BY rowid DESC").fetchall()
            runs = db.execute("SELECT summary FROM runs ORDER BY rowid DESC").fetchall()
        return {
            "datasets": [json.loads(row[0]) for row in datasets],
            "runs": [json.loads(row[0]) for row in runs],
        }

    def import_dataset(self, raw: bytes) -> dict:
        with activity():
            files = _decode_archive(raw)
            _verify_frozen_files(files)
            identifier = digest(raw)
            summary = {
                "id": identifier,
                "name": "冻结行情 · 2026-11-13",
                "sha256": identifier,
            }
            with self._db(write=True) as db:
                found = db.execute(
                    "SELECT summary FROM datasets WHERE id = ?", (identifier,)
                ).fetchone()
                if found:
                    return json.loads(found[0])
                if db.execute("SELECT count(*) FROM datasets").fetchone()[0] >= MAX_DATASETS:
                    raise reject("strategy_dataset_storage_full", 409)
                db.execute("INSERT INTO datasets VALUES (?, ?)", (identifier, serialized(summary)))
                db.executemany(
                    "INSERT INTO dataset_files VALUES (?, ?, ?)",
                    ((identifier, name, content) for name, content in files.items()),
                )
            log.info("strategy_dataset_imported", dataset_id=identifier, files=len(files))
            return summary

    def _calculate(self, db, identifier: str, config: ValidationConfig):
        from .engine import run_validation

        blobs = db.execute(
            "SELECT name, bytes FROM dataset_files WHERE id = ?", (config.dataset_id,)
        )
        files = dict(blobs)
        if not files:
            raise reject("strategy_record_not_found", 404)
        _verify_frozen_files(files)
        with tempfile.TemporaryDirectory(prefix="rwb-strategy-") as temporary:
            root = Path(temporary)
            (root / "bars").mkdir(mode=0o700)
            for name, content in files.items():
                # Keys have passed the exact whitelist and per-ticker digest check.
                (root / name).write_bytes(content)
            result, events = run_validation(root, config.model_dump(exclude={"dataset_id"}))

            # Consume lazy output before the private scratch directory retires.
            def rows():
                counts: Counter = Counter()
                for position, event in enumerate(events):
                    rule = event["rule"]
                    if rule not in config.rules or position >= MAX_EVENTS:
                        raise reject("strategy_result_budget_exceeded", 413)
                    counts[rule] += 1
                    payload = serialized(event)
                    if len(payload.encode()) > 2_048:
                        raise reject("strategy_result_budget_exceeded", 413)
                    yield identifier, rule, counts[rule], payload

            db.executemany("INSERT INTO events VALUES (?, ?, ?, ?)", rows())
        return result

    def create_run(self, config: ValidationConfig, key: str) -> dict:
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{8,128}", key):
            raise reject("strategy_idempotency_key_invalid")
        key_hash = digest(key.encode())
        raw_config = serialized(config.model_dump()).encode()
        fingerprint = digest(raw_config)
        with activity(), self._db(write=True) as db:
            previous = db.execute(
                "SELECT fingerprint, run_id FROM requests WHERE key_hash = ?", (key_hash,)
            ).fetchone()
            if previous:
                if previous[0] != fingerprint:
                    raise reject("strategy_idempotency_conflict", 409)
                found = db.execute(
                    "SELECT summary FROM runs WHERE id = ?", (previous[1],)
                ).fetchone()
                if found is None:
                    raise reject("strategy_storage_unavailable", 503)
                return json.loads(found[0])
            if db.execute("SELECT count(*) FROM requests").fetchone()[0] >= MAX_KEYS:
                raise reject("strategy_run_storage_full", 409)
            code_sha256 = _engine_identity()
            identifier = digest(f"{code_sha256}:{fingerprint}".encode())
            found = db.execute("SELECT summary FROM runs WHERE id = ?", (identifier,)).fetchone()
            if found is None:
                if db.execute("SELECT count(*) FROM runs").fetchone()[0] >= MAX_RUNS:
                    raise reject("strategy_run_storage_full", 409)
                created_at = datetime.now(UTC).isoformat(timespec="seconds")
                summary = {
                    "id": identifier,
                    "dataset_id": config.dataset_id,
                    "horizon": config.horizon,
                    "created_at": created_at,
                }
                # Keep provisional rows inside the transaction until both results close.
                db.execute(
                    "INSERT INTO runs VALUES (?, ?, ?)", (identifier, "{}", serialized(summary))
                )
                result = self._calculate(db, identifier, config)
                if (
                    not isinstance(result, dict)
                    or "rules" not in result
                    or "coverage" not in result
                ):
                    raise reject("strategy_calculation_unavailable", 503)
                detail = {
                    **summary,
                    "rules": result["rules"],
                    "coverage": result["coverage"],
                    "research_only": True,
                    "historical_pit_verified": False,
                    "engine_sha256": code_sha256,
                    "configuration": config.model_dump(),
                }
                encoded = serialized(detail)
                if len(encoded.encode()) > 512 * 1024:
                    raise reject("strategy_result_budget_exceeded", 413)
                db.execute("UPDATE runs SET detail = ? WHERE id = ?", (encoded, identifier))
                log.info(
                    "strategy_validation_calculated",
                    run_id=identifier,
                    rule_count=len(config.rules),
                )
            else:
                summary = json.loads(found[0])
            db.execute("INSERT INTO requests VALUES (?, ?, ?)", (key_hash, fingerprint, identifier))
        return summary

    def run(self, identifier: str) -> dict:
        identifier = _identity(identifier)
        if not self.exists:
            raise reject("strategy_record_not_found", 404)
        with self._db() as db:
            row = db.execute("SELECT detail FROM runs WHERE id = ?", (identifier,)).fetchone()
        if row is None:
            raise reject("strategy_record_not_found", 404)
        return json.loads(row[0])

    def events(self, identifier: str, rule: str, offset: int, limit: int) -> dict:
        result = self.run(identifier)
        if rule not in result["configuration"]["rules"]:
            raise reject("strategy_record_not_found", 404)
        with self._db() as db:
            total = db.execute(
                "SELECT count(*) FROM events WHERE id = ? AND rule = ?", (identifier, rule)
            ).fetchone()[0]
            rows = db.execute(
                "SELECT row FROM events WHERE id = ? AND rule = ? ORDER BY ordinal LIMIT ? OFFSET ?",
                (identifier, rule, limit, offset),
            ).fetchall()
        return {
            "items": [json.loads(row[0]) for row in rows],
            "total": total,
            "offset": offset,
            "limit": limit,
        }
