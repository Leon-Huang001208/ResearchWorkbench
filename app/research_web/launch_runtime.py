"""Launch only an owned DSH instance with a fixed build and clean environment."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from core.observability import get_logger, setup_logging

from .capabilities.catalog import CapabilityCatalog
from .datahub.catalog import build_catalog
from .datahub.connections import MySQLConnectionStore
from .datahub.contracts import BUSINESS_TOOLS
from .datahub.security import load_control
from .store import StoreError

log = get_logger(__name__)
PINNED_COMMIT = "c919b2a460753859665db3f60143d525fb9140cf"
TABBIT_VERSION = "0.3.4"
TABBIT_SOURCE_COMMIT = "361ef61f4d42ae51d657ca1351acacd6b5db5d44"
TABBIT_VENDOR = Path(__file__).parents[2] / "vendor" / "dsh-tabbit" / TABBIT_VERSION
TABBIT_INSTANCE_PATTERN = re.compile(r"^[A-F0-9]{16}$")


def load_tabbit_config(data: Path) -> dict[str, object]:
    """Read the non-secret Tabbit switches used for the next Runtime start."""
    defaults: dict[str, object] = {
        "browser_enabled": True,
        "web_fetch_enabled": False,
        "instance_id": None,
    }
    path = data / ".control" / "tabbit.json"
    if not path.exists():
        return defaults
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise RuntimeError("Tabbit 配置文件无效") from exc
    if not isinstance(raw, dict):
        raise TypeError("Tabbit 配置文件无效")
    value = {**defaults, **raw}
    browser_enabled = value.get("browser_enabled")
    web_fetch_enabled = value.get("web_fetch_enabled")
    instance_id = value.get("instance_id")
    if not isinstance(browser_enabled, bool) or not isinstance(web_fetch_enabled, bool):
        raise TypeError("Tabbit 开关配置无效")
    if web_fetch_enabled and not browser_enabled:
        raise RuntimeError("Tabbit web_fetch 要求浏览器自动化同时开启")
    if instance_id is not None and (
        not isinstance(instance_id, str)
        or TABBIT_INSTANCE_PATTERN.fullmatch(instance_id) is None
    ):
        raise RuntimeError("Tabbit 实例 ID 无效")
    return value


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def _profile_manifest(home: Path) -> tuple[Path, dict]:
    path = home / "profiles" / "web" / "package.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise RuntimeError("DSH Web Profile 清单无效") from exc
    if not isinstance(manifest, dict):
        raise TypeError("DSH Web Profile 清单无效")
    return path, manifest


def _append_profile_bundle(home: Path, name: str, version: str) -> None:
    path, manifest = _profile_manifest(home)
    dependencies = manifest.setdefault("dependencies", {})
    profile = manifest.setdefault("dsh", {}).setdefault("profile", {})
    bundles = profile.setdefault("bundles", [])
    if not isinstance(dependencies, dict) or not isinstance(bundles, list):
        raise TypeError("DSH Web Profile bundle 配置无效")
    dependencies[name] = version
    bundles[:] = [bundle for bundle in bundles if bundle != name]
    bundles.append(name)
    _atomic_json(path, manifest)


def stage_tabbit_package(vendor: Path, home: Path) -> dict:
    """Verify and extract the reviewed Tabbit archive into the private profile."""
    try:
        manifest = json.loads((vendor / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise RuntimeError("Tabbit 供应清单无效") from exc
    expected = {
        "name": "dsh-tabbit",
        "version": TABBIT_VERSION,
        "source_commit": TABBIT_SOURCE_COMMIT,
    }
    if not isinstance(manifest, dict) or any(
        manifest.get(key) != value for key, value in expected.items()
    ):
        raise RuntimeError("Tabbit 供应版本或来源不符")
    archive_name = f"dsh-tabbit-{TABBIT_VERSION}.tgz"
    if manifest.get("archive") != archive_name:
        raise RuntimeError("Tabbit 供应归档名称不符")
    archive = vendor / archive_name
    if not archive.is_file():
        raise RuntimeError("Tabbit 供应归档缺失")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != manifest.get("sha256"):
        raise RuntimeError("Tabbit 供应归档完整性校验失败")
    license_path = vendor / "LICENSE"
    license_digest = (
        hashlib.sha256(license_path.read_bytes()).hexdigest()
        if license_path.is_file()
        else None
    )
    if manifest.get("license") != "MIT" or license_digest != manifest.get(
        "license_sha256"
    ):
        raise RuntimeError("Tabbit 许可证完整性校验失败")
    expected_files = manifest.get("files")
    if (
        not isinstance(expected_files, list)
        or not expected_files
        or any(not isinstance(item, str) for item in expected_files)
    ):
        raise RuntimeError("Tabbit 供应文件清单无效")
    destination = home / "profiles" / "node_modules" / "dsh-tabbit"
    temporary = destination.with_name(".dsh-tabbit-staging")
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir(parents=True, mode=0o700)
    try:
        with tarfile.open(archive, "r:gz") as bundle:
            members = bundle.getmembers()
            if len(members) > 4096 or sum(item.size for item in members) > 16 * 1024 * 1024:
                raise RuntimeError("Tabbit 供应归档超过安全上限")
            actual_files = sorted(
                str(Path(*Path(member.name).parts[1:]))
                for member in members
                if member.isfile() and len(Path(member.name).parts) >= 2
            )
            if actual_files != sorted(expected_files):
                raise RuntimeError("Tabbit 供应文件清单不匹配")
            for member in members:
                parts = Path(member.name).parts
                if len(parts) < 2 or parts[0] != "package" or member.issym() or member.islnk():
                    raise RuntimeError("Tabbit 供应归档包含不安全路径")
                relative = Path(*parts[1:])
                target = (temporary / relative).resolve()
                if not target.is_relative_to(temporary.resolve()):
                    raise RuntimeError("Tabbit 供应归档包含越界路径")
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True, mode=0o700)
                    continue
                if not member.isfile():
                    raise RuntimeError("Tabbit 供应归档包含不支持的文件类型")
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                source = bundle.extractfile(member)
                if source is None:
                    raise RuntimeError("Tabbit 供应归档读取失败")
                with target.open("wb") as stream:
                    shutil.copyfileobj(source, stream)
        package = json.loads((temporary / "package.json").read_text(encoding="utf-8"))
        if package.get("name") != "dsh-tabbit" or package.get("version") != TABBIT_VERSION:
            raise RuntimeError("Tabbit 供应包身份校验失败")
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if destination.is_symlink():
            raise RuntimeError("Tabbit Profile 目标不可为符号链接")
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    _append_profile_bundle(home, "dsh-tabbit", TABBIT_VERSION)
    return manifest


def stage_tabbit_adapter(source: Path, home: Path) -> Path:
    """Stage the project adapter as the final private profile bundle."""
    if not source.is_file():
        raise RuntimeError("Research Tabbit adapter 缺失")
    destination = home / "profiles" / "node_modules" / "research-tabbit-adapter"
    if destination.is_symlink():
        raise RuntimeError("Research Tabbit adapter 目标不可为符号链接")
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    shutil.copyfile(source, destination / "index.mjs")
    (destination / "cordis.patch.yml").write_text(
        "- insert:\n"
        "    - id: research-tabbit-adapter\n"
        "      name: research-tabbit-adapter\n",
        encoding="utf-8",
    )
    _atomic_json(
        destination / "package.json",
        {
            "name": "research-tabbit-adapter",
            "version": "1.0.0",
            "private": True,
            "type": "module",
            "main": "./index.mjs",
            "exports": {".": "./index.mjs"},
            "dsh": {"bundle": {"patch": "./cordis.patch.yml"}},
        },
    )
    _append_profile_bundle(home, "research-tabbit-adapter", "1.0.0")
    return destination / "index.mjs"


def tabbit_overlay(config: dict[str, object], adapter_path: Path) -> str:
    """Build the startup-only overrides that prevent installation and updates."""
    browser = config["browser_enabled"] is True
    web_fetch = config["web_fetch_enabled"] is True
    return "\n".join(
        [
            "- id: tabbit-installer",
            "  disabled: true",
            "- id: tabbit-tool-browser",
            f"  disabled: {'false' if browser else 'true'}",
            "- id: tabbit-web-fetch",
            f"  disabled: {'false' if web_fetch else 'true'}",
            "- id: tool-web",
            "  config:",
            f"    fetch: {'true' if web_fetch else 'false'}",
            "    searchTimeoutMs: 60000",
            "- id: web",
            "  config:",
            "    searchProvider: deepseek-official",
            f"    fetchProvider: {'tabbit-browser' if web_fetch else 'http'}",
            "- id: research-tabbit-adapter",
            f"  name: {json.dumps(str(adapter_path))}",
            "  config:",
            f"    browserEnabled: {'true' if browser else 'false'}",
            f"    webFetchEnabled: {'true' if web_fetch else 'false'}",
        ]
    )


def validate_tabbit_node(node: str) -> str:
    """Enforce the reviewed package's exact Node engine floor."""
    try:
        version = subprocess.check_output(
            [node, "--version"], text=True, timeout=5
        ).strip()
        match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", version)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("无法确认 Tabbit Runtime 的 Node.js 版本") from exc
    if match is None:
        raise RuntimeError("Tabbit Runtime 的 Node.js 版本格式无效")
    major, minor, _ = map(int, match.groups())
    if not (major >= 24 or (major == 22 and minor >= 19)):
        raise RuntimeError("dsh-tabbit 0.3.4 要求 Node.js 22.19+ 或 24+")
    return version.removeprefix("v")


