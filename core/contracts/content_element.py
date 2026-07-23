"""
通用内容元素契约 - 格式无关的可组合内容元素类型层级.

定义 AlphaFoundry 报告框架的核心内容抽象层。所有内容结构（报告、PPT、
简报等）都由这些基础元素组合而成，通过统一的 Document 模型描述，
并由各格式渲染器（Word/PPT/Markdown/HTML）消费。

设计原则：
- 内容与格式分离：ContentElement 不含任何格式特定的样式信息
- 富文本支持：通过 TextRun 序列支持内联样式（粗体/斜体/颜色/超链接）
- 可组合性：ContentBlock → ContentElement → TextRun 的层级结构
- 向后兼容：旧 SectionOutput.content: str 通过适配器映射到 ParagraphElement
"""

from enum import Enum
from typing import List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

# ============================================================================
# 基础枚举
# ============================================================================


class ContentElementType(str, Enum):
    """通用内容元素类型枚举."""

    PARAGRAPH = "paragraph"
    HEADING = "heading"
    BULLET_LIST = "bullet_list"
    ORDERED_LIST = "ordered_list"
    TABLE = "table"
    CHART = "chart"
    IMAGE = "image"
    QUOTE = "quote"
    CALLOUT = "callout"
    KEY_VALUE = "key_value"  # 键值对 / 指标卡
    DIVIDER = "divider"
    SPEAKER_NOTES = "speaker_notes"


class CalloutType(str, Enum):
    """高亮提示框类型."""

    INFO = "info"
    WARNING = "warning"
    TIP = "tip"
    KEY_FINDING = "key_finding"


class HorizontalAlignment(str, Enum):
    """水平对齐."""

    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class ChartElementType(str, Enum):
    """图表类型."""

    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    SCATTER = "scatter"
    AREA = "area"


# ============================================================================
# 内联文本元素
# ============================================================================


class TextRun(BaseModel):
    """富文本片段 - 带样式的文本运行单元.

    映射到 OpenXML 中的 <w:r>（Word）或 <a:r>（PPT）元素。
    所有样式字段均为可选，默认值表示继承文档级样式。

    Attributes:
        text: 文本内容.
        bold: 是否加粗.
        italic: 是否斜体.
        underline: 是否下划线.
        color: 文字颜色（hex 格式，如 "#1A365D"）.
        size: 字号（pt），如 11 表示 11pt.
        font: 字体名称.
        hyperlink: 超链接 URL.
        citation_id: 引用 ID（指向 Citation.fact_ids）.
    """

    text: str = Field(description="文本内容")
    bold: bool = Field(default=False, description="是否加粗")
    italic: bool = Field(default=False, description="是否斜体")
    underline: bool = Field(default=False, description="是否下划线")
    color: Optional[str] = Field(default=None, description="文字颜色（hex）")
    size: Optional[int] = Field(default=None, description="字号（pt）")
    font: Optional[str] = Field(default=None, description="字体名称")
    hyperlink: Optional[str] = Field(default=None, description="超链接 URL")
    citation_id: Optional[str] = Field(default=None, description="引用 ID")

    @classmethod
    def plain(cls, text: str) -> "TextRun":
        """创建无样式的纯文本 TextRun."""
        return cls(text=text)


# ============================================================================
# 内容元素基类
# ============================================================================


class ContentElement(BaseModel):
    """内容元素基类 - 所有内容元素的公共属性.

    使用 discriminated union 模式：子类通过 element_type 字段
    区分类型，渲染器通过 element_type 分发到对应处理方法。

    Attributes:
        element_id: 元素唯一 ID.
        element_type: 元素类型（判别字段）.
        visible: 是否可见（支持条件渲染）.
    """

    element_id: str = Field(default="", description="元素唯一 ID")
    element_type: ContentElementType = Field(description="元素类型（判别字段）")
    visible: bool = Field(default=True, description="是否可见")


# ============================================================================
# 文本类元素
# ============================================================================


class ParagraphElement(ContentElement):
    """段落元素 - 由富文本 run 序列组成的段落.

    对应 Word 中的 <w:p> 或 PPT 中的 <a:p>。
    每个 run 可独立设置样式，实现段落内的混合格式。

    Attributes:
        runs: 文本运行序列.
        alignment: 水平对齐方式.
        line_spacing: 行距倍数（1.0 = 单倍，1.5 = 1.5 倍，2.0 = 双倍）.
    """

    element_type: Literal[ContentElementType.PARAGRAPH] = ContentElementType.PARAGRAPH
    runs: List[TextRun] = Field(default_factory=list, description="文本运行序列")
    alignment: HorizontalAlignment = Field(default=HorizontalAlignment.LEFT, description="水平对齐")
    line_spacing: float = Field(default=1.5, description="行距倍数")

    @classmethod
    def plain(cls, text: str, element_id: str = "") -> "ParagraphElement":
        """创建纯文本段落（无样式）."""
        return cls(element_id=element_id, runs=[TextRun.plain(text)])


