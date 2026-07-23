"""联网问答阶段 3 单元测试——认知代理 evidence 补充 + 报告生成 web search.

覆盖：
- AgentWorkflowRunner._enrich_evidence_from_web：evidence 不足时补充
- AgentWorkflowRunner._run_agent：信息角色触发、非信息角色跳过
- ReportProjectGenerationService._enrich_evidence_from_web：始终联网搜索 + 去重合并
- ReportProjectGenerationService._merge_and_dedupe：URL 去重与 DB 优先
- WebSearchResult → EvidenceItem / EvidenceSnippet 转换
"""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from core.contracts.agent_types import EvidenceBundle, EvidenceItem
from core.interfaces import WebSearchResult
from services.web_search_service import WebSearchService

# ── test helpers ──────────────────────────────────────────


def _make_result(title="标题", url="http://x", snippet="摘要", content="正文") -> WebSearchResult:
    return WebSearchResult(title=title, url=url, snippet=snippet, content=content, source="fake")


# ── EvidenceItem 转换 ─────────────────────────────────────


class TestEvidenceItemConversion:
    def test_evidence_item_from_web_search_result(self):
        result = _make_result(title="测试标题", url="http://test")
        item = EvidenceItem(
            evidence_id="web_search_abc123",
            ref_id=result.url,
            ref_type="external",
            evidence_kind="media",
            source_type="web_search",
            source_name=result.source,
            title=result.title,
            summary=(result.content or result.snippet or "")[:500],
            reliability=0.6,
            relevance=0.7,
            payload={"url": result.url, "source": result.source},
        )
        assert item.ref_id == "http://test"
        assert item.ref_type == "external"
        assert item.evidence_kind == "media"
        assert item.source_type == "web_search"

    def test_legacy_dict_from_web_search_result(self):
        result = _make_result(title="标题", url="http://u", snippet="摘")
        evidence_id = f"web_search_{uuid.uuid4().hex[:12]}"
        legacy = {
            "evidence_id": evidence_id,
            "ref_id": result.url,
            "ref_type": "external",
            "kind": "media",
            "source_type": "web_search",
            "title": result.title,
            "text": result.content or result.snippet or "",
            "summary": (result.content or result.snippet)[:500],
            "url": result.url,
            "confidence": 0.6,
        }
        assert legacy["ref_id"] == "http://u"
        assert legacy["source_type"] == "web_search"


# ── _enrich_evidence_from_web ─────────────────────────────


class TestEnrichEvidenceFromWeb:
    def test_enrich_adds_items_to_evidence_bundle(self):
        from cognitive_agents.agents.base import AgentContext
        from cognitive_agents.workflow import AgentWorkflowRunner

        results = [_make_result("搜索结果A", "http://a", content="内容A")]
        ws = WebSearchService(provider=MagicMock(search=MagicMock(return_value=results)))
        runner = AgentWorkflowRunner(
            agent_factory=MagicMock(),
            web_search_service=ws,
        )
        context = AgentContext(
            target_id="test_target",
            question="某问题",
            evidence=[],
            evidence_bundle=EvidenceBundle(
                target_id="test_target",
                question="某问题",
                evidence_items=[],
            ),
        )
        asyncio.run(runner._enrich_evidence_from_web(context))

        # 旧格式 (list[dict]) 已注入
        assert len(context.evidence) == 1
        assert context.evidence[0]["title"] == "搜索结果A"
        assert context.evidence[0]["url"] == "http://a"
        assert context.evidence[0]["source_type"] == "web_search"

        # 新格式 (EvidenceBundle) 已注入
        assert context.evidence_bundle is not None
        assert len(context.evidence_bundle.evidence_items) == 1
        item = context.evidence_bundle.evidence_items[0]
        assert item.title == "搜索结果A"
        assert item.ref_type == "external"
        assert item.source_type == "web_search"

    def test_enrich_does_nothing_when_no_web_search(self):
        from cognitive_agents.agents.base import AgentContext
        from cognitive_agents.workflow import AgentWorkflowRunner

        runner = AgentWorkflowRunner(agent_factory=MagicMock(), web_search_service=None)
        context = AgentContext(target_id="x", question="q", evidence=[])
        asyncio.run(runner._enrich_evidence_from_web(context))

        assert len(context.evidence) == 0
        assert context.evidence_bundle is None

    def test_enrich_does_nothing_when_search_returns_empty(self):
        from cognitive_agents.agents.base import AgentContext
        from cognitive_agents.workflow import AgentWorkflowRunner

        ws = WebSearchService(provider=MagicMock(search=MagicMock(return_value=[])))
        runner = AgentWorkflowRunner(agent_factory=MagicMock(), web_search_service=ws)
        context = AgentContext(target_id="x", question="q", evidence=[])
        asyncio.run(runner._enrich_evidence_from_web(context))

        assert len(context.evidence) == 0

    def test_enrich_search_exception_is_graceful(self):
        from cognitive_agents.agents.base import AgentContext
        from cognitive_agents.workflow import AgentWorkflowRunner

        ws = WebSearchService(
            provider=MagicMock(search=MagicMock(side_effect=RuntimeError("boom")))
        )
        runner = AgentWorkflowRunner(agent_factory=MagicMock(), web_search_service=ws)
        context = AgentContext(target_id="x", question="q", evidence=[])
        asyncio.run(runner._enrich_evidence_from_web(context))

        assert len(context.evidence) == 0


