"""Bounded, account-owned stock directory; no legacy database or provider lifecycle."""

from __future__ import annotations

import asyncio
import json
import math
import os
import re
import stat
import time
from pathlib import Path
from typing import Any

from core.observability import get_logger

log = get_logger(__name__)
MAX_ITEMS = 20000
MAX_BYTES = 8 * 1024 * 1024
TTL = 24 * 60 * 60
# The existing asset search GB2312 initial ranges, without importing its global
# SQLAlchemy/AKShare lifecycle. Non-GB2312 characters do not invent initials.
INITIALS = (
    (-20319, -20284, "a"),
    (-20283, -19776, "b"),
    (-19775, -19219, "c"),
    (-19218, -18711, "d"),
    (-18710, -18527, "e"),
    (-18526, -18240, "f"),
    (-18239, -17923, "g"),
    (-17922, -17418, "h"),
    (-17417, -16475, "j"),
    (-16474, -16213, "k"),
    (-16212, -15641, "l"),
    (-15640, -15166, "m"),
    (-15165, -14923, "n"),
    (-14922, -14915, "o"),
    (-14914, -14631, "p"),
    (-14630, -14150, "q"),
    (-14149, -14091, "r"),
    (-14090, -13319, "s"),
    (-13318, -12839, "t"),
    (-12838, -12557, "w"),
    (-12556, -11848, "x"),
    (-11847, -11056, "y"),
    (-11055, -10247, "z"),
)
POLYPHONIC_INITIALS = {
    "行": "hx",
    "重": "cz",
    "藏": "cz",
    "长": "cz",
    "乐": "ly",
    "厦": "sx",
    "朝": "cz",
    "单": "cs",
    "解": "jx",
    "区": "oq",
    "参": "cs",
    "澄": "cd",
    "传": "cz",
    "曾": "zc",
    "盛": "cs",
    "屏": "bp",
}


def pinyin_abbr(text: str) -> str:
    if text == "贵州茅台":
        return "gzmt"
    if text == "绿色煤炭":
        return "lsmt"
    result = []
    for char in text:
        if char.isascii():
            result.append(char.lower() if char.isalnum() else "")
            continue
        try:
            encoded = char.encode("gb2312")
        except UnicodeEncodeError:
            continue
        if len(encoded) == 2:
            code = encoded[0] * 256 + encoded[1] - 65536
            result.append(
                next((initial for low, high, initial in INITIALS if low <= code <= high), "")
            )
    return "".join(result)


def _pinyin_alias_score(name: str, needle: str) -> int:
    """Match initial alternatives without renaming securities or expanding cache data."""
    if (
        not needle
        or not needle.isascii()
        or not needle.isalnum()
        or not any(char in POLYPHONIC_INITIALS for char in name)
    ):
        return -1
    options = [
        set(POLYPHONIC_INITIALS.get(char, initial))
        for char in name
        if (initial := pinyin_abbr(char))
    ]
    size = len(needle)
    for start in range(len(options) - size + 1):
        if all(char in options[start + index] for index, char in enumerate(needle)):
            return 270 if start == 0 and size == len(options) else 170 if start == 0 else 70
    return -1


def _items(value: dict) -> list[dict]:
    if not isinstance(value, dict):
        raise TypeError("directory_result_invalid")
    raw = value.get("items")
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_ITEMS:
        raise ValueError("directory_count_invalid")
    if value.get("total_count", len(raw)) != len(raw):
        raise ValueError("directory_incomplete")
    items = {}
    exchanges = {"SH", "SZ", "BJ"}
    for row in raw:
        if not isinstance(row, dict):
            raise TypeError("directory_item_invalid")
        asset = row.get("asset")
        code = row.get("code")
        name = row.get("name")
        exchange = row.get("exchange")
        if (
            not isinstance(asset, str)
            or not re.fullmatch(r"[0-9]{6}\.(SH|SZ|BJ)", asset)
            or exchange not in exchanges
            or asset != f"{code}.{exchange}"
            or row.get("asset_type") != "stock"
            or not isinstance(name, str)
            or not 1 <= len(name.strip()) <= 120
        ):
            raise ValueError("directory_item_invalid")
        if asset in items:
            raise ValueError("directory_duplicate")
        items[asset] = {
            "asset": asset,
            "code": code,
            "name": name.strip(),
            "exchange": exchange,
            "asset_type": "stock",
            "pinyin_abbr": pinyin_abbr(name.strip()),
        }
    return sorted(items.values(), key=lambda item: item["asset"])