class HeadingElement(ContentElement):
    """标题元素 - 文档/章节/小节标题.

    映射到 Word 的 Heading 1-6 样式或 PPT 的标题占位符。

    Attributes:
        level: 标题级别（1-6）.
        text: 标题文本（纯文本，不支持富文本 run）.
    """

    element_type: Literal[ContentElementType.HEADING] = ContentElementType.HEADING
    level: int = Field(default=2, ge=1, le=6, description="标题级别 1-6")
    text: str = Field(description="标题文本")


# ============================================================================
# 列表类元素
# ============================================================================


class ListItem(BaseModel):
    """列表项 - 支持嵌套子列表.

    Attributes:
        runs: 列表项文本（富文本）.
        sub_items: 子列表项（用于嵌套列表）.
    """

    runs: List[TextRun] = Field(default_factory=list, description="列表项文本（富文本）")
    sub_items: List["ListItem"] = Field(default_factory=list, description="子列表项")

    @classmethod
    def plain(cls, text: str) -> "ListItem":
        """创建纯文本列表项."""
        return cls(runs=[TextRun.plain(text)])


class BulletListElement(ContentElement):
    """无序列表元素 - 带项目符号的列表.

    Attributes:
        items: 列表项序列.
    """

    element_type: Literal[ContentElementType.BULLET_LIST] = ContentElementType.BULLET_LIST
    items: List[ListItem] = Field(default_factory=list, description="列表项")


class OrderedListElement(ContentElement):
    """有序列表元素 - 带编号的列表.

    Attributes:
        items: 列表项序列.
        start: 起始编号.
    """

    element_type: Literal[ContentElementType.ORDERED_LIST] = ContentElementType.ORDERED_LIST
    items: List[ListItem] = Field(default_factory=list, description="列表项")
    start: int = Field(default=1, description="起始编号")


# ============================================================================
# 数据类元素
# ============================================================================


class TableElement(ContentElement):
    """表格元素 - 结构化数据表.

    每行每列包含富文本内容，支持列宽控制。

    Attributes:
        headers: 表头行（富文本列）.
        rows: 数据行（rows[行][列] 为富文本 run 列表）.
        col_widths: 相对列宽比例（如 [2.0, 1.0, 1.0]）.
        title: 可选的表格标题.
        style: 表格样式（bordered / minimal / striped）.
    """

    element_type: Literal[ContentElementType.TABLE] = ContentElementType.TABLE
    headers: List[List[TextRun]] = Field(default_factory=list, description="表头行")
    rows: List[List[List[TextRun]]] = Field(
        default_factory=list, description="数据行（行→列→富文本）"
    )
    col_widths: Optional[List[float]] = Field(default=None, description="相对列宽比例")
    title: Optional[str] = Field(default=None, description="表格标题")
    style: Literal["bordered", "minimal", "striped"] = Field(
        default="bordered", description="表格样式"
    )


class ChartElement(ContentElement):
    """图表元素 - 数据可视化图表.

    支持两种数据传递方式：
    1. data_series（结构化数据）→ 渲染时由渲染器生成图表
    2. image_bytes（已渲染的图片）→ 直接嵌入，适用于 Excel 生成的图表

    Attributes:
        chart_id: 图表唯一 ID.
        chart_type: 图表类型（line/bar/pie/scatter/area）.
        title: 图表标题.
        data_labels: 数据标签（X 轴标签或系列名）.
        data_series: 数据系列（二维数组，每行一个系列）.
        source_note: 数据来源说明.
        width_inches: 图表宽度（英寸）.
        height_inches: 图表高度（英寸）.
        image_bytes: 预渲染的图表图片（可选，优先使用）.
    """

    element_type: Literal[ContentElementType.CHART] = ContentElementType.CHART
    chart_id: str = Field(description="图表唯一 ID")
    chart_type: ChartElementType = Field(default=ChartElementType.BAR, description="图表类型")
    title: str = Field(description="图表标题")
    data_labels: List[str] = Field(default_factory=list, description="数据标签")
    data_series: List[List[float]] = Field(default_factory=list, description="数据系列")
    source_note: Optional[str] = Field(default=None, description="数据来源说明")
    width_inches: float = Field(default=6.0, description="图表宽度（英寸）")
    height_inches: float = Field(default=3.5, description="图表高度（英寸）")
    image_bytes: Optional[bytes] = Field(default=None, description="预渲染的图表图片", exclude=True)


