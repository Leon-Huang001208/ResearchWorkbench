"""Offline plugin UI fixture with the real managed Host and official MCP SDK.

Only registry metadata/artifact transport and the model-free DSH transport are
fixtures. Installation, confirmation, authorization, Seatbelt and MCP are real.
Run only in a fresh --root. No model, vendor or resident service is contacted.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import logging
import os
import secrets
import zipfile
from pathlib import Path

CANARY = "RWB_REAL_SDK_CANARY_20261022"
SERVER = """import json,sys
for line in sys.stdin:
    try:
        request=json.loads(line)
        if "id" not in request:
            continue
        method=request.get("method")
        if method=="initialize":
            result={"protocolVersion":request["params"]["protocolVersion"],"capabilities":{"tools":{},"resources":{},"prompts":{}},"serverInfo":{"name":"offline-canary","version":"1.0.0"}}
        elif method=="tools/list":
            result={"tools":[{"name":"canary","description":"Return the supplied isolated canary","inputSchema":{"type":"object","properties":{"text":{"type":"string"}},"required":["text"],"additionalProperties":False},"annotations":{"readOnlyHint":True,"destructiveHint":False,"openWorldHint":False}}]}
        elif method=="resources/list": result={"resources":[]}
        elif method=="prompts/list": result={"prompts":[]}
        elif method=="tools/call":
            result={"content":[{"type":"text","text":"RWB_REAL_SDK_CANARY_20261022:"+request["params"]["arguments"]["text"]}],"isError":False}
        elif method=="ping": result={}
        else:
            print(json.dumps({"jsonrpc":"2.0","id":request["id"],"error":{"code":-32601,"message":"unsupported"}}),flush=True)
            continue
        print(json.dumps({"jsonrpc":"2.0","id":request["id"],"result":result}),flush=True)
    except Exception as error:
        print("fixture_protocol_error:"+type(error).__name__,file=sys.stderr,flush=True)
        raise
