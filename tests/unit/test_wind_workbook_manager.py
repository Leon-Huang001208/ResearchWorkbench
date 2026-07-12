"""Wind realtime workbook lifecycle manager tests."""

import sys
from pathlib import Path
from types import SimpleNamespace


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


def test_wind_workbook_manager_rebuilds_stale_open_workbook(monkeypatch, tmp_path):
    from services import wind_workbook_manager as module
    from services.wind_workbook_manager import SNAPSHOT_HEADERS, WindWorkbookManager

    catalog_path = tmp_path / "wind_index_catalog.csv"
    workbook_path = tmp_path / "book.xlsx"
    workbook_path.write_text("stale workbook placeholder", encoding="utf-8")
    catalog_path.write_text(
        "wind_code,name,family,category,is_active,priority,is_concept,view_key,view_label\n"
        "884001.WI,概念一,wind_concept,热门概念,true,100,true,wind_hot_concept,Wind热门概念\n"
        "884002.WI,概念二,wind_concept,热门概念,true,99,true,wind_hot_concept,Wind热门概念\n",
        encoding="utf-8",
    )

    class FakeRange:
        def __init__(self, value, last_row=2):
            self.value = value
            self.last_cell = SimpleNamespace(row=last_row)

    class FakeSheet:
        def __init__(self, *, active_count: int | None = None, snapshot_ok: bool = False):
            self.active_count = active_count
            self.snapshot_ok = snapshot_ok

        @property
        def used_range(self):
            if self.active_count is None:
                return FakeRange(None, last_row=2)
            return FakeRange(
                [
                    ["metric", "value", "updated_at", "notes"],
                    ["active_index_count", self.active_count, "", ""],
                ],
                last_row=2,
            )

        def range(self, *_args):
            row = ["wind_hot_concept", "Wind热门概念", "884002.WI", "概念二"]
            row.extend([100.0, 1.2, True, "wind", "2026-06-30T00:00:00", "ok"])
            return FakeRange([row] if self.snapshot_ok else [])

    class FakeBook:
        def __init__(self, path: Path, active_count: int):
            self.fullname = str(path)
            self.closed = False
            self.app = None
            self.sheets = {
                "Health": FakeSheet(active_count=active_count),
                "Snapshot": FakeSheet(snapshot_ok=True),
            }

        def close(self):
            self.closed = True
            self.fullname = ""

    class FakeBooks(list):
        def __init__(self, stale_book, fresh_book):
            super().__init__([stale_book])
            self.fresh_book = fresh_book
            self.opened = False

        def open(self, *_args, **_kwargs):
            self.opened = True
            self[:] = [self.fresh_book]
            return self.fresh_book

    stale_book = FakeBook(workbook_path, active_count=1)
    fresh_book = FakeBook(workbook_path, active_count=2)
    fake_books = FakeBooks(stale_book, fresh_book)
    fake_app = SimpleNamespace(books=fake_books, visible=True)

    class FakeApps(list):
        @property
        def active(self):
            return fake_app

    stale_book.app = fake_app
    fresh_book.app = fake_app
    fake_xlwings = SimpleNamespace(
        apps=FakeApps([fake_app]),
        App=lambda visible=False: fake_app,
    )

    built: list[tuple[Path, Path]] = []
    primed: list[Path] = []

    monkeypatch.setenv("ALPHAFOUNDRY_DESKTOP", "1")
    monkeypatch.setattr(module.platform, "system", lambda: "Darwin")
    monkeypatch.setitem(sys.modules, "xlwings", fake_xlwings)
    monkeypatch.setattr(
        module,
        "build_realtime_workbook",
        lambda catalog, workbook: built.append((Path(catalog), Path(workbook))),
    )
    monkeypatch.setattr(
        module,
        "prime_realtime_workbook_formulas",
        lambda workbook, **_kwargs: primed.append(Path(workbook)) or 1,
    )
    monkeypatch.setattr(module.subprocess, "run", lambda *_args, **_kwargs: None)

    manager = WindWorkbookManager(
        workbook_path=workbook_path,
        catalog_path=catalog_path,
    )
    status = manager.ensure_ready(reason="catalog_changed")

    assert len(SNAPSHOT_HEADERS) == 10
    assert built == [(catalog_path, workbook_path)]
    assert stale_book.closed is True
    assert fake_books.opened is True
    assert primed == []
    assert status.status == "ready"
    assert status.ready is True
    assert status.built is True
