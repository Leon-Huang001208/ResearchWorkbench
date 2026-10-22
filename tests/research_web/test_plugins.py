"""Plugin import and immutable, fail-closed lifecycle regressions (no network)."""

import asyncio
import io
import json
import stat
import zipfile

import pytest

from app.research_web.plugins.packages import PluginError, parse_archive
from app.research_web.plugins.service import PluginService


def bundle(manifest_path=".claude-plugin/plugin.json", version="1.0.0", extra=None):
    files = {
        manifest_path: json.dumps({"name": "fixture", "version": version}),
        "skills/read/SKILL.md": "---\nname: read\ndescription: Read supplied text\n---\nRead carefully.",
        "commands/explain.md": "Explain $ARGUMENTS using supplied evidence.",
        "agents/reviewer.md": "Review evidence. Do not invent facts.",
    }
    files.update(extra or {})
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return stream.getvalue()


@pytest.mark.parametrize(
    "manifest", ["plugin.json", ".codex-plugin/plugin.json", ".claude-plugin/plugin.json"]
)
def test_ecosystem_manifests_are_inert_and_content_addressed(manifest):
    parsed = parse_archive(bundle(manifest))
    assert parsed["name"] == "fixture"
    assert len(parsed["digest"]) == 64
    assert {row["kind"] for row in parsed["components"]} == {"skill", "command", "agent"}
    assert all(not row["ready"] for row in parsed["components"])


@pytest.mark.parametrize(
    "name", ["../escape.md", "/escape.md", "a/../escape.md", "a\\x.md", "A.md"]
)
def test_hostile_paths_and_case_collisions_rejected(name):
    extra = {name: "bad"}
    if name == "A.md":
        extra["a.md"] = "collision"
    with pytest.raises(PluginError):
        parse_archive(bundle(extra=extra))


def test_symlink_and_unknown_executable_hooks_never_execute():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        link = zipfile.ZipInfo("skills/link/SKILL.md")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(link, "/etc/passwd")
    with pytest.raises(PluginError):
        parse_archive(stream.getvalue())
    parsed = parse_archive(
        bundle(
            extra={
                "hooks/hooks.json": json.dumps(
                    {
                        "hooks": {
                            "PreToolUse": [
                                {"hooks": [{"type": "command", "command": "touch /tmp/never"}]}
                            ]
                        }
                    }
                )
            }
        )
    )
    hooks = [row for row in parsed["components"] if row["kind"] == "hook"]
    assert hooks and all(row["support"] == "unsupported" for row in hooks)


class Catalog:
    def __init__(self):
        self.items = {}

    def create(self, value):
        cid = "cap-" + str(len(self.items))
        self.items[cid] = {"id": cid, "version": 0, "status": "draft", "draft": value}
        return {"id": cid}

    def publish(self, cid, **kwargs):
        self.items[cid].update(
            version=1, status=kwargs.get("_status", "enabled"), native_name="native-" + cid
        )

    def transition(self, cid, action, version=None):
        self.items[cid]["status"] = "disabled" if action == "disable" else "enabled"

    def row(self, cid):
        return self.items[cid]


@pytest.mark.asyncio
async def test_review_upgrade_rollback_idle_and_frozen_session(tmp_path):
    catalog = Catalog()
    idle = [True]
    service = PluginService(tmp_path, catalog, None, idle_gate=lambda: idle[0])
    first = service.preview(bundle())
    with pytest.raises(PluginError, match="review_required"):
        await service.enable(first["digest"])
    service.review(first["digest"], first["permissions"], "local-admin")
    await service.enable(first["digest"])
    service.confirm_native("native-" + cid for cid in catalog.items)
    snapshot = service.pin("session-1")
    assert snapshot["plugins"][0]["digest"] == first["digest"]
    second = service.preview(bundle(version="2.0.0"))
    with pytest.raises(PluginError, match="review_required"):
        await service.enable(second["digest"])
    service.review(second["digest"], second["permissions"], "local-admin")
    idle[0] = False
    with pytest.raises(PluginError, match="runtime_busy"):
        await service.enable(second["digest"])
    idle[0] = True
    await service.enable(second["digest"])
    service.confirm_native("native-" + cid for cid in catalog.items)
    assert service.pin("session-1") == snapshot
    assert service.pin("session-2")["plugins"][0]["digest"] == second["digest"]
    await service.enable(first["digest"])
    assert service.pin("session-3")["plugins"][0]["digest"] == first["digest"]
    with pytest.raises(PluginError, match="version_pinned"):
        await service.uninstall(first["digest"])


