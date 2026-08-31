"""Contract tests for the merged AlphaFoundry platform shared kernel."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from core.contracts.asset_observation import AlertOperator, AlertRule
from core.contracts.platform_shared import (
    AssetIdentifier,
    AssetRef,
    FreshnessStatus,
    ObservationEnvelope,
    SourceRef,
)
from core.contracts.research_workspace import (
    AgentBudget,
    AgentSchedule,
    AgentTeamDefinition,
    ResearchSession,
    SkillManifest,
)
from core.contracts.theme_research import (
    PackLifecycle,
    ThemeObservation,
    ThemePackManifest,
)

NOW = datetime(2026, 8, 31, 9, 30, tzinfo=UTC)
SOURCE = SourceRef(
    source_id="wind",
    name="Wind",
    tier="licensed",
    content_hash="sha256:abc",
)


def _observation(**overrides: object) -> ObservationEnvelope:
    payload: dict[str, object] = {
        "observation_id": "obs-1",
        "subject_ref": "asset:asset-1",
        "metric_key": "close",
        "value": 10.0,
        "unit": "CNY/share",
        "as_of": NOW,
        "observed_at": NOW,
        "available_at": NOW,
        "source_refs": [SOURCE],
        "freshness_status": FreshnessStatus.FRESH,
        "quality_flags": [],
    }
    payload.update(overrides)
    return ObservationEnvelope(**payload)


def test_fact_observation_requires_all_six_context_fields():
    payload = _observation().model_dump()
    for field in (
        "as_of",
        "observed_at",
        "available_at",
        "source_refs",
        "freshness_status",
        "quality_flags",
    ):
        incomplete = dict(payload)
        incomplete.pop(field)
        with pytest.raises(ValidationError):
            ObservationEnvelope(**incomplete)


def test_observation_rejects_available_time_before_observation_time():
    with pytest.raises(ValidationError, match="available_at"):
        _observation(available_at=NOW - timedelta(seconds=1))


def test_numeric_observation_requires_unit_but_zero_is_not_missing():
    with pytest.raises(ValidationError, match="unit"):
        _observation(unit=None)

    zero = _observation(value=0, unit="CNY/share")
    assert zero.value == 0
    assert zero.missing_reason is None


def test_missing_observation_is_distinct_from_zero():
    missing = _observation(value=None, unit=None, missing_reason="source_unavailable")
    assert missing.value is None
    assert missing.missing_reason == "source_unavailable"

    with pytest.raises(ValidationError, match="missing_reason"):
        _observation(value=None, unit=None, missing_reason=None)


def test_freshness_status_has_exact_approved_values():
    assert {status.value for status in FreshnessStatus} == {
        "fresh",
        "stale",
        "unavailable",
        "quarantined",
    }


@pytest.mark.parametrize("asset_type", ["stock", "index", "etf", "active_fund"])
def test_asset_ref_accepts_exactly_four_asset_types(asset_type: str):
    assert AssetRef(asset_id="asset-1", asset_type=asset_type).asset_type.value == asset_type


def test_asset_identifier_rejects_reversed_validity_window():
    with pytest.raises(ValidationError, match="valid_to"):
        AssetIdentifier(
            asset_id="asset-1",
            scheme="wind",
            value="600519.SH",
            market="CN",
            valid_from=NOW,
            valid_to=NOW - timedelta(days=1),
        )


def test_source_ref_requires_a_traceable_hash_or_url():
    with pytest.raises(ValidationError, match="content_hash"):
        SourceRef(source_id="unknown", name="Unknown", tier="public")


def test_theme_pack_lifecycle_and_permissions_are_bounded():
    manifest = ThemePackManifest(
        pack_key="gold",
        name="黄金",
        version="1.0.0",
        compatibility_version="1",
        status=PackLifecycle.DISCOVERED,
        boundary="黄金供需与价格",
        plugin_permissions=["normalize", "validate", "derive"],
    )
    assert manifest.status is PackLifecycle.DISCOVERED

    with pytest.raises(ValidationError):
        ThemePackManifest(
            pack_key="unsafe",
            name="unsafe",
            version="1.0.0",
            compatibility_version="1",
            status="enabled",
            boundary="unsafe",
            plugin_permissions=["network"],
        )


def test_theme_observation_requires_source_hash_for_idempotent_ingestion():
    payload = _observation().model_dump()
    payload.update(pack_key="gold", dataset_key="prices", row_identity="2026-08-31")
    with pytest.raises(ValidationError, match="source_hash"):
        ThemeObservation(**payload)


def test_workspace_session_requires_workspace_scope():
    with pytest.raises(ValidationError, match="workspace_id"):
        ResearchSession(
            session_id="session-1",
            mode="workspace",
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )


@pytest.mark.parametrize(
    "tool",
    [
        "shell",
        "python:exec",
        "filesystem:write",
        "internal:shell",
        "internal:filesystem_write",
        "https://example.com",
        "mcp:unregistered",
    ],
)
def test_skill_rejects_unbounded_or_unregistered_tools(tool: str):
    with pytest.raises(ValidationError, match="allowed_tools"):
        SkillManifest(
            skill_key="unsafe",
            name="unsafe",
            version="1.0.0",
            prompt_template="x",
            input_schema={},
            output_schema={},
            allowed_tools=[tool],
            registered_mcp_tools=["mcp:approved"],
        )


def test_skill_accepts_internal_attachment_controlled_web_and_registered_mcp():
    manifest = SkillManifest(
        skill_key="safe",
        name="safe",
        version="1.0.0",
        prompt_template="x",
        input_schema={},
        output_schema={},
        allowed_tools=[
            "internal:asset_snapshot",
            "attachment:read",
            "web:controlled",
            "mcp:approved",
        ],
        registered_mcp_tools=["mcp:approved"],
    )
    assert manifest.allowed_tools[-1] == "mcp:approved"


def test_agent_budget_and_team_enforce_hard_limits():
    with pytest.raises(ValidationError):
        AgentBudget(
            max_steps=101,
            max_concurrency=1,
            max_tokens=1_000,
            max_cost=1,
            deadline_seconds=60,
        )

    with pytest.raises(ValidationError, match="supervisor_role"):
        AgentTeamDefinition(
            team_id="team-1",
            name="team",
            supervisor_role="supervisor",
            roles=["analyst"],
            budget=AgentBudget(
                max_steps=10,
                max_concurrency=2,
                max_tokens=10_000,
                max_cost=10,
                deadline_seconds=600,
            ),
        )


def test_agent_schedule_forbids_reentry_and_requires_latest_coalescing():
    with pytest.raises(ValidationError, match="concurrent"):
        AgentSchedule(
            schedule_id="schedule-1",
            team_id="team-1",
            cron_expression="0 9 * * 1-5",
            status="active",
            allow_concurrent=True,
            coalesce_policy="latest",
        )

    with pytest.raises(ValidationError, match="coalesce"):
        AgentSchedule(
            schedule_id="schedule-1",
            team_id="team-1",
            cron_expression="0 9 * * 1-5",
            status="active",
            allow_concurrent=False,
            coalesce_policy="all",
        )


def test_alert_operator_is_bounded_and_numeric_rule_requires_unit():
    assert {operator.value for operator in AlertOperator} == {
        "gt",
        "gte",
        "lt",
        "lte",
        "crosses_above",
        "crosses_below",
        "pct_change",
    }
    with pytest.raises(ValidationError, match="unit"):
        AlertRule(
            rule_id="rule-1",
            asset_id="asset-1",
            metric_type="price",
            metric_key="close",
            operator="gte",
            threshold=100,
            status="active",
            unit=None,
        )
