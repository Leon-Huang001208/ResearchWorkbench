"""Keep this feature's unittest temporary files inside its registered pytest root."""

import tempfile

import pytest

from core.observability import get_logger

log = get_logger(__name__)


@pytest.fixture(autouse=True)
def managed_event_temporary_files(request):
    name = request.node.path.name
    if not (
        name.startswith(("test_event_timeline", "test_event_studies", "test_market_scoring"))
        or name in {"test_event_datahub_bridge.py", "test_event_host_inputs.py"}
    ):
        return
    root = request.getfixturevalue("tmp_path")
    patch = request.getfixturevalue("monkeypatch")
    if root.is_symlink() or not root.is_dir():
        log.error("event_test_temporary_root_invalid")
        raise RuntimeError("event_test_temporary_root_invalid")
    patch.setattr(tempfile, "tempdir", str(root))
