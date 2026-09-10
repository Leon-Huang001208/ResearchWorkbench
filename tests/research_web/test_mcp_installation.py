from __future__ import annotations

import base64
import hashlib
import importlib
import inspect
import io
import json
import tarfile
import tempfile
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.research_web.mcp_runtime import models as installation_models
from app.research_web.mcp_runtime.credentials import RuntimeCredentialStore
from app.research_web.mcp_runtime.installation_store import (
    ConfirmationError,
    ConfirmationTokenManager,
    InstallationStore,
    InstallationStoreError,
)
from app.research_web.mcp_runtime.models import InstallationRequest, PackageArtifact
from app.research_web.mcp_runtime.package_planner import (
    PackagePlanError,
    PackagePlanner,
)
from app.research_web.mcp_runtime.package_resolver import (
    PackageResolutionError,
    PackageResolver,
)

_PAYLOADS: dict[str, bytes] = {}


class _Keyring:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, account: str):
        return self.values.get((service, account))

    def set_password(self, service: str, account: str, value: str):
        self.values[(service, account)] = value

    def delete_password(self, service: str, account: str):
        self.values.pop((service, account), None)


class _FailingKeyring(_Keyring):
    def set_password(self, service: str, account: str, value: str):
        raise RuntimeError("keyring unavailable with secret payload")


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _artifact(
    *,
    name: str = "@example/server",
    version: str = "1.2.3",
    payload: bytes = b"artifact",
    filename: str = "server.tgz",
) -> PackageArtifact:
    if filename.lower().endswith(".tgz"):
        manifest = json.dumps({"name": name, "version": version}).encode("utf-8")
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            member = tarfile.TarInfo("package/package.json")
            member.size = len(manifest)
            archive.addfile(member, io.BytesIO(manifest))
        payload = buffer.getvalue()
    elif filename.lower().endswith(".whl"):
        buffer = io.BytesIO()
        dist_info = f"{name.replace('-', '_')}-{version}.dist-info"
        with zipfile.ZipFile(buffer, "w") as wheel:
            wheel.writestr(f"{name.replace('-', '_')}/__init__.py", "")
            wheel.writestr(f"{dist_info}/METADATA", f"Name: {name}\nVersion: {version}\n")
            wheel.writestr(
                f"{dist_info}/WHEEL",
                "Wheel-Version: 1.0\nGenerator: tests\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
            )
            wheel.writestr(f"{dist_info}/RECORD", "")
        payload = buffer.getvalue()
    digest = _sha(payload)
    _PAYLOADS[digest] = payload
    integrity = "sha512-" + base64.b64encode(hashlib.sha512(payload).digest()).decode("ascii")
    return PackageArtifact(
        name=name,
        version=version,
        filename=filename,
        sha256=digest,
        integrity=integrity,
    )


def _request(package_type: str = "npm", **changes: object) -> InstallationRequest:
    payload: dict[str, object] = {
        "registry_id": "official",
        "server_name": "example/server",
        "server_version": "1.2.3",
        "package_type": package_type,
        "package_identifier": "@example/server" if package_type == "npm" else "example-server",
        "package_version": "1.2.3",
        "package_source": (
            "https://registry.npmjs.org" if package_type == "npm" else "https://pypi.org"
        ),
        "argv": ["node", "dist/server.js", "--stdio"],
        "environment_names": ["EXAMPLE_API_KEY"],
        "inherit_environment": False,
        "lifecycle_hooks": [],
        "artifacts": [_artifact()],
        "package_lock_sha256": _sha(b"package-lock"),
    }
    payload.update(changes)
    return InstallationRequest.model_validate(payload)


