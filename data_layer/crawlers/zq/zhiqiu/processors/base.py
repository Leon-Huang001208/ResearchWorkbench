#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
处理器基类模块

定义了数据处理的统一接口，不同文档类型的处理器继承自此类。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


class BaseProcessor(ABC):
    """
    数据处理器基类

    所有文档类型的处理器都应继承此类并实现抽象方法。
    """

    def __init__(self, client):
        """
        初始化处理器

        Args:
            client: ZhiQiuClient 实例
        """
        self.client = client

    @abstractmethod
    def process(
        self, data: Dict[str, Any], output_file: str, **kwargs
    ) -> Tuple[pd.DataFrame, List[Dict], int]:
        """
        处理数据并保存结果

        Args:
            data: 原始 JSON 数据
            output_file: 输出 JSON 文件路径
            **kwargs: 其他处理参数

        Returns:
            (DataFrame, new_reports_list, skipped_count)
        """
        pass

    @abstractmethod
    def build_item(self, report: Dict[str, Any], **kwargs) -> Optional[Dict[str, Any]]:
        """
        从原始数据构建单个条目

        Args:
            report: 单条原始数据
            **kwargs: 其他构建参数

        Returns:
            构建后的条目字典
        """
        pass


def _clean_html(text: str) -> str:
    """
    移除 HTML 标签（工具函数）

    Args:
        text: 包含 HTML 标签的文本

    Returns:
        清理后的纯文本
    """
    import re

    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text)


# 文档类型名称映射（通用）
DOC_TYPE_NAMES = {
    "NEWS": "公众号",
    "REPORT": "研报",
    "ZQMEETING": "纪要",
    "INVESTOR": "问答",
    "CJAUTONEWS": "新闻",
    "CJCAST": "快讯",
    "IMPNEWS": "重要舆情",
    "EVENTNODENEWS": "产业事件",
}
