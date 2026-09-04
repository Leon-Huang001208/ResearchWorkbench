"""
通用文档模型契约 - Document / Section / DesignTokens.

定义 Research Workbench 报告框架的顶层文档结构。Document 是任何内容结构
的统一容器，由 Section 组成，Section 由 ContentBlock 组成，
ContentBlock 由 ContentElement 组成。

DesignTokens 提供文档级视觉配置（色彩/字体/间距），所有格式共享。
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from core.contracts.content_element import ContentBlock

# ============================================================================
# 设计令牌
# ============================================================================


class DesignTokens(BaseModel):
    """文档级设计令牌 - 所有输出格式共享的视觉配置.

    设计令牌在 Document 级别定义，由各格式渲染器消费。
    格式特定的差异（如 PPT 需要更大的字号）由渲染器内部的
    style_mapper 处理，而非修改令牌本身。

    Attributes:
        primary_color: 主色（hex）.
        secondary_color: 辅色（hex）.
        accent_color: 强调色（hex）.
        text_color: 正文文字色（hex）.
        muted_text_color: 次要文字色（hex）.
        border_color: 边框色（hex）.
        background_color: 背景色（hex）.
        callout_colors: 提示框背景色映射（callout_type → hex）.
        chart_palette: 图表调色板（hex 列表）.
        heading_font: 标题字体.
        body_font: 正文字体.
        code_font: 代码字体.
        heading_sizes: 标题级别 → 字号（pt）映射.
        body_size: 正文基准字号（pt）.
        small_size: 小字字号（pt）.
        body_line_spacing: 正文行距倍数.
        paragraph_spacing_after: 段落间距（pt）.
        ppt_slide_width: PPT 幻灯片宽度（英寸，默认 16:9）.
        ppt_slide_height: PPT 幻灯片高度（英寸）.
    """

    # ── 色彩 ──
    primary_color: str = Field(default="#1A365D", description="主色（hex）")
    secondary_color: str = Field(default="#2B6CB0", description="辅色（hex）")
    accent_color: str = Field(default="#E53E3E", description="强调色（hex）")
    text_color: str = Field(default="#1A202C", description="正文文字色（hex）")
    muted_text_color: str = Field(default="#718096", description="次要文字色（hex）")
    border_color: str = Field(default="#CBD5E0", description="边框色（hex）")
    background_color: str = Field(default="#FFFFFF", description="背景色（hex）")

    callout_colors: Dict[str, str] = Field(
        default_factory=lambda: {
            "info": "#E8F4FD",
            "warning": "#FFF4CE",
            "tip": "#E8F5E9",
            "key_finding": "#F3E5F5",
        },
        description="提示框背景色映射",
    )

    chart_palette: List[str] = Field(
        default_factory=lambda: [
            "#1A365D",
            "#2B6CB0",
            "#3182CE",
            "#63B3ED",
            "#E53E3E",
            "#DD6B20",
            "#38A169",
            "#805AD5",
        ],
        description="图表调色板",
    )

    # ── 字体 ──
    heading_font: str = Field(default="Microsoft YaHei", description="标题字体")
    body_font: str = Field(default="Microsoft YaHei", description="正文字体")
    code_font: str = Field(default="Consolas", description="代码字体")

    # ── 字号 ──
    heading_sizes: Dict[int, int] = Field(
        default_factory=lambda: {1: 28, 2: 22, 3: 16, 4: 14, 5: 12, 6: 11},
        description="标题级别 → 字号（pt）",
    )
    body_size: int = Field(default=11, description="正文基准字号（pt）")
    small_size: int = Field(default=9, description="小字字号（pt）")

    # ── 间距 ──
    body_line_spacing: float = Field(default=1.5, description="正文行距倍数")
    paragraph_spacing_after: int = Field(default=6, description="段落间距（pt）")

    # ── PPT 画布 ──
    ppt_slide_width: float = Field(default=13.333, description="PPT 幻灯片宽度（英寸）")
    ppt_slide_height: float = Field(default=7.5, description="PPT 幻灯片高度（英寸）")
    ppt_template_path: Optional[str] = Field(default=None, description="自定义 PPT 模板文件路径（.pptx）")
    ppt_transition: Optional[str] = Field(default=None, description="幻灯片过渡效果（none/fade/push/cut）")


# ============================================================================
# 预设令牌集
# ============================================================================


def report_tokens() -> DesignTokens:
    """研报风格令牌 - 适合正式研究报告."""
    return DesignTokens(
        primary_color="#1A365D",
        heading_font="SimHei",
        body_font="SimSun",
        body_size=12,
    )


def presentation_tokens() -> DesignTokens:
    """演示文稿令牌 - 适合 PPT 演示."""
    return DesignTokens(
        primary_color="#2B579A",
        heading_sizes={1: 36, 2: 28, 3: 22, 4: 18, 5: 14, 6: 12},
        body_size=14,
        body_line_spacing=1.3,
    )


def brief_tokens() -> DesignTokens:
    """简报令牌 - 适合快速阅读的短报告."""
    return DesignTokens(
        primary_color="#0078D4",
        heading_sizes={1: 24, 2: 18, 3: 14, 4: 12, 5: 11, 6: 10},
        body_size=10,
        body_line_spacing=1.3,
    )


# ============================================================================
# Section
# ============================================================================


class Section(BaseModel):
    """文档章节 - 由有序内容元素组成的结构单元.

    每个 Section 代表文档的一个逻辑章节。在 Word 中映射为带有标题的
    连续页面区域，在 PPT 中映射为一个或多个幻灯片。

    Attributes:
        section_id: 章节唯一 ID.
        title: 章节标题.
        blocks: 内容块列表（有序）.
        page_break_before: 是否在此 section 前分页.
        speaker_notes: PPT 演讲者备注（仅在 PPT 中渲染）.
        slide_layout: PPT 幻灯片布局提示（如 "TITLE_AND_CONTENT"）.
        metadata: 附加元数据.
    """

    section_id: str = Field(description="章节唯一 ID")
    title: str = Field(description="章节标题")
    blocks: List[ContentBlock] = Field(default_factory=list, description="内容块列表")
    page_break_before: bool = Field(default=False, description="是否在此前分页")
    speaker_notes: Optional[str] = Field(default=None, description="PPT 演讲者备注")
    slide_layout: Optional[str] = Field(default=None, description="PPT 幻灯片布局提示")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="附加元数据")


# ============================================================================
# Document
# ============================================================================


class Document(BaseModel):
    """顶层文档模型 - 任何内容结构的统一容器.

    Document 是通用报告框架的枢纽：上游流水线（模板驱动/深度研究/
    项目驱动）产出 Document，下游渲染器（Word/PPT/Markdown/HTML）
    消费 Document。

    每个 Document 自包含其视觉配置（design_tokens），
    因此同一个 Document 可以被不同格式渲染器消费，产生风格一致的输出。

    Attributes:
        document_id: 文档唯一 ID.
        title: 文档标题.
        subtitle: 副标题.
        sections: 章节列表（有序）.
        design_tokens: 设计令牌（文档级视觉配置）.
        metadata: 文档元数据（作者/日期/标签等）.
        version: 文档模型版本.
    """

    document_id: str = Field(default="", description="文档唯一 ID")
    title: str = Field(description="文档标题")
    subtitle: Optional[str] = Field(default=None, description="副标题")
    sections: List[Section] = Field(default_factory=list, description="章节列表（有序）")
    design_tokens: DesignTokens = Field(default_factory=DesignTokens, description="设计令牌")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="文档元数据")
    version: str = Field(default="1.0", description="文档模型版本")


# ============================================================================
# 模板槽位
# ============================================================================


class TemplateSlot(BaseModel):
    """模板结构槽位 - 文档模板中的内容插入点.

    替代旧的平面占位符（{{placeholder}}）系统，提供结构级绑定：
    每个槽位声明它接受什么类型的内容元素，渲染器据此将
    ContentElement 分配到正确的模板位置。

    Attributes:
        slot_id: 槽位唯一 ID.
        slot_type: 接受的元素类型.
        placeholder_pattern: 模板中的占位符标记（如 "{{text_market_summary}}"）.
        constraints: 附加约束（如 max_chars, allowed_element_types）.
    """

    slot_id: str = Field(description="槽位唯一 ID")
    slot_type: Literal["text", "table", "chart", "image", "section"] = Field(description="接受的元素类型")
    placeholder_pattern: str = Field(default="", description="模板中的占位符标记")
    constraints: Dict[str, Any] = Field(default_factory=dict, description="附加约束")