class _FixtureBackend:
    def __init__(self, request: InstallationRequest) -> None:
        self.request = request

    def resolve(self, selection, registry_detail, staging_directory):
        del selection, registry_detail
        for artifact in self.request.artifacts:
            (staging_directory / artifact.filename).write_bytes(_PAYLOADS[artifact.sha256])
        request = self.request
        if request.package_type == "npm" and request.package_lock_sha256 is not None:
            packages = {}
            for artifact in request.artifacts:
                key = f"node_modules/{artifact.name}"
                packages[key] = {
                    "name": artifact.name,
                    "version": artifact.version,
                    "integrity": artifact.integrity,
                }
            lock = json.dumps(
                {"name": request.package_identifier, "lockfileVersion": 3, "packages": packages},
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            (staging_directory / "package-lock.json").write_bytes(lock)
            request = request.model_copy(update={"package_lock_sha256": _sha(lock)}, deep=True)
        return request


def _plan(request: InstallationRequest):
    temporary = tempfile.TemporaryDirectory()
    plan, _ = _resolved_plan(request, Path(temporary.name))
    temporary.cleanup()
    return plan


def _resolved_plan(request: InstallationRequest, root: Path):
    staging_root = root / "staging"
    selection = installation_models.InstallationSelection(
        registry_id=request.registry_id,
        server_name=request.server_name,
        server_version=request.server_version,
        package_index=0,
        environment_names=list(request.environment_names),
    )
    detail = {
        "registry_id": request.registry_id,
        "name": request.server_name,
        "version": request.server_version,
        "packages": [
            {
                "registry_type": request.package_type,
                "identifier": request.package_identifier,
                "version": request.package_version,
                "immutable_reference": True,
                "package_type_supported": True,
                "transport_type": "stdio",
                "environment_variables": [{"name": name} for name in request.environment_names],
            }
        ],
        "remotes": [],
    }
    resolver = PackageResolver(
        staging_root,
        registry_lookup=lambda ignored: detail,
        backend=_FixtureBackend(request),
    )
    resolution = resolver.resolve(selection)
    plan = PackagePlanner().plan(resolution)
    return plan, staging_root


def test_public_installation_selection_accepts_only_registry_target_and_environment_names() -> None:
    InstallationSelection = getattr(installation_models, "InstallationSelection", None)
    assert InstallationSelection is not None, "minimal public selection is not implemented"
    selection = InstallationSelection.model_validate(
        {
            "registry_id": "official",
            "server_name": "example/server",
            "server_version": "1.2.3",
            "package_index": 0,
            "environment_names": ["EXAMPLE_API_KEY"],
        }
    )
    assert selection.model_dump() == {
        "registry_id": "official",
        "server_name": "example/server",
        "server_version": "1.2.3",
        "package_index": 0,
        "remote_index": None,
        "environment_names": ["EXAMPLE_API_KEY"],
    }

    with pytest.raises(ValidationError):
        InstallationSelection.model_validate(
            {
                **selection.model_dump(),
                "argv": ["python", "attacker.py"],
                "artifacts": [{"sha256": "0" * 64}],
            }
        )


def test_planner_rejects_browser_constructible_installation_request() -> None:
    with pytest.raises(PackagePlanError, match="trusted_resolution"):
        PackagePlanner().plan(_request())  # type: ignore[arg-type]


def test_package_installer_fails_closed_when_npm_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = importlib.import_module("app.research_web.mcp_runtime.package_installer")
    plan, staging_root = _resolved_plan(_request(environment_names=[]), tmp_path)
    monkeypatch.setattr(module.shutil, "which", lambda ignored: None)
    installer = module.PackageInstaller(staging_root, tmp_path / "installed")

    with pytest.raises(module.PackageInstallError, match="unavailable"):
        installer.install(plan)


def test_default_package_installer_installs_verified_pypi_wheel_offline(
    tmp_path: Path,
) -> None:
    module = importlib.import_module("app.research_web.mcp_runtime.package_installer")
    request = _request(
        "pypi",
        package_identifier="example-server",
        package_source="https://pypi.org",
        argv=["python", "-m", "example_server"],
        environment_names=[],
        artifacts=[
            _artifact(
                name="example-server",
                filename="example_server-1.2.3-py3-none-any.whl",
            )
        ],
        package_lock_sha256=None,
    )
    plan, staging_root = _resolved_plan(request, tmp_path)
    destination = module.PackageInstaller(staging_root, tmp_path / "installed").install(plan)

    assert destination.is_dir()
    assert (destination / "example_server" / "__init__.py").is_file()


def test_installer_publishes_by_manifest_id_and_builds_keyring_backed_target(
    tmp_path: Path,
) -> None:
    module = importlib.import_module("app.research_web.mcp_runtime.package_installer")
    request = _request(
        "pypi",
        package_identifier="example-server",
        package_source="https://pypi.org",
        argv=["python", "-m", "example_server"],
        artifacts=[
            _artifact(
                name="example-server",
                filename="example_server-1.2.3-py3-none-any.whl",
            )
        ],
        package_lock_sha256=None,
    )
    plan, staging_root = _resolved_plan(request, tmp_path)
    tokens = ConfirmationTokenManager(b"s" * 32, replay_root=tmp_path)
    manifest = InstallationStore(tmp_path, integrity_key=b"k" * 32).create(
        plan, tokens.issue(plan), tokens
    )
    credentials = RuntimeCredentialStore(_Keyring())
    installer = module.PackageInstaller(
        staging_root, tmp_path / "installed", credentials=credentials
    )

    destination = installer.install(manifest, {"EXAMPLE_API_KEY": "secret"})
    target = installer.target(manifest)

    assert destination.name == manifest.id
    assert target.cwd == destination
    assert target.argv[0].startswith(str(destination))
    assert target.env["EXAMPLE_API_KEY"] == "secret"


def test_installer_rolls_back_published_payload_when_keyring_write_fails(
    tmp_path: Path,
) -> None:
    module = importlib.import_module("app.research_web.mcp_runtime.package_installer")
    request = _request(
        "pypi",
        package_identifier="example-server",
        package_source="https://pypi.org",
        argv=["python", "-m", "example_server"],
        artifacts=[
            _artifact(
                name="example-server",
                filename="example_server-1.2.3-py3-none-any.whl",
            )
        ],
        package_lock_sha256=None,
    )
    plan, staging_root = _resolved_plan(request, tmp_path)
    tokens = ConfirmationTokenManager(b"s" * 32, replay_root=tmp_path)
    manifest = InstallationStore(tmp_path, integrity_key=b"k" * 32).create(
        plan, tokens.issue(plan), tokens
    )
    installer = module.PackageInstaller(
        staging_root,
        tmp_path / "installed",
        credentials=RuntimeCredentialStore(_FailingKeyring()),
    )

    with pytest.raises(module.PackageInstallError, match="credential_store"):
        installer.install(manifest, {"EXAMPLE_API_KEY": "secret"})

    assert not (tmp_path / "installed" / manifest.id).exists()


def test_default_resolver_reports_missing_package_manager(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolver_module = importlib.import_module("app.research_web.mcp_runtime.package_resolver")
    monkeypatch.setattr(resolver_module.shutil, "which", lambda ignored: None)
    selection = installation_models.InstallationSelection(
        registry_id="official",
        server_name="example/server",
        server_version="1.2.3",
        package_index=0,
    )
    detail = {
        "registry_id": "official",
        "name": "example/server",
        "version": "1.2.3",
        "packages": [
            {
                "registry_type": "npm",
                "identifier": "@example/server",
                "version": "1.2.3",
                "transport_type": "stdio",
                "immutable_reference": True,
                "package_type_supported": True,
                "environment_variables": [],
            }
        ],
        "remotes": [],
    }

    with pytest.raises(PackageResolutionError, match="unavailable"):
        resolver_module.PackageResolver(tmp_path / "staging").resolve(selection, detail)


def test_remote_preview_locks_registry_endpoint_without_artifacts(tmp_path: Path) -> None:
    selection = installation_models.InstallationSelection(
        registry_id="official",
        server_name="example/server",
        server_version="1.2.3",
        remote_index=0,
        environment_names=[],
    )
    detail = {
        "registry_id": "official",
        "name": "example/server",
        "version": "1.2.3",
        "packages": [],
        "remotes": [{"type": "streamable-http", "url": "https://mcp.example.test/api"}],
    }

    resolution = PackageResolver(tmp_path / "staging").resolve(selection, detail)
    plan = PackagePlanner().plan(resolution)

    assert plan.target_kind == "remote"
    assert plan.endpoint == "https://mcp.example.test/api"
    assert "artifacts" not in plan.model_dump()
    assert "argv" not in plan.model_dump()
    assert plan.environment_names == []

    tokens = ConfirmationTokenManager(b"s" * 32, replay_root=tmp_path)
    store = InstallationStore(tmp_path, integrity_key=b"k" * 32)
    manifest = store.create(plan, tokens.issue(plan), tokens)
    assert store.get(manifest.id).plan.target_kind == "remote"


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://mcp.example.test/api",
        "http://localhost:8080/api",
        "https://user:secret@mcp.example.test/api",
    ],
)
def test_remote_preview_rejects_insecure_or_credentialed_endpoint(
    tmp_path: Path, endpoint: str
) -> None:
    selection = installation_models.InstallationSelection(
        registry_id="official",
        server_name="example/server",
        server_version="1.2.3",
        remote_index=0,
    )
    detail = {
        "registry_id": "official",
        "name": "example/server",
        "version": "1.2.3",
        "packages": [],
        "remotes": [{"type": "streamable-http", "url": endpoint}],
    }
    with pytest.raises(PackageResolutionError, match="endpoint"):
        PackageResolver(tmp_path / "staging").resolve(selection, detail)