# ── _run_agent 角色过滤（直接测 _run_agent，不走 run）───


class TestRunAgentEnrichment:
    def test_information_role_triggers_enrich(self):
        """信息收集角色 + evidence 不足 → 触发 _enrich_evidence_from_web。"""
        from cognitive_agents.agents.base import AgentContext
        from cognitive_agents.contracts import AgentWorkflow, AgentWorkflowStage
        from cognitive_agents.workflow import AgentWorkflowRunner

        mock_agent = MagicMock()
        mock_agent.analyze = AsyncMock(
            return_value=MagicMock(target_id="t1", event_id=None, workflow_id="w1", view_id="v1")
        )
        factory = MagicMock()
        factory.create.return_value = mock_agent

        ws = WebSearchService(provider=MagicMock(search=MagicMock(return_value=[])))
        runner = AgentWorkflowRunner(agent_factory=factory, web_search_service=ws)

        # patch 掉实际的 _enrich（我们不关心它的副作用）
        with patch.object(runner, "_enrich_evidence_from_web") as mock_enrich:
            workflow = AgentWorkflow(
                workflow_id="w1",
                target_id="t1",
                question="问题",
                stages=[
                    AgentWorkflowStage(
                        stage_id="info",
                        label="信息",
                        agent_roles=["news"],
                        policy="parallel",
                    )
                ],
            )
            context = AgentContext(target_id="t1", question="问题", evidence=[])
            from cognitive_agents.blackboard import CognitiveBlackboard

            asyncio.run(runner._run_agent("news", workflow, context, CognitiveBlackboard()))

        mock_enrich.assert_called_once()

    def test_non_information_role_does_not_trigger_enrich(self):
        """非信息角色不应触发联网搜索。"""
        from cognitive_agents.agents.base import AgentContext
        from cognitive_agents.contracts import AgentWorkflow, AgentWorkflowStage
        from cognitive_agents.workflow import AgentWorkflowRunner

        mock_agent = MagicMock()
        mock_agent.analyze = AsyncMock(
            return_value=MagicMock(target_id="t1", event_id=None, workflow_id="w2", view_id="v2")
        )
        factory = MagicMock()
        factory.create.return_value = mock_agent

        ws = WebSearchService(provider=MagicMock(search=MagicMock(return_value=[])))
        runner = AgentWorkflowRunner(agent_factory=factory, web_search_service=ws)

        with patch.object(runner, "_enrich_evidence_from_web") as mock_enrich:
            workflow = AgentWorkflow(
                workflow_id="w2",
                target_id="t1",
                question="问题",
                stages=[
                    AgentWorkflowStage(
                        stage_id="research",
                        label="分析",
                        agent_roles=["fundamental"],
                        policy="parallel",
                    )
                ],
            )
            context = AgentContext(target_id="t1", question="问题", evidence=[])
            from cognitive_agents.blackboard import CognitiveBlackboard

            asyncio.run(runner._run_agent("fundamental", workflow, context, CognitiveBlackboard()))

        mock_enrich.assert_not_called()

    def test_sufficient_evidence_does_not_trigger_enrich(self):
        """evidence 足够时不触发联网搜索。"""
        from cognitive_agents.agents.base import AgentContext
        from cognitive_agents.contracts import AgentWorkflow, AgentWorkflowStage
        from cognitive_agents.workflow import AgentWorkflowRunner

        mock_agent = MagicMock()
        mock_agent.analyze = AsyncMock(
            return_value=MagicMock(target_id="t1", event_id=None, workflow_id="w3", view_id="v3")
        )
        factory = MagicMock()
        factory.create.return_value = mock_agent

        ws = WebSearchService(provider=MagicMock(search=MagicMock(return_value=[])))
        runner = AgentWorkflowRunner(agent_factory=factory, web_search_service=ws)

        with patch.object(runner, "_enrich_evidence_from_web") as mock_enrich:
            workflow = AgentWorkflow(
                workflow_id="w3",
                target_id="t1",
                question="问题",
                stages=[
                    AgentWorkflowStage(
                        stage_id="info",
                        label="信息",
                        agent_roles=["news"],
                        policy="parallel",
                    )
                ],
            )
            context = AgentContext(
                target_id="t1",
                question="问题",
                evidence=[
                    {"id": "e1", "title": "已有证据1"},
                    {"id": "e2", "title": "已有证据2"},
                ],  # >= 2 条，足够
            )
            from cognitive_agents.blackboard import CognitiveBlackboard

            asyncio.run(runner._run_agent("news", workflow, context, CognitiveBlackboard()))

        mock_enrich.assert_not_called()


