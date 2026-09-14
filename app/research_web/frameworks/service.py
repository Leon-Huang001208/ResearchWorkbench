"""Framework catalog, lifecycle and exact-snapshot DSH conversations."""

import json
from pathlib import Path

from core.observability import get_logger

from .base import FrameworkError
from .registry import FrameworkRegistry, FrameworkRuntime
from .scheduler import FrameworkScheduler

log = get_logger(__name__)
MAX_FRAMEWORK_CONTEXT_CHARS = 80_000


class FrameworkService:
    def __init__(self, research, root: Path):
        self.research = research
        self.registry = FrameworkRegistry(root)
        self.scheduler = FrameworkScheduler(self.registry)
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        for runtime in self.registry.all():
            runtime.snapshot()
        await self.scheduler.start()
        self._started = True
        log.info("framework_runtime_started", framework_count=len(self.registry.all()))

    async def close(self) -> None:
        if not self._started:
            return
        await self.scheduler.close()
        self._started = False
        log.info("framework_runtime_closed", framework_count=len(self.registry.all()))

    def catalog(self) -> dict:
        return {"items": [runtime.catalog_item() for runtime in self.registry.all()]}

    def data(self, slug: str) -> dict:
        runtime = self.registry.get(slug)
        return {
            "framework": runtime.definition.model_dump(mode="json"),
            "snapshot": runtime.snapshot().model_dump(mode="json"),
        }

    def _binding(self, slug: str, revision: str, focus_section=None, gap_ids=()) -> dict:
        runtime = self.registry.get(slug)
        snapshot = runtime.snapshot()
        if revision != snapshot.revision:
            raise FrameworkError(
                "框架数据已经更新，请基于新快照重新开始对话",
                "framework_snapshot_changed",
                409,
            )
        sections = {section.id for section in runtime.definition.sections}
        if focus_section is not None and focus_section not in sections:
            raise FrameworkError("研究章节不存在", "framework_section_invalid", 422)
        known_gaps = {gap.id for gap in snapshot.gaps}
        if any(gap_id not in known_gaps for gap_id in gap_ids):
            raise FrameworkError("数据缺口不存在", "framework_gap_invalid", 422)
        return {
            "slug": slug,
            "framework_version": runtime.definition.version,
            "snapshot_revision": snapshot.revision,
            "snapshot_as_of": snapshot.as_of,
            "focus_section": focus_section,
            "gap_ids": list(gap_ids),
        }

    def _session_binding(self, slug: str, sid: str, expected_revision: str) -> tuple[dict, dict]:
        row = self.research.store.session(sid)
        binding = row.get("framework_binding")
        if not isinstance(binding, dict) or binding.get("slug") != slug:
            raise FrameworkError("会话不属于当前框架", "framework_session_mismatch", 404)
        self._binding(slug, expected_revision)
        if binding.get("snapshot_revision") != expected_revision:
            raise FrameworkError(
                "会话绑定的数据版本已变化，请重新开始对话",
                "framework_snapshot_changed",
                409,
            )
        return row, binding

    def _context(self, runtime: FrameworkRuntime, binding: dict, *, verification: bool) -> str:
        snapshot = runtime.snapshot()
        context = {
            "binding": binding,
            "model_version": runtime.definition.version,
            **runtime.context_builder(snapshot),
        }
        contract = (
            "这是服务器绑定的框架上下文。只解释其中已提供的事实，明确区分支持、反证、代理和"
            "未解决缺口；不得改变分数、快照或输出交易操作。"
        )
        if verification:
            contract += (
                "本回合是用户显式发起的深度验证。可使用当前预设实际提供的只读检索工具补证；"
                "逐条给出观测日期、来源链接、与原快照的差异及仍未解决的缺口。"
            )
        serialized = json.dumps(context, ensure_ascii=False, separators=(",", ":"))
        if len(serialized) > MAX_FRAMEWORK_CONTEXT_CHARS:
            log.error(
                "framework_context_too_large",
                framework=runtime.definition.slug,
                context_chars=len(serialized),
            )
            raise FrameworkError("框架上下文超过安全限制", "framework_context_too_large", 503)
        return contract + "\n\n" + serialized

    async def create_session(
        self, slug: str, revision: str, *, focus_section=None, gap_ids=()
    ) -> dict:
        runtime = self.registry.get(slug)
        binding = self._binding(slug, revision, focus_section, gap_ids)
        session = await self.research.create(
            "fingpt",
            f"{runtime.definition.name} · 框架解释",
            agent_preset="framework-explain",
            purpose="framework_explain",
            metadata={"framework_binding": binding},
        )
        return {"session": session, "binding": binding, "mode": "explain"}

    async def send_message(self, slug: str, sid: str, revision: str, text: str, key: str) -> dict:
        row, binding = self._session_binding(slug, sid, revision)
        if row.get("purpose") != "framework_explain":
            raise FrameworkError("该会话不是框架解释会话", "framework_session_mismatch", 409)
        runtime = self.registry.get(slug)
        prompt = self._context(runtime, binding, verification=False) + "\n\n用户问题：" + text
        return await self.research.send(sid, prompt, key)

    async def verify(self, slug: str, sid: str, revision: str, question: str, key: str) -> dict:
        _, binding = self._session_binding(slug, sid, revision)
        runtime = self.registry.get(slug)
        session = await self.research.create(
            "fingpt",
            f"{runtime.definition.name} · 深度验证",
            agent_preset="framework-verify",
            purpose="framework_verify",
            metadata={"framework_binding": binding, "upgraded_from": sid},
        )
        prompt = self._context(runtime, binding, verification=True) + "\n\n待验证问题：" + question
        accepted = await self.research.send(
            session["id"], prompt, key, skill_id="framework-research"
        )
        return {"session": session, "binding": binding, "mode": "verify", **accepted}