def test_remote_preview_rejects_environment_passthrough(tmp_path: Path) -> None:
    selection = installation_models.InstallationSelection(
        registry_id="official",
        server_name="example/server",
        server_version="1.2.3",
        remote_index=0,
        environment_names=["PASSTHROUGH_TOKEN"],
    )
    detail = {
        "registry_id": "official",
        "name": "example/server",
        "version": "1.2.3",
        "packages": [],
        "remotes": [{"type": "streamable-http", "url": "https://mcp.example.test/api"}],
    }

    with pytest.raises(PackageResolutionError, match="passthrough"):
        PackageResolver(tmp_path / "staging").resolve(selection, detail)


def test_selection_requires_exactly_one_package_or_remote() -> None:
    identity = {
        "registry_id": "official",
        "server_name": "example/server",
        "server_version": "1.2.3",
    }
    with pytest.raises(ValidationError):
        installation_models.InstallationSelection.model_validate(identity)
    with pytest.raises(ValidationError):
        installation_models.InstallationSelection.model_validate(
            {**identity, "package_index": 0, "remote_index": 0}
        )


def test_installation_request_rejects_shell_string_and_ambient_environment() -> None:
    with pytest.raises(ValidationError):
        _request(argv="node server.js && curl attacker")

    with pytest.raises(ValidationError):
        _request(inherit_environment=True)


