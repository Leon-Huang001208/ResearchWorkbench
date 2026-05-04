"""
报告合成器

整合 SectionGenerator 和 EvidenceBinder，提供一键生成报告的接口。
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from core.contracts import SectionOutput
from core.interfaces import ModelGateway
from core.observability import get_logger
from reporting.composer.evidence_binder import EvidenceBinder
from reporting.composer.section_generator import SectionGenerator
from reporting.projections.markdown import MarkdownProjection
from reporting.projections.word import WordProjection

logger = get_logger(__name__)


class ReportComposer:
    """报告合成器"""

    def __init__(
        self,
        model_gateway: Optional[ModelGateway] = None,
        templates_dir: Optional[Path] = None,
    ):
        self.model_gateway = model_gateway
        self.section_generator = SectionGenerator(model_gateway, templates_dir)
        self.evidence_binder = EvidenceBinder()

    def add_evidence(
        self,
        evidence_id: str,
        source: str,
        content: str,
        relevance_score: float = 1.0,
    ):
        """添加证据"""
        self.evidence_binder.add_evidence(evidence_id, source, content, relevance_score)

    def generate_report(
        self,
        template_name: str,
        context: Dict[str, Any],
    ) -> List[SectionOutput]:
        """
        生成完整报告

        Args:
            template_name: 模板名称
            context: 上下文数据

        Returns:
            章节列表
        """
        logger.info(f"Generating report using template: {template_name}")

        # 加载模板
        sections = self.section_generator.load_template(template_name)

        # 为每个章节生成内容
        outputs = []
        for spec in sections:
            # 查找相关证据
            evidence = self.evidence_binder.bind_to_section(spec.key, str(context), top_k=5)
            evidence_dicts = self.evidence_binder.to_dict_list(evidence)

            # 生成段落
            output = self.section_generator.generate_section(spec, context, evidence_dicts)
            outputs.append(output)

        logger.info(f"Generated {len(outputs)} sections")
        return outputs

    def save_report(
        self,
        output_path: Path | str,
        title: str,
        sections: List[SectionOutput],
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        保存报告到文件

        Args:
            output_path: 输出路径
            title: 报告标题
            sections: 章节列表
            metadata: 元数据
        """
        output_path = Path(output_path)
        suffix = output_path.suffix.lower()

        if suffix == ".md":
            projection = MarkdownProjection()
            projection.save(output_path, title, sections, metadata)
        elif suffix == ".docx":
            projection = WordProjection()
            projection.save(output_path, title, sections, metadata)
        else:
            raise ValueError(f"Unsupported output format: {suffix}")

    def list_templates(self) -> List[str]:
        """列出所有可用的模板"""
        templates_dir = self.section_generator.templates_dir
        if not templates_dir.exists():
            return []

        templates = []
        for f in templates_dir.glob("*.yaml"):
            templates.append(f.stem)

        return sorted(templates)
