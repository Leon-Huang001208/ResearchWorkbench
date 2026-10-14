"""Seed snapshot for an embedded framework."""

from ..storage import compute_revision
from .contracts import EmbeddedSnapshot

AS_OF = "2026-10-14"
IMPORTED_AT = "2026-10-14T00:00:00+08:00"


def build_seed() -> EmbeddedSnapshot:
    value = {
        "schema_version": 1,
        "as_of": AS_OF,
        "fetched_at": IMPORTED_AT,
        "status": "可用",
        "coverage": 0,
        "overview": {
            "as_of": AS_OF,
            "fetched_at": IMPORTED_AT,
            "checked_at": IMPORTED_AT,
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
            "note": "静态导入快照；没有实时采集或框架 Bot。",
        },
        "gaps": [],
    }
    value["revision"] = compute_revision(value)
    return EmbeddedSnapshot.model_validate(value)
