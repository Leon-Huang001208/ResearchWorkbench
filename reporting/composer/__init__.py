"""报告合成器"""

from reporting.composer.evidence_binder import BoundEvidence, EvidenceBinder
from reporting.composer.fact_card_builder import FactCardBuilder
from reporting.composer.report_composer import ReportComposer
from reporting.composer.report_pipeline import ReportPipeline
from reporting.composer.section_generator import SectionGenerator
from reporting.composer.validator import ReportValidator

__all__ = [
    "SectionGenerator",
    "EvidenceBinder",
    "BoundEvidence",
    "ReportComposer",
    "FactCardBuilder",
    "ReportValidator",
    "ReportPipeline",
]
