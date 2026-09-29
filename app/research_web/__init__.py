"""Standalone native-DSH research product; no legacy app lifecycle."""

from .runtime_contract import load_runtime_contract

RUNTIME_CONTRACT = load_runtime_contract()
PINNED_DSH_COMMIT = RUNTIME_CONTRACT.dsh_commit
