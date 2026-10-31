"""Synthetic source picker Host; real HTTPResponse captures, zero public network/LLM."""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import research_web_packs_backend as packs

base = packs.base


def build_fixture(root, output):
    stat = root.stat()
    (output / "host-owner.json").write_text(
        json.dumps(
            {
                "task": "seek-packs-20261027-7bda5752",
                "fixture": True,
                "pid": os.getpid(),
                "uid": os.getuid(),
                "root": str(root),
                "dev": stat.st_dev,
                "inode": stat.st_ino,
            }
        )
    )
    app, research, native = packs.build_fixture(root, output)
    import pytest

    from app.research_web import research_web_sources as reader
    from app.research_web.client import RuntimeFailure
    from app.research_web.resources.research_report import source_id

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research_web"))
    from source_capture_fixture import fixed_response, offline_http

    patch = pytest.MonkeyPatch()
    fixture = Path(__file__).resolve().parents[1] / "research_web/fixtures/pack-owned-source-v1"
    meta = json.loads((fixture / "manifest.json").read_bytes())
    offline_http(patch, fixed_response((fixture / "body.txt").read_bytes()))
    sessions = []
    for index in range(2):
        session = research.store.create("fingpt", f"Synthetic 原文会话 {index + 1}")
        session["created"] = True
        session["source_scope"] = ["datahub", "uploads", "web"]
        identifier = source_id(meta["origin"])
        asyncio.run(
            reader.read_source(
                research,
                session["id"],
                "read",
                identifier,
                search_activities=[
                    {
                        "id": "synthetic-offline-search",
                        "title": "web_search",
                        "status": "completed",
                        "detail": json.dumps(
                            {
                                "results": [
                                    {
                                        "title": "Synthetic 冻结原文 <安全标题> " + "长标题" * 40,
                                        "url": meta["origin"],
                                    }
                                ]
                            }
                        ),
                    }
                ],
            )
        )
        sessions.append(session["id"])
    empty = research.store.create("fingpt", "Synthetic 空原文会话")
    empty["created"] = True
    empty["source_scope"] = ["datahub", "uploads", "web"]
    research.store.save()
    creation = {"fail_next": False, "attempts": 0}
    original_rpc = research.client.rpc

    async def rpc(method, payload):
        if method == "session.create":
            creation["attempts"] += 1
            if creation["fail_next"]:
                creation["fail_next"] = False
                raise RuntimeFailure("Synthetic Native create reply unknown", "fixture_unknown")
        return await original_rpc(method, payload)

    research.client.rpc = rpc

    @app.post("/__fixture/source-picker/unknown-next")
    def unknown_next():
        creation["fail_next"] = True
        return {"fixture": True}

    @app.get("/__fixture/source-picker/creation-state")
    def creation_state():
        return {"fixture": True, **creation}

    @app.get("/__fixture/source-picker")
    def source_fixture():
        return {
            "fixture": True,
            "sessions": sessions,
            "empty": empty["id"],
            "source_id": identifier,
            "as_of": datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat(),
        }

    @app.post("/__fixture/source-picker/revoke")
    def revoke():
        research.store.session(sessions[0])["source_scope"] = ["datahub", "uploads"]
        research.store.save()
        base.log.info("source_picker_fixture_revoked synthetic=1")
        return {"fixture": True}

    @app.post("/__fixture/source-picker/restore")
    def restore():
        research.store.session(sessions[0])["source_scope"] = ["datahub", "uploads", "web"]
        research.store.save()
        return {"fixture": True}

    @app.post("/__fixture/source-picker/delete-empty")
    def delete_empty():
        research.store.soft_delete(empty["id"])
        return {"fixture": True}

    @app.post("/__fixture/source-picker/change")
    def change():
        research.store.session(sessions[0])["web_evidence"][identifier]["title"] += " changed"
        research.store.save()
        return {"fixture": True}

    base.log.info("source_picker_fixture_ready synthetic=1 provider_calls=0")
    return app, research, native


if __name__ == "__main__":
    base.build_fixture = build_fixture
    base.main()
