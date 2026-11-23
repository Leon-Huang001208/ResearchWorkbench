"""Delete exclusive old chats while preserving financial and shared artifacts."""

from app.research_web.fingpt_retirement import retire_fingpt_history
from app.research_web.store import Store


def test_remove_chat_and_native_generation_without_backup(tmp_path):
    store = Store(tmp_path / "data")
    old = store.create("fingpt", "old confidential chat")
    claw = store.create("claw", "keep Claw")
    sid = old["id"]
    chat = store.directory(sid) / "outputs/chat.txt"
    chat.write_text("old chat")
    store.files(sid)
    assert all(isinstance(path, str) for path in old["files"].values())
    native = store.root / "runtime/home/sessions/project" / sid
    native.mkdir(parents=True)
    (native / "generation.jsonl").write_text("old native messages")
    store.data["receipts"][sid + ":one"] = {"digest": "old"}
    assert retire_fingpt_history(store) == {"deleted_chats": 1, "retained_data_contexts": 0}
    assert sid not in store.data["sessions"]
    assert claw["id"] in store.data["sessions"]
    assert not chat.exists() and not native.exists()
    assert not store.data["receipts"]


def test_keep_datahub_and_formal_report_references(tmp_path):
    store = Store(tmp_path / "data")
    old = store.create("fingpt", "old title")
    sid = old["id"]
    root = store.directory(sid)
    dataset = root / "inputs/datasets/d1/rows.json"
    dataset.parent.mkdir(parents=True)
    dataset.write_text('[{"value": 5.33}]')
    receipt = store.root / ".control/calls" / sid / "provider-call.json"
    receipt.parent.mkdir(parents=True)
    receipt.write_text('{"dataset_id":"d1","data_success":true}')
    chat = root / ".control/qa.json"
    chat.parent.mkdir()
    chat.write_text('{"messages": ["old chat"]}')
    output = root / "outputs/report.pdf"
    output.write_bytes(b"formal report")
    exclusive = root / "outputs/chat-attachment.txt"
    exclusive.write_text("private chat output")
    file_ids = {item["name"]: item["id"] for item in store.files(sid)}
    formal_id = file_ids["report.pdf"]
    assert all(isinstance(path, str) for path in old["files"].values())
    store.data["report_runs"]["formal"] = {"session_id": sid, "artifacts": [formal_id]}
    report = dict(store.data["report_runs"])
    assert retire_fingpt_history(store)["retained_data_contexts"] == 1
    assert dataset.read_text() == '[{"value": 5.33}]'
    assert receipt.read_text() == '{"dataset_id":"d1","data_success":true}'
    assert output.read_bytes() == b"formal report"
    assert not exclusive.exists()
    assert store.data["sessions"][sid]["files"] == {formal_id: "outputs/report.pdf"}
    assert not chat.exists()
    assert store.data["report_runs"] == report
    assert store.data["sessions"][sid]["data_only"] is True
    assert "old title" not in str(store.data["sessions"][sid])


def test_reviewed_cutover_deletes_before_install_and_keeps_deleted_baseline(tmp_path):
    from types import SimpleNamespace

    from app.research_web.multiuser.accounts import AccountStore
    from research_workbench_entrypoint.resident import model_provider_upgrade as upgrade

    home = tmp_path / "home"
    server = home / "server"
    AccountStore(server)
    (server / "users").mkdir()
    store = Store(home / "research-web")
    old = store.create("fingpt", "discard")
    claw = store.create("claw", "keep")
    (store.directory(old["id"]) / "outputs/chat.txt").write_text("delete")
    (store.directory(claw["id"]) / "outputs/keep.txt").write_text("keep")
    state = {"mode": upgrade.REVIEWED_MODE, "discard_fingpt_history": True}
    events = []

    def install(previous):
        assert old["id"] not in Store(store.root).data["sessions"]
        assert (store.directory(claw["id"]) / "outputs/keep.txt").read_text() == "keep"
        events.append(("install", previous))

    ops = SimpleNamespace(
        home=home,
        server=server,
        install=install,
        checkpoint=lambda state, name: events.append(("checkpoint", name)),
    )
    upgrade.Operations.action(ops, "activate_sources_and_wheel", state)
    assert state["fingpt_history_retired"][0]["deleted_chats"] == 1
    assert events == [("checkpoint", "activate_sources_and_wheel"), ("install", False)]
    baseline = state["before"]
    upgrade.Operations.action(ops, "restore_sources_and_wheel", state)
    assert state["before"] == baseline
    assert events[-1] == ("install", True)


