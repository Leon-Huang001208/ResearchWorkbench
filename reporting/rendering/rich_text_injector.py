"""富文本注入器 — 将 RichTextSpec + 生成内容注入到 Word 模板段落中.

替代扁平的 {{placeholder}} → str 替换，支持多 Run 段落生成。
每个 Run 可以是静态的（固定标签，如加粗的 "A股方面："）或动态的（LLM 生成内容）。

核心场景：
    模板段落中有 {{event_review}} 占位符，
    配置定义了 RichTextSpec：
        runs:
          - text: "A股方面："  bold: true    # 静态标签
          - is_dynamic: true                # LLM 填充的正文
    注入后段落包含两个 Run：加粗标签 + 普通正文。
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from core.contracts.reporting import InlineRunSpec, RichTextSpec
from core.observability import get_logger

logger = get_logger(__name__)

# XML 1.0 / OOXML 非法字符（C0+C1 控制字符 + 代理对 + 非字符）
_XML_INVALID_CONTROL = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F\uD800-\uDFFF￾￿]")

if TYPE_CHECKING:
    from docx.text.paragraph import Paragraph

try:
    from docx.shared import Pt, RGBColor

    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False


class RichTextInjector:
    """将 RichTextSpec 和生成内容注入 Word 段落.

    支持两种模式：
    1. runs 为空 → 纯文本替换（继承模板段落全部样式）
    2. runs 非空 → 按 spec 生成多 Run 段落
    """

    def inject(
        self,
        paragraph: "Paragraph",
        placeholder_key: str,
        spec: RichTextSpec,
        generated_text: str,
        *,
        preserve_paragraph_style: bool = True,
    ) -> None:
        """替换段落中的占位符为富文本内容.

        Args:
            paragraph: 模板中包含占位符的段落.
            placeholder_key: 占位符 key（用于日志）.
            spec: 富文本规格.
            generated_text: LLM 或数据驱动生成的文本内容.
            preserve_paragraph_style: 是否保留模板段落的段落级样式.
        """
        if not DOCX_AVAILABLE:
            logger.warning("python-docx 不可用，RichTextInjector 无法工作")
            return

        # 保存段落级样式（对齐、间距、行距等）
        para_alignment = paragraph.alignment

        # 清除占位符（找到包含占位符的 Run 并清除）
        self._clear_placeholder_runs(paragraph, placeholder_key)

        if not spec.runs:
            # 简单模式：无 Run spec，直接填入纯文本
            self._inject_simple_text(paragraph, generated_text, spec)
        else:
            # 富文本模式：按 spec.runs 顺序生成多 Run
            self._inject_rich_runs(paragraph, spec, generated_text, placeholder_key)

        # 恢复段落级样式
        if preserve_paragraph_style:
            paragraph.alignment = para_alignment

        self._remove_empty_runs(paragraph)
        logger.info(
            "RichTextInjector: 注入完成",
            extra={"placeholder": placeholder_key, "run_count": len(spec.runs)},
        )

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _clear_placeholder_runs(self, paragraph: "Paragraph", placeholder_key: str) -> None:
        """清除段落中包含占位符的 Run.

        查找包含 {{placeholder_key}} 或 {placeholder_key} 的 Run，
        清除其文本内容，保留 Run 元素以便后续填充。
        """
        patterns = [f"{{{{{placeholder_key}}}}}", f"{{{placeholder_key}}}"]
        full_text = paragraph.text

        for run in paragraph.runs:
            for pattern in patterns:
                if pattern in (run.text or ""):
                    run.text = ""
                    break

        # 如果整个段落文本就是占位符，清除所有 Run
        if full_text.strip() in patterns:
            for run in paragraph.runs:
                run.text = ""

    def _inject_simple_text(
        self,
        paragraph: "Paragraph",
        generated_text: str,
        spec: RichTextSpec,
    ) -> None:
        """简单模式：将生成文本作为单个 Run 注入.

        继承模板中第一个 Run 的格式属性。
        """
        # 清除现有 Run，保留第一个用于填充
        for run in paragraph.runs[1:]:
            run._element.getparent().remove(run._element)

        if paragraph.runs:
            paragraph.runs[0].text = _XML_INVALID_CONTROL.sub("", generated_text)
        else:
            new_run = paragraph.add_run(_XML_INVALID_CONTROL.sub("", generated_text))
            if spec.default_font:
                new_run.font.name = spec.default_font
            if spec.default_size_pt:
                new_run.font.size = Pt(spec.default_size_pt)

    def _inject_rich_runs(
        self,
        paragraph: "Paragraph",
        spec: RichTextSpec,
        generated_text: str,
        placeholder_key: str,
    ) -> None:
        """富文本模式：按 spec.runs 顺序创建多个带格式的 Run.

        对每个 InlineRunSpec：
        - 静态 Run：使用 spec.text 作为内容
        - 动态 Run：使用 generated_text 作为内容
        所有 Run 按 spec 中的顺序依次添加到段落中。
        """
        # 清除段落中所有现有 Run
        for run in list(paragraph.runs):
            run._element.getparent().remove(run._element)

        for idx, run_spec in enumerate(spec.runs):
            text = self._resolve_run_text(run_spec, generated_text, placeholder_key)
            if not text:
                continue

            new_run = paragraph.add_run(_XML_INVALID_CONTROL.sub("", text))
            self._apply_run_formatting(new_run, run_spec, spec)

        # 如果所有 runs 都为空，至少保留一个空 Run 避免 Word 报错
        if not paragraph.runs:
            paragraph.add_run("")

    def _resolve_run_text(
        self,
        run_spec: InlineRunSpec,
        generated_text: str,
        placeholder_key: str,
    ) -> str:
        """解析 Run 的文本内容.

        Args:
            run_spec: Run 规格.
            generated_text: LLM 生成的文本（用于动态 Run）.
            placeholder_key: 占位符 key（用于日志）.

        Returns:
            解析后的文本.
        """
        if run_spec.is_dynamic:
            if not generated_text:
                logger.warning(
                    "动态 Run 无生成内容",
                    extra={"placeholder": placeholder_key},
                )
                return ""
            return generated_text
        else:
            return run_spec.text or ""

    def _apply_run_formatting(
        self,
        run: Any,
        run_spec: InlineRunSpec,
        spec: RichTextSpec,
    ) -> None:
        """应用 Run 级别的格式属性.

        Args:
            run: python-docx Run 对象.
            run_spec: Run 规格.
            spec: 父级 RichTextSpec（提供默认值）.
        """
        # bold
        if run_spec.bold is not None:
            run.bold = run_spec.bold

        # italic
        if run_spec.italic is not None:
            run.italic = run_spec.italic

        # font name
        font_name = run_spec.font_name or (spec.default_font if run_spec.is_dynamic else None)
        if font_name:
            run.font.name = font_name

        # font size
        font_size = run_spec.font_size_pt or (spec.default_size_pt if run_spec.is_dynamic else None)
        if font_size:
            run.font.size = Pt(font_size)

        # color
        if run_spec.color_hex:
            try:
                hex_str = run_spec.color_hex.lstrip("#")
                r, g, b = int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
                run.font.color.rgb = RGBColor(r, g, b)
            except (ValueError, IndexError):
                logger.warning("无效的颜色值", extra={"color": run_spec.color_hex})

    @staticmethod
    def _remove_empty_runs(paragraph: "Paragraph") -> None:
        """移除空 <w:r> 元素，兼容 WPS Office."""
        runs_to_remove = []
        for run in paragraph.runs:
            text = run.text
            if not text or not text.strip():
                runs_to_remove.append(run)
        for run in runs_to_remove:
            run._element.getparent().remove(run._element)
