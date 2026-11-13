"""Turn-scoped DataHub, evidence and deterministic report tools."""

import asyncio
import json
from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from . import sandbox
from .datahub.contracts import BUSINESS_TOOLS, CAPABILITY_PARAMETERS, BusinessQuery
from .datahub.providers import ProviderError
from .qa_acceptance import acceptance_enabled
from .research_evidence import evidence_index
from .research_quality_service import business_prompt_index, write_business_snapshot
from .research_web_sources import execute_source, stored_sources, upload_evidence_files
from .resources.research_report import required_report_formats
from .resources.research_report_plan import required_body_target
from .scenario_handoffs import trusted_context
from .store import StoreError

READ_CAPABILITIES = {
    name: tool
    for name, tool in BUSINESS_TOOLS.items()
    if name not in {"database_schema", "table_query"}
}
MAX_TOOL_CALLS = 48


def _tool(name, description, props=None, required=()):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": props or {},
                "required": list(required),
                "additionalProperties": False,
            },
        },
    }


def _source(row):
    return {
        "evidence_id": row["id"],
        "title": row["title"],
        "url": row.get("url"),
        "provider": row.get("provider", "RWB"),
        "asof": row.get("as_of"),
    }


class TurnTools:
    def __init__(self, service, sid, receipt, attachments):
        self.service, self.sid, self.receipt = service, sid, receipt
        self.store = service.store
        self.scope = set(self.store.session(sid)["source_scope"])
        self.attachments = set(attachments)
        self.contract = receipt.get("research_contract")
        self.calls = 0
        self.report_written = False
        self.acquired = {}
        automation = self.store.session(sid).get("automation_research_scope")
        tools = receipt.get("qa_tool_scope", [])
        self.approved = set(tools) if automation or tools else None
        self.automation = bool(automation)
        self.query_names = {
            tool: cap
            for cap, tool in READ_CAPABILITIES.items()
            if not acceptance_enabled()
            and ("web" if cap == "search_web" else "datahub") in self.scope
            and (self.approved is None or tool in self.approved)
        }

    def schemas(self):
        result = [
            _tool(
                tool,
                f"RWB DataHub {cap}。parameters 可用字段为 "
                + "、".join(sorted(CAPABILITY_PARAMETERS[cap])),
                {"parameters": {"type": "object"}},
                ("parameters",),
            )
            for tool, cap in self.query_names.items()
        ]
        if self.sources_allowed:
            result.extend(
                [
                    _tool("list_research_sources", "列出本轮已获准读取的网页、档案与附件。"),
                    _tool(
                        "read_research_source",
                        "按已登记 ID 读取来源，不能提供任意 URL 或路径。",
                        {"id": {"type": "string"}},
                        ("id",),
                    ),
                ]
            )
        if "datahub" in self.scope and not self.automation:
            result.extend(
                [
                    _tool("list_frozen_datasets", "列出当前会话已经绑定的 DataHub 资料快照。"),
                    _tool(
                        "read_frozen_dataset",
                        "读取当前会话的冻结快照，保留原始口径与日期。",
                        {"dataset_id": {"type": "string"}},
                        ("dataset_id",),
                    ),
                ]
            )
        if self.store.session(self.sid).get("purpose") == "discovery_research":
            result.append(_tool("read_frozen_discovery", "读取本轮冻结选材和资料快照。"))
        if self.contract:
            result.append(
                _tool("list_research_observations", "列出实际观测 ID、计量口径及冻结要求。")
            )
        if self.report_allowed:
            result.append(
                _tool(
                    "write_research_report",
                    "提交报告计划。先调用 list_research_observations，使用准确 evidence_ids 与 "
                    "requirement_ids。sections 项含 id/heading/evidence_ids/requirement_ids，"
                    "可选 analysis。可选 calculations、summary、controls。缺口写入 missing。",
                    {"plan": {"type": "object"}},
                    ("plan",),
                )
            )
        return result

    @property
    def sources_allowed(self):
        return bool(self.scope) and not self.automation

    @property
    def report_allowed(self):
        return (
            self.contract
            and self.receipt["delivery"]["required_formats"]
            and (self.approved is None or "research_run_script" in self.approved)
        )

    async def call(self, params, _emit):
        self.calls += 1
        if self.calls > MAX_TOOL_CALLS:
            raise ValueError("qa_tool_budget_exhausted")
        name, args = params["name"], params["arguments"]
        if not isinstance(args, dict):
            raise TypeError("qa_tool_arguments_invalid")
        call_id = "qa:" + self.receipt["delivery"]["task_id"] + ":" + str(self.calls)
        try:
            if name in self.query_names and set(args) == {"parameters"}:
                return await self.query(name, args["parameters"], call_id)
            if name == "list_research_sources" and not args and self.sources_allowed:
                sources = await self.sources(call_id)
                return {"data": sources, "sources": []}
            if (
                name == "read_research_source"
                and self.sources_allowed
                and set(args) == {"id"}
                and isinstance(args["id"], str)
            ):
                return await self.read(args["id"], call_id)
            if "datahub" in self.scope and not self.automation:
                if name == "list_frozen_datasets" and not args:
                    items = self.service.datahub.summaries(self.sid)[:30]
                    return {"data": items, "sources": []}
                if name == "read_frozen_dataset" and set(args) == {"dataset_id"}:
                    return self.frozen_dataset(args["dataset_id"])
            if name == "read_frozen_discovery" and not args:
                context = self.service.discovery.trusted_context(self.sid)
                if context:
                    return self.frozen_discovery(context)
            if name == "list_research_observations" and not args and self.contract:
                data = await asyncio.to_thread(
                    business_prompt_index,
                    self.service,
                    self.sid,
                    self.contract,
                    attachment_ids=self.attachments,
                    sources=self.observation_sources(),
                )
                return {
                    "data": {**data, "requirements": self.contract["requirements"]},
                    "sources": [],
                }
            if name == "write_research_report" and set(args) == {"plan"} and self.report_allowed:
                return await self.report(args["plan"])
        except (ValidationError, StoreError, sandbox.SandboxError, ProviderError) as exc:
            code = getattr(exc, "code", "qa_tool_rejected")
            return {
                "data": {"status": "unavailable", "code": code},
                "sources": [],
                "warnings": ["资料或报告计划未通过 RWB 校验"],
            }
        return {
            "data": {"status": "unavailable", "code": "qa_tool_not_allowed"},
            "sources": [],
            "warnings": ["当前研究未授权此工具或参数"],
        }

    def record_source(self, source):
        self.acquired[source["id"]] = source
        self.receipt["qa_acquired_sources"] = {
            source_id: value["sha256"]
            for source_id, value in self.acquired.items()
            if isinstance(value.get("sha256"), str)
        }
        self.store.save()

    def observation_sources(self):
        web = [
            source
            for source in stored_sources(self.store, self.sid)
            if source["id"] in self.acquired
        ]
        return [
            *web,
            *(source for source in self.acquired.values() if source["id"].startswith("dataset:")),
        ]

    async def query(self, name, args, call_id):
        capability = self.query_names[name]
        as_of = None
        if self.contract:
            cutoff = datetime.fromisoformat(self.contract["as_of"]).date()
            if cutoff < datetime.now(ZoneInfo("Asia/Shanghai")).date():
                as_of = datetime.combine(cutoff, time.max, ZoneInfo("Asia/Shanghai")).astimezone(
                    UTC
                )
        manifest = await self.service.datahub.query(
            self.sid, call_id, BusinessQuery(capability=capability, parameters=args, as_of=as_of)
        )
        did = manifest["dataset_id"]
        rows = self.service.datahub.rows(self.sid, did, limit=20)
        sample = []
        for row in rows["items"]:
            if len(json.dumps([*sample, row], ensure_ascii=False).encode()) > 32000:
                break
            sample.append(row)
        if capability in {"search_web", "search_research"} and "web" in self.scope:
            activity = {"title": name, "status": "completed", "detail": json.dumps(sample)}
            session = self.store.session(self.sid)
            existing = {row["id"]: row for row in session.get("web_search_sources", [])}
            existing.update({row["id"]: row for row in evidence_index([], [], [activity])})
            session["web_search_sources"] = list(existing.values())[-300:]
            self.store.save()
        if not manifest.get("data_success"):
            return {
                "data": {"status": "unavailable", "dataset_id": did},
                "sources": [],
                "warnings": ["数据源未通过当前研究口径核验"],
            }
        source = {
            "id": "dataset:" + did,
            "title": manifest.get("name") or capability,
            "provider": manifest.get("provider", "DataHub"),
            "as_of": manifest.get("as_of"),
            "sha256": manifest.get("manifest_sha256"),
        }
        self.record_source(source)
        return {
            "data": {
                "status": manifest["status"],
                "dataset_id": did,
                "items": sample,
                "total": rows["total"],
                "as_of": manifest.get("as_of"),
                "provider_metadata": manifest.get("provider_metadata", {}),
            },
            "sources": [_source(source)],
        }

    def frozen_dataset(self, did, *, manifest_sha256=None):
        trusted_context(self.service, self.sid, check_capabilities=False)
        manifest = self.service.datahub.detail(self.sid, did)
        if manifest.get("snapshot_kind") == "mcp_evidence":
            self.service.mcp_runtime.assert_frozen_result_authorized(self.sid, did)
            if (
                manifest.get("provider_metadata", {}).get("admission", {}).get("report_admitted")
                is not True
            ):
                raise StoreError("该资料仅为线索", "qa_dataset_not_admitted", 403)
        if manifest_sha256 and manifest["manifest_sha256"] != manifest_sha256:
            raise StoreError("跟踪冻结资料已变化", "qa_discovery_snapshot_changed", 409)
        as_of = manifest.get("as_of")
        if self.contract and manifest_sha256 is None:
            cutoff = datetime.fromisoformat(self.contract["as_of"]).date()
            today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
            if cutoff < today and (
                not isinstance(as_of, str)
                or as_of in {"unknown", ""}
                or datetime.fromisoformat(as_of).date() > cutoff
            ):
                raise StoreError("资料时点未获本轮授权", "qa_snapshot_cutoff", 403)
        values = self.service.datahub.rows(self.sid, did, limit=20)
        sample = []
        for item in values["items"]:
            if len(json.dumps([*sample, item], ensure_ascii=False).encode()) > 64000:
                break
            sample.append(item)
        source = {
            "id": "dataset:" + did,
            "title": manifest.get("name") or "冻结资料",
            "provider": manifest.get("provider") or "RWB",
            "as_of": manifest.get("as_of"),
            "sha256": manifest.get("manifest_sha256"),
        }
        self.record_source(source)
        return {
            "data": {
                "dataset_id": did,
                "manifest_sha256": source["sha256"],
                "as_of": source["as_of"],
                "items": sample,
                "total": values["total"],
                "limitations": manifest.get("limitations", []),
            },
            "sources": [_source(source)],
        }

    def frozen_discovery(self, context):
        result = self.frozen_dataset(
            context["dataset_id"], manifest_sha256=context["dataset_manifest_sha256"]
        )
        result["data"]["cutoff"] = context["cutoff"]
        return result

    async def sources(self, call_id):
        sources = []
        if "uploads" in self.scope:
            sources.extend(
                source
                for source in evidence_index(
                    upload_evidence_files(self.store, self.sid, self.store.files(self.sid)), [], []
                )
                if source["file_id"] in self.attachments
            )
        sources.extend(self.service.dossiers.registered_sources(self.sid))
        if "web" in self.scope:
            found = await execute_source(self.service, self.sid, call_id, "list")
            sources.extend(source for source in found["sources"] if source["id"].startswith("web:"))
        return sources

    async def read(self, identifier, call_id):
        if "uploads" in self.scope and identifier.startswith("file:"):
            fid = identifier[5:]
            if fid not in self.attachments or not any(
                item["id"] == fid and item["kind"] == "inputs"
                for item in upload_evidence_files(self.store, self.sid, self.store.files(self.sid))
            ):
                raise StoreError("附件未获本轮授权", "qa_attachment_scope", 403)
            stream, name = self.store.open_file(self.sid, fid)
            with stream:
                raw = stream.read(24001)
            try:
                text = raw[:24000].decode("utf-8")
            except UnicodeError:
                raise StoreError(
                    "此附件不能直接读取为文本", "qa_attachment_not_text", 409
                ) from None
            return {
                "data": {"content": text, "truncated": len(raw) > 24000},
                "sources": [_source({"id": identifier, "title": name})],
            }
        allowed = ("web" in self.scope and identifier.startswith("web:")) or (
            "uploads" in self.scope and identifier.startswith("dossier:")
        )
        if not allowed:
            raise StoreError("来源未获本轮授权", "qa_source_scope", 403)
        data = await execute_source(self.service, self.sid, call_id, "read", identifier)
        source = data.get("source") or {
            "id": identifier,
            "title": data.get("title") or identifier,
            "url": data.get("url"),
            "as_of": data.get("as_of"),
        }
        self.record_source(source)
        return {"data": data, "sources": [_source(source)]}

    async def report(self, plan):
        if self.report_written:
            raise StoreError("本轮报告已生成", "qa_report_already_written", 409)
        await asyncio.to_thread(
            write_business_snapshot,
            self.service,
            self.sid,
            self.contract,
            attachment_ids=self.attachments,
            sources=self.observation_sources(),
        )
        context = {
            "task_id": self.contract["task_id"],
            "contract_sha256": self.contract["sha256"],
            "as_of": self.contract["as_of"],
            "requirement_ids": [row["id"] for row in self.contract["requirements"]],
            "formats": required_report_formats(self.contract, self.receipt["delivery"]),
        }
        target = required_body_target(self.contract)
        if target:
            context["body_target"] = target
        code = (
            "import json\nfrom research_report_plan import write_business_report_plan\n"
            "write_business_report_plan(json.loads(" + repr(json.dumps(context)) + "), "
            "json.loads(" + repr(json.dumps(plan)) + "))\n"
        )
        run = asyncio.create_task(
            asyncio.to_thread(
                sandbox.run_script,
                self.service.delivery.config,
                self.store.directory(self.sid),
                code,
            )
        )
        try:
            outcome = await asyncio.shield(run)
        except asyncio.CancelledError:
            await run
            raise
        if outcome.status != "completed":
            raise StoreError("报告计划未完成", "qa_report_plan_failed", 409)
        self.report_written = True
        return {"data": {"status": "generated", "quality": "pending_host_check"}, "sources": []}