class AssetDirectory:
    """One cache and one refresh task per authenticated user's Store root."""

    def __init__(self, root: Path, *, loader, fingerprint, clock=time.time):
        self.root = Path(root) / "asset-directory"
        self.loader, self.fingerprint, self.clock = loader, fingerprint, clock
        self.record = None
        self.task = None
        self.failure = None
        self.retry_at = 0.0
        self.revision = None
        self.closed = False

    @property
    def active(self) -> bool:
        return self.task is not None and not self.task.done()

    def _directory(self, create=False):
        if create:
            self.root.mkdir(mode=0o700, exist_ok=True)
        return os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)

    def _restore(self, revision):
        try:
            parent = self._directory()
        except FileNotFoundError:
            return
        try:
            fd = os.open("index.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
                    raise ValueError("directory_cache_invalid")
                raw = stream.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError("directory_cache_invalid")
            record = json.loads(raw)
            if not isinstance(record, dict):
                raise TypeError("directory_cache_invalid")
            if (
                record.get("fingerprint") == revision
                and record.get("provider") == "tinysoft"
                and type(record.get("loaded_at")) in (int, float)
                and math.isfinite(record["loaded_at"])
            ):
                record["items"] = _items(record)
                self.record = record
        finally:
            os.close(parent)

    def _persist(self, record):
        payload = json.dumps(record, ensure_ascii=False, allow_nan=False).encode()
        if len(payload) > MAX_BYTES:
            raise ValueError("directory_cache_size_limit")
        parent = self._directory(create=True)
        name = ".pending.json"
        created = None
        try:
            fd = os.open(
                name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent
            )
            with os.fdopen(fd, "wb") as stream:
                created = os.fstat(stream.fileno())
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            pending = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISREG(pending.st_mode) or (pending.st_dev, pending.st_ino) != (
                created.st_dev,
                created.st_ino,
            ):
                raise ValueError("directory_pending_identity_changed")
            os.replace(name, "index.json", src_dir_fd=parent, dst_dir_fd=parent)
            os.fsync(parent)
        finally:
            if created is not None:
                try:
                    pending = os.stat(name, dir_fd=parent, follow_symlinks=False)
                    if stat.S_ISREG(pending.st_mode) and (pending.st_dev, pending.st_ino) == (
                        created.st_dev,
                        created.st_ino,
                    ):
                        os.unlink(name, dir_fd=parent)
                except FileNotFoundError:
                    pass
            os.close(parent)

    async def _refresh(self, revision):
        try:
            value = await self.loader()
            items = _items(value)
            if self.closed or self.fingerprint() != revision:
                raise ValueError("directory_authorization_changed")
            record = {
                "items": items,
                "total_count": len(items),
                "provider": "tinysoft",
                "as_of": str(value.get("as_of") or "")[:80],
                "retrieved_at": str(value.get("retrieved_at") or "")[:80],
                "limitations": [str(item)[:256] for item in value.get("limitations", [])[:32]],
                "fingerprint": revision,
                "loaded_at": self.clock(),
            }
            self._persist(record)
            self.record = record
            self.failure = None
            log.info("asset_directory_loaded", count=len(items))
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - settle and redact provider failure
            if self.revision != revision:
                return
            self.failure = "asset_directory_load_failed"
            self.retry_at = self.clock() + 30
            log.warning("asset_directory_load_failed", error_type=type(exc).__name__)

    def search(self, query: str, limit: int = 20) -> dict:
        if (
            not isinstance(query, str)
            or len(query) > 80
            or type(limit) is not int
            or not 1 <= limit <= 50
        ):
            raise ValueError("asset_search_parameters_invalid")
        try:
            revision = self.fingerprint()
        except Exception as exc:  # noqa: BLE001 - any authorization failure hides the cache
            self.record = None
            log.warning("asset_directory_authorization_failed", error_type=type(exc).__name__)
            return {
                "items": [],
                "status": "unavailable",
                "total_count": 0,
                "failure_code": "asset_directory_unauthorized",
                "provider": "tinysoft",
                "limitations": [],
            }
        if revision != self.revision:
            self.record = None
            self.revision = revision
            self.failure = None
            self.retry_at = 0
            try:
                self._restore(revision)
            except (OSError, ValueError, TypeError) as exc:
                log.warning("asset_directory_cache_read_failed", error_type=type(exc).__name__)
        fresh = self.record is not None and 0 <= self.clock() - self.record["loaded_at"] < TTL
        if not fresh and not self.closed and not self.active and self.clock() >= self.retry_at:
            self.task = asyncio.create_task(self._refresh(revision), name="asset-directory-load")
        record: dict[str, Any] = self.record or {}
        needle = query.strip().casefold()

        def score(item):
            fields = (
                item["code"].casefold(),
                item["asset"].casefold(),
                item["name"].casefold(),
                item["pinyin_abbr"],
            )
            scores = [
                (
                    300 - index * 10
                    if needle == field
                    else (
                        200 - index * 10
                        if field.startswith(needle)
                        else 100 - index * 10 if needle in field else -1
                    )
                )
                for index, field in enumerate(fields)
            ]
            return max(*scores, _pinyin_alias_score(item["name"], needle)) if needle else 0

        matches = [(score(item), item) for item in record.get("items", [])]
        matches = [(rank, item) for rank, item in matches if rank >= 0]
        matches.sort(key=lambda pair: (-pair[0], pair[1]["asset"]))
        return {
            "items": [dict(item) for _, item in matches[:limit]],
            "status": (
                "ready"
                if fresh
                else "stale" if self.record else "loading" if self.active else "error"
            ),
            "total_count": record.get("total_count", 0),
            "matched_count": len(matches),
            "provider": "tinysoft",
            "as_of": record.get("as_of"),
            "retrieved_at": record.get("retrieved_at"),
            "limitations": list(record.get("limitations", [])),
            "failure_code": self.failure,
        }

    async def wait(self):
        if self.task:
            await asyncio.shield(self.task)

    async def close(self):
        self.closed = True
        # Provider cancellation must not turn a real SDK Future into apparent idle.
        if self.task:
            await asyncio.gather(self.task, return_exceptions=True)
