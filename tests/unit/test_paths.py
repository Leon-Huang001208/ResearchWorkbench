"""跨平台应用数据路径解析测试。"""

from pathlib import Path


def test_app_data_dir_windows_uses_localappdata(monkeypatch, tmp_path):
    from core.settings import paths as module

    monkeypatch.delenv("ALPHAFOUNDRY_DESKTOP_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    monkeypatch.setattr(module.platform, "system", lambda: "Windows")

    result = module.app_data_dir(roaming=False)
    assert result == tmp_path / "Local" / "AlphaFoundry"


def test_app_data_dir_windows_roaming_uses_appdata(monkeypatch, tmp_path):
    from core.settings import paths as module

    monkeypatch.delenv("ALPHAFOUNDRY_DESKTOP_DATA_DIR", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setattr(module.platform, "system", lambda: "Windows")

    result = module.app_data_dir(roaming=True)
    assert result == tmp_path / "Roaming" / "AlphaFoundry"


def test_app_data_dir_macos(monkeypatch, tmp_path):
    from core.settings import paths as module

    monkeypatch.delenv("ALPHAFOUNDRY_DESKTOP_DATA_DIR", raising=False)
    monkeypatch.setattr(module.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = module.app_data_dir()
    assert result == tmp_path / "Library" / "Application Support" / "AlphaFoundry"


def test_app_data_dir_env_override(monkeypatch, tmp_path):
    from core.settings import paths as module

    override = tmp_path / "custom"
    monkeypatch.setenv("ALPHAFOUNDRY_DESKTOP_DATA_DIR", str(override))
    monkeypatch.setattr(module.platform, "system", lambda: "Windows")

    result = module.app_data_dir()
    assert result == override


def test_default_wind_workbook_path_name(monkeypatch, tmp_path):
    from core.settings import paths as module

    monkeypatch.delenv("ALPHAFOUNDRY_DESKTOP_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    monkeypatch.setattr(module.platform, "system", lambda: "Windows")

    result = module.default_wind_workbook_path()
    assert result.name == "AlphaFoundry_Wind_Realtime.xlsx"
    assert result.parent.name == "wind"


def test_migrate_legacy_wind_workbook_copies_when_target_missing(monkeypatch, tmp_path):
    """旧路径有工作簿、目标不存在时，应复制过去。"""
    from core.settings import paths as module

    legacy_dir = tmp_path / "legacy" / "wind"
    legacy_dir.mkdir(parents=True)
    legacy_path = legacy_dir / "AlphaFoundry_Wind_Realtime.xlsx"
    legacy_path.write_bytes(b"fake xlsx content")

    monkeypatch.setattr(module, "legacy_macos_style_wind_workbook_path", lambda: legacy_path)

    target = tmp_path / "target" / "AlphaFoundry_Wind_Realtime.xlsx"
    migrated = module.migrate_legacy_wind_workbook(target)

    assert migrated is True
    assert target.exists()
    assert target.read_bytes() == b"fake xlsx content"


def test_migrate_legacy_wind_workbook_skips_when_target_exists(monkeypatch, tmp_path):
    """目标已存在时，不应覆盖。"""
    from core.settings import paths as module

    legacy_dir = tmp_path / "legacy" / "wind"
    legacy_dir.mkdir(parents=True)
    legacy_path = legacy_dir / "AlphaFoundry_Wind_Realtime.xlsx"
    legacy_path.write_bytes(b"old")

    target_dir = tmp_path / "target"
    target_dir.mkdir()
    target = target_dir / "AlphaFoundry_Wind_Realtime.xlsx"
    target.write_bytes(b"new")

    monkeypatch.setattr(module, "legacy_macos_style_wind_workbook_path", lambda: legacy_path)

    migrated = module.migrate_legacy_wind_workbook(target)
    assert migrated is False
    assert target.read_bytes() == b"new"


def test_migrate_legacy_wind_workbook_no_legacy(monkeypatch, tmp_path):
    """旧路径不存在时，不迁移。"""
    from core.settings import paths as module

    legacy_path = tmp_path / "nonexistent.xlsx"
    monkeypatch.setattr(module, "legacy_macos_style_wind_workbook_path", lambda: legacy_path)

    target = tmp_path / "target.xlsx"
    migrated = module.migrate_legacy_wind_workbook(target)
    assert migrated is False
    assert not target.exists()
