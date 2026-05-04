"""段落生成器"""
from pathlib import Path
from typing import Any

import yaml

from core.contracts import SectionOutput, SectionSpec
from core.interfaces import ModelGateway
from core.observability import get_logger

logger = get_logger(__name__)


class SectionGenerator:
    """报告段落生成器"""

    def __init__(self, model_gateway: ModelGateway, templates_dir: Path | None = None):
        self.model_gateway = model_gateway
        self.templates_dir = templates_dir or Path(__file__).parent.parent / "templates"
        self._template_cache: dict[str, dict[str, Any]] = {}

    def load_template(self, template_name: str) -> list[SectionSpec]:
        """加载报告模板"""
        if template_name in self._template_cache:
            return self._template_cache[template_name]

        template_path = self.templates_dir / f"{template_name}.yaml"
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        with open(template_path, "r", encoding="utf-8") as f:
            template_data = yaml.safe_load(f)

        sections = [SectionSpec(**s) for s in template_data["sections"]]
        self._template_cache[template_name] = sections

        logger.info(f"Loaded template: {template_name} with {len(sections)} sections")
        return sections

    def generate_section(
        self,
        spec: SectionSpec,
        context: dict[str, Any],
        evidence: list[dict[str, Any]] | None = None,
    ) -> SectionOutput:
        """生成单个段落"""
        logger.info(f"Generating section: {spec.key} - {spec.title}")

        prompt = self._build_prompt(spec, context, evidence)

        try:
            response = self.model_gateway.chat(
                messages=[{"role": "user", "content": prompt}],
                model="default",
                temperature=0.7,
            )

            content = response.content.strip()
            evidence_refs = self._extract_evidence_refs(content)

            output = SectionOutput(
                key=spec.key,
                content=content,
                evidence_refs=evidence_refs,
                scenario_refs=[],
                warnings=[],
            )

            logger.info(f"Successfully generated section: {spec.key}")
            return output

        except Exception as e:
            logger.error(f"Failed to generate section {spec.key}: {e}", exc_info=True)
            return SectionOutput(
                key=spec.key,
                content=f"[生成失败: {e}]",
                evidence_refs=[],
                scenario_refs=[],
                warnings=[str(e)],
            )

    def generate_report(
        self,
        template_name: str,
        context: dict[str, Any],
        evidence: dict[str, list[dict[str, Any]]] | None = None,
    ) -> list[SectionOutput]:
        """生成完整报告"""
        sections = self.load_template(template_name)
        evidence = evidence or {}

        outputs = []
        for spec in sections:
            section_evidence = evidence.get(spec.key, [])
            output = self.generate_section(spec, context, section_evidence)
            outputs.append(output)

        return outputs

    def _build_prompt(
        self,
        spec: SectionSpec,
        context: dict[str, Any],
        evidence: list[dict[str, Any]] | None,
    ) -> str:
        """构建生成提示词"""
        prompt_parts = [
            f"# 段落：{spec.title}",
            f"请生成约 {spec.target_words} 字的内容。",
        ]

        if spec.required_facets:
            prompt_parts.append(f"\n需要覆盖的方面：{', '.join(spec.required_facets)}")

        if context:
            prompt_parts.append("\n## 上下文信息：")
            for key, value in context.items():
                prompt_parts.append(f"- {key}: {value}")

        if evidence:
            prompt_parts.append("\n## 参考证据：")
            for idx, ev in enumerate(evidence, 1):
                source = ev.get("source", "unknown")
                content = ev.get("content", "")[:200]
                prompt_parts.append(f"[{idx}] {source}: {content}")

        prompt_parts.append("\n## 输出要求：")
        prompt_parts.append("- 内容准确，基于提供的证据")
        prompt_parts.append("- 语言专业，逻辑清晰")
        prompt_parts.append("- 引用证据时使用 [1], [2] 这样的标记")

        if spec.evidence_policy == "strict":
            prompt_parts.append("- 仅限使用提供的证据，不得编造")

        return "\n".join(prompt_parts)

    def _extract_evidence_refs(self, content: str) -> list[str]:
        """从内容中提取证据引用"""
        import re

        refs = re.findall(r"\[(\d+)\]", content)
        return refs