@pytest.mark.asyncio
async def test_denied_permissions_and_hook_policy(tmp_path):
    service = PluginService(tmp_path, Catalog(), None, idle_gate=lambda: True)
    preview = service.preview(
        bundle(
            "plugin.json",
            extra={
                "plugin.json": json.dumps(
                    {
                        "name": "fixture",
                        "version": "1.0.0",
                        "extensions": {
                            "research_workbench": {
                                "hooks": [
                                    {
                                        "event": "before_message",
                                        "decision": "deny",
                                        "reason": "review required",
                                    }
                                ]
                            }
                        },
                    }
                )
            },
        )
    )
    with pytest.raises(PluginError, match="permission_mismatch"):
        service.review(preview["digest"], [], "admin")
    service.review(preview["digest"], preview["permissions"], "admin")
    await service.enable(preview["digest"])
    service.confirm_native("native-" + cid for cid in service.capabilities.items)
    with pytest.raises(PluginError, match="hook_denied"):
        service.before_message("session", "hello")


@pytest.mark.asyncio
async def test_real_native_catalog_projection_and_command(tmp_path):
    from app.research_web.capabilities.catalog import CapabilityCatalog

    catalog = CapabilityCatalog(tmp_path)
    service = PluginService(tmp_path, catalog, idle_gate=lambda: True)
    item = service.preview(bundle())
    service.review(item["digest"], item["permissions"], "admin")
    result = await service.enable(item["digest"])
    assert all(
        component["projected"] and not component["ready"] for component in result["components"]
    )
    service.confirm_native(
        row["versions"][str(row["version"])]["native_name"]
        for row in catalog.data["items"].values()
        if row["status"] == "enabled"
    )
    assert all(component["ready"] for component in service.detail(item["digest"])["components"])
    command = service.command("session1", "/fixture:explain sample")
    assert "Explain sample" in command["text"]
    native = catalog.row(command["capability"]["id"])
    assert native["status"] == "enabled"
    assert (catalog.native_root / native["versions"]["1"]["native_name"]).is_dir()
    successor = service.preview(bundle(version="2.0.0"))
    service.review(successor["digest"], successor["permissions"], "admin")
    upgraded = await service.enable(successor["digest"])
    assert upgraded["enabled"]
    assert service.pin("session1")["plugins"][0]["digest"] == item["digest"]
    assert service.command("session1", "/fixture:explain sample")["text"] == command["text"]
    old_name = native["versions"]["1"]["native_name"]
    assert service.native_authorized(old_name, "session1")
    service.confirm_native(
        row["versions"][str(row["version"])]["native_name"]
        for row in catalog.data["items"].values()
        if row["status"] == "enabled"
    )
    service.pin("session2")
    assert not service.native_authorized(old_name, "session2")
    await service.disable(item["digest"])
    with pytest.raises(PluginError, match="authorization_revoked"):
        service.command("session1", "/fixture:explain sample")
    assert (await service.enable(item["digest"]))["enabled"]


@pytest.mark.asyncio
async def test_shared_approval_projection_and_scope_collision(tmp_path):
    shared = PluginService(tmp_path / "shared", idle_gate=lambda: True)
    item = shared.preview(bundle())
    shared.review(item["digest"], item["permissions"], "admin")
    await shared.enable(item["digest"])
    tenant = PluginService(tmp_path / "tenant", Catalog(), idle_gate=lambda: True)
    await tenant.synchronize([tmp_path / "shared"])
    tenant.confirm_native("native-" + cid for cid in tenant.capabilities.items)
    assert tenant.detail(item["digest"])["enabled"]
    assert all(component["ready"] for component in tenant.detail(item["digest"])["components"])
    personal = PluginService(tmp_path / "personal", idle_gate=lambda: True)
    second = personal.preview(bundle(version="2.0.0"))
    personal.review(second["digest"], second["permissions"], "admin")
    await personal.enable(second["digest"])
    with pytest.raises(PluginError, match="scope_name_collision"):
        await tenant.synchronize([tmp_path / "shared", tmp_path / "personal"])