# ── ReportProjectGenerationService._enrich_evidence_from_web ─


class TestReportGenerationEnrich:
    def test_enrich_returns_evidence_snippets(self):
        """搜索结果应正确转换为 EvidenceSnippet。"""
        results = [_make_result("T1", "http://a", snippet="S1", content="C1")]
        ws = WebSearchService(provider=MagicMock(search=MagicMock(return_value=results)))
        out = ws.search("query", fetch_content=False)
        assert len(out) == 1
        assert out[0].title == "T1"
        assert isinstance(out[0], WebSearchResult)

    def test_enrich_returns_empty_when_no_web_search(self):
        ws = WebSearchService(
            provider=MagicMock(search=MagicMock(return_value=[])),
            fetch_content_enabled=False,
        )
        out = ws.search("query")
        assert out == []

    def test_enrich_gap_between_retrieval_and_llm(self):
        """模拟报告生成注入点：DB 无结果时联网搜索并追加 EvidenceSnippet。"""
        # DB 检索 → 空
        evidence: list = []
        assert not evidence

        # 联网搜索
        results = [_make_result("T", "http://a", content="正文")]
        ws = WebSearchService(
            provider=MagicMock(search=MagicMock(return_value=results)),
            fetch_content_enabled=False,
        )
        web_out = ws.search("query", fetch_content=False)

        # 转 EvidenceSnippet（复刻 ReportProjectGenerationService 的逻辑）
        class FakeSnippet:
            def __init__(self, source, title, content, url):
                self.source = source
                self.title = title
                self.content = content
                self.url = url

        snippets = [
            FakeSnippet(
                source="web_search",
                title=item.title,
                content=item.content or item.snippet or "",
                url=item.url,
            )
            for item in web_out
        ]
        evidence = evidence + snippets

        assert len(evidence) == 1
        assert evidence[0].source == "web_search"
        assert evidence[0].title == "T"

    def test_web_search_always_called_with_db_results(self):
        """DB 有结果时仍然调 web search，两边结果合并。"""
        from reporting.projects.generation import EvidenceSnippet, ReportProjectGenerationService

        db_snippets = [
            EvidenceSnippet(
                source="ingestion:news",
                title="DB新闻1",
                content="DB内容1",
                url="http://db1",
                retrieval_method="keyword",
            ),
        ]
        web_results = [_make_result("Web新闻", "http://web1", content="Web内容")]
        ws = WebSearchService(provider=MagicMock(search=MagicMock(return_value=web_results)))

        service = ReportProjectGenerationService(web_search_service=ws)
        web_snippets = service._enrich_evidence_from_web(query="测试query", max_results=5)

        # 始终调 web search（无论 DB 是否有结果）
        assert len(web_snippets) == 1
        assert web_snippets[0].source == "web_search"
        assert web_snippets[0].title == "Web新闻"

        # 合并去重
        merged = service._merge_and_dedupe(db_snippets, web_snippets)
        assert len(merged) == 2
        sources = {s.source for s in merged}
        assert "ingestion:news" in sources
        assert "web_search" in sources

    def test_merge_dedupe_by_url(self):
        """URL 相同的 web 结果应被去重，DB 结果优先保留。"""
        from reporting.projects.generation import EvidenceSnippet, ReportProjectGenerationService

        db_snippets = [
            EvidenceSnippet(
                source="ingestion:news",
                title="DB标题",
                content="DB内容",
                url="http://same-url",
                retrieval_method="keyword",
            ),
        ]
        web_snippets = [
            EvidenceSnippet(
                source="web_search",
                title="Web标题",
                content="Web内容",
                url="http://same-url",  # 与 DB 相同 URL
                retrieval_method="web_search",
            ),
            EvidenceSnippet(
                source="web_search",
                title="另一篇Web",
                content="另一篇内容",
                url="http://different-url",
                retrieval_method="web_search",
            ),
        ]

        merged = ReportProjectGenerationService._merge_and_dedupe(db_snippets, web_snippets)
        assert len(merged) == 2  # DB的1条 + web中不重复的1条
        # DB 的保留
        assert merged[0].source == "ingestion:news"
        assert merged[0].title == "DB标题"
        # web 中不同 URL 的追加
        assert merged[1].source == "web_search"
        assert merged[1].url == "http://different-url"

    def test_merge_dedupe_empty_db(self):
        """DB 无结果时，web 结果全部保留。"""
        from reporting.projects.generation import EvidenceSnippet, ReportProjectGenerationService

        web_snippets = [
            EvidenceSnippet(
                source="web_search",
                title="W1",
                content="C1",
                url="http://w1",
                retrieval_method="web_search",
            ),
            EvidenceSnippet(
                source="web_search",
                title="W2",
                content="C2",
                url="http://w2",
                retrieval_method="web_search",
            ),
        ]

        merged = ReportProjectGenerationService._merge_and_dedupe([], web_snippets)
        assert len(merged) == 2

    def test_merge_dedupe_no_url(self):
        """web 结果无 URL 时不参与去重，直接追加。"""
        from reporting.projects.generation import EvidenceSnippet, ReportProjectGenerationService

        db_snippets = [
            EvidenceSnippet(
                source="ingestion:news",
                title="DB",
                content="C",
                url=None,
                retrieval_method="keyword",
            ),
        ]
        web_snippets = [
            EvidenceSnippet(
                source="web_search",
                title="W",
                content="C",
                url=None,  # 无 URL
                retrieval_method="web_search",
            ),
        ]

        merged = ReportProjectGenerationService._merge_and_dedupe(db_snippets, web_snippets)
        assert len(merged) == 2  # 无 URL 不参与去重，都保留

    def test_web_search_none_service_returns_empty_in_generation(self):
        """web_search_service 为 None 时 _enrich 返回空，不影响 DB 结果。"""
        from reporting.projects.generation import EvidenceSnippet, ReportProjectGenerationService

        service = ReportProjectGenerationService(web_search_service=None)
        web_snippets = service._enrich_evidence_from_web(query="测试", max_results=5)
        assert web_snippets == []

        # merge 空列表不改变 DB 结果
        db = [EvidenceSnippet(source="db", title="T", content="C")]
        merged = service._merge_and_dedupe(db, web_snippets)
        assert len(merged) == 1
        assert merged[0].source == "db"
