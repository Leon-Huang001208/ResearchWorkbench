"""CNY 50 ceiling shared by isolated acceptance runs on this Host."""

import json
import os
import re
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from core.observability import get_logger
from research_workbench_entrypoint.resident.admission import file_lock

from .datahub.security import atomic_json, directory, json_bytes, read_file
from .store import StoreError

log = get_logger(__name__)

# Peak DeepSeek Flash rates in millionths of CNY. Reserve the full supported
# context at cache-miss price and retain that hold if provider usage is missing.
LIMIT = 50_000_000
INPUT_LIMIT = 1_000_000
INPUT_RESERVATION = 2_000_000
OUTPUT_PRICE = 8
MAX_OUTPUT_TOKENS = 8192
MAX_LEDGER_BYTES = 512 * 1024
ROOT_ENV = "RWB_QA_ACCEPTANCE_ROOT"
OFFICIAL_MODEL = "deepseek-flash"
OFFICIAL_ENDPOINT = "https://api.deepseek.com/chat/completions"
SOURCE_ERROR = "qa_acceptance_source_price_unknown"


@dataclass(frozen=True)
class Reservation:
    root: Path
    identifier: str


def acceptance_enabled():
    return ROOT_ENV in os.environ


def _held(max_tokens):
    return INPUT_RESERVATION + OUTPUT_PRICE * max_tokens