@pytest.mark.asyncio
async def test_launcher_without_mcp_lifecycle_defers_upgrade_and_preserves_old_sessions(tmp_path):
    source = PluginService(tmp_path / "source", idle_gate=lambda: True)
    first = source.preview(bundle())
    source.review(first["digest"], first["permissions"], "admin")
    await source.enable(first["digest"])
    tenant = PluginService(tmp_path / "tenant", Catalog(), idle_gate=lambda: True)
    await tenant.synchronize([tmp_path / "source"])
    tenant.confirm_native("native-" + cid for cid in tenant.capabilities.items)
    frozen = tenant.pin("old-session")
    tenant._row(first["digest"])["mcp_bindings"]["fixture"] = "mcp-installation-" + "a" * 32
    tenant.save()
    second = source.preview(bundle(version="2.0.0"))
    source.review(second["digest"], second["permissions"], "admin")
    await source.enable(second["digest"])
    result = await tenant.synchronize([tmp_path / "source"])
    assert result["deferred_updates"] == {"fixture": second["digest"]}
    assert tenant.pin("old-session") == frozen
    assert tenant.command("old-session", "/fixture:explain old")["text"].endswith(
        "supplied evidence."
    )
    with pytest.raises(PluginError, match="activation_deferred"):
        tenant.pin("new-session")
    await tenant.disable(first["digest"])
    assert not tenant.version_authorized(first["digest"])


@pytest.mark.asyncio
async def test_approved_old_hook_policy_survives_upgrade_until_explicit_withdrawal(tmp_path):
    def hook_bundle(version, decision):
        manifest = {
            "name": "fixture",
            "version": version,
            "extensions": {
                "research_workbench": {"hooks": [{"event": "before_message", "decision": decision}]}
            },
        }
        return bundle("plugin.json", version=version, extra={"plugin.json": json.dumps(manifest)})

    service = PluginService(tmp_path, Catalog(), idle_gate=lambda: True)
    first = service.preview(hook_bundle("1.0.0", "allow"))
    service.review(first["digest"], first["permissions"], "admin")
    await service.enable(first["digest"])
    service.confirm_native("native-" + cid for cid in service.capabilities.items)
    frozen = service.before_message("old", "message")
    second = service.preview(hook_bundle("2.0.0", "deny"))
    service.review(second["digest"], second["permissions"], "admin")
    await service.enable(second["digest"])
    service.confirm_native("native-" + cid for cid in service.capabilities.items)
    assert service.before_message("old", "message") == frozen
    with pytest.raises(PluginError, match="hook_denied"):
        service.before_message("new", "message")
    await service.disable(first["digest"])
    with pytest.raises(PluginError, match="authorization_revoked"):
        service.before_message("old", "message")


@pytest.mark.asyncio
async def test_macos_hook_sandbox_denies_host_reads_and_bounds_cancel(tmp_path):
    from app.research_web.plugins.sandbox_runner import available, run_script

    if not available():
        pytest.skip("macOS Seatbelt unavailable")
    result = await run_script(b'printf \'{"decision":"allow"}\'')
    assert result == {"decision": "allow"}
    secret = tmp_path / "secret"
    secret.write_text("private fixture")
    denied = f'if read line < "{secret}"; then printf \'{{"decision":"allow"}}\'; else printf \'{{"decision":"deny"}}\'; fi'.encode()
    assert await run_script(denied) == {"decision": "deny"}
    with pytest.raises(PluginError, match="timeout"):
        await run_script(b"while :; do :; done", timeout=0.1)
    cancel = asyncio.Event()
    cancel.set()
    with pytest.raises(PluginError, match="cancelled"):
        await run_script(b"while :; do :; done", cancel=cancel)


def test_gateway_admin_identity_cannot_be_forged(tmp_path):
    import httpx
    from fastapi.testclient import TestClient
    from test_multiuser_gateway import Pool

    from app.research_web.multiuser.accounts import AccountStore
    from app.research_web.multiuser.gateway import create_gateway

    accounts = AccountStore(tmp_path / "server")
    admin = accounts.create_user("admin", "a safe admin password", role="admin")
    consumer = accounts.create_user("consumer", "a safe consumer password")
    upstream = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={}))
    )
    app = create_gateway(accounts, Pool(), origin="http://localhost", upstream=upstream)
    with TestClient(app, base_url="http://localhost") as client:
        client.post(
            "/api/server/login",
            json={"username": "consumer", "password": "a safe consumer password"},
            headers={"Origin": "http://localhost"},
        )
        denied = client.post(
            "/api/server/plugins/shared/preview",
            files={"file": ("plugin.zip", bundle())},
            headers={
                "Origin": "http://localhost",
                "X-RWB-Page-User": consumer.id,
                "X-RWB-Role": "admin",
            },
        )
        assert denied.status_code == 403
        client.post(
            "/api/server/login",
            json={"username": "admin", "password": "a safe admin password"},
            headers={"Origin": "http://localhost"},
        )
        preview = client.post(
            "/api/server/plugins/shared/preview",
            files={"file": ("plugin.zip", bundle())},
            headers={"Origin": "http://localhost", "X-RWB-Page-User": admin.id},
        )
        assert preview.status_code == 201, preview.text
