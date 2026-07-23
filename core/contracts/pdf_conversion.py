"""
PDF 转换契约 —— 统一的转换结果模型和策略相关枚举.

本模块定义了 PDF 转换管道的核心数据模型，包括策略类型、转换状态和统一的转换结果。
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class StrategyType(str, Enum):
    """PDF 转换策略类型"""

    AUTO = "auto"
    MARKITDOWN = "markitdown"
    MINERU = "mineru"
    RAW_TEXT = "raw_text"


class ConversionStatus(str, Enum):
    """PDF 转换状态"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    SKIPPED = "skipped"


class ConversionResult(BaseModel):
    """PDF 转换统一结果模型"""

    success: bool = Field(..., description="转换是否成功")
    strategy_used: str = Field(default="", description="使用的策略名称")
    error_message: str = Field(default="", description="错误信息（仅在失败时）")

    # 文本输出
    raw_text: str = Field(default="", description="提取的原始文本")
    markdown: str = Field(default="", description="转换后的 Markdown 内容")

    # 文件路径（外部存储时使用）
    raw_text_path: Optional[str] = Field(default=None, description="原始文本文件路径")
    markdown_path: Optional[str] = Field(default=None, description="Markdown 文件路径")

    # 转换统计
    page_count: int = Field(default=0, description="PDF 页数")
    token_count: int = Field(default=0, description="估算的 token 数量")

    # 质量指标
    quality_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="转换质量评分 0.0-1.0"
    )
    has_tables: bool = Field(default=False, description="是否检测到表格")
    has_images: bool = Field(default=False, description="是否检测到图片")
    has_code_blocks: bool = Field(default=False, description="是否检测到代码块")

    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict, description="策略特定的元数据")


class ConversionRequest(BaseModel):
    """PDF 转换请求"""

    pdf_id: str = Field(..., description="要转换的 PDF 制品 ID")
    strategy: StrategyType = Field(default=StrategyType.AUTO, description="使用的策略")


class ConversionStatusResponse(BaseModel):
    """转换状态响应"""

    conversion_id: str = Field(..., description="转换记录 ID")
    pdf_id: str = Field(..., description="关联的 PDF 制品 ID")
    status: ConversionStatus = Field(..., description="当前状态")
    strategy_used: Optional[str] = Field(default=None, description="使用的策略")
    page_count: Optional[int] = Field(default=None, description="PDF 页数")
    token_count: Optional[int] = Field(default=None, description="估算 token 数")
    quality_score: Optional[float] = Field(default=None, description="质量评分")
    error_log: Optional[str] = Field(default=None, description="错误日志")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")
