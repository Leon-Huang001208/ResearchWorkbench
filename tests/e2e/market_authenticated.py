"""Own a real, isolated account gateway and RuntimePool for market acceptance.

Synthetic passwords arrive over stdin and remain in process memory. No auth,
runtime, market or browser requests are mocked by this helper.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]


async def independent_metadata() -> dict:
    """Compare the public center's combined directory with three scoped captures.

    This fixed contract comes from the official center index.js hs_a_board entry,
    rather than importing the provider's exchange scopes or cached snapshot.
    """
    import httpx

    scope = "m:0 t:6 f:!2,m:0 t:80 f:!2,m:1 t:2 f:!2,m:1 t:23 f:!2,m:0 t:81 s:262144 f:!2"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            "https://push2.eastmoney.com/webguest/api/qt/clist/get",
            params={
                "pn": 1,
                "pz": 1,
                "po": 0,
                "np": 1,
                "fltt": 2,
                "invt": 2,
                "fid": "f12",
                "fs": scope,
                "fields": "f12,f13,f124",
                "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            },
        )
        response.raise_for_status()
        payload = response.json()
    total = payload.get("data", {}).get("total")
    if not isinstance(total, int) or total <= 5000:
        raise ValueError("independent_directory_count_invalid")
    return {
        "status": response.status_code,
        "total": total,
        "scope_sha256": hashlib.sha256(scope.encode()).hexdigest(),
        "body_sha256": hashlib.sha256(response.content).hexdigest(),
        "source": "official-center-combined-A-directory",
    }


def emit(value: dict) -> None:
    print(json.dumps(value, ensure_ascii=False), flush=True)


def resident_snapshot() -> list[dict]:
    """Record identities only, never process arguments or credential material."""
    rows = subprocess.check_output(
        ["/bin/ps", "-axo", "pid=,command="], text=True, timeout=5
    ).splitlines()
    selected = []
    for row in rows:
        parts = row.strip().split(None, 1)
        if len(parts) != 2:
            continue
        command = parts[1]
        executable = Path(command.split(None, 1)[0]).name.lower()
        if not executable.startswith("python"):
            continue
        if "app.research_web.multiuser.resident" in command or (
            "-m uvicorn app.research_web.main:app" in command and str(PROJECT) not in command
        ):
            pid = int(parts[0])
            started = subprocess.check_output(
                ["/bin/ps", "-p", str(pid), "-o", "lstart="], text=True, timeout=5
            ).strip()
            selected.append(
                {
                    "pid": pid,
                    "started": started,
                    "source_identity_sha256": hashlib.sha256(command.encode()).hexdigest(),
                }
            )
    return sorted(selected, key=lambda item: item["pid"])


async def serve(arguments: argparse.Namespace, accounts_input: list[dict]) -> None:
    import uvicorn

    from app.research_web.multiuser.accounts import AccountStore
    from app.research_web.multiuser.gateway import create_gateway
    from app.research_web.multiuser.runtime import RuntimeConfig, RuntimePool
    from core.observability import get_logger

    log = get_logger(__name__)
    store = AccountStore(arguments.root)
    users = [
        store.create_user(item["username"], item["password"], item["role"]).public()
        for item in accounts_input
    ]
    for item in accounts_input:
        item.clear()
    accounts_input.clear()
    before = resident_snapshot()
    protected = set(arguments.protect_pid)
    if not protected:
        raise ValueError("explicit_protected_resident_pids_required")
    protected_before = [item for item in before if item["pid"] in protected]
    if len(protected_before) != len(protected):
        raise ValueError("protected_resident_identity_missing")
    config = RuntimeConfig(
        root=arguments.root,
        project=PROJECT,
        source=arguments.source,
        python=sys.executable,
        node=str(arguments.node),
        max_instances=1,
    )
    pool = RuntimePool(config)
    owned_children = {}

    def record_owned() -> list[int]:
        for entry in pool._instances.values():
            for child in entry.children:
                owned_children[child.pid] = child
        return sorted(owned_children)

    origin = f"http://127.0.0.1:{arguments.port}"
    app = create_gateway(store, pool, origin=origin)
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=arguments.port,
            access_log=False,
            proxy_headers=False,
            log_config=None,
        )
    )

    async def controls() -> None:
        while not server.started:
            await asyncio.sleep(0.05)
        emit({"ready": True, "origin": origin, "users": users})
        while True:
            line = await asyncio.to_thread(sys.stdin.readline)
            if not line:
                server.should_exit = True
                return
            try:
                request = json.loads(line)
            except ValueError:
                emit({"control_error": "invalid_json"})
                continue
            if request.get("operation") == "shutdown":
                server.should_exit = True
                return
            if request.get("operation") == "metadata":
                try:
                    emit({"independent_metadata": await independent_metadata()})
                except (ValueError, OSError) as exc:
                    emit({"metadata_error": type(exc).__name__})
                except Exception as exc:  # noqa: BLE001 - public probe emits only safe error class.
                    log.warning(
                        "market_authenticated_metadata_failed", error_type=type(exc).__name__
                    )
                    emit({"metadata_error": type(exc).__name__})
                continue
            if request.get("operation") == "owned":
                emit({"owned": {"pool_instance": pool.instance, "pids": record_owned()}})
                continue
            emit({"control_error": "unsupported_operation"})

    controller = asyncio.create_task(controls())
    try:
        await server.serve()
    finally:
        if not controller.done():
            controller.cancel()
        await asyncio.gather(controller, return_exceptions=True)
        record_owned()
        await pool.close()
        after = resident_snapshot()
        protected_after = [item for item in after if item["pid"] in protected]
        observed_exited = [
            item for item in before if item not in after and item["pid"] not in protected
        ]
        stopped = not pool._instances and all(
            child.poll() is not None for child in owned_children.values()
        )
        log.info("market_authenticated_shutdown", owned_stopped=stopped)
        emit(
            {
                "shutdown": True,
                "owned_instances": len(pool._instances),
                "resident_unchanged": protected_before == protected_after,
                "resident_before": protected_before,
                "resident_after": protected_after,
                "observed_exited_unknown_ownership": observed_exited,
                "owned_pool_instance": pool.instance,
                "owned_child_pids": sorted(owned_children),
                "owned_children_closed": stopped,
            }
        )
        if not stopped or protected_before != protected_after:
            raise RuntimeError("owned_shutdown_or_resident_preservation_failed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--protect-pid", action="append", type=int, default=[])
    args = parser.parse_args()
    args.root = args.root.absolute()
    if args.root.exists() or args.root.is_symlink():
        raise ValueError("acceptance root must be new")
    args.root.mkdir(mode=0o700, parents=True)
    if not args.port:
        with socket.socket() as reserved:
            reserved.bind(("127.0.0.1", 0))
            args.port = reserved.getsockname()[1]
    pin = json.loads((PROJECT / "runtimes/research_web.json").read_text())["dsh"]["commit"]
    actual = subprocess.check_output(
        ["/usr/bin/git", "-C", str(args.source), "rev-parse", "HEAD"], text=True, timeout=5
    ).strip()
    if actual != pin:
        raise ValueError("pinned_runtime_mismatch")
    version = subprocess.check_output([str(args.node), "--version"], text=True, timeout=5)
    if not version.startswith("v24."):
        raise ValueError("node24_required")
    request = json.loads(sys.stdin.readline())
    accounts_input = request.get("accounts")
    if not isinstance(accounts_input, list) or len(accounts_input) != 2:
        raise ValueError("two_synthetic_accounts_required")
    os.environ["PATH"] = os.pathsep.join(
        [str(args.node.parent), str(Path(sys.executable).parent), "/usr/bin", "/bin", "/usr/sbin"]
    )
    from app.research_web.multiuser.__main__ import _server_context

    with _server_context(args.root):
        asyncio.run(serve(args, accounts_input))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - CLI privacy boundary emits only the error class.
        # Never stringify errors that might contain submitted credentials.
        emit({"startup_error": type(exc).__name__})
        raise SystemExit(1) from None