def test_retained_data_contexts_are_not_retired_chat_executions(monkeypatch):
    from types import SimpleNamespace

    from app.research_web import qa_execution

    monkeypatch.setenv("RWB_ALPHADESK_QA", "1")
    service = SimpleNamespace(service_only=False)
    row = {"mode": "fingpt", "created": False}
    assert qa_execution.retired(service, row) is True
    assert qa_execution.retired(service, {**row, "data_only": True}) is False
    assert qa_execution.retired(service, {**row, "mcp_data_grant_id": "grant"}) is False


def test_cutover_registers_native_oauth_only_in_forward_gateway_config():
    from research_workbench_entrypoint.resident import model_provider_upgrade as upgrade

    old = {
        "revision": "a" * 40,
        "binding": {"revision": "a" * 40},
        "mcp_readonly_enabled": True,
        "alphadesk_qa": True,
    }
    state = {
        "mode": upgrade.REVIEWED_MODE,
        "gateway_config": old,
        "target": "b" * 40,
        "discard_fingpt_history": True,
        "fingpt_workspace_origin": "https://rwb.tail123.ts.net:9443",
    }
    forward = upgrade.gateway_configuration(state)
    assert forward["weknora_oauth_origin"] == state["fingpt_workspace_origin"]
    assert forward["weknora_cookie_isolated"] is True
    assert forward["alphadesk_qa"] is True
    assert upgrade.gateway_configuration(state, previous=True) == old
    assert "weknora_oauth_origin" not in old


def test_rollback_never_starts_an_unperformed_chat_deletion(tmp_path):
    from types import SimpleNamespace

    from research_workbench_entrypoint.resident import model_provider_upgrade as upgrade

    store = Store(tmp_path / "data")
    old = store.create("fingpt", "not deleted")
    artifact = store.directory(old["id"]) / "outputs/chat.txt"
    artifact.write_text("untouched")
    state = {"mode": upgrade.REVIEWED_MODE, "discard_fingpt_history": True}
    calls = []
    ops = SimpleNamespace(install=lambda previous: calls.append(previous))
    upgrade.Operations.action(ops, "restore_sources_and_wheel", state)
    assert calls == [True]
    assert artifact.read_text() == "untouched"
    assert "fingpt_history_retired" not in state


def test_remove_sealed_resources_but_keep_referenced_file(tmp_path):
    store = Store(tmp_path / "data")
    old = store.create("fingpt", "discard sealed chat")
    sid = old["id"]
    root = store.directory(sid)
    sealed = root / "resources/capabilities/fund-evaluation/2/scripts"
    sealed.mkdir(parents=True)
    (sealed / "workflow.py").write_text("exclusive skill")
    formal = root / "outputs/report.pdf"
    formal.write_bytes(b"formal")
    exclusive = root / "outputs/chat.txt"
    exclusive.write_text("exclusive chat")
    ids = {item["name"]: item["id"] for item in store.files(sid)}
    store.data["report_runs"]["formal"] = {"session_id": sid, "artifacts": [ids["report.pdf"]]}
    for path in sorted((root / "resources").rglob("*"), reverse=True):
        path.chmod(0o500 if path.is_dir() else 0o400)
    (root / "resources").chmod(0o500)
    (root / "outputs").chmod(0o500)
    assert retire_fingpt_history(store) == {"deleted_chats": 1, "retained_data_contexts": 1}
    assert not (root / "resources").exists()
    assert not exclusive.exists()
    assert formal.read_bytes() == b"formal"
    assert store.data["sessions"][sid]["files"] == {ids["report.pdf"]: "outputs/report.pdf"}
