"""Pure cancellation identity remains task-scoped and requires server acceptance."""

import copy

import pytest


def values():
    task = "a" * 24
    return {"status": "accepted"}, {
        "task_id": task,
        "marker": "[RESEARCH_TASK:" + task + "]",
        "cancel_request": {
            "key": "request-a",
            "task_id": task,
            "marker": "[RESEARCH_TASK:" + task + "]",
            "accepted": True,
            "requested_at": 1,
        },
    }


def test_same_task_accepted_cancel_does_not_depend_on_execution_start_time():
    from app.research_web.delivery import accepted_task_cancel

    receipt, delivery = values()
    before = copy.deepcopy((receipt, delivery))
    assert accepted_task_cancel(receipt, delivery, "request-a", task_id="a" * 24)
    assert (receipt, delivery) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("accepted", False),
        ("accepted", "true"),
        ("key", "foreign"),
        ("task_id", "b" * 24),
        ("marker", "foreign"),
    ],
)
def test_unaccepted_or_foreign_cancel_cannot_authorize_a_cancelled_execution(field, value):
    from app.research_web.delivery import accepted_task_cancel

    receipt, delivery = values()
    delivery["cancel_request"][field] = value
    assert not accepted_task_cancel(receipt, delivery, "request-a", task_id="a" * 24)


def test_new_task_or_unaccepted_server_receipt_is_not_cancelled_by_old_request():
    from app.research_web.delivery import accepted_task_cancel

    receipt, delivery = values()
    assert not accepted_task_cancel(receipt, delivery, "request-a", task_id="b" * 24)
    assert not accepted_task_cancel({"status": "reserved"}, delivery, "request-a", task_id="a" * 24)
