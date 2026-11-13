"""CNY 50 ceiling shared by isolated acceptance runs on this Host."""

import json
import os
from pathlib import Path

from core.observability import get_logger
from research_workbench_entrypoint.resident.admission import file_lock

from .datahub.security import atomic_json, directory, read_file
from .store import StoreError

log = get_logger(__name__)

# Peak, uncached rates for the exact accepted model and its one-million-token
# context. Reserve the full context and output cap before dispatch, even when
# the upstream response or final usage is lost. Units are millionths of CNY.
LIMIT = 50_000_000
INPUT_RESERVATION = 2_000_000
OUTPUT_PRICE = 8


def acceptance_enabled():
    return "RWB_QA_ACCEPTANCE_ROOT" in os.environ


def reserve(connection, max_tokens):
    if not acceptance_enabled():
        return
    if connection[1] != "deepseek-flash" or connection[3] != "deepseek-official":
        raise StoreError("验收模型费用无法核算", "qa_acceptance_model_price_unknown", 409)
    root = Path(os.environ["RWB_QA_ACCEPTANCE_ROOT"])
    if not root.is_absolute() or not root.is_dir():
        raise StoreError("验收费用账本不可用", "qa_acceptance_budget_unavailable", 409)
    with (
        file_lock(root, "qa-acceptance.lock", exclusive=True),
        directory(root, private=True) as folder,
    ):
        try:
            value = json.loads(read_file(folder, "ledger.json", private=True, limit=1024))
        except (StoreError, ValueError):
            raise StoreError(
                "验收费用账本不可用", "qa_acceptance_budget_unavailable", 409
            ) from None
        if (
            not isinstance(value, dict)
            or set(value) != {"version", "reserved_micro_cny", "calls"}
            or type(value["version"]) is not int
            or value["version"] != 1
            or type(value["reserved_micro_cny"]) is not int
            or not 0 <= value["reserved_micro_cny"] <= LIMIT
            or type(value["calls"]) is not int
            or not 0 <= value["calls"] <= 24
            or value["reserved_micro_cny"] < value["calls"] * INPUT_RESERVATION
        ):
            raise StoreError("验收费用账本不可用", "qa_acceptance_budget_unavailable", 409)
        amount = value["reserved_micro_cny"] + INPUT_RESERVATION + OUTPUT_PRICE * max_tokens
        if amount > LIMIT:
            raise StoreError("本轮真实验收已达费用上限", "qa_acceptance_budget_exhausted", 409)
        value.update(reserved_micro_cny=amount, calls=value["calls"] + 1)
        atomic_json(folder, "ledger.json", value)
    log.info("research_qa_acceptance_reserved", calls=value["calls"], reserved_micro_cny=amount)
