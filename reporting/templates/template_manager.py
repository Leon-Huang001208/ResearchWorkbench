"""
模板管理器 - 管理报告模板的加载、验证和存储.

Template manager handles loading, validation, and storage of report templates.
"""

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Set

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

        # 模板文件存储子目录
        self.yaml_dir = self.templates_dir / "yaml"
        self.docx_dir = self.templates_dir / "docx"
        self.pptx_dir = self.templates_dir / "pptx"
        self.excel_dir = self.templates_dir / "excel"

        # 确保所有子目录存在
        for dir_path in [self.yaml_dir, self.docx_dir, self.pptx_dir, self.excel_dir]:
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created templates subdirectory: {dir_path}")

    def _ensure_templates_dir(self):
        """确保模板目录存在."""
        if not self.templates_dir.exists():
            self.templates_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created templates directory: {self.templates_dir}")

    def list_templates(self) -> List[str]:
        """列出所有可用的模板.

        Returns:
            List of template names sorted by sort_order.
        """
        if not self.yaml_dir.exists():
            return []

        # 加载所有模板并按sort_order排序
        templates_with_order = []
        for f in self.yaml_dir.glob("*.yaml"):
            try:
                config = self.load_template(f.stem)
                templates_with_order.append((config.sort_order, f.stem))
            except Exception:
                templates_with_order.append((0, f.stem))

        # 同时也检查旧位置（向后兼容）
        for f in self.templates_dir.glob("*.yaml"):
            if not any(t[1] == f.stem for t in templates_with_order):
                templates_with_order.append((0, f.stem))

        # 按sort_order排序，然后按名称
        templates_with_order.sort(key=lambda x: (x[0], x[1]))
        return [t[1] for t in templates_with_order]

    def update_template_metadata(self, template_name: str, **kwargs) -> TemplateConfig:
        """更新模板元数据.

        Args:
            template_name: Name of the template to update.
            **kwargs: Metadata to update (name, description, version, sort_order, etc.).

        Returns:
            Updated TemplateConfig.
        """
        config = self.load_template(template_name)

        # 更新字段
        if "name" in kwargs and kwargs["name"]:
            # 如果改了名字，需要删除旧的，保存新的
            new_name = kwargs["name"]
            if new_name != template_name:
                self.delete_template(template_name)
                config.name = new_name

        if "description" in kwargs:
            config.description = kwargs["description"]
        if "version" in kwargs:
            config.version = kwargs["version"]
        if "sort_order" in kwargs:
            config.sort_order = kwargs["sort_order"]
        if "target_audience" in kwargs:
            config.target_audience = kwargs["target_audience"]

        self.save_template(config, overwrite=True)
        return config

    def update_templates_order(self, template_names: List[str]) -> bool:
        """批量更新模板排序.

        Args:
            template_names: List of template names in desired order.

        Returns:
            Success status.
        """
        for idx, template_name in enumerate(template_names):
            try:
                self.update_template_metadata(template_name, sort_order=idx)
            except Exception as e:
                logger.error(f"Failed to update order for {template_name}: {e}")
                return False
        return True

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

        # 先检查新位置
        template_path = self.yaml_dir / f"{template_name}.yaml"
        if not template_path.exists():
            # 检查旧位置（向后兼容）
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
        template_path = self.yaml_dir / f"{config.name}.yaml"

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
        # 从新位置删除
        template_path = self.yaml_dir / f"{template_name}.yaml"
        if template_path.exists():
            template_path.unlink()

        # 也检查旧位置
        old_path = self.templates_dir / f"{template_name}.yaml"
        if old_path.exists():
            old_path.unlink()

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
            sort_order=data.get("sort_order", 0),
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
        if config.sort_order != 0:
            data["sort_order"] = config.sort_order
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

    # ========================================================================
    # v1 → v2 升级
    # ========================================================================

    def upgrade_to_v2(self, template_name: str) -> TemplateConfig:
        """将 v1 模板升级为 v2 格式.

        v1 → v2 变更：
        - version: "1.x" → "2.0"
        - metadata 中添加 "upgraded_from": "1.x"
        - 保持 SectionSpec 列表不变（ContentBuilder.from_template 兼容 v1 section）

        v2 模板额外支持（通过 metadata）：
        - metadata.design_tokens: 设计令牌字典
        - metadata.blocks: 每 section 的 blocks 定义

        Args:
            template_name: 模板名称.

        Returns:
            升级后的 TemplateConfig.

        Raises:
            FileNotFoundError: 如果模板不存在.
        """
        config = self.load_template(template_name)

        if config.is_v2:
            logger.info(
                "Template already v2, no upgrade needed",
                extra={"template": template_name, "version": config.version},
            )
            return config

        old_version = config.version
        config.version = "2.0"
        config.metadata["upgraded_from"] = old_version

        self.save_template(config, overwrite=True)
        logger.info(
            "Upgraded template to v2",
            extra={"template": template_name, "from_version": old_version},
        )
        return config

    def upgrade_all_to_v2(self) -> List[str]:
        """批量升级所有 v1 模板到 v2.

        Returns:
            已升级的模板名称列表.
        """
        upgraded: List[str] = []
        for name in self.list_templates():
            try:
                config = self.load_template(name)
                if not config.is_v2:
                    self.upgrade_to_v2(name)
                    upgraded.append(name)
            except Exception as e:
                logger.error(
                    "Failed to upgrade template",
                    extra={"template": name, "error": str(e)},
                )
        logger.info(
            "Batch upgrade complete",
            extra={"upgraded_count": len(upgraded), "templates": upgraded},
        )
        return upgraded

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

    # ========================================================================
    # 模板文件管理
    # ========================================================================

    def save_template_file(
        self,
        template_name: str,
        file_type: Literal["docx", "pptx", "excel"],
        file_content: bytes,
        overwrite: bool = False,
    ) -> Path:
        """保存模板文件（DOCX/PPTX/Excel）.

        Args:
            template_name: 模板名称
            file_type: 文件类型（docx/pptx/excel）
            file_content: 文件二进制内容
            overwrite: 是否覆盖已有文件

        Returns:
            保存的文件路径

        Raises:
            FileExistsError: 如果文件已存在且 overwrite=False
        """
        # 选择目标目录
        if file_type == "docx":
            target_dir = self.docx_dir
            ext = "docx"
        elif file_type == "pptx":
            target_dir = self.pptx_dir
            ext = "pptx"
        elif file_type == "excel":
            target_dir = self.excel_dir
            ext = "xlsx"
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

        # 构建文件名
        filename = f"{template_name}_template.{ext}"
        file_path = target_dir / filename

        # 检查是否已存在
        if file_path.exists() and not overwrite:
            raise FileExistsError(f"Template file already exists: {file_path}")

        # 保存文件
        file_path.write_bytes(file_content)
        logger.info(f"Saved template file: {file_path}")

        # 更新 TemplateConfig 中的文件路径
        try:
            config = self.load_template(template_name)
            if file_type == "docx":
                config.word_template_path = str(file_path)
            elif file_type == "pptx":
                # 注意：当前 TemplateConfig 没有 powerpoint_template_path 字段
                # 可以扩展或存储在 metadata 中
                config.metadata["powerpoint_template_path"] = str(file_path)
            elif file_type == "excel":
                config.excel_template_path = str(file_path)

            self.save_template(config, overwrite=True)
        except FileNotFoundError:
            # YAML 配置不存在，仅保存文件
            logger.info(f"Template YAML not found for {template_name}, only file saved")

        return file_path

    def get_template_file_path(
        self, template_name: str, file_type: Literal["docx", "pptx", "excel"]
    ) -> Optional[Path]:
        """获取模板文件路径.

        Args:
            template_name: 模板名称
            file_type: 文件类型

        Returns:
            文件路径，如果不存在返回 None
        """
        if file_type == "docx":
            target_dir = self.docx_dir
            ext = "docx"
        elif file_type == "pptx":
            target_dir = self.pptx_dir
            ext = "pptx"
        elif file_type == "excel":
            target_dir = self.excel_dir
            ext = "xlsx"
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

        file_path = target_dir / f"{template_name}_template.{ext}"
        if file_path.exists():
            return file_path

        try:
            config = self.load_template(template_name)
        except FileNotFoundError:
            return None

        configured_path: Optional[str] = None
        if file_type == "docx":
            configured_path = config.word_template_path
        elif file_type == "pptx":
            configured_path = config.metadata.get("powerpoint_template_path")
        elif file_type == "excel":
            configured_path = config.excel_template_path

        if configured_path:
            path = Path(configured_path)
            if path.exists():
                return path

        return None

    def delete_template_file(
        self, template_name: str, file_type: Literal["docx", "pptx", "excel"]
    ) -> bool:
        """删除模板文件.

        Args:
            template_name: 模板名称
            file_type: 文件类型

        Returns:
            是否成功删除
        """
        file_path = self.get_template_file_path(template_name, file_type)
        if file_path and file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted template file: {file_path}")

            # 更新 TemplateConfig
            try:
                config = self.load_template(template_name)
                if file_type == "docx":
                    config.word_template_path = None
                elif file_type == "excel":
                    config.excel_template_path = None
                if "powerpoint_template_path" in config.metadata:
                    del config.metadata["powerpoint_template_path"]
                self.save_template(config, overwrite=True)
            except FileNotFoundError:
                pass

            return True
        return False

    # ========================================================================
    # 占位符发现
    # ========================================================================

    def discover_placeholders_from_docx(
        self,
        template_name: str,
    ) -> Set[str]:
        """从 DOCX 模板文件中发现占位符.

        支持的占位符格式：
        - {{placeholder_name}}
        - {placeholder_name}
        - placeholder_name（仅当在段落中单独存在时）

        Args:
            template_name: 模板名称

        Returns:
            发现的占位符集合

        Raises:
            FileNotFoundError: 如果模板文件不存在
            ImportError: 如果 python-docx 未安装
        """
        # 检查 python-docx 是否可用
        try:
            import docx
        except ImportError:
            raise ImportError(
                "python-docx is required for placeholder discovery. "
                "Please install it with: pip install python-docx"
            )

        file_path = self.get_template_file_path(template_name, "docx")
        if not file_path:
            raise FileNotFoundError(f"DOCX template not found: {template_name}")

        doc = docx.Document(str(file_path))
        placeholders: Set[str] = set()

        # 从段落中发现
        for paragraph in doc.paragraphs:
            found = self._extract_placeholders_from_text(paragraph.text)
            placeholders.update(found)

        # 从表格中发现
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        found = self._extract_placeholders_from_text(paragraph.text)
                        placeholders.update(found)

        # 从页眉页脚中发现
        for section in doc.sections:
            for paragraph in section.header.paragraphs:
                found = self._extract_placeholders_from_text(paragraph.text)
                placeholders.update(found)
            for paragraph in section.footer.paragraphs:
                found = self._extract_placeholders_from_text(paragraph.text)
                placeholders.update(found)

        logger.info(f"Discovered {len(placeholders)} placeholders from {template_name}")
        return placeholders

    def _extract_placeholders_from_text(self, text: str) -> Set[str]:
        """从文本中提取占位符.

        Args:
            text: 文本内容

        Returns:
            发现的占位符集合
        """
        import re

        placeholders: Set[str] = set()

        # 匹配 {{placeholder}} 格式
        double_brace_pattern = r"\{\{([^}]+)\}\}"
        for match in re.finditer(double_brace_pattern, text):
            placeholder = match.group(1).strip()
            if placeholder:
                placeholders.add(placeholder)

        # 匹配 {placeholder} 格式（不与双大括号重叠）
        single_brace_pattern = r"(?<!\{)\{([^}]+)\}(?!\})"
        for match in re.finditer(single_brace_pattern, text):
            placeholder = match.group(1).strip()
            if placeholder and placeholder not in placeholders:
                placeholders.add(placeholder)

        return placeholders

    def discover_placeholders_from_pptx(
        self,
        template_name: str,
    ) -> Set[str]:
        """从 PPTX 模板文件中发现占位符.

        支持的占位符格式：
        - {{placeholder_name}}
        - {placeholder_name}

        Args:
            template_name: 模板名称

        Returns:
            发现的占位符集合

        Raises:
            FileNotFoundError: 如果模板文件不存在
            ImportError: 如果 python-pptx 未安装
        """
        # Check if python-pptx is available
        try:
            import pptx  # noqa: F401
            from pptx import Presentation
        except ImportError:
            raise ImportError(
                "python-pptx is required for PPTX placeholder discovery. "
                "Please install it with: pip install python-pptx"
            )

        file_path = self.get_template_file_path(template_name, "pptx")
        if not file_path:
            raise FileNotFoundError(f"PPTX template not found: {template_name}")

        prs = Presentation(str(file_path))
        placeholders: Set[str] = set()

        # Discover from slides
        for slide in prs.slides:
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        found = self._extract_placeholders_from_text(paragraph.text)
                        placeholders.update(found)
                if shape.has_table:
                    for row in shape.table.rows:
                        for cell in row.cells:
                            for paragraph in cell.text_frame.paragraphs:
                                found = self._extract_placeholders_from_text(paragraph.text)
                                placeholders.update(found)

        logger.info(f"Discovered {len(placeholders)} placeholders from PPTX {template_name}")
        return placeholders

    def list_all_template_files(self) -> Dict[str, Dict[str, Optional[Path]]]:
        """列出所有模板及其文件.

        Returns:
            模板名称 -> 文件类型 -> 文件路径的字典
        """
        template_names = self.list_templates()
        result: Dict[str, Dict[str, Optional[Path]]] = {}

        for name in template_names:
            result[name] = {
                "docx": self.get_template_file_path(name, "docx"),
                "pptx": self.get_template_file_path(name, "pptx"),
                "excel": self.get_template_file_path(name, "excel"),
            }

        return result
