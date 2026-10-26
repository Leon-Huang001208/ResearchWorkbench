"""Explicit macOS LaunchAgent runner for an attached private multiuser gateway.

Installation and Tailscale cutover are separately authorized operator actions.
This runner never updates or stops the original resident service.
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import os
import platform
import subprocess
import sys
from pathlib import Path


def run(root: Path) -> int:
    from .__main__ import PROJECT, _configured_capacity, _server_context

    with _server_context(root):
        import uvicorn

        from .accounts import AccountStore
        from .gateway import create_gateway
        from .resident_binding import AttachedPool, LegacyBinding, read_json
        from .resident_boot import boot_identity, retire_previous_boot
        from .runtime import RuntimeConfig, RuntimeErrorSafe, RuntimePool

        if platform.system() != "Darwin":
            raise RuntimeErrorSafe("server_platform_unsupported")
        config = read_json(root / "resident.json")
        revision = subprocess.check_output(
            ["/usr/bin/git", "-C", str(PROJECT), "rev-parse", "HEAD"],
            text=True,
            timeout=5,
        ).strip()
        if config.get("version") != 1 or config.get("revision") != revision:
            raise RuntimeErrorSafe("server_revision_mismatch")
        if config.get("project") != str(PROJECT) or config.get("port") != 8089:
            raise RuntimeErrorSafe("server_configuration_invalid")
        capacity = _configured_capacity(config)
        accounts = AccountStore(root)
        binding = LegacyBinding.from_config(config["binding"])
        original = read_json(binding.home / "resident/config.json")
        if config["node"] != original["node"]:
            raise RuntimeErrorSafe("server_configuration_invalid")
        boot = boot_identity()
        recover = functools.partial(
            retire_previous_boot,
            current_boot=boot,
            accounts=accounts,
            archive=root / "run/recovery",
        )
        private = RuntimePool(
            RuntimeConfig(
                root=root,
                project=PROJECT,
                source=Path(config["source"]),
                python=sys.executable,
                node=config["node"],
                max_instances=capacity,
            ),
            recover=recover,
            boot_id=boot,
        )
        try:
            pool = AttachedPool(accounts, private, binding, revision)
            pool.maintenance_path = root / "run/cutover.json"
            pool.deployment_path = root / "run/gateway-upgrade.json"
            app = create_gateway(accounts, pool, origin=config["origin"])
            uvicorn.run(
                app,
                host="127.0.0.1",
                port=8089,
                access_log=False,
                proxy_headers=False,
                log_config=None,
            )
        finally:
            asyncio.run(private.close())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the explicitly installed private gateway")
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    try:
        os.umask(0o077)
        return run(args.root.expanduser().absolute())
    except Exception as exc:  # noqa: BLE001
        # Final boundary never prints private configuration or exception values.
        from .__main__ import _SAFE_CODE

        code = getattr(exc, "code", "server_resident_failed")
        print(
            (
                code
                if isinstance(code, str) and _SAFE_CODE.fullmatch(code)
                else "server_resident_failed"
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
