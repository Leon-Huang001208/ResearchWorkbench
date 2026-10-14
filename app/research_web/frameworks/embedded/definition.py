"""Embedded framework definition for external standalone research apps."""

from ..base import FrameworkDefinition

DEFINITION = FrameworkDefinition.model_validate(
    {
        "slug": "embedded",
        "name": "嵌入式研究框架",
        "domain": "embedded",
        "version": "1.0.0",
        "source_revision": "0000000000000000000000000000000000000000",
        "question": "外部独立研究项目如何与本站研究框架集成？",
        "chain": ["入口", "外部项目", "数据回传"],
        "counter_evidence": ["外部项目未运行", "外部项目数据不可达"],
        "sections": [
            {"id": "overview", "label": "总览", "question": "当前框架状态与入口是什么？"},
            {"id": "external", "label": "外部项目", "question": "独立项目提供了哪些研究视角？"},
            {"id": "data", "label": "数据回传", "question": "哪些结论可以回传到主研究台？"},
        ],
        "method": "通过 iframe 嵌入外部独立研究项目，保留其完整交互；元数据注册到框架目录便于统一发现。",
    }
)
