"""FinGPT native plan contracts; fixtures do not certify live model execution."""

import pytest
from pydantic import ValidationError

from app.research_web.main import NewSession, Prompt
from app.research_web.projection import project


def entries(*events):
    return [
        {"event": {"seq": index, "type": kind, "data": data}}
        for index, (kind, data) in enumerate(events, 1)
    ]


def test_plan_is_native_whole_list_and_does_not_certify_delivery():
    view = project(
        entries(
            ("turn/start", {"turn": 1}),
            ("todo/write", {"todos": [{"content": "检索资料", "status": "pending"}]}),
            ("todo/write", {"todos": [{"content": "汇总报告", "status": "completed"}]}),
            ("turn/end", {"reason": {"kind": "error", "error": {"message": "failed"}}}),
        )
    )
    assert view["research_plan"]["items"] == [{"content": "汇总报告", "status": "completed"}]
    assert view["research_plan"]["seq"] == 3
    assert view["research_plan"]["turn"] == 1
    assert view["status"] == "failed"


def test_new_turn_clears_plan_and_bad_event_does_not_restore_old_success():
    old = ("todo/write", {"todos": [{"content": "旧计划", "status": "completed"}]})
    view = project(entries(("turn/start", {"turn": 1}), old, ("turn/start", {"turn": 2})))
    assert view["research_plan"] is None
    view = project(
        entries(
            ("turn/start", {"turn": 2}),
            old,
            ("todo/write", {"todos": [{"content": "坏状态", "status": "blocked"}]}),
        )
    )
    assert view["research_plan"]["status"] == "invalid"
    assert view["research_plan"]["items"] == []


def test_plan_without_turn_cannot_claim_complete_history():
    view = project(entries(("todo/write", {"todos": [{"content": "计划", "status": "pending"}]})))
    assert view["research_plan"]["history_complete"] is False


def test_request_depth_and_pdf_preserve_legacy_default_and_reject_unknown_depth():
    assert NewSession().research_depth == "instant"
    assert NewSession(research_depth="deep").research_depth == "deep"
    assert Prompt(text="研究", expected_formats=["pdf"]).expected_formats == ["pdf"]
    with pytest.raises(ValidationError):
        NewSession(research_depth="unlimited")


@pytest.mark.parametrize("outcome", ["completed", "failed"])
def test_pinned_dsh_native_tool_role_result_is_projected_without_legacy_wrapper(outcome):
    view = project(
        entries(
            ("tool/call", {"callId": "script", "name": "research_run_script", "arguments": "{}"}),
            (
                "tool/result",
                {
                    "message": {
                        "role": "tool",
                        "toolCallId": "script",
                        "source": {"callId": "script"},
                        "content": [{"type": "text", "text": '{"status":"' + outcome + '"}'}],
                    }
                },
            ),
        )
    )
    assert view["activities"][0]["status"] == outcome
    assert outcome in view["activities"][0]["detail"]
