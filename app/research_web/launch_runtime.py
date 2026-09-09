"""Launch only an owned DSH instance with a fixed build and clean environment."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
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
        (preset / "agent.cordis.yml").write_text(content)
        log.info(
            "datahub_runtime_tools_prepared",
            enabled_tool_count=len(public_data_tools),
            enabled_tool_ids=public_data_tools,
        )
    else:
        shutil.copyfile(package / "agent.cordis.yml", preset / "agent.cordis.yml")
    guard = (package / "guard.mjs").resolve()
    overlay = runtime / "overlay.yml"
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
                "",
            ]
        )
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
        log.info(
            "owned_dsh_launch",
            port=args.port,
            commit=PINNED_COMMIT,
            module_count=module_count,
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
