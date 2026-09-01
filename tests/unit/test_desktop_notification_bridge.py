"""Executable and static contracts for the Tauri notification bridge."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_official_notification_plugin_is_registered_on_both_sides():
    cargo = (ROOT / "src-tauri" / "Cargo.toml").read_text(encoding="utf-8")
    rust = (ROOT / "src-tauri" / "src" / "lib.rs").read_text(encoding="utf-8")
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))

    assert 'tauri-plugin-notification = "2"' in cargo
    assert ".plugin(tauri_plugin_notification::init())" in rust
    assert "@tauri-apps/plugin-notification" in package["dependencies"]


def test_notification_capability_grants_only_three_required_operations():
    default_capability = json.loads(
        (ROOT / "src-tauri" / "capabilities" / "default.json").read_text(encoding="utf-8")
    )
    remote_capability = json.loads(
        (ROOT / "src-tauri" / "capabilities" / "notification-remote.json").read_text(
            encoding="utf-8"
        )
    )
    notification_permissions = {
        item
        for item in default_capability["permissions"]
        if isinstance(item, str) and item.startswith("notification:")
    }

    assert notification_permissions == {
        "notification:allow-is-permission-granted",
        "notification:allow-request-permission",
        "notification:allow-notify",
    }
    assert "remote" not in default_capability
    assert remote_capability == {
        "$schema": "../gen/schemas/desktop-schema.json",
        "identifier": "notification-remote",
        "description": "Notification-only permissions for the packaged local FastAPI origin",
        "local": False,
        "windows": ["main"],
        "remote": {"urls": ["http://127.0.0.1:8765/*"]},
        "permissions": [
            "notification:allow-is-permission-granted",
            "notification:allow-request-permission",
            "notification:allow-notify",
        ],
    }


def test_frontend_uses_global_tauri_notification_api_without_rust_payload_command():
    config = json.loads((ROOT / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
    rust = (ROOT / "src-tauri" / "src" / "lib.rs").read_text(encoding="utf-8")
    app = (ROOT / "app" / "web" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    bridge = (ROOT / "app" / "web" / "static" / "js" / "desktop-notifications.js").read_text(
        encoding="utf-8"
    )

    assert config["app"]["withGlobalTauri"] is True
    assert "desktop-notifications.js" in app
    assert "initDesktopNotifications" in app
    assert "window.__TAURI__.notification" in bridge
    assert "new Notification" not in bridge
    assert "deliver_persisted_notification" not in rust
    assert "NotificationExt" not in rust


def test_node_notification_behavior_suite_passes():
    result = subprocess.run(
        ["node", "--test", "tests/js/desktop_notifications.test.mjs"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
