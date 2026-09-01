"""Static contracts for the least-privilege Tauri notification bridge."""

from __future__ import annotations

import json
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
    capability = json.loads(
        (ROOT / "src-tauri" / "capabilities" / "default.json").read_text(encoding="utf-8")
    )
    notification_permissions = {
        item
        for item in capability["permissions"]
        if isinstance(item, str) and item.startswith("notification:")
    }

    assert notification_permissions == {
        "notification:allow-is-permission-granted",
        "notification:allow-request-permission",
        "notification:allow-notify",
    }


def test_rust_bridge_accepts_only_bounded_persisted_safe_payload():
    rust = (ROOT / "src-tauri" / "src" / "lib.rs").read_text(encoding="utf-8")

    assert "deliver_persisted_notification" in rust
    assert "notification_id" in rust
    assert "MAX_NOTIFICATION_TITLE_CHARS" in rust
    assert "MAX_NOTIFICATION_BODY_CHARS" in rust
    assert "NotificationExt" in rust
    assert "notification title" not in rust.lower()
    assert "notification body" not in rust.lower()