def _in_range(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


def _validate_legacy(value):
    if (
        not isinstance(value, dict)
        or set(value) != {"version", "reserved_micro_cny", "calls"}
        or type(value["version"]) is not int
        or value["version"] != 1
        or not _in_range(value["calls"], 0, 24)
        or not _in_range(
            value["reserved_micro_cny"],
            value["calls"] * INPUT_RESERVATION,
            min(LIMIT, value["calls"] * _held(MAX_OUTPUT_TOKENS)),
        )
    ):
        raise ValueError("qa_acceptance_legacy_ledger_invalid")


def _usage_cost(usage, max_tokens):
    if (
        not isinstance(usage, dict)
        or set(usage)
        != {
            "completion_id",
            "prompt_cache_hit_tokens",
            "prompt_cache_miss_tokens",
            "completion_tokens",
        }
        or not isinstance(usage["completion_id"], str)
        or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", usage["completion_id"])
        or not _in_range(usage["prompt_cache_hit_tokens"], 0, INPUT_LIMIT)
        or not _in_range(usage["prompt_cache_miss_tokens"], 0, INPUT_LIMIT)
        or not _in_range(usage["completion_tokens"], 0, max_tokens)
    ):
        raise ValueError("qa_acceptance_usage_invalid")
    hit = usage["prompt_cache_hit_tokens"]
    miss = usage["prompt_cache_miss_tokens"]
    if not 1 <= hit + miss <= INPUT_LIMIT:
        raise ValueError("qa_acceptance_usage_invalid")
    # ¥0.04 per million cached tokens equals 1/25 micro-CNY per token.
    return (hit + 24) // 25 + 2 * miss + OUTPUT_PRICE * usage["completion_tokens"]


def _load(folder):
    value = json.loads(read_file(folder, "ledger.json", private=True, limit=MAX_LEDGER_BYTES))
    if not isinstance(value, dict) or type(value.get("version")) is not int:
        raise ValueError("qa_acceptance_ledger_invalid")
    if value["version"] == 1:
        _validate_legacy(value)
        return {**value, "version": 2, "legacy": value, "requests": {}}
    if (
        value["version"] != 2
        or set(value) != {"version", "reserved_micro_cny", "calls", "legacy", "requests"}
        or not isinstance(value["requests"], dict)
    ):
        raise ValueError("qa_acceptance_ledger_invalid")
    _validate_legacy(value["legacy"])
    amount = value["legacy"]["reserved_micro_cny"]
    completions = set()
    for identifier, entry in value["requests"].items():
        if (
            not re.fullmatch(r"[0-9a-f]{32}", identifier)
            or not isinstance(entry, dict)
            or set(entry) != {"max_tokens", "usage"}
            or not _in_range(entry["max_tokens"], 1, MAX_OUTPUT_TOKENS)
        ):
            raise ValueError("qa_acceptance_ledger_invalid")
        usage, max_tokens = entry["usage"], entry["max_tokens"]
        if usage is None:
            amount += _held(max_tokens)
            continue
        amount += _usage_cost(usage, max_tokens)
        if usage["completion_id"] in completions:
            raise ValueError("qa_acceptance_duplicate_completion")
        completions.add(usage["completion_id"])
    if (
        not _in_range(value["reserved_micro_cny"], 0, LIMIT)
        or value["reserved_micro_cny"] != amount
        or type(value["calls"]) is not int
        or value["calls"] != value["legacy"]["calls"] + len(value["requests"])
    ):
        raise ValueError("qa_acceptance_ledger_invalid")
    return value


@contextmanager
def _ledger(root):
    try:
        if not root.is_absolute() or not root.is_dir():
            raise ValueError("qa_acceptance_root_invalid")
        with file_lock(root, "qa-acceptance.lock", exclusive=True), directory(root) as folder:
            yield folder, _load(folder)
    except (OSError, RuntimeError, StoreError, TypeError, ValueError) as exc:
        if isinstance(exc, StoreError) and exc.code.startswith("qa_acceptance_"):
            raise
        log.warning("research_qa_acceptance_ledger_unavailable", error_type=type(exc).__name__)
        raise StoreError("验收费用账本不可用", "qa_acceptance_budget_unavailable", 409) from None


def reserve(connection, max_tokens):
    if not acceptance_enabled():
        return None
    endpoint, model, _, provider = connection
    if (endpoint, model, provider) != (OFFICIAL_ENDPOINT, OFFICIAL_MODEL, "deepseek-official"):
        raise StoreError("验收模型费用无法核算", "qa_acceptance_model_price_unknown", 409)
    if not _in_range(max_tokens, 1, MAX_OUTPUT_TOKENS):
        raise StoreError("验收模型输出预算无效", "qa_acceptance_output_budget_invalid", 409)
    reservation = Reservation(Path(os.environ[ROOT_ENV]), uuid4().hex)
    with _ledger(reservation.root) as (folder, value):
        amount = value["reserved_micro_cny"] + _held(max_tokens)
        if amount > LIMIT:
            raise StoreError("本轮真实验收已达费用上限", "qa_acceptance_budget_exhausted", 409)
        value["requests"][reservation.identifier] = {"max_tokens": max_tokens, "usage": None}
        value.update(reserved_micro_cny=amount, calls=value["calls"] + 1)
        if len(json_bytes(value)) > MAX_LEDGER_BYTES:
            raise StoreError("验收费用账本已达容量上限", "qa_acceptance_ledger_limit", 409)
        atomic_json(folder, "ledger.json", value)
    log.info("research_qa_acceptance_reserved", calls=value["calls"], reserved_micro_cny=amount)
    return reservation


def settle(reservation, completion_id, usage):
    """Release only the proven difference from the peak-priced official usage."""
    try:
        with _ledger(reservation.root) as (folder, value):
            entry = value["requests"].get(reservation.identifier)
            if entry is None:
                raise ValueError("qa_acceptance_reservation_missing")
            if not isinstance(usage, dict):
                raise TypeError("qa_acceptance_usage_invalid")
            evidence = {
                "completion_id": completion_id,
                **{
                    key: usage.get(key)
                    for key in (
                        "prompt_cache_hit_tokens",
                        "prompt_cache_miss_tokens",
                        "completion_tokens",
                    )
                },
            }
            cost = _usage_cost(evidence, entry["max_tokens"])
            prompt_tokens = (
                evidence["prompt_cache_hit_tokens"] + evidence["prompt_cache_miss_tokens"]
            )
            if (
                type(usage.get("prompt_tokens")) is not int
                or usage["prompt_tokens"] != prompt_tokens
                or type(usage.get("total_tokens")) is not int
                or usage["total_tokens"] != prompt_tokens + evidence["completion_tokens"]
            ):
                raise ValueError("qa_acceptance_usage_invalid")
            if entry["usage"] == evidence:
                return
            if entry["usage"] is not None or any(
                row["usage"] and row["usage"]["completion_id"] == completion_id
                for row in value["requests"].values()
            ):
                raise ValueError("qa_acceptance_duplicate_completion")
            entry["usage"] = evidence
            value["reserved_micro_cny"] -= _held(entry["max_tokens"]) - cost
            if len(json_bytes(value)) > MAX_LEDGER_BYTES:
                raise ValueError("qa_acceptance_ledger_limit")
            atomic_json(folder, "ledger.json", value)
    except StoreError as exc:
        log.warning("research_qa_acceptance_usage_unsettled", code=exc.code)
        return
    log.info("research_qa_acceptance_usage_settled", usage_upper_bound_micro_cny=cost)