"""


class MemoryCredentials:
    """Explicit ephemeral backend, never a system/file credential fallback."""

    def __init__(self):
        self.values = {}

    def get_password(self, service, account):
        return self.values.get((service, account))

    def set_password(self, service, account, value):
        self.values[(service, account)] = value

    def delete_password(self, service, account):
        self.values.pop((service, account), None)


class NoModelsNative:
    """DSH discovery stub; deliberately cannot accept prompts or execute tools."""

    def __init__(self):
        self.calls = []
        self.running = set()

    async def rpc(self, method, payload):
        self.calls.append(method)
        if method == "host.describe":
            return {"version": "fixture-no-models", "model": None, "provider": None}
        if method == "session.list":
            return {"items": [{"sessionId": sid, "running": True} for sid in self.running]}
        if method == "subagent.list":
            return {"entries": []}
        if method == "skill.list":
            return {"skills": []}
        if method == "credentials.describe":
            return {
                "credentials": {
                    ref: {"configured": False, "writable": False} for ref in payload.get("refs", [])
                }
            }
        if method == "llm.models":
            return {"groups": [], "failures": []}
        from app.research_web.client import RuntimeFailure

        raise RuntimeFailure(
            "Fixture has no model or native execution", "fixture_native_method_forbidden"
        )

    async def frames(self, channel):
        yield {"type": "connected", "channel": channel}
        await asyncio.Event().wait()

    async def close(self):
        return None


def archive(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as bundle:
        for name, content in files.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 22, 0, 0, 0))
            info.external_attr = 0o100600 << 16
            bundle.writestr(info, content)
    return stream.getvalue()


def plugin_archive(version="1.0.0"):
    manifest = {
        "name": "fixture",
        "version": version,
        "extensions": {
            "research_workbench": {
                "mcp": {
                    "canary": {
                        "registry_id": "official",
                        "server_name": "io.example/canary",
                        "server_version": "1.0.0",
                        "package_index": 0,
                        "environment_names": [],
                    }
                }
            }
        },
    }
    return archive(
        {
            "plugin.json": json.dumps(manifest),
            "skills/read/SKILL.md": "---\nname: read\ndescription: Read supplied text\n---\nRead carefully.",
            "commands/explain.md": "Explain $ARGUMENTS using supplied evidence.",
            "agents/reviewer.md": "Review supplied evidence. Do not invent facts.",
            "offline-canary.mcpb": archive({"server.py": SERVER}),
        }
    )


def build_fixture(root: Path):
    """Build a fresh isolated app; real credential constructors fail closed first."""
    if root.exists():
        raise RuntimeError("fixture_requires_empty_root")
    root.mkdir(mode=0o700, parents=True)
    # Fixture entrypoints run in their own process: no provider/model configuration
    # or resident endpoint may enter the Host through inherited environment.
    os.environ.clear()
    os.environ.update(PATH=os.defpath, PYTHONIOENCODING="utf-8")
    os.environ.update(
        RESEARCH_DATA_HOME=str(root),
        RESEARCH_AUTOMATIONS_ENABLED="0",
        LOG_DIR=str(root / "logs"),
        RESEARCH_MCP_RUNTIME_ENABLED="1",
    )
    for name in ("RWB_TENANT_MODE", "RWB_SHARED_PLUGINS_ROOT", "RWB_PERSONAL_PLUGINS_ROOT"):
        os.environ.pop(name, None)
    (root / "logs").mkdir(mode=0o700)
    logger = logging.getLogger("real_plugin_fixture")
    logger.addHandler(logging.FileHandler(root / "logs/fixture.log"))
    logger.setLevel(logging.INFO)
    from app.research_web import credential_backend

    def forbidden(*_args, **_kwargs):
        raise RuntimeError("fixture_real_credential_backend_forbidden")

    import keyring

    keyring.get_password = forbidden
    keyring.set_password = forbidden
    keyring.delete_password = forbidden
    credential_backend.SystemKeyringBackend.__init__ = forbidden
    credential_backend.PrivateFileCredentialBackend.__init__ = forbidden
    memory = MemoryCredentials()
    from app.research_web.datahub import connections

    connections.default_credential_backend = lambda: memory
    from app.research_web import main as web_main

    web_main.default_credential_backend = lambda: memory
    from app.research_web.main import create_app
    from app.research_web.mcp_registry.service import MCPRegistryService
    from app.research_web.mcp_runtime.authorization import AuthorizationManager
    from app.research_web.mcp_runtime.credentials import RuntimeCredentialStore
    from app.research_web.mcp_runtime.installation_store import (
        ConfirmationTokenManager,
        InstallationStore,
    )
    from app.research_web.mcp_runtime.models import InstallationRequest, PackageArtifact
    from app.research_web.mcp_runtime.package_installer import PackageInstaller
    from app.research_web.mcp_runtime.package_planner import PackagePlanner
    from app.research_web.mcp_runtime.package_resolver import PackageResolver
    from app.research_web.mcp_runtime.sdk_host import SDKHost
    from app.research_web.mcp_runtime.service import MCPRuntimeService
    from app.research_web.service import ResearchService
    from app.research_web.store import Store

    bundle = plugin_archive()
    (root / "fixture-plugin.zip").write_bytes(bundle)
    (root / "fixture-plugin-v2.zip").write_bytes(plugin_archive("2.0.0"))
    with zipfile.ZipFile(io.BytesIO(bundle)) as plugin:
        artifact_bytes = plugin.read("offline-canary.mcpb")
    digest = hashlib.sha256(artifact_bytes).hexdigest()
    metadata = {
        "registry_id": "official",
        "name": "io.example/canary",
        "version": "1.0.0",
        "packages": [
            {
                "registry_type": "mcpb",
                "identifier": "offline-canary",
                "version": "1.0.0",
                "immutable_reference": True,
                "package_type_supported": True,
                "transport_type": "stdio",
                "environment_variables": [],
            }
        ],
        "remotes": [],
    }

    class OfflineArtifactTransport:
        def resolve(self, selection, detail, staging):
            if detail != metadata or selection.environment_names:
                raise RuntimeError("fixture_offline_selection_invalid")
            (staging / "offline-canary.mcpb").write_bytes(artifact_bytes)
            return InstallationRequest(
                registry_id=selection.registry_id,
                server_name=selection.server_name,
                server_version=selection.server_version,
                package_type="mcpb",
                package_identifier="offline-canary",
                package_version="1.0.0",
                package_source="https://offline.example/canary",
                argv=["python3", "server.py"],
                artifacts=[
                    PackageArtifact(
                        name="offline-canary",
                        version="1.0.0",
                        filename="offline-canary.mcpb",
                        sha256=digest,
                    )
                ],
                registry_sha256=digest,
                archive_path=str(staging / "offline-canary.mcpb"),
            )

    registry = MCPRegistryService(root, keyring_backend=memory)

    async def version_detail(registry_id, server_name, server_version, **_kwargs):
        if (registry_id, server_name, server_version) != ("official", "io.example/canary", "1.0.0"):
            raise RuntimeError("fixture_offline_registry_identity_invalid")
        return json.loads(json.dumps(metadata))

    registry.version_detail = version_detail
    credentials = RuntimeCredentialStore(memory)
    staging = root / "mcp-runtime/staging"
    staging.parent.mkdir(mode=0o700)
    staging.mkdir(mode=0o700)
    restarts = []

    async def idle():
        return not native.running

    async def restart(bindings):
        # This is an explicit NoModels boundary, never a claimed DSH restart.
        restarts.append(bindings)

    runtime = MCPRuntimeService(
        root,
        enabled=True,
        registry=registry,
        resolver=PackageResolver(staging, backend=OfflineArtifactTransport()),
        planner=PackagePlanner(),
        tokens=ConfirmationTokenManager(secrets.token_bytes(32), replay_root=root),
        store=InstallationStore(root, keyring_backend=memory),
        installer=PackageInstaller(staging, root / "mcp-runtime/packages", credentials=credentials),
        host=SDKHost(credentials=credentials),
        authorization=AuthorizationManager(root),
        idle_gate=idle,
        restart_callback=restart,
        control={"token": secrets.token_hex(32)},
        approval_timeout_seconds=10,
    )
    native = NoModelsNative()
    research = ResearchService(
        native,
        Store(root),
        mcp_registry=registry,
        mcp_runtime=runtime,
        mcp_keyring_backend=memory,
        delivery_keyring_backend=memory,
    )

    async def offline():
        return None

    research.frameworks.start = offline
    research.report_workflows.start = offline
    app = create_app(research)

    @app.get("/__fixture/audit")
    def audit():
        return {
            "fixture": True,
            "host": type(runtime.host).__name__,
            "installer": type(runtime.installer).__name__,
            "model_prompts": native.calls.count("session.prompt"),
            "native_methods": native.calls,
            "installations": len(runtime.store.list()),
            "no_models_binding_updates": len(restarts),
            "root": str(root),
            "canary": CANARY,
            "boundary": "real-host-sdk; no DSH/model execution",
        }

    # A pre-owned session supports the product's actual session-grant controls.
    session = research.store.create("claw", "Real SDK canary (no models)")
    app.state.fixture_session_id = session["id"]
    app.state.fixture_memory = memory
    logger.info("fixture_ready session=%s artifact_sha256=%s", session["id"], digest)
    return app


def verify_lifecycle(app, root):
    """Drive public HTTP lifecycle and internal tool dispatch, without a browser."""
    import time
    from concurrent.futures import ThreadPoolExecutor

    from fastapi.testclient import TestClient

    def checked(response, status=200):
        if response.status_code != status:
            raise AssertionError(f"HTTP {response.status_code}: {response.text[:600]}")
        return response.json()

    with TestClient(app) as client:
        service = app.state.research
        imported = checked(
            client.post(
                "/api/research/plugins/preview",
                files={
                    "file": (
                        "fixture-plugin.zip",
                        (root / "fixture-plugin.zip").read_bytes(),
                        "application/zip",
                    )
                },
            ),
            201,
        )
        digest = imported["digest"]
        base = f"/api/research/plugins/{digest}"
        checked(client.post(base + "/review", json={"permissions": imported["permissions"]}))
        checked(client.post(base + "/enable"))
        mcp = base + "/mcp/canary"
        preview = checked(client.post(mcp + "/preview"))
        assert preview["plan"]["environment_names"] == []
        rejected = client.post(
            mcp + "/install",
            json={"confirmation_token": "invalid-confirmation-token", "environment_values": {}},
        )
        assert rejected.status_code == 409
        rejected_environment = client.post(
            mcp + "/install",
            json={
                "confirmation_token": preview["confirmation_token"],
                "environment_values": {"WEATHER_TOKEN": "forbidden-fixture-value"},
            },
        )
        assert rejected_environment.status_code == 403
        installed = checked(
            client.post(
                mcp + "/install",
                json={
                    "confirmation_token": preview["confirmation_token"],
                    "environment_values": {},
                },
            )
        )
        installation = installed["installation"]["id"]
        probed = checked(client.post(mcp + "/probe"))
        assert probed["tools"][0]["name"] == "canary"
        snapshot = checked(client.post(mcp + "/status"))
        before_review = json.dumps(service.plugins._reviewed(digest)["mcp_reviews"], sort_keys=True)
        malformed = {**snapshot["fingerprint"], "unexpected": "0" * 64}
        rejected_review = client.post(mcp + "/review", json={"expected": malformed})
        assert rejected_review.status_code == 422
        assert (
            json.dumps(service.plugins._reviewed(digest)["mcp_reviews"], sort_keys=True)
            == before_review
        )
        checked(client.post(mcp + "/review", json={"expected": snapshot["fingerprint"]}))
        checked(client.post(mcp + "/enable"))
        tool = probed["tools"][0]
        binding = {
            "session_id": app.state.fixture_session_id,
            "version": "1.0.0",
            "tool_name": "canary",
            "schema_sha256": tool["schema_sha256"],
        }
        call = {
            **binding,
            "installation_id": installation,
            "call_id": "real-sdk-canary",
            "arguments": {"text": "actual-child"},
        }
        headers = {"X-Research-MCP-Key": service.mcp_runtime.runtime.control["token"]}
        denied = client.post("/api/research/internal/mcp/tools/call", json=call, headers=headers)
        assert denied.status_code == 403
        checked(client.post(mcp + "/authorize", json=binding))
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(
                client.post, "/api/research/internal/mcp/tools/call", json=call, headers=headers
            )
            approval = None
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                approvals = checked(
                    client.post(mcp + "/approvals", json={"session_id": binding["session_id"]})
                )["items"]
                if approvals:
                    approval = approvals[-1]
                    break
                if pending.done():
                    checked(pending.result())
                time.sleep(0.05)
            assert approval is not None, "real approval was not requested"
            checked(
                client.post(
                    mcp + "/decide",
                    json={
                        "session_id": binding["session_id"],
                        "approval_id": approval["id"],
                        "approve": True,
                    },
                )
            )
            result = checked(pending.result(timeout=15))
        assert CANARY + ":actual-child" in json.dumps(result)
        audit = checked(client.get("/__fixture/audit"))
        assert audit["model_prompts"] == 0
        assert audit["host"] == "SDKHost"
        evidence = {
            "status": "passed",
            "fixture_root": str(root),
            "plugin_digest": digest,
            "canary": CANARY,
            "real_sdk_result": result,
            "audit": audit,
            "role_scope": "single-user local-owner; gateway roles separately tested",
            "coverage": [
                "ZIP import",
                "permission review",
                "real HMAC confirmation",
                "real package install",
                "Seatbelt SDK initialize/list/call",
                "schema review",
                "activation",
                "session grant",
                "call approval",
                "invalid confirmation rejected",
                "credential environment rejected",
                "malformed schema snapshot rejected without mutation",
                "ungranted call rejected",
            ],
            "not_run": ["browser", "DSH runtime tool bridge", "model inference"],
        }
        (root / "lifecycle-evidence.json").write_text(json.dumps(evidence, indent=2))
        return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18991)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    app = build_fixture(args.root.resolve())
    if args.verify:
        print(json.dumps(verify_lifecycle(app, args.root.resolve())))
        return
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
