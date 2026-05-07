#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据处理器模块

提供不同文档类型的专用处理器。
"""

from .base import BaseProcessor, DOC_TYPE_NAMES, _clean_html
from .news_processor import NewsProcessor, _get_allowed_open_names, _is_allowed_open_name
from .report_processor import ReportProcessor, _is_valid_core, _is_valid_companies, _parse_companies
from .meeting_processor import MeetingProcessor

__all__ = [
    'BaseProcessor',
    'DOC_TYPE_NAMES',
    '_clean_html',
    'NewsProcessor',
    '_get_allowed_open_names',
    '_is_allowed_open_name',
    'ReportProcessor',
    '_is_valid_core',
    '_is_valid_companies',
    '_parse_companies',
    'MeetingProcessor',
]
