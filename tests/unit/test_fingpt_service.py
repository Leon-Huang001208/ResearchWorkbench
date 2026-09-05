import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from data_layer.repositories.base import Base
from data_layer.repositories.fingpt_repository import FinGPTRepository
from data_layer.repositories.models import RuntimeArtifactDB, RuntimeWorkflowRunDB
from services.fingpt_service import FinGPTService


class FakeWorkflowService:
    def __init__(self):
        self._runtime_adapters = {}


def service(session):
    return FinGPTService(FinGPTRepository(session), FakeWorkflowService())


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    connection = sessionmaker(bind=engine)()
    try:
        yield connection
    finally:
        connection.close()


def test_generic_launch_is_single_use_and_does_not_store_prompt(db):
    result = service(db).create_task("theme-research")
    task = service(db)._repository.get_task_or_raise(result["task_id"])

    assert task.launch_id
    assert task.task_metadata == {}
    consumed = service(db).consume_launch(task.launch_id)
    assert "市场和数据库数据必须调用 AlphaFoundry Tool" in consumed["prompt"]
    with pytest.raises(KeyError):
        service(db).consume_launch(task.launch_id)


def test_sync_event_is_idempotent_and_sanitises_payload(db):
    accepted = service(db).accept_dsh_event(
        {
            "session_id": "dsh-a",
            "event_key": "event-a",
            "event_type": "turn/end",
            "sequence": 3,
            "metadata": {"title": "ignored?", "status": "idle", "secret": "no"},
            "payload": {"reason": "done", "message": "must not persist"},
        }
    )
    assert accepted is True
    assert (
        service(db).accept_dsh_event(
            {"session_id": "dsh-a", "event_key": "event-a", "event_type": "turn/end"}
        )
        is False
    )
    session = service(db).sessions()[0]
    assert session["sync_cursor"] == 3
    assert session["title"] is None


def test_artifacts_are_linked_not_duplicated(db):
    db.add(
        RuntimeWorkflowRunDB(
            run_id="run-a",
            workflow_id="w",
            workflow_version="1",
            runtime_id="dsh",
            request_payload={},
            workflow_payload={},
            status="completed",
        )
    )
    db.add(
        RuntimeArtifactDB(
            artifact_id="artifact-a",
            run_id="run-a",
            artifact_type="report_document",
            content_hash="hash",
            payload={},
        )
    )
    db.flush()
    task = service(db).create_task("daily-market-commentary")
    service(db)._repository.attach_workflow(task_id=task["task_id"], workflow_run_id="run-a")
    service(db)._repository.link_artifacts_for_workflow(
        task_id=task["task_id"], workflow_run_id="run-a"
    )
    assert service(db).artifacts(task["task_id"])[0]["artifact_id"] == "artifact-a"
