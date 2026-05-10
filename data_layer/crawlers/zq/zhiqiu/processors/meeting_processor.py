#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
纪要数据处理器

专门处理 ZQMEETING 类型文档。
"""

import json
import os
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from ..utils import parse_timestamp
from .base import BaseProcessor, _clean_html


class MeetingProcessor(BaseProcessor):
    """
    纪要数据处理器

    专门处理 ZQMEETING 类型文档。
    """

    def __init__(self, client):
        """
        初始化纪要处理器

        Args:
            client: ZhiQiuClient 实例
        """
        super().__init__(client)

    def process(
        self,
        data: Dict[str, Any],
        output_file: str,
        state_manager: Optional[Any] = None,
        skip_existing: bool = True,
        **kwargs,
    ) -> Tuple[pd.DataFrame, List[Dict], int]:
        """
        处理纪要数据

        Args:
            data: 原始 JSON 数据
            output_file: 输出 JSON 文件路径
            state_manager: 状态管理器（可选，用于去重）
            skip_existing: 是否跳过已存在的条目

        Returns:
            (DataFrame, new_meetings_list, skipped_count)
        """
        reports_list = data.get("reports", [])
        if isinstance(reports_list, dict):
            inner_reports = reports_list.get("reports", [])
            if isinstance(inner_reports, list):
                reports_list = inner_reports

        results = []
        new_meetings = []
        skipped_count = 0

        for report in reports_list:
            doc_type = report.get("docType", "") or report.get("type", "")

            if doc_type != "ZQMEETING":
                continue

            obj_id = report.get("id") or report.get("objId")
            if state_manager and skip_existing and obj_id:
                if state_manager.is_report_processed(str(obj_id)):
                    skipped_count += 1
                    continue

            item = self.build_item(report)
            if item:
                results.append(item)
                new_meetings.append(item)

        if output_file:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

        self.client.logger.info(f"已处理 {len(results)} 条纪要（跳过 {skipped_count} 条），保存至 {output_file}")
        return pd.DataFrame(results), new_meetings, skipped_count

    def build_item(self, report: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        构建纪要条目

        Args:
            report: 原始数据

        Returns:
            纪要条目字典
        """
        obj_id = report.get("id") or report.get("objId")
        if not obj_id:
            return None

        internal_url = (
            f"https://www.kanzhiqiu.com/newweb/zqsite/#/intelligentMeetingDetail?id={obj_id}"
        )

        date_str = parse_timestamp(report)

        # 获取纪要详情内容
        detail_data = self.client.get_meeting_detail(str(obj_id))
        if not detail_data or detail_data.get("ret") != 1:
            return None

        data = detail_data.get("data", {})
        meeting = data.get("meeting", {})

        result = {
            "OBJID": str(obj_id),
            "docType": "ZQMEETING",
            "docTypeName": "纪要",
            "title": _clean_html(report.get("title", "")),
            "summary": _clean_html(meeting.get("summary", "")),
            "qa": _clean_html(meeting.get("qa", "")),
            "argument": _clean_html(meeting.get("argument", "")),
            "extraQa": _clean_html(meeting.get("extraQa", "")),
            "stockName": meeting.get("stockName", ""),
            "stockCode": meeting.get("stockCode", ""),
            "url": internal_url,
            "date": date_str,
        }

        return result
