"""Bounded local SQLite transaction for immutable specs, inputs and paper runs."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import stat
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

from core.observability import get_logger

from .engine import IMPLEMENTATION_DIGEST, digest, replay

log = get_logger(__name__)
MAX_BYTES = 8 * 1024 * 1024


class DecisionStore:
    def __init__(self, root: Path, *, initialize: bool = True):
        self.initialize = initialize
        self.directory = root / "portfolio-decisions"
        self.path = self.directory / "paper.sqlite3"
        if not initialize and not self.directory.exists() and not self.directory.is_symlink():
            return
        if initialize:
            self.directory.mkdir(mode=0o700, exist_ok=True)
        info = self.directory.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or self.directory.is_symlink()
            or os.name == "posix"
            and (stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != os.getuid())
        ):
            raise ValueError("decision_directory_unsafe")
        if self.path.is_symlink() or self.path.exists() and not self.path.is_file():
            raise ValueError("decision_store_unsafe")
        if not initialize:
            return
        with self._connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS specs (identity TEXT PRIMARY KEY, digest TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, request TEXT NOT NULL, result TEXT NOT NULL, summary TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS request_keys (key_digest TEXT PRIMARY KEY, run_id TEXT NOT NULL);
            """)
        os.chmod(self.path, 0o600)

    @contextmanager
    def _connection(self):
        db = None
        try:
            db = (
                sqlite3.connect(self.path, timeout=5)
                if self.initialize
                else sqlite3.connect(f"file:{quote(str(self.path))}?mode=ro", timeout=5, uri=True)
            )
            db.execute("PRAGMA busy_timeout=5000")
            yield db
            db.commit()
        except sqlite3.Error as exc:
            if db is not None:
                db.rollback()
            log.error("etf_paper_store_failed", error_type=type(exc).__name__)
            raise ValueError("decision_store_failed") from exc
        except Exception:
            if db is not None:
                db.rollback()
            raise
        finally:
            if db is not None:
                db.close()

    def run(self, body, key):
        if not self.initialize:
            raise ValueError("decision_store_read_only")
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{8,128}", key):
            raise ValueError("invalid_idempotency_key")
        request = body.model_dump(mode="json")
        encoded = json.dumps(request, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if len(encoded.encode()) > MAX_BYTES:
            raise ValueError("snapshot_budget_exceeded")
        run_id = digest([IMPLEMENTATION_DIGEST, request])
        key_digest = digest(key)
        spec_identity = digest([body.strategy.strategy_id, body.strategy.version])
        spec_digest = digest(request["strategy"])
        # All monetary state, orders and fills commit together, never piecemeal.
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute(
                "SELECT run_id FROM request_keys WHERE key_digest=?", (key_digest,)
            ).fetchone()
            if previous and previous[0] != run_id:
                raise ValueError("idempotency_conflict")
            version = db.execute(
                "SELECT digest FROM specs WHERE identity=?", (spec_identity,)
            ).fetchone()
            if version and version[0] != spec_digest:
                raise ValueError("immutable_strategy_version_conflict")
            existing = db.execute("SELECT result FROM runs WHERE id=?", (run_id,)).fetchone()
            if existing:
                db.execute("INSERT OR IGNORE INTO request_keys VALUES (?,?)", (key_digest, run_id))
                return json.loads(existing[0])
            if db.execute("SELECT COUNT(*) FROM runs").fetchone()[0] >= 100:
                raise ValueError("run_storage_budget_exceeded")
            result = {"id": run_id, "mode": "engineering_paper", **replay(body)}
            output = json.dumps(result, sort_keys=True, ensure_ascii=False)
            if len(output.encode()) > MAX_BYTES:
                raise ValueError("result_budget_exceeded")
            db.execute("INSERT OR IGNORE INTO specs VALUES (?,?)", (spec_identity, spec_digest))
            summary = {
                "id": run_id,
                "strategy": request["strategy"],
                "data_cutoff": result["data_cutoff"],
                "mode": "engineering_paper",
                "real_chain_status": "BLOCKED",
            }
            db.execute(
                "INSERT INTO runs VALUES (?,?,?,?)", (run_id, encoded, output, json.dumps(summary))
            )
            db.execute("INSERT INTO request_keys VALUES (?,?)", (key_digest, run_id))
        log.info("etf_paper_run_saved", admission="blocked")
        return result

    def get(self, run_id):
        if not re.fullmatch(r"[a-f0-9]{64}", run_id):
            raise ValueError("invalid_run_id")
        if not self.path.exists():
            raise ValueError("run_not_found")
        with self._connection() as db:
            row = db.execute("SELECT result FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise ValueError("run_not_found")
        return json.loads(row[0])

    def list_runs(self):
        if not self.path.exists():
            return []
        with self._connection() as db:
            rows = db.execute("SELECT summary FROM runs ORDER BY rowid DESC LIMIT 100").fetchall()
        return [json.loads(row[0]) for row in rows]