class ImageElement(ContentElement):
    """图片元素 - 嵌入的图片.

    Attributes:
        image_id: 图片唯一 ID.
        image_data: 图片二进制数据.
        alt_text: 替代文本（无障碍访问）.
        caption: 图片说明文字.
        width_inches: 显示宽度（英寸）.
        height_inches: 显示高度（英寸）.
    """

    element_type: Literal[ContentElementType.IMAGE] = ContentElementType.IMAGE
    image_id: str = Field(description="图片唯一 ID")
    image_data: bytes = Field(description="图片二进制数据", exclude=True)
    alt_text: str = Field(default="", description="替代文本")
    caption: Optional[str] = Field(default=None, description="图片说明文字")
    width_inches: float = Field(default=4.5, description="显示宽度（英寸）")
    height_inches: float = Field(default=3.0, description="显示高度（英寸）")


# ============================================================================
# 装饰/提示类元素
# ============================================================================


class QuoteElement(ContentElement):
    """引用块元素 - 引用/摘录文本.

    Attributes:
        text: 引用文本.
        attribution: 出处/署名.
    """

    element_type: Literal[ContentElementType.QUOTE] = ContentElementType.QUOTE
    text: str = Field(description="引用文本")
    attribution: Optional[str] = Field(default=None, description="出处/署名")


class CalloutElement(ContentElement):
    """高亮提示框元素 - 信息提示/警告/关键发现.

    在 Word 中渲染为带背景色的边框段落，
    在 PPT 中渲染为彩色文本框。

    Attributes:
        callout_type: 提示框类型（info/warning/tip/key_finding）.
        title: 提示框标题.
        text: 提示框内容.
    """

    element_type: Literal[ContentElementType.CALLOUT] = ContentElementType.CALLOUT
    callout_type: CalloutType = Field(default=CalloutType.INFO, description="提示框类型")
    title: Optional[str] = Field(default=None, description="提示框标题")
    text: str = Field(description="提示框内容")


class KeyValueElement(ContentElement):
    """键值对/指标卡元素 - KPI 展示.

    适合渲染为指标仪表盘（PPT）或小表格（Word）。

    Attributes:
        pairs: (标签, 值) 对列表.
        columns: 每行列数（PPT 中控制网格布局）.
    """

    element_type: Literal[ContentElementType.KEY_VALUE] = ContentElementType.KEY_VALUE
    pairs: List[Tuple[str, str]] = Field(default_factory=list, description="(标签, 值) 对")
    columns: int = Field(default=2, description="每行列数")


class DividerElement(ContentElement):
    """分隔线元素 - 视觉分段线.

    Word 中为水平线，PPT 中为分隔形状。
    """

    element_type: Literal[ContentElementType.DIVIDER] = ContentElementType.DIVIDER


# ============================================================================
# PPT 专用元素
# ============================================================================


class SpeakerNotesElement(ContentElement):
    """演讲者备注元素 - PPT 演讲者备注.

    仅在 PPT 格式中渲染为 slide notes，
    在 Word/Markdown 中忽略。

    Attributes:
        text: 备注文本.
    """

    element_type: Literal[ContentElementType.SPEAKER_NOTES] = ContentElementType.SPEAKER_NOTES
    text: str = Field(description="备注文本")


# ============================================================================
# 内容块容器
# ============================================================================


class ContentBlock(BaseModel):
    """内容块 - section 内的元素容器.

    一个 section 可包含多个 block，每个 block 有自己的布局提示。
    block 之间可插入分页符。

    Attributes:
        block_id: 块唯一 ID.
        elements: 内容元素列表（有序）.
        layout_hint: 布局提示（控制列数）.
        page_break_before: 是否在此 block 前分页.
    """

    block_id: str = Field(description="块唯一 ID")
    elements: List[ContentElement] = Field(default_factory=list, description="内容元素列表（有序）")
    layout_hint: Literal["full", "two_col", "three_col"] = Field(
        default="full", description="布局提示（控制列数）"
    )
    page_break_before: bool = Field(default=False, description="是否在此之前分页")


# Rebuild forward references (ListItem → ListItem self-ref).
ListItem.model_rebuild()
