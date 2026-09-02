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

from .datahub.security import load_control
from .store import StoreError

log = get_logger(__name__)
PINNED_COMMIT = "b150a551b8d465e31e418e1b2eaf5e79bbb7d28e"


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
    preset = home / ".agent-presets" / "alphafoundry-research"
    preset.mkdir(parents=True, exist_ok=True, mode=0o700)
    package = Path(__file__).parent / "runtime"
    if research_tools:
        load_control(data, datahub_url)
        runner = package.parent / "sandbox.py"
        if not runner.exists() or not (package / "research-tools.mjs").exists():
            raise RuntimeError("安全脚本运行器尚未完成，禁止启用研究工具")
        content = (package / "research.cordis.yml").read_text()
        for key, value in {
            "__SKILL_ROOT__": package.parent / "skills",
            "__TOOLS_MODULE__": package / "research-tools.mjs",
            "__PUBLIC_DATA_MODULE__": package / "public-data.mjs",
            "__PYTHON__": Path(sys.executable),
            "__RUNNER__": runner,
            "__RESEARCH_ROOT__": data,
        }.items():
            content = content.replace(key, json.dumps(str(value)))
        (preset / "agent.cordis.yml").write_text(content)
    else:
        shutil.copyfile(package / "agent.cordis.yml", preset / "agent.cordis.yml")
    guard = (package / "guard.mjs").resolve()
    overlay = runtime / "overlay.yml"
    overlay.write_text(
        "\n".join(
            [
                "- id: llm-deepseek",
                "  config:",
                "    apiKeyEnv: ALPHAFOUNDRY_DSH_API_KEY",
                "    thinking: disabled",
                "    maxTokens: 4096",
                "- id: web-search-deepseek",
                "  config:",
                "    apiKeyEnv: ALPHAFOUNDRY_DSH_API_KEY",
                "- id: agent-default-model",
                "  config:",
                "    provider: deepseek-official",
                "    model: deepseek-v4-flash",
                "- id: agent-presets",
                "  config:",
                "    default: alphafoundry-research",
                "- id: session-title-llm",
                "  disabled: true",
                "- id: tools",
                "  config:",
                "    mode: native",
                "- insert:",
                "    - id: alphafoundry-tool-guard",
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
        "--datahub-url", default=None, help="Trusted loopback BFF origin; default 127.0.0.1:8088"
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
        log.info("owned_dsh_launch", port=args.port, commit=PINNED_COMMIT)
        os.chdir(work)
        os.execve(args.node, command, env)
    except (OSError, ValueError, RuntimeError, StoreError, subprocess.SubprocessError) as exc:
        log.error("owned_dsh_launch_failed", error=str(exc))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
