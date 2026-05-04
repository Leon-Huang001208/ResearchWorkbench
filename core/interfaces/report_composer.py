from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from core.contracts import SectionOutput, SectionSpec


class ReportComposer(ABC):
    """报告合成器基类 - 生成各类报告"""

    @abstractmethod
    def compose_section(
        self,
        spec: SectionSpec,
        evidence_refs: list[str] | None = None,
        scenario_refs: list[str] | None = None,
        **kwargs: Any,
    ) -> SectionOutput:
        """合成单个报告段落"""
        pass

    @abstractmethod
    def compose_report(
        self,
        specs: list[SectionSpec],
        template_name: str,
        **kwargs: Any,
    ) -> list[SectionOutput]:
        """合成完整报告"""
        pass

    @abstractmethod
    def export_markdown(self, sections: list[SectionOutput], output_path: Path) -> None:
        """导出为 Markdown"""
        pass

    @abstractmethod
    def export_word(self, sections: list[SectionOutput], output_path: Path) -> None:
        """导出为 Word"""
        pass
