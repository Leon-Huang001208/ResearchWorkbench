#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
公众号数据处理器

专门处理 NEWS 类型（公众号）数据的模块。
"""

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from ..utils import extract_text_from_html, parse_timestamp
from .base import BaseProcessor, _clean_html

# 默认允许的公众号列表
DEFAULT_ALLOWED_OPEN_NAMES = [
    "中国证券报",
    "上海证券报",
    "ETF和LOF圈",
    "券商中国",
    "中国基金报",
    "第一财经",
    "经济观察报",
    "锦缎",
    "锦缎研究院",
    "中信证券研究",
    "广发证券研究",
    "韭圈儿",
    "木鱼ETF",
    "有连云",
    "财联社",
    "每日经济新闻",
    "冷眼局中人",
    "澎湃新闻评论",
    "21世纪经济报道",
    "华尔街见闻",
]


@lru_cache(maxsize=8)
def _get_allowed_open_names(custom_path: Optional[str] = None) -> Tuple[str, ...]:
    """
    获取允许的公众号列表（带缓存）

    查找优先级：
    1. custom_path（如果指定）
    2. 当前工作目录 ./allowed_accounts.json
    3. 用户配置目录 ~/.config/zq/allowed_accounts.json
    4. Skill 内置配置目录 {skill_dir}/config/allowed_accounts.json
    5. 默认列表

    Args:
        custom_path: 自定义配置文件路径

    Returns:
        允许的公众号名称元组（用于缓存）
    """
    search_paths = []

    # 1. 自定义路径优先
    if custom_path:
        search_paths.append(Path(custom_path))

    # 2. 当前工作目录
    search_paths.append(Path.cwd() / "allowed_accounts.json")

    # 3. 用户配置目录
    try:
        home = Path.home()
        search_paths.append(home / ".config" / "zq" / "allowed_accounts.json")
    except Exception:
        pass

    # 4. Skill 内置配置目录
    try:
        skill_dir = Path(__file__).parent.parent.parent.parent
        search_paths.append(skill_dir / "config" / "allowed_accounts.json")
    except Exception:
        pass

    # 依次尝试
    for config_path in search_paths:
        if config_path and config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    names = config.get("allowed_open_names", DEFAULT_ALLOWED_OPEN_NAMES)
                    return tuple(names)
            except Exception:
                continue

    # 5. 使用默认列表
    return tuple(DEFAULT_ALLOWED_OPEN_NAMES)


def _is_allowed_open_name(open_name: str, custom_path: Optional[str] = None) -> bool:
    """
    判断公众号是否在允许列表中

    Args:
        open_name: 公众号名称
        custom_path: 自定义配置文件路径

    Returns:
        是否在允许列表中
    """
    if not open_name:
        return False
    allowed = _get_allowed_open_names(custom_path)
    return open_name in allowed


class NewsProcessor(BaseProcessor):
    """
    公众号数据处理器

    专门处理 NEWS 类型文档，包括：
    - 公众号白名单验证
    - 文章内容获取
    - 数据保存
    """

    def __init__(self, client: Any, allowed_accounts_path: Optional[str] = None):
        """
        初始化公众号处理器

        Args:
            client: ZhiQiuClient 实例
            allowed_accounts_path: 公众号白名单配置文件路径（可选）
        """
        super().__init__(client)
        self.allowed_accounts_path = allowed_accounts_path
        # 初始化时就加载并缓存允许的公众号列表
        self._allowed_names: Optional[Tuple[str, ...]] = None
        self._allowed_path_cache: Optional[str] = None

    def _get_cached_allowed_names(self, custom_path: Optional[str]) -> Tuple[str, ...]:
        """
        获取缓存的允许公众号列表

        Args:
            custom_path: 自定义配置文件路径

        Returns:
            允许的公众号名称元组
        """
        if custom_path != self._allowed_path_cache or self._allowed_names is None:
            self._allowed_names = _get_allowed_open_names(custom_path)
            self._allowed_path_cache = custom_path
        return self._allowed_names

    def _is_allowed_cached(self, open_name: str, custom_path: Optional[str] = None) -> bool:
        """
        判断公众号是否在允许列表中（使用缓存）

        Args:
            open_name: 公众号名称
            custom_path: 自定义配置文件路径

        Returns:
            是否在允许列表中
        """
        if not open_name:
            return False
        allowed = self._get_cached_allowed_names(custom_path)
        return open_name in allowed

    def process(
        self,
        data: Dict[str, Any],
        output_file: str,
        state_manager: Optional[Any] = None,
        skip_existing: bool = True,
        stop_on_known: bool = True,
        watermark_key: Optional[str] = None,
        **kwargs,
    ) -> Tuple[pd.DataFrame, List[Dict], int, bool]:
        """
        处理公众号数据

        Args:
            data: 原始 JSON 数据
            output_file: 输出 JSON 文件路径
            state_manager: 状态管理器（可选，用于去重）
            skip_existing: 是否跳过已存在的条目
            stop_on_known: 遇到已处理记录时是否停止
            watermark_key: 水位线标识键
            **kwargs: 其他参数，可传入 allowed_accounts_path 覆盖初始化时的设置

        Returns:
            (DataFrame, new_reports_list, skipped_count, stopped_by_watermark)
        """
        # 从 kwargs 获取允许的账号路径，优先级高于初始化参数
        allowed_path = kwargs.get("allowed_accounts_path", self.allowed_accounts_path)

        # 判断数据格式
        reports_list = data.get("reports", [])
        if isinstance(reports_list, dict):
            # 旧格式或嵌套格式
            inner_reports = reports_list.get("reports", [])
            if isinstance(inner_reports, list):
                reports_list = inner_reports

        results = []
        new_reports = []
        skipped_count = 0
        stopped_by_watermark = False
        first_new_obj_id: Optional[str] = None

        for report in reports_list:
            doc_type = report.get("docType", "") or report.get("type", "")

            # 只处理 NEWS 类型
            if doc_type != "NEWS":
                continue

            # 检查是否已处理过（持久化去重）
            obj_id = report.get("id") or report.get("objId")
            if state_manager and skip_existing and obj_id:
                if state_manager.is_report_processed(str(obj_id)):
                    skipped_count += 1
                    if stop_on_known:
                        stopped_by_watermark = True
                        self.client.logger.info(f"[水位线] 遇到已知公众号文章 {obj_id}，停止抓取")
                        break
                    continue

            # 检查公众号是否在允许列表中
            open_name = report.get("openName", "")
            if not self._is_allowed_cached(open_name, allowed_path):
                self.client.logger.debug(f"跳过未允许的公众号: {open_name}")
                continue

            # 构建条目
            item = self.build_item(report)
            if item:
                results.append(item)
                new_reports.append(item)

                # 记录第一个新项目作为水位线
                if first_new_obj_id is None and obj_id:
                    first_new_obj_id = str(obj_id)

        # 设置水位线
        if state_manager and first_new_obj_id and watermark_key:
            state_manager.set_watermark(watermark_key, first_new_obj_id)
            self.client.logger.info(f"[水位线] 设置水位线为 {first_new_obj_id}")

        # 保存结果
        if output_file:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

        self.client.logger.info(
            f"已处理 {len(results)} 条公众号 (跳过 {skipped_count} 条)，保存至 {output_file}"
        )
        return pd.DataFrame(results), new_reports, skipped_count, stopped_by_watermark

    def build_item(self, report: Dict[str, Any], **kwargs) -> Optional[Dict[str, Any]]:
        """
        构建公众号条目

        Args:
            report: 原始数据
            **kwargs: 其他参数

        Returns:
            公众号条目字典
        """
        obj_id = report.get("id") or report.get("objId")
        if not obj_id:
            return None

        # 生成内部链接
        internal_url = f"https://www.kanzhiqiu.com/newsadapter/newcjnews/read_news.htm?id={obj_id}"
        external_url = report.get("url", "")

        # 获取文章内容
        content = self._fetch_news_content(internal_url, external_url)

        # 处理时间戳
        date_str = parse_timestamp(report)

        return {
            "OBJID": str(obj_id),
            "docType": "NEWS",
            "docTypeName": "公众号",
            "title": _clean_html(report.get("title", "")),
            "url": internal_url,
            "externalUrl": external_url,
            "content": content,
            "date": date_str,
            "openName": report.get("openName", ""),
        }

    def _fetch_news_content(self, internal_url: str, external_url: str) -> str:
        """
        获取公众号文章内容

        优先尝试从知丘内部链接获取，失败则尝试外部链接

        Args:
            internal_url: 知丘内部链接
            external_url: 原始外部链接

        Returns:
            文章内容文本
        """
        content = ""

        # 首先尝试从知丘内部链接获取
        try:
            self.client.anti_scrape.before_request(is_ai_request=False)
            headers = self.client.anti_scrape.get_headers(
                {"user-agent": self.client.USER_AGENT, "referer": f"{self.client.BASE_URL}/"}
            )
            resp = self.client.session.get(internal_url, headers=headers, timeout=30)
            self.client.anti_scrape.after_success()

            if resp.status_code == 200:
                content = self._extract_text_from_html(resp.text)
                if content and len(content.strip()) > 50:
                    return content
        except Exception as e:
            self.client.logger.debug(f"从内部链接获取内容失败: {e}")

        # 如果内部链接失败，尝试外部链接（通常是微信公众号链接）
        if external_url:
            try:
                self.client.anti_scrape.before_request(is_ai_request=False)
                headers = self.client.anti_scrape.get_headers(
                    {"user-agent": self.client.USER_AGENT}
                )
                resp = self.client.session.get(external_url, headers=headers, timeout=30)
                self.client.anti_scrape.after_success()

                if resp.status_code == 200:
                    content = self._extract_text_from_html(resp.text)
                    if content and len(content.strip()) > 50:
                        return content
            except Exception as e:
                self.client.logger.debug(f"从外部链接获取内容失败: {e}")

        return content or ""

    def _extract_text_from_html(self, html: str) -> str:
        """
        从 HTML 中提取纯文本内容（使用 utils 中的实现）

        Args:
            html: HTML 文本

        Returns:
            提取的纯文本
        """
        return extract_text_from_html(html)
