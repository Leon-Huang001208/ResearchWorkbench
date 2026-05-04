"""报告合成器"""
from reporting.composer.evidence_binder import BoundEvidence, EvidenceBinder
from reporting.composer.report_composer import ReportComposer
from reporting.composer.section_generator import SectionGenerator

__all__ = [
    "SectionGenerator",
    "EvidenceBinder",
    "BoundEvidence",
    "ReportComposer",
]
