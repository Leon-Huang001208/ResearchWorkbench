"""
Abstract base class (interface) for report composers.

Defines the interface for report composers, which generate reports by composing sections
and exporting to Markdown or Word in AlphaFoundry.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from core.contracts import SectionOutput, SectionSpec


class ReportComposer(ABC):
    """报告合成器基类 - 生成各类报告.

    Abstract base class for report composers, which are responsible for composing
    individual report sections, full reports, and exporting to Markdown or Word.
    """

    @abstractmethod
    def compose_section(
        self,
        spec: SectionSpec,
        evidence_refs: list[str] | None = None,
        scenario_refs: list[str] | None = None,
        **kwargs: Any,
    ) -> SectionOutput:
        """合成单个报告段落.

        Composes a single report section from a SectionSpec, optional evidence and
        scenario references, and implementation-specific kwargs.

        Args:
            spec: Specification for the section to compose.
            evidence_refs: Optional list of evidence references to use.
            scenario_refs: Optional list of scenario references to use.
            **kwargs: Implementation-specific keyword arguments.

        Returns:
            SectionOutput: Composed section output.
        """
        pass

    @abstractmethod
    def compose_report(
        self,
        specs: list[SectionSpec],
        template_name: str,
        **kwargs: Any,
    ) -> list[SectionOutput]:
        """合成完整报告.

        Composes a full report from a list of SectionSpecs, a template name, and
        implementation-specific kwargs.

        Args:
            specs: List of section specifications for the report.
            template_name: Name of the template to use for the report.
            **kwargs: Implementation-specific keyword arguments.

        Returns:
            list[SectionOutput]: List of composed section outputs for the report.
        """
        pass

    @abstractmethod
    def export_markdown(self, sections: list[SectionOutput], output_path: Path) -> None:
        """导出为 Markdown.

        Exports the list of SectionOutputs to a Markdown file at the specified path.

        Args:
            sections: List of composed section outputs to export.
            output_path: Path to the output Markdown file.
        """
        pass

    @abstractmethod
    def export_word(self, sections: list[SectionOutput], output_path: Path) -> None:
        """导出为 Word.

        Exports the list of SectionOutputs to a Word document at the specified path.

        Args:
            sections: List of composed section outputs to export.
            output_path: Path to the output Word document.
        """
        pass
