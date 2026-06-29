"""Wind realtime workbook lifecycle manager tests."""

from pathlib import Path


def test_wind_workbook_manager_autostart_requires_desktop_mac(monkeypatch, tmp_path):
    from services import wind_workbook_manager as module
    from services.wind_workbook_manager import WindWorkbookManager

    monkeypatch.delenv("ALPHAFOUNDRY_DESKTOP", raising=False)
    monkeypatch.delenv("ALPHAFOUNDRY_WIND_WORKBOOK_AUTOSTART", raising=False)
    monkeypatch.setattr(module.platform, "system", lambda: "Darwin")

    manager = WindWorkbookManager(workbook_path=tmp_path / "book.xlsx")

    assert manager.autostart_enabled() is False

    monkeypatch.setenv("ALPHAFOUNDRY_DESKTOP", "1")
    assert manager.autostart_enabled() is True


def test_wind_workbook_manager_autostart_env_override(monkeypatch, tmp_path):
    from services import wind_workbook_manager as module
    from services.wind_workbook_manager import WindWorkbookManager

    monkeypatch.setenv("ALPHAFOUNDRY_DESKTOP", "1")
    monkeypatch.setenv("ALPHAFOUNDRY_WIND_WORKBOOK_AUTOSTART", "0")
    monkeypatch.setattr(module.platform, "system", lambda: "Darwin")

    manager = WindWorkbookManager(workbook_path=tmp_path / "book.xlsx")

    assert manager.autostart_enabled() is False
    status = manager.start_background_ensure(reason="test")
    assert status.status == "disabled"
    assert status.ready is False


def test_wind_workbook_manager_starts_one_background_thread(monkeypatch, tmp_path):
    from services import wind_workbook_manager as module
    from services.wind_workbook_manager import WindWorkbookManager

    started: list[str] = []

    class FakeThread:
        def __init__(self, target, kwargs, name, daemon):
            self.target = target
            self.kwargs = kwargs
            self.name = name
            self.daemon = daemon
            self._alive = False

        def start(self):
            started.append(self.name)
            self._alive = True

        def is_alive(self):
            return self._alive

    monkeypatch.setenv("ALPHAFOUNDRY_DESKTOP", "1")
    monkeypatch.delenv("ALPHAFOUNDRY_WIND_WORKBOOK_AUTOSTART", raising=False)
    monkeypatch.setattr(module.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(module, "Thread", FakeThread)

    manager = WindWorkbookManager(workbook_path=Path(tmp_path) / "book.xlsx")
    first = manager.start_background_ensure(reason="startup")
    second = manager.start_background_ensure(reason="api_recovery")

    assert first.status == "starting"
    assert second.status == "starting"
    assert started == ["wind-workbook-manager"]
