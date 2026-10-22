"""Real temporary AccountStore/gateway for Plugin UI role/approval acceptance.

The fixed backend is the separately started, test-owned native API fixture.
This fixture deliberately does not claim to validate real tenant DSH startup.
"""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import uvicorn

from app.research_web.multiuser.accounts import AccountStore
from app.research_web.multiuser.gateway import create_gateway


class FixturePool:
    def __init__(self, root, backend):
        self.config = SimpleNamespace(root=root)
        self.backend = backend

    async def backend_for(self, _user):
        return SimpleNamespace(url=self.backend, key="fixture-only-manager-key")

    async def close(self):
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18992)
    parser.add_argument("--backend", default="http://127.0.0.1:18991")
    args = parser.parse_args()
    root = args.root.resolve()
    if root.exists() or args.backend != "http://127.0.0.1:18991":
        raise RuntimeError("fixture_root_or_fixed_backend_invalid")
    accounts = AccountStore(root)
    admin = accounts.create_user("plugin-admin", "fixture-admin-safe-2026-10-22", role="admin")
    reader = accounts.create_user("plugin-reader", "fixture-reader-safe-2026-10-22")
    (root / "fixture-users.json").write_text(json.dumps({"admin": admin.id, "reader": reader.id}))
    (root / "fixture-users.json").chmod(0o600)
    from test_plugins import bundle

    (root / "personal-plugin.zip").write_bytes(
        bundle(
            "plugin.json", extra={"plugin.json": '{"name":"personal-fixture","version":"1.0.0"}'}
        )
    )
    app = create_gateway(
        accounts, FixturePool(root, args.backend), origin=f"http://127.0.0.1:{args.port}"
    )
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
