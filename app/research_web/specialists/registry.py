"""Maintainer-published, immutable logical roles over existing capabilities."""

import copy
import hashlib
import json

from core.observability import get_logger

from .contracts import SpecialistError

log = get_logger(__name__)
_ROLES = {
    "orchestrator": {
        "responsibility": "规划行业投资研究、管理依赖与分歧，整合已验证成果。",
        "skills": ["industry-research"],
        "tools": ["research_check_quality"],
    },
    "industry": {
        "responsibility": "研究供需、景气及竞争格局，区分事实与推断，不决定仓位。",
        "skills": ["industry-research"],
        "tools": ["datahub_search_news"],
    },
    "quant": {
        "responsibility": "基于获授权的本会话快照进行可复算描述统计，不冒充预测或回测。",
        "skills": ["factor-database-research"],
        "tools": ["research_run_script"],
    },
    "review": {
        "responsibility": "在独立上下文核验来源、日期、计算及缺口；不以模型自评批准定稿。",
        "skills": [],
        "tools": ["research_check_quality"],
    },
}


def catalog() -> dict:
    roles = {
        key: {"id": key, "version": "1.0.0", "model": "inherit_frozen", **value}
        for key, value in _ROLES.items()
    }
    digest = hashlib.sha256(
        json.dumps(roles, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    return {"schema_version": 1, "digest": digest, "roles": copy.deepcopy(roles)}


def role(role_id: str) -> dict:
    entry = catalog()["roles"].get(role_id)
    if entry is None:
        log.warning("specialist_role_denied")
        raise SpecialistError("专业角色未发布", "specialist_role_unavailable")
    return entry