@pytest.mark.parametrize(
    "version",
    ["latest", "^1.2.3", "~1.2.3", ">=1.2.3", "1.*", "1.2.x", "1.2.3 || 2.0.0"],
)
def test_npm_planner_rejects_non_fixed_versions(version: str) -> None:
    with pytest.raises((ValidationError, PackagePlanError)):
        _plan(_request(package_version=version))


def test_npm_planner_rejects_lifecycle_hooks_and_missing_dependency_hashes() -> None:
    with pytest.raises((ValidationError, PackagePlanError), match="lifecycle"):
        _plan(_request(lifecycle_hooks=["postinstall"]))

    with pytest.raises((ValidationError, PackagePlanError)):
        _plan(_request(artifacts=[]))

    with pytest.raises(ValidationError):
        _artifact(name="transitive", version="4.5.6", payload=b"", filename="dep.tgz").model_copy(
            update={"sha256": ""}
        ).model_dump()
        _request(
            artifacts=[
                _artifact(),
                {
                    "name": "transitive",
                    "version": "4.5.6",
                    "filename": "dep.tgz",
                    "sha256": "",
                },
            ]
        )

    with pytest.raises((PackagePlanError, PackageResolutionError), match="artifact|lock"):
        _plan(_request(package_lock_sha256=None))

    with pytest.raises((PackagePlanError, PackageResolutionError), match="integrity"):
        _plan(_request(artifacts=[_artifact().model_copy(update={"integrity": None})]))


