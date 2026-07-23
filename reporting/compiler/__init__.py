"""
报告编译器 - outline-first + evidence-first 报告编译器.

把报告生成从"单次长文生成"重构为多阶段流水线：
任务分解 → 来源规划 → 检索 → 事实抽取 → 大纲 → 分节写作 → 引用绑定 → 批判 → 渲染

设计依据：deep-research-report.md（STORM/RAPID/FoRAG/CRAG/LongCite 思路）。
"""

from reporting.compiler.citation_binder import CitationBinder
from reporting.compiler.compiler import ReportCompiler
from reporting.compiler.critic import Critic
from reporting.compiler.evidence_retriever import (
    EvidenceRetriever,
    EvidenceRetrieverProtocol,
    PassthroughEvidenceRetriever,
)
from reporting.compiler.fact_extractor import FactExtractor
from reporting.compiler.outline_planner import OutlinePlanner
from reporting.compiler.renderer import Renderer
from reporting.compiler.section_writer import SectionWriter
from reporting.compiler.source_planner import SourcePlan, SourcePlanner
from reporting.compiler.task_decomposer import TaskDecomposer

__all__ = [
    "ReportCompiler",
    "TaskDecomposer",
    "SourcePlanner",
    "SourcePlan",
    "EvidenceRetriever",
    "EvidenceRetrieverProtocol",
    "PassthroughEvidenceRetriever",
    "FactExtractor",
    "OutlinePlanner",
    "SectionWriter",
    "CitationBinder",
    "Critic",
    "Renderer",
]
