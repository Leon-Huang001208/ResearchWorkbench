"""Contract tests for the merged Research Workbench platform shared kernel."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from core.contracts.asset_observation import (
    AlertEvaluation,
    AlertEvent,
    AlertOperator,
    AlertRule,
    Notification,
    PeerSet,
    Watchlist,
    WatchlistItem,
)
from core.contracts.market_home import (
    MarketHomeEnvelope,
    MarketHomeSection,
    MarketHomeSectionKey,
    MarketHomeSnapshot,
)
from core.contracts.platform_shared import (
    AssetIdentifier,
    AssetRef,
    DomainEvent,
    FreshnessStatus,
    ObservationEnvelope,
    ScheduledJob,
    SourceRef,
)
from core.contracts.research_workspace import (
    AgentBudget,
    AgentSchedule,
    AgentTeamDefinition,
    ResearchMessage,
    ResearchNote,
    ResearchSession,
    ResearchWorkspace,
    RuntimeProvider,
    SkillManifest,
)
from core.contracts.theme_research import (
    PackLifecycle,
    PluginBinding,
    ThemeObservation,
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


@pytest.mark.parametrize("valid_to", [NOW, NOW - timedelta(days=1)])
def test_asset_identifier_requires_strictly_positive_validity_window(
    valid_to: datetime,
):
    with pytest.raises(ValidationError, match="valid_to"):
        AssetIdentifier(
            asset_id="asset-1",
            scheme="wind",
            value="600519.SH",
            market="CN",
            valid_from=NOW,
            valid_to=valid_to,
        )


def test_source_ref_requires_a_traceable_hash_or_url():
    with pytest.raises(ValidationError, match="content_hash"):
        SourceRef(source_id="unknown", name="Unknown", tier="public")


@pytest.mark.parametrize(
    "source_url",
    [
        "https://user@example.com/report",
        "https://user:secret@example.com/report",
        "http:///missing-host",
        "https://",
        "http://[::1",
    ],
)
def test_source_ref_rejects_credentials_and_urls_without_a_host(source_url: str):
    with pytest.raises(ValidationError, match="source_url"):
        SourceRef(
            source_id="unsafe",
            name="Unsafe",
            tier="public",
            source_url=source_url,
        )


def test_source_ref_keeps_valid_http_url_as_a_serialized_string():
    source_url = "https://example.com/report?id=1"
    source = SourceRef(
        source_id="official",
        name="Official",
        tier="official",
        source_url=source_url,
    )
    assert source.source_url == source_url
    assert source.model_dump()["source_url"] == source_url


def test_theme_pack_lifecycle_and_permissions_are_bounded():
    assert {status.value for status in PackLifecycle} == {
        "discovered",
        "validated",
        "enabled",
        "degraded",
        "disabled",
    }
    binding = PluginBinding(plugin_id="builtin.identity.v1", operation="normalize")
    assert binding.operation == "normalize"

    with pytest.raises(ValidationError):
        PluginBinding(plugin_id="arbitrary.python", operation="normalize")
    with pytest.raises(ValidationError):
        PluginBinding(plugin_id="builtin.identity.v1", operation="network")


def test_theme_observation_requires_source_hash_for_idempotent_ingestion():
    payload = _observation().model_dump()
    payload.update(pack_key="gold", dataset_key="prices", row_identity="2026-08-31")
    with pytest.raises(ValidationError, match="source_hash"):
        ThemeObservation(**payload)


@pytest.mark.parametrize("workspace_id", [None, "   "])
def test_workspace_session_requires_nonempty_workspace_scope(
    workspace_id: str | None,
):
    with pytest.raises(ValidationError, match="workspace_id"):
        ResearchSession(
            session_id="session-1",
            mode="workspace",
            status="active",
            workspace_id=workspace_id,
            created_at=NOW,
            updated_at=NOW,
        )


@pytest.mark.parametrize(
    "tool",
    [
        "shell",
        "python:exec",
        "filesystem:write",
        "https://example.com",
    ],
)
def test_skill_rejects_unbounded_tool_schemes(tool: str):
    with pytest.raises(ValidationError, match="allowed_tools"):
        SkillManifest(
            skill_key="unsafe",
            name="unsafe",
            version="1.0.0",
            prompt_template="x",
            input_schema={},
            output_schema={},
            allowed_tools=[tool],
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
    )
    manifest.validate_tool_registry({"internal:asset_snapshot", "mcp:approved"})
    assert manifest.allowed_tools[-1] == "mcp:approved"


@pytest.mark.parametrize(
    "tool",
    [
        "internal:browser",
        "internal:python",
        "internal:shellrunner",
        "internal:filesystem_write",
        "mcp:evil",
    ],
)
def test_skill_cannot_self_authorize_forbidden_or_unregistered_tool(tool: str):
    manifest = SkillManifest(
        skill_key="registry-check",
        name="registry-check",
        version="1.0.0",
        prompt_template="x",
        input_schema={},
        output_schema={},
        allowed_tools=[tool],
    )
    with pytest.raises(ValueError, match="authorized tool registry"):
        manifest.validate_tool_registry({"internal:asset_snapshot", "mcp:approved"})


def test_skill_manifest_rejects_removed_self_authorization_field():
    with pytest.raises(ValidationError, match="registered_mcp_tools"):
        SkillManifest.model_validate(
            {
                "skill_key": "strict-manifest",
                "name": "strict-manifest",
                "version": "1.0.0",
                "prompt_template": "x",
                "input_schema": {},
                "output_schema": {},
                "registered_mcp_tools": ["mcp:evil"],
            }
        )


@pytest.mark.parametrize(
    "tool",
    [
        "internal:bash",
        "internal:sh",
        "internal:cmd",
        "internal:os_system",
        "internal:file_write",
    ],
)
def test_skill_rejects_unsafe_internal_tool_even_if_registry_is_misconfigured(
    tool: str,
):
    manifest = SkillManifest(
        skill_key="closed-internal-tools",
        name="closed-internal-tools",
        version="1.0.0",
        prompt_template="x",
        input_schema={},
        output_schema={},
        allowed_tools=[tool],
    )
    with pytest.raises(ValueError, match="safe internal tool allowlist"):
        manifest.validate_tool_registry({tool})


def test_research_note_sources_are_mutually_exclusive():
    claim_note = ResearchNote(
        note_id="note-1",
        workspace_id="workspace-1",
        revision=1,
        source_kind="claim",
        claim_id="claim-1",
        summary="claim",
        created_at=NOW,
    )
    assert claim_note.run_id is None

    paragraph_note = ResearchNote(
        note_id="note-2",
        workspace_id="workspace-1",
        revision=1,
        source_kind="paragraph",
        run_id="run-1",
        paragraph_ref="artifact:1#p2",
        summary="paragraph",
        created_at=NOW,
    )
    assert paragraph_note.claim_id is None

    with pytest.raises(ValidationError, match="claim note"):
        ResearchNote(
            note_id="note-3",
            workspace_id="workspace-1",
            revision=1,
            source_kind="claim",
            claim_id="claim-1",
            run_id="run-1",
            summary="invalid",
            created_at=NOW,
        )

    with pytest.raises(ValidationError, match="paragraph note"):
        ResearchNote(
            note_id="note-4",
            workspace_id="workspace-1",
            revision=1,
            source_kind="paragraph",
            run_id="run-1",
            paragraph_ref="artifact:1#p2",
            claim_id="claim-1",
            summary="invalid",
            created_at=NOW,
        )


def test_research_message_scope_is_derived_from_session():
    assert "workspace_id" not in ResearchMessage.model_fields


@pytest.mark.parametrize(
    ("content", "content_ref"),
    [(None, None), ("message", "attachment:1"), ("   ", None), (None, "   ")],
)
def test_research_message_requires_exactly_one_nonempty_content_source(
    content: str | None, content_ref: str | None
):
    with pytest.raises(ValidationError, match="exactly one"):
        ResearchMessage(
            message_id="message-invalid",
            session_id="session-1",
            role="user",
            content=content,
            content_ref=content_ref,
            idempotency_key="message-invalid-key",
            created_at=NOW,
        )


NAIVE = datetime(2026, 8, 31, 9, 30)  # noqa: DTZ001 - invalid input under test


def _fact_payload() -> dict[str, Any]:
    return _observation().model_dump()


def _market_home_section(section_key: MarketHomeSectionKey) -> MarketHomeSection:
    return MarketHomeSection(
        section_key=section_key,
        status="ready",
        payload={},
        as_of=NOW,
        observed_at=NOW,
        available_at=NOW,
        source_refs=[SOURCE],
        freshness_status="fresh",
        quality_flags=[],
    )


def test_market_home_requires_each_fixed_section_exactly_once():
    complete_sections = [_market_home_section(key) for key in MarketHomeSectionKey]
    envelope = MarketHomeEnvelope(
        trading_day=NOW.date(),
        trading_status="closed",
        sections=complete_sections,
    )
    assert {section.section_key for section in envelope.sections} == set(MarketHomeSectionKey)

    with pytest.raises(ValidationError, match="exactly once"):
        MarketHomeEnvelope(
            trading_day=NOW.date(),
            trading_status="closed",
            sections=[*complete_sections[:-1], complete_sections[0]],
        )

    with pytest.raises(ValidationError):
        MarketHomeEnvelope(
            trading_day=NOW.date(),
            trading_status="closed",
            sections=complete_sections[:-1],
        )


@pytest.mark.parametrize(
    ("factory", "field"),
    [
        (lambda: _fact_payload(), "as_of"),
        (
            lambda: {
                "asset_id": "asset-1",
                "scheme": "wind",
                "value": "600000.SH",
                "market": "CN",
                "valid_from": NOW,
            },
            "valid_from",
        ),
        (
            lambda: {
                "event_id": "event-1",
                "event_type": "changed",
                "occurred_at": NOW,
                "payload_ref": "payload:1",
                "aggregate_type": "asset",
                "aggregate_id": "asset-1",
                "idempotency_key": "event-key",
                "sequence": 1,
            },
            "occurred_at",
        ),
        (
            lambda: {
                "job_id": "job-1",
                "owner": "scheduler",
                "job_type": "refresh",
                "idempotency_key": "job-key",
                "scheduled_for": NOW,
            },
            "scheduled_for",
        ),
        (
            lambda: {
                "workspace_id": "workspace-1",
                "project_id": "project-1",
                "title": "workspace",
                "created_at": NOW,
                "updated_at": NOW,
            },
            "created_at",
        ),
        (
            lambda: {
                "session_id": "session-1",
                "mode": "temporary",
                "created_at": NOW,
                "updated_at": NOW,
            },
            "created_at",
        ),
        (
            lambda: {
                "message_id": "message-1",
                "session_id": "session-1",
                "role": "user",
                "content": "hello",
                "idempotency_key": "message-key",
                "created_at": NOW,
            },
            "created_at",
        ),
        (
            lambda: {
                "provider_id": "provider-1",
                "provider_type": "langgraph",
                "name": "LangGraph",
                "capabilities": {"single_agent"},
                "status": "healthy",
                "checked_at": NOW,
            },
            "checked_at",
        ),
        (
            lambda: {
                "schedule_id": "schedule-1",
                "team_id": "team-1",
                "cron_expression": "0 9 * * 1-5",
                "status": "active",
                "last_run_at": NOW,
            },
            "last_run_at",
        ),
        (
            lambda: {
                "note_id": "note-1",
                "workspace_id": "workspace-1",
                "revision": 1,
                "source_kind": "claim",
                "claim_id": "claim-1",
                "summary": "note",
                "created_at": NOW,
            },
            "created_at",
        ),
        (
            lambda: {
                "peer_set_id": "peers-1",
                "asset_id": "asset-1",
                "rule": "industry",
                "sample_size": 0,
                "as_of": NOW,
            },
            "as_of",
        ),
        (
            lambda: {
                "watchlist_id": "watchlist-1",
                "profile_id": "profile-1",
                "name": "default",
                "created_at": NOW,
                "updated_at": NOW,
            },
            "created_at",
        ),
        (
            lambda: {
                "item_id": "item-1",
                "watchlist_id": "watchlist-1",
                "asset_id": "asset-1",
                "position": 0,
                "created_at": NOW,
            },
            "created_at",
        ),
        (
            lambda: {
                "rule_id": "rule-1",
                "observation_id": "obs-1",
                "status": "not_matched",
                "evaluated_at": NOW,
            },
            "evaluated_at",
        ),
        (
            lambda: {
                "event_id": "alert-1",
                "rule_id": "rule-1",
                "observation_id": "obs-1",
                "dedupe_key": "dedupe-1",
                "triggered_at": NOW,
            },
            "triggered_at",
        ),
        (
            lambda: {
                "notification_id": "notification-1",
                "alert_event_id": "alert-1",
                "profile_id": "profile-1",
                "title": "title",
                "body": "body",
                "created_at": NOW,
            },
            "created_at",
        ),
        (
            lambda: {
                **_fact_payload(),
                "snapshot_id": "snapshot-1",
                "trading_day": NOW.date(),
                "snapshot_kind": "close",
                "section_key": "a_share_status",
                "formula_version": "mainline-v1",
            },
            "as_of",
        ),
    ],
)
def test_public_contracts_reject_naive_datetimes(factory: Callable[[], dict[str, Any]], field: str):
    payload = factory()
    payload[field] = NAIVE
    model_by_keys = [
        ("snapshot_id", MarketHomeSnapshot),
        ("notification_id", Notification),
        ("dedupe_key", AlertEvent),
        ("evaluated_at", AlertEvaluation),
        ("item_id", WatchlistItem),
        ("peer_set_id", PeerSet),
        ("note_id", ResearchNote),
        ("cron_expression", AgentSchedule),
        ("provider_type", RuntimeProvider),
        ("message_id", ResearchMessage),
        ("mode", ResearchSession),
        ("project_id", ResearchWorkspace),
        ("job_type", ScheduledJob),
        ("event_type", DomainEvent),
        ("scheme", AssetIdentifier),
        ("metric_key", ObservationEnvelope),
        ("watchlist_id", Watchlist),
    ]
    model = next(model for key, model in model_by_keys if key in payload)
    with pytest.raises(ValidationError, match=field):
        model(**payload)


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