def test_npm_plan_preserves_untruncated_argv_and_all_artifact_hashes() -> None:
    long_argument = "x" * 12_000
    dependency = _artifact(
        name="transitive", version="4.5.6", payload=b"dependency", filename="dep.tgz"
    )
    plan = _plan(
        _request(
            argv=["node", "dist/server.js", long_argument], artifacts=[_artifact(), dependency]
        )
    )

    assert plan.argv[-1] == long_argument
    assert plan.install_argv[:5] == ["npm", "ci", "--ignore-scripts", "--offline", "--cache"]
    assert [item.sha256 for item in plan.artifacts] == [_artifact().sha256, dependency.sha256]
    assert plan.environment_names == ["EXAMPLE_API_KEY"]
    assert plan.canonical_summary["argv"][-1] == long_argument
    assert plan.summary_sha256 == _sha(
        json.dumps(
            plan.canonical_summary,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def test_pypi_planner_requires_fixed_wheels_with_hashes() -> None:
    request = _request(
        "pypi",
        argv=["python", "-m", "example_server"],
        artifacts=[
            _artifact(
                name="example-server",
                version="1.2.3",
                payload=b"wheel",
                filename="example_server-1.2.3-py3-none-any.whl",
            ),
            _artifact(
                name="dependency",
                version="4.5.6",
                payload=b"dependency-wheel",
                filename="dependency-4.5.6-py3-none-any.whl",
            ),
        ],
        package_lock_sha256=None,
    )
    plan = _plan(request)

    assert plan.install_argv[:5] == ["python", "-m", "pip", "install", "--no-index"]
    assert "--require-hashes" in plan.install_argv
    assert all(item.filename.endswith(".whl") for item in plan.artifacts)

    with pytest.raises((ValidationError, PackagePlanError)):
        _plan(
            _request(
                "pypi",
                package_version=">=1.2",
                artifacts=[_artifact(filename="example-server.tar.gz")],
                package_lock_sha256=None,
            )
        )


def _write_mcpb(path: Path, members: dict[str, bytes]) -> str:
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
    return _sha(path.read_bytes())


def test_mcpb_planner_verifies_digest_and_rejects_archive_escape(tmp_path: Path) -> None:
    archive = tmp_path / "server.mcpb"
    digest = _write_mcpb(archive, {"server.json": b"{}", "dist/server.js": b"ok"})
    plan = _plan(
        _request(
            "mcpb",
            package_source="https://registry.example.test",
            argv=["node", "dist/server.js"],
            artifacts=[
                _artifact(
                    name="example-server",
                    payload=archive.read_bytes(),
                    filename="server.mcpb",
                )
            ],
            archive_path=str(archive),
            registry_sha256=digest,
            package_lock_sha256=None,
        )
    )
    assert plan.package_type == "mcpb"

    with pytest.raises((PackagePlanError, PackageResolutionError), match="digest"):
        _plan(
            _request(
                "mcpb",
                package_source="https://registry.example.test",
                artifacts=[
                    _artifact(
                        name="example-server",
                        payload=archive.read_bytes(),
                        filename="server.mcpb",
                    )
                ],
                archive_path=str(archive),
                registry_sha256="0" * 64,
                package_lock_sha256=None,
            )
        )

    escaped = tmp_path / "escaped.mcpb"
    escaped_digest = _write_mcpb(escaped, {"../outside": b"bad"})
    with pytest.raises(PackagePlanError, match="archive"):
        _plan(
            _request(
                "mcpb",
                package_source="https://registry.example.test",
                artifacts=[
                    _artifact(
                        name="example-server",
                        payload=escaped.read_bytes(),
                        filename="escaped.mcpb",
                    )
                ],
                archive_path=str(escaped),
                registry_sha256=escaped_digest,
                package_lock_sha256=None,
            )
        )


def test_mcpb_planner_rejects_symlink_archive_members(tmp_path: Path) -> None:
    archive = tmp_path / "symlink.mcpb"
    with zipfile.ZipFile(archive, "w") as bundle:
        member = zipfile.ZipInfo("linked-server")
        member.external_attr = 0o120777 << 16
        bundle.writestr(member, "server.js")
    digest = _sha(archive.read_bytes())

    with pytest.raises(PackagePlanError, match="symlink"):
        _plan(
            _request(
                "mcpb",
                package_source="https://registry.example.test",
                artifacts=[
                    _artifact(
                        name="example-server",
                        payload=archive.read_bytes(),
                        filename="symlink.mcpb",
                    )
                ],
                archive_path=str(archive),
                registry_sha256=digest,
                package_lock_sha256=None,
            )
        )


def test_confirmation_token_is_short_lived_and_bound_to_exact_summary() -> None:
    clock = [datetime(2026, 9, 11, 8, 0, tzinfo=UTC)]
    manager = ConfirmationTokenManager(
        b"s" * 32,
        ttl=timedelta(seconds=30),
        now=lambda: clock[0],
    )
    plan = _plan(_request())
    token = manager.issue(plan)

    manager.verify(token, plan)
    with pytest.raises(ConfirmationError, match="mismatch"):
        manager.verify(token, _plan(_request(argv=["node", "changed.js"])))

    clock[0] += timedelta(seconds=30)
    with pytest.raises(ConfirmationError, match="expired"):
        manager.verify(token, plan)


def test_confirmation_replay_store_is_required_and_shared_across_managers(tmp_path: Path) -> None:
    signature = inspect.signature(ConfirmationTokenManager)
    assert "replay_root" in signature.parameters, "persistent replay store is not implemented"
    plan = _plan(_request())
    first = ConfirmationTokenManager(b"s" * 32, replay_root=tmp_path)
    second = ConfirmationTokenManager(b"s" * 32, replay_root=tmp_path)
    token = first.issue(plan)

    first.verify(token, plan, consume=True)
    with pytest.raises(ConfirmationError, match="replayed"):
        second.verify(token, plan, consume=True)


def test_confirmation_token_rejects_tampering() -> None:
    manager = ConfirmationTokenManager(b"s" * 32)
    plan = _plan(_request())
    token = manager.issue(plan)
    replacement = "a" if token[-1] != "a" else "b"

    with pytest.raises(ConfirmationError, match="invalid"):
        manager.verify(f"{token[:-1]}{replacement}", plan)


def test_confirmation_rejects_deep_mutation_after_preview() -> None:
    manager = ConfirmationTokenManager(b"s" * 32)
    plan = _plan(_request())
    token = manager.issue(plan)

    plan.argv[-1] = "changed-after-preview"
    with pytest.raises(ConfirmationError, match="mismatch"):
        manager.verify(token, plan)


def test_installation_store_persists_immutable_manifest_atomically(tmp_path: Path) -> None:
    plan = _plan(_request())
    tokens = ConfirmationTokenManager(b"s" * 32, replay_root=tmp_path)
    token = tokens.issue(plan)
    store = InstallationStore(tmp_path, integrity_key=b"k" * 32)

    installed = store.create(plan, token, tokens)

    assert installed.id.startswith("mcp-installation-")
    assert installed.manifest_sha256
    assert store.get(installed.id) == installed
    assert store.list() == [installed]
    path = tmp_path / "mcp-runtime" / "installations" / installed.id / "manifest.json"
    assert path.is_file()
    assert not list(path.parent.glob(".manifest-*"))
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["plan"]["summary_sha256"] == plan.summary_sha256
    assert token not in path.read_text(encoding="utf-8")

    with pytest.raises(InstallationStoreError, match="immutable"):
        store.create(plan, tokens.issue(plan), tokens, installation_id=installed.id)


def test_installation_store_requires_keyed_integrity_and_private_runtime_root(
    tmp_path: Path,
) -> None:
    signature = inspect.signature(InstallationStore)
    assert "integrity_key" in signature.parameters, "keyed manifest integrity is not implemented"

    runtime = tmp_path / "mcp-runtime"
    runtime.mkdir(mode=0o755)
    with pytest.raises(InstallationStoreError, match="private|unsafe"):
        InstallationStore(tmp_path, integrity_key=b"k" * 32)


def test_installation_confirmation_is_single_use(tmp_path: Path) -> None:
    plan = _plan(_request())
    tokens = ConfirmationTokenManager(b"s" * 32, replay_root=tmp_path)
    token = tokens.issue(plan)
    store = InstallationStore(tmp_path, integrity_key=b"k" * 32)
    store.create(plan, token, tokens)

    with pytest.raises(ConfirmationError, match="replayed"):
        store.create(plan, token, tokens)


def test_atomic_manifest_never_overwrites_a_racing_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.research_web.mcp_runtime import installation_store

    plan = _plan(_request())
    tokens = ConfirmationTokenManager(b"s" * 32, replay_root=tmp_path)
    store = InstallationStore(tmp_path, integrity_key=b"k" * 32)
    installation_id = "mcp-installation-" + "b" * 32
    destination = tmp_path / "mcp-runtime" / "installations" / installation_id / "manifest.json"
    link = installation_store.os.link

    def create_racing_target(source: str | Path, target: str | Path, **kwargs: object) -> None:
        Path(target).write_text("racing-target", encoding="utf-8")
        link(source, target, **kwargs)

    monkeypatch.setattr(installation_store.os, "link", create_racing_target)
    with pytest.raises(InstallationStoreError, match="immutable"):
        store.create(
            plan,
            tokens.issue(plan),
            tokens,
            installation_id=installation_id,
        )

    assert destination.read_text(encoding="utf-8") == "racing-target"


def test_installation_store_rejects_symlinked_root_and_manifest(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    runtime = tmp_path / "mcp-runtime"
    runtime.symlink_to(outside, target_is_directory=True)

    with pytest.raises(InstallationStoreError, match="unsafe"):
        InstallationStore(tmp_path, integrity_key=b"k" * 32)

    runtime.unlink()
    plan = _plan(_request())
    tokens = ConfirmationTokenManager(b"s" * 32, replay_root=tmp_path)
    store = InstallationStore(tmp_path, integrity_key=b"k" * 32)
    installation = "mcp-installation-" + "a" * 32
    folder = runtime / "installations" / installation
    folder.mkdir()
    (folder / "manifest.json").symlink_to(outside / "manifest.json")
    with pytest.raises(InstallationStoreError, match="unsafe"):
        store.create(plan, tokens.issue(plan), tokens, installation_id=installation)


def test_legacy_server_no_longer_shadows_official_mcp_sdk() -> None:
    repository = Path(__file__).resolve().parents[2]

    assert not (repository / "mcp").exists()
    assert (repository / "research_workbench_mcp_server" / "server.py").is_file()
    assert '"research_workbench_mcp_server"' in (repository / "pyproject.toml").read_text(
        encoding="utf-8"
    )


def test_installation_logging_never_contains_argv_or_artifact_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "app.research_web.mcp_runtime.installation_store.log.info",
        lambda event, **fields: events.append((event, fields)),
    )
    plan = _plan(_request(argv=["node", "SECRET_ARGUMENT"]))
    tokens = ConfirmationTokenManager(b"s" * 32, replay_root=tmp_path)
    InstallationStore(tmp_path, integrity_key=b"k" * 32).create(plan, tokens.issue(plan), tokens)

    serialized = json.dumps(events)
    assert "SECRET_ARGUMENT" not in serialized
    assert _artifact().sha256 not in serialized
    assert events[0][0] == "mcp_installation_manifest_created"
    assert set(events[0][1]) == {"installation_id_digest", "status"}
