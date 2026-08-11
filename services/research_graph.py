"""Pure LangGraph execution plan for the A-share deep-research template.

The graph owns execution order only.  ResearchRunService persists every input and
output, making PostgreSQL instead of LangGraph checkpoints the source of truth.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph


class ResearchGraphState(TypedDict, total=False):
    run_id: str
    target_id: str
    subject: dict[str, Any]
    as_of: str
    question: str
    evidence: list[dict[str, Any]]
    source_plan: dict[str, Any]
    research_notes: list[dict[str, Any]]
    claims: list[dict[str, Any]]
    quality_checks: list[dict[str, Any]]
    decision_card: dict[str, Any]
    report_markdown: str
    blocked_reasons: list[str]
    status: str


class AShareDeepResearchGraph:
    """Build the deterministic, evidence-first first-version research graph."""

    REQUIRED_KINDS = ("financial", "industry", "valuation", "risk", "consensus")

    def __init__(self) -> None:
        graph = StateGraph(ResearchGraphState)
        graph.add_node("plan_sources", self._plan_sources)
        graph.add_node("normalize_evidence", self._normalize_evidence)
        graph.add_node("build_notes", self._build_notes)
        graph.add_node("synthesize_claims", self._synthesize_claims)
        graph.add_node("challenge", self._challenge)
        graph.add_node("validate", self._validate)
        graph.add_node("publish", self._publish)
        graph.add_edge(START, "plan_sources")
        graph.add_edge("plan_sources", "normalize_evidence")
        graph.add_edge("normalize_evidence", "build_notes")
        graph.add_edge("build_notes", "synthesize_claims")
        graph.add_edge("synthesize_claims", "challenge")
        graph.add_edge("challenge", "validate")
        graph.add_conditional_edges(
            "validate", self._after_validation, {"publish": "publish", "blocked": END}
        )
        graph.add_edge("publish", END)
        self._graph = graph.compile()

    def invoke(self, state: ResearchGraphState) -> ResearchGraphState:
        return self._graph.invoke(state)

    def _plan_sources(self, state: ResearchGraphState) -> ResearchGraphState:
        tiers = ("licensed", "official", "public", "user")
        available = {
            item["evidence_kind"]: item["source_tier"] for item in state.get("evidence", [])
        }
        downgrades = [
            {
                "evidence_id": item["evidence_id"],
                "from": "licensed",
                "to": item["source_tier"],
            }
            for item in state.get("evidence", [])
            if item["source_tier"] != "licensed"
        ]
        return {
            "status": "collecting",
            "source_plan": {
                "priority": list(tiers),
                "available_by_kind": available,
                "downgrades": downgrades,
                "fallback_policy": "record_each_downgrade",
            },
        }

    def _normalize_evidence(self, state: ResearchGraphState) -> ResearchGraphState:
        return {"status": "analyzing", "evidence": list(state.get("evidence", []))}

    def _build_notes(self, state: ResearchGraphState) -> ResearchGraphState:
        notes = [
            {
                "category": evidence["evidence_kind"],
                "summary": evidence["summary"],
                "evidence_refs": [evidence["source_ref"]],
            }
            for evidence in state.get("evidence", [])
        ]
        return {"research_notes": notes}

    def _synthesize_claims(self, state: ResearchGraphState) -> ResearchGraphState:
        claims = [
            {
                "category": evidence["evidence_kind"],
                "text": evidence["claim_text"],
                "evidence_refs": [evidence["source_ref"]],
                "numeric_context": {
                    key: evidence[key]
                    for key in ("numeric_value", "numeric_unit", "numeric_period", "calculation")
                    if evidence.get(key) is not None
                },
                "conflict_status": "unresolved" if evidence.get("conflict") else "clear",
            }
            for evidence in state.get("evidence", [])
        ]
        return {"claims": claims}

    def _challenge(self, state: ResearchGraphState) -> ResearchGraphState:
        return {"status": "validating"}

    def _validate(self, state: ResearchGraphState) -> ResearchGraphState:
        claims = state.get("claims", [])
        categories = {claim["category"] for claim in claims}
        checks = [
            {
                "gate_key": "citation_coverage",
                "passed": bool(claims) and all(claim["evidence_refs"] for claim in claims),
                "message": "所有研究观点必须绑定来源。",
            },
            {
                "gate_key": "required_facets",
                "passed": {"financial", "industry", "valuation", "risk"}.issubset(categories),
                "message": "财务、行业、估值和风险证据必须齐备。",
            },
            {
                "gate_key": "consensus_coverage",
                "passed": "consensus" in categories,
                "message": "A股深研必须具备一致预期或等效覆盖说明。",
            },
            {
                "gate_key": "numeric_integrity",
                "passed": all(
                    not claim["numeric_context"]
                    or {"numeric_value", "numeric_unit", "numeric_period"}.issubset(
                        claim["numeric_context"]
                    )
                    for claim in claims
                ),
                "message": "数值观点必须具有数值、单位和期间。",
            },
            {
                "gate_key": "conflict_resolution",
                "passed": all(claim["conflict_status"] == "clear" for claim in claims),
                "message": "未解决的关键观点冲突不可发布。",
            },
        ]
        blocked_reasons = [check["message"] for check in checks if not check["passed"]]
        return {
            "quality_checks": checks,
            "blocked_reasons": blocked_reasons,
            "status": "blocked" if blocked_reasons else "publishing",
        }

    @staticmethod
    def _after_validation(state: ResearchGraphState) -> str:
        return "blocked" if state.get("blocked_reasons") else "publish"

    def _publish(self, state: ResearchGraphState) -> ResearchGraphState:
        notes = state.get("research_notes", [])
        claims = state.get("claims", [])
        by_category = {note["category"]: note["summary"] for note in notes}
        coverage = {kind: kind in by_category for kind in self.REQUIRED_KINDS}
        decision_card = {
            "run_id": state["run_id"],
            "target_id": state["target_id"],
            "subject": state["subject"],
            "as_of": state["as_of"],
            "conclusion": "研究证据已通过发布门禁；结论应结合持续跟踪更新。",
            "confidence": min(0.9, 0.5 + 0.08 * len(claims)),
            "core_drivers": [by_category[k] for k in ("financial", "industry") if k in by_category],
            "catalysts": [by_category["consensus"]] if "consensus" in by_category else [],
            "risks": [by_category["risk"]] if "risk" in by_category else [],
            "invalidation_triggers": ["后续披露与当前财务或行业证据显著矛盾。"],
            "open_questions": [],
            "data_coverage": coverage,
        }
        markdown_lines = [
            f"# {state['subject'].get('display_name') or state['target_id']} A股深研",
            "",
            "## 研究结论",
            decision_card["conclusion"],
            "",
        ]
        for claim in claims:
            markdown_lines.append(
                f"- [{claim['category']}] {claim['text']}（来源：{', '.join(claim['evidence_refs'])}）"
            )
        return {
            "status": "completed",
            "decision_card": decision_card,
            "report_markdown": "\n".join(markdown_lines),
        }