def enabled_datahub_tools(data: Path | None = None) -> list[str]:
    """Resolve the fixed business tool IDs backed by callable offline catalog sources."""
    try:
        connection_statuses = MySQLConnectionStore(data).statuses() if data is not None else None
        capabilities = build_catalog(connection_statuses=connection_statuses)["capabilities"]
        callable_capabilities = {
            item["id"] for item in capabilities if item["callable_source_count"] > 0
        }
        return [
            tool_id
            for capability_id, tool_id in BUSINESS_TOOLS.items()
            if capability_id in callable_capabilities
        ]
    except Exception as exc:
        log.error("datahub_runtime_tool_catalog_failed", error_type=type(exc).__name__)
        raise RuntimeError("DataHub 可调用工具目录无效，拒绝启动 Runtime") from exc


def prepare_runtime_module_fallback(source: Path, home: Path, node: str) -> int:
    """Heal DSH profile module links and reject dependencies outside the pinned tree."""
    module = source / "packages/boot/app-boot/lib/index.js"
    anchor = source / "apps/cli/package.json"
    if not module.is_file() or not anchor.is_file():
        raise RuntimeError("DSH 构建缺少 profile 模块；请重新构建固定源码")
    script = """
import { pathToFileURL } from 'node:url';
const [modulePath, anchor, home] = process.argv.slice(1);
const runtime = await import(pathToFileURL(modulePath).href);
await runtime.healProfilesModuleFallback({ installAnchor: anchor, home });
"""
    environment = {
        "PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        "LANG": "en_US.UTF-8",
        "HOME": str(home),
        "DSH_HOME": str(home),
        "DSH_TELEMETRY_DISABLED": "1",
    }
    try:
        subprocess.run(
            [
                node,
                "--input-type=module",
                "--eval",
                script,
                str(module),
                str(anchor),
                str(home),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("DSH profile 模块初始化失败") from exc

    modules = home / "profiles" / "node_modules"
    links: list[Path] = []
    if modules.is_dir():
        for item in modules.iterdir():
            if item.is_symlink():
                links.append(item)
            elif item.is_dir() and item.name.startswith("@"):
                links.extend(child for child in item.iterdir() if child.is_symlink())
    if not links:
        raise RuntimeError("DSH profile 模块目录为空")
    for link in links:
        try:
            target = link.resolve(strict=True)
        except OSError as exc:
            raise RuntimeError("DSH profile 存在失效模块链接") from exc
        if not target.is_relative_to(source):
            raise RuntimeError("DSH profile 模块越出项目私有源码目录")
    return len(links)


def prepare(
    source: Path,
    data: Path,
    node: str,
    port: int,
    source_mode=False,
    research_tools=False,
    datahub_url: str | None = None,
) -> tuple[list[str], dict, Path]:
    source, data = source.resolve(), data.resolve()
    tabbit_config = load_tabbit_config(data)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    if commit != PINNED_COMMIT:
        raise RuntimeError("DSH 源码提交与已验证版本不符；未自动升级")
    executable = source / ("apps/cli/src/bin.ts" if source_mode else "apps/cli/lib/bin.js")
    if not executable.is_file():
        raise RuntimeError("DSH 构建不存在；请先授权构建依赖")
    runtime = data / "runtime"
    home, work, temp = (runtime / name for name in ("home", "work", "tmp"))
    for path in (home, work, temp):
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.is_symlink():
            raise RuntimeError("Runtime 目录不可为符号链接")
    if (work / ".env").exists() or (home / ".env").exists():
        raise RuntimeError("专属 Runtime 中存在未授权 .env，拒绝隐式导入")
    preset = home / ".agent-presets" / "research-web"
    preset.mkdir(parents=True, exist_ok=True, mode=0o700)
    package = Path(__file__).parent / "runtime"
    if research_tools:
        load_control(data, datahub_url)
        public_data_tools = enabled_datahub_tools(data)
        runner = package.parent / "sandbox.py"
        if not runner.exists() or not (package / "research-tools.mjs").exists():
            raise RuntimeError("安全脚本运行器尚未完成，禁止启用研究工具")
        content = (package / "research.cordis.yml").read_text()
        for key, value in {
            "__SKILL_ROOT__": CapabilityCatalog(data).prepare_native_root(),
            "__TOOLS_MODULE__": package / "research-tools.mjs",
            "__PUBLIC_DATA_MODULE__": package / "public-data.mjs",
            "__PYTHON__": Path(sys.executable),
            "__RUNNER__": runner,
            "__RESEARCH_ROOT__": data,
        }.items():
            content = content.replace(key, json.dumps(str(value)))
        content = content.replace("__PUBLIC_DATA_ENABLED_TOOLS__", json.dumps(public_data_tools))
        content = content.replace(
            "fetch: false",
            f"fetch: {'true' if tabbit_config['web_fetch_enabled'] is True else 'false'}",
        )
        (preset / "agent.cordis.yml").write_text(content)
        log.info(
            "datahub_runtime_tools_prepared",
            enabled_tool_count=len(public_data_tools),
            enabled_tool_ids=public_data_tools,
        )
    else:
        content = (package / "agent.cordis.yml").read_text(encoding="utf-8")
        if tabbit_config["browser_enabled"] is True:
            content = content.replace(
                "当前处于真实聊天接入阶段，没有网页检索、文件读取、脚本或文件生成工具。",
                "当前已启用受控 Tabbit 浏览器自动化；没有文件读取、脚本或文件生成工具。",
            )
        (preset / "agent.cordis.yml").write_text(content, encoding="utf-8")
    guard = (package / "guard.mjs").resolve()
    overlay = runtime / "overlay.yml"
    adapter = home / "profiles" / "node_modules" / "research-tabbit-adapter" / "index.mjs"
    overlay.write_text(
        "\n".join(
            [
                "- id: llm-deepseek",
                "  config:",
                "    apiKeyEnv: RESEARCH_DSH_API_KEY",
                "    thinking: disabled",
                "    maxTokens: 4096",
                "- id: web-search-deepseek",
                "  config:",
                "    apiKeyEnv: RESEARCH_DSH_API_KEY",
                "- id: agent-default-model",
                "  config:",
                "    provider: deepseek-official",
                "    model: deepseek-v4-flash",
                "- id: agent-presets",
                "  config:",
                "    default: research-web",
                "- id: session-title-llm",
                "  disabled: true",
                "- id: tools",
                "  config:",
                "    mode: native",
                "- insert:",
                "    - id: research-tool-guard",
                f"      name: {json.dumps(str(guard))}",
                "      config:",
                f"        enabled: {'true' if research_tools else 'false'}",
                f"        tabbitBrowserEnabled: {'true' if tabbit_config['browser_enabled'] is True else 'false'}",
                f"        tabbitWebFetchEnabled: {'true' if tabbit_config['web_fetch_enabled'] is True else 'false'}",
                "",
            ]
        )
        + tabbit_overlay(tabbit_config, adapter)
        + "\n",
        encoding="utf-8",
    )
    # Pin the actual JS/config closure, not just the top-level CLI version.
    digest = hashlib.sha256()
    count = 0
    for root in (source / "packages", source / "apps/cli", source / "vendor"):
        for path in sorted(root.rglob("*")):
            if (
                path.is_file()
                and "node_modules" not in path.parts
                and ("lib" in path.parts or path.suffix in {".yml", ".json", ".ts"})
            ):
                digest.update(str(path.relative_to(source)).encode())
                digest.update(path.read_bytes())
                count += 1
    manifest = {
        "source_commit": commit,
        "closure_sha256": digest.hexdigest(),
        "closure_files": count,
        "mode": "source" if source_mode else "build",
    }
    manifest_path = runtime / ("source-lock.json" if source_mode else "build-lock.json")
    if manifest_path.exists() and json.loads(manifest_path.read_text()) != manifest:
        raise RuntimeError("DSH 构建发生变化，请重新审核后更新专属构建锁")
    manifest_path.write_text(json.dumps(manifest, indent=2))
    env = {
        "PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        "LANG": "en_US.UTF-8",
        "HOME": str(home),
        "DSH_HOME": str(home),
        "DSH_TELEMETRY_DISABLED": "1",
        "TMPDIR": str(temp),
    }
    if isinstance(tabbit_config.get("instance_id"), str):
        env["TABBIT_PLAYWRIGHT_INSTANCE"] = str(tabbit_config["instance_id"])
    command = [
        node,
        str(executable),
        "--profile",
        "web",
        "--patch",
        str(overlay),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--no-open",
    ]
    if source_mode:
        env["TSX_TSCONFIG_PATH"] = str(source / "tsconfig.json")
        command[1:1] = ["--import", str(source / "node_modules/tsx/dist/loader.mjs")]
    return command, env, work


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--node", default="/usr/local/bin/node")
    parser.add_argument("--port", type=int, default=3081)
    parser.add_argument(
        "--datahub-url",
        default=None,
        help="Trusted loopback BFF origin; default 127.0.0.1:8088",
    )
    parser.add_argument(
        "--source-mode",
        action="store_true",
        help="Use pinned source with existing tsx; no installation",
    )
    parser.add_argument(
        "--research-tools",
        action="store_true",
        help="Enable verified research runner, native Skills and subagents",
    )
    args = parser.parse_args()
    setup_logging()
    try:
        node_version = validate_tabbit_node(args.node)
        command, env, work = prepare(
            args.source,
            args.data,
            args.node,
            args.port,
            args.source_mode,
            args.research_tools,
            args.datahub_url,
        )
        module_count = prepare_runtime_module_fallback(
            args.source.resolve(), args.data.resolve() / "runtime/home", args.node
        )
        tabbit_manifest = stage_tabbit_package(
            TABBIT_VENDOR, args.data.resolve() / "runtime/home"
        )
        stage_tabbit_adapter(
            Path(__file__).parent / "runtime" / "tabbit-adapter.mjs",
            args.data.resolve() / "runtime/home",
        )
        _atomic_json(
            args.data.resolve() / ".control" / "tabbit-applied.json",
            load_tabbit_config(args.data.resolve()),
        )
        log.info(
            "owned_dsh_launch",
            port=args.port,
            commit=PINNED_COMMIT,
            module_count=module_count,
            tabbit_version=tabbit_manifest["version"],
            tabbit_source_commit=tabbit_manifest["source_commit"],
            node_version=node_version,
        )
        os.chdir(work)
        os.execve(args.node, command, env)
    except (
        OSError,
        ValueError,
        RuntimeError,
        StoreError,
        subprocess.SubprocessError,
    ) as exc:
        log.error("owned_dsh_launch_failed", error=str(exc))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
