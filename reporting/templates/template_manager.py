"""
模板管理器 - 管理报告模板的加载、验证和存储.

Template manager handles loading, validation, and storage of report templates.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from core.contracts import RetrievalProfileType, SectionSpec, TemplateConfig
from core.observability import get_logger

logger = get_logger(__name__)


class TemplateManager:
    """模板管理器.

    Manages report templates, including loading, validation, and storage.
    Templates are YAML files that define the structure of a report.

    Attributes:
        templates_dir: Directory containing template files.
        template_cache: Cache of loaded templates.
    """

    def __init__(self, templates_dir: Optional[Path] = None):
        """初始化模板管理器.

        Args:
            templates_dir: Directory containing template files.
        """
        self.templates_dir = templates_dir or Path(__file__).parent
        self.template_cache: Dict[str, TemplateConfig] = {}
        self._ensure_templates_dir()

    def _ensure_templates_dir(self):
        """确保模板目录存在."""
        if not self.templates_dir.exists():
            self.templates_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created templates directory: {self.templates_dir}")

    def list_templates(self) -> List[str]:
        """列出所有可用的模板.

        Returns:
            List of template names (without .yaml extension).
        """
        if not self.templates_dir.exists():
            return []

        templates = []
        for f in self.templates_dir.glob("*.yaml"):
            templates.append(f.stem)

        return sorted(templates)

    def load_template(self, template_name: str) -> TemplateConfig:
        """加载模板配置.

        Args:
            template_name: Name of the template (without .yaml extension).

        Returns:
            Loaded TemplateConfig.

        Raises:
            FileNotFoundError: If template not found.
            ValueError: If template is invalid.
        """
        if template_name in self.template_cache:
            logger.debug(f"Using cached template: {template_name}")
            return self.template_cache[template_name]

        template_path = self.templates_dir / f"{template_name}.yaml"
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_name}")

        try:
            with open(template_path, "r", encoding="utf-8") as f:
                template_data = yaml.safe_load(f)

            config = self._parse_template_config(template_data, template_name)
            self._validate_template(config)

            self.template_cache[template_name] = config
            logger.info(f"Loaded template: {template_name} with {len(config.sections)} sections")
            return config

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse template {template_name}: {e}", exc_info=True)
            raise ValueError(f"Invalid YAML in template: {e}") from e
        except Exception as e:
            logger.error(f"Failed to load template {template_name}: {e}", exc_info=True)
            raise

    def save_template(self, config: TemplateConfig, overwrite: bool = False):
        """保存模板配置.

        Args:
            config: TemplateConfig to save.
            overwrite: Whether to overwrite existing template.

        Raises:
            FileExistsError: If template exists and overwrite is False.
        """
        template_path = self.templates_dir / f"{config.name}.yaml"

        if template_path.exists() and not overwrite:
            raise FileExistsError(f"Template already exists: {config.name}")

        try:
            template_data = self._template_config_to_dict(config)

            with open(template_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    template_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False
                )

            self.template_cache[config.name] = config
            logger.info(f"Saved template: {config.name}")

        except Exception as e:
            logger.error(f"Failed to save template {config.name}: {e}", exc_info=True)
            raise

    def delete_template(self, template_name: str):
        """删除模板.

        Args:
            template_name: Name of the template to delete.
        """
        template_path = self.templates_dir / f"{template_name}.yaml"

        if template_path.exists():
            template_path.unlink()

        if template_name in self.template_cache:
            del self.template_cache[template_name]

        logger.info(f"Deleted template: {template_name}")

    def clear_cache(self):
        """清空模板缓存."""
        self.template_cache.clear()
        logger.info("Template cache cleared")

    def _parse_template_config(self, data: Dict[str, Any], template_name: str) -> TemplateConfig:
        """解析模板配置字典.

        Args:
            data: Template data dictionary.
            template_name: Name of the template.

        Returns:
            Parsed TemplateConfig.
        """
        sections = []
        for section_data in data.get("sections", []):
            section = self._parse_section_spec(section_data)
            sections.append(section)

        retrieval_profile = RetrievalProfileType(
            data.get("default_retrieval_profile", "weekly_report")
        )

        config = TemplateConfig(
            name=data.get("name", template_name),
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
            target_audience=data.get("target_audience"),
            sections=sections,
            default_retrieval_profile=retrieval_profile,
            word_template_path=data.get("word_template_path"),
            excel_template_path=data.get("excel_template_path"),
            placeholders=data.get("placeholders", {}),
            metadata=data.get("metadata", {}),
        )

        return config

    def _parse_section_spec(self, data: Dict[str, Any]) -> SectionSpec:
        """解析章节规范.

        Args:
            data: Section data dictionary.

        Returns:
            Parsed SectionSpec.
        """
        retrieval_profile = None
        if "retrieval_profile" in data:
            retrieval_profile = RetrievalProfileType(data["retrieval_profile"])

        return SectionSpec(
            key=data["key"],
            title=data["title"],
            target_words=data.get("target_words", 200),
            required_facets=data.get("required_facets", []),
            scenario_required=data.get("scenario_required", True),
            evidence_policy=data.get("evidence_policy", "strict"),
            retrieval_profile=retrieval_profile,
            prompt_template=data.get("prompt_template"),
            forbidden_terms=data.get("forbidden_terms", []),
            structure=data.get("structure"),
            placeholder=data.get("placeholder"),
        )

    def _template_config_to_dict(self, config: TemplateConfig) -> Dict[str, Any]:
        """将 TemplateConfig 转换为字典.

        Args:
            config: TemplateConfig to convert.

        Returns:
            Dictionary representation.
        """
        sections_data = []
        for section in config.sections:
            section_data = {
                "key": section.key,
                "title": section.title,
                "target_words": section.target_words,
                "required_facets": section.required_facets,
                "scenario_required": section.scenario_required,
                "evidence_policy": section.evidence_policy,
            }
            if section.retrieval_profile:
                section_data["retrieval_profile"] = section.retrieval_profile.value
            if section.prompt_template:
                section_data["prompt_template"] = section.prompt_template
            if section.forbidden_terms:
                section_data["forbidden_terms"] = section.forbidden_terms
            if section.structure:
                section_data["structure"] = section.structure
            if section.placeholder:
                section_data["placeholder"] = section.placeholder
            sections_data.append(section_data)

        data = {
            "name": config.name,
            "description": config.description,
            "version": config.version,
            "default_retrieval_profile": config.default_retrieval_profile.value,
            "sections": sections_data,
        }
        if config.target_audience:
            data["target_audience"] = config.target_audience
        if config.word_template_path:
            data["word_template_path"] = config.word_template_path
        if config.excel_template_path:
            data["excel_template_path"] = config.excel_template_path
        if config.placeholders:
            data["placeholders"] = config.placeholders
        if config.metadata:
            data["metadata"] = config.metadata

        return data

    def _validate_template(self, config: TemplateConfig):
        """验证模板配置.

        Args:
            config: TemplateConfig to validate.

        Raises:
            ValueError: If template is invalid.
        """
        if not config.sections:
            raise ValueError("Template must have at least one section")

        seen_keys = set()
        for section in config.sections:
            if not section.key:
                raise ValueError("Section key cannot be empty")
            if section.key in seen_keys:
                raise ValueError(f"Duplicate section key: {section.key}")
            seen_keys.add(section.key)

            if not section.title:
                raise ValueError(f"Section {section.key} must have a title")

            if section.target_words <= 0:
                raise ValueError(f"Section {section.key} target_words must be positive")

        logger.debug(f"Template validation passed: {config.name}")

    def create_weekly_report_template(self) -> TemplateConfig:
        """创建周报模板.

        Returns:
            Weekly report TemplateConfig.
        """
        sections = [
            SectionSpec(
                key="market_summary",
                title="市场概览",
                target_words=300,
                required_facets=["大盘走势", "主要指数表现", "成交量"],
                retrieval_profile=RetrievalProfileType.WEEKLY_REPORT,
                placeholder="market_summary_placeholder",
            ),
            SectionSpec(
                key="key_events",
                title="本周重要事件",
                target_words=400,
                required_facets=["政策新闻", "公司公告", "行业动态"],
                retrieval_profile=RetrievalProfileType.WEEKLY_REPORT,
                placeholder="key_events_placeholder",
            ),
            SectionSpec(
                key="industry_performance",
                title="行业表现分析",
                target_words=350,
                required_facets=["涨幅居前行业", "跌幅居前行业", "行业资金流向"],
                retrieval_profile=RetrievalProfileType.WEEKLY_REPORT,
                placeholder="industry_performance_placeholder",
            ),
            SectionSpec(
                key="notable_stocks",
                title="重点股票观察",
                target_words=300,
                required_facets=["涨幅榜", "跌幅榜", "异动股票"],
                retrieval_profile=RetrievalProfileType.WEEKLY_REPORT,
                placeholder="notable_stocks_placeholder",
            ),
            SectionSpec(
                key="outlook",
                title="后市展望",
                target_words=250,
                required_facets=["技术面", "消息面", "风险提示"],
                retrieval_profile=RetrievalProfileType.WEEKLY_REPORT,
                evidence_policy="allow_synthesis",
                placeholder="outlook_placeholder",
            ),
        ]

        config = TemplateConfig(
            name="weekly_report",
            description="每周市场分析报告模板",
            version="1.0",
            target_audience="投资研究团队",
            sections=sections,
            default_retrieval_profile=RetrievalProfileType.WEEKLY_REPORT,
        )

        return config
