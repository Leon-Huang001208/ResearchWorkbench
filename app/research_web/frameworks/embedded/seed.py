"""Seed snapshot for an embedded framework."""

from datetime import UTC, datetime

from ..storage import compute_revision
from .contracts import EmbeddedSnapshot


AS_OF = datetime.now(UTC).date().isoformat()


def build_seed() -> EmbeddedSnapshot:
    value = {
        "schema_version": 1,
        "as_of": AS_OF,
        "fetched_at": datetime.now(UTC).isoformat(),
        "status": "可用",
        "coverage": 100,
        "overview": {
            "as_of": AS_OF,
            "fetched_at": datetime.now(UTC).isoformat(),
            "checked_at": datetime.now(UTC).isoformat(),
            "failure_code": None,
            "status": "complete",
            "sources": [
                {
                    "name": "外部独立研究项目",
                    "url": "https://github.com/Leon-Huang001208/ResearchWorkbench",
                    "observed_at": AS_OF,
                    "unit": "元数据",
                    "method": "本地文件系统注册",
                    "proxy": False,
                }
            ],
            "gaps": [],
        },
        "external_app": {
            "url": "about:blank",
            "local_path": "",
            "launch_command": "",
            "port": None,
        },
        "research_state": {
            "label": "可用",
            "note": "外部项目独立运行，点击进入完整交互。",
        },
        "gaps": [],
    }
    value["revision"] = compute_revision(value)
    return EmbeddedSnapshot.model_validate(value)
