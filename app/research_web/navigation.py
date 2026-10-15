"""Mode-scoped local navigation metadata, without changing research ownership."""

import copy

from core.observability import get_logger

from .claw_projects import ClawProjects
from .store import StoreError

log = get_logger(__name__)


class Navigation:
    """Callers hold ResearchService.lock for the entire read/update operation."""

    def __init__(self, research, mode):
        self.projects = ClawProjects(research, mode)
        self.mode = mode
        self.store = research.store

    def _live_ids(self):
        projects = {item["id"] for item in self.projects.list()["items"] if not item["archived"]}
        sessions = {
            row["id"]
            for row in self.store.data["sessions"].values()
            if row.get("mode") == self.mode
            and row.get("deleted_at") is None
            and row.get("project_id", "default") in projects
        }
        return {"session": sessions, "project": projects}

    def get(self):
        state = self.store.data.get("session_navigation", {}).get(self.mode, {})
        live = self._live_ids()
        return {
            "mode": self.mode,
            "revision": state.get("revision", 0),
            "pinned": [
                dict(item) for item in state.get("pinned", []) if item["id"] in live[item["kind"]]
            ],
            "project_order": [
                pid for pid in state.get("project_order", []) if pid in live["project"]
            ],
        }

    def update(self, *, revision, pinned, project_order):
        current = self.get()
        if type(revision) is not int or revision < 0:
            raise StoreError("导航版本无效", "invalid_navigation", 422)
        if revision != current["revision"]:
            raise StoreError("导航已变化，请刷新后重试", "navigation_changed", 409)
        if not isinstance(pinned, list) or not isinstance(project_order, list):
            raise StoreError("导航列表无效", "invalid_navigation", 422)
        live = self._live_ids()
        seen = set()
        for item in pinned:
            if (
                not isinstance(item, dict)
                or set(item) != {"kind", "id"}
                or not isinstance(item["kind"], str)
                or item["kind"] not in live
                or not isinstance(item["id"], str)
                or item["id"] not in live[item["kind"]]
                or (item["kind"], item["id"]) in seen
            ):
                raise StoreError("置顶对象无效、重复或已失效", "invalid_navigation", 422)
            seen.add((item["kind"], item["id"]))
        if any(
            not isinstance(pid, str) or pid not in live["project"] for pid in project_order
        ) or len(set(project_order)) != len(project_order):
            raise StoreError("项目排序无效或重复", "invalid_navigation", 422)
        previous = self.store.data.get("session_navigation")
        updated = copy.deepcopy(previous) if previous is not None else {}
        updated[self.mode] = {
            "revision": revision + 1,
            "pinned": copy.deepcopy(pinned),
            "project_order": list(project_order),
        }
        self.store.data["session_navigation"] = updated
        try:
            self.store.save()
        except (OSError, StoreError) as exc:
            if previous is None:
                self.store.data.pop("session_navigation", None)
            else:
                self.store.data["session_navigation"] = previous
            log.error("research_navigation_save_failed", mode=self.mode)
            if isinstance(exc, StoreError):
                raise
            raise StoreError("导航保存失败", "navigation_save_failed", 500) from exc
        log.info("research_navigation_saved", mode=self.mode, revision=revision + 1)
        return self.get()
