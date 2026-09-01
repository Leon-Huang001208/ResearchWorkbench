"""Behavior tests for the LSH retirement evidence gate."""

from pathlib import Path

import pytest

from services.legacy_capability_gate import (
    CapabilityMapError,
    LegacyCapabilityGate,
)

ROOT = Path(__file__).resolve().parents[2]
CAPABILITY_MAP = ROOT / "docs/architecture/merged-platform/lsh-capability-map.yaml"


def test_duplicate_capability_stays_blocked_until_every_removal_evidence_exists():
    """Regression caught: parity alone must never authorize deletion."""

    gate = LegacyCapabilityGate.from_file(CAPABILITY_MAP)

    decision = gate.evaluate("lsh.flask.skill_snapshot")

    assert decision.allowed is False
    assert decision.action == "block_removal"
    assert decision.target == "/api/themes/{theme_key}/snapshot"
    assert set(decision.missing_evidence) == {
        "data_migration",
        "parity_test",
        "regression",
        "call_count_zero",
        "archive_path",
        "stable_version_observed",
        "archived_status",
    }


def test_frozen_strategy_capability_can_never_be_deleted_even_with_evidence(tmp_path):
    """Regression caught: migration evidence must not override the freeze policy."""

    capability_map = tmp_path / "capabilities.yaml"
    capability_map.write_text(
        """{
          "version": 1,
          "capabilities": [{
            "key": "lsh.strategy.orders",
            "source": "/api/v1/strategies/confirm-orders",
            "target": null,
            "classification": "strategy_trading",
            "disposition": "freeze_read_only",
            "status": "archived",
            "evidence": {
              "data_migration": true,
              "parity_test": true,
              "regression": true,
              "call_count_zero": true,
              "archive_path": "/archive/lsh-v1",
              "stable_version_observed": true
            }
          }]
        }""",
        encoding="utf-8",
    )

    decision = LegacyCapabilityGate.from_file(capability_map).evaluate("lsh.strategy.orders")

    assert decision.allowed is False
    assert decision.action == "retain_read_only"
    assert decision.missing_evidence == ("policy_forbids_removal",)


def test_removal_is_allowed_only_after_archival_and_stable_observation(tmp_path):
    """Regression caught: a green checklist in a pre-archive state is insufficient."""

    capability_map = tmp_path / "capabilities.yaml"
    capability_map.write_text(
        """{
          "version": 1,
          "capabilities": [{
            "key": "lsh.static.dashboard",
            "source": "static/data-dashboard.html",
            "target": "/api/themes",
            "classification": "duplicate_ui",
            "disposition": "remove_after_gate",
            "status": "archived",
            "evidence": {
              "data_migration": true,
              "parity_test": true,
              "regression": true,
              "call_count_zero": true,
              "archive_path": "/archive/lsh-v1",
              "stable_version_observed": true
            }
          }]
        }""",
        encoding="utf-8",
    )

    decision = LegacyCapabilityGate.from_file(capability_map).evaluate("lsh.static.dashboard")

    assert decision.allowed is True
    assert decision.action == "allow_removal"
    assert decision.missing_evidence == ()


def test_unknown_or_malformed_capability_map_fails_closed(tmp_path):
    """Regression caught: missing inventory entries or fields must not default to removal."""

    malformed = tmp_path / "malformed.yaml"
    malformed.write_text('{"version": 1, "capabilities": [{"key": "broken"}]}', encoding="utf-8")

    with pytest.raises(CapabilityMapError):
        LegacyCapabilityGate.from_file(malformed)

    gate = LegacyCapabilityGate.from_file(CAPABILITY_MAP)
    with pytest.raises(KeyError):
        gate.evaluate("lsh.unknown")
