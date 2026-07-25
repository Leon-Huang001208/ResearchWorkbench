#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
news.py - 知丘公众号爬取模块

专门用于爬取公众号文章的独立模块。

使用方法：
    python news.py --config config.yaml --search 宏观经济
"""

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .zhiqiu.base_fetcher import BaseConfig, BaseFetcher, BaseStateManager
from .zhiqiu.processors.news_processor import NewsProcessor


@dataclass
class NewsConfig(BaseConfig):
    """
    公众号爬取配置

    专注于 NEWS 类型的配置，移除了 AI 和 PDF 相关的配置。
    """

    # 公众号特有配置
    allowed_accounts_path: Optional[str] = None

    # 重写基类的默认值
    use_homepage_search: bool = True
    date_limit: str = "CUSTOM"
    doc_type: str = "NEWS"
    module_name: str = "news"
    module_label: str = "公众号"
    processed_key: str = "processed_news"


class NewsStateManager(BaseStateManager):
    """
    公众号状态管理器 - 保持向后兼容
    """

    def __init__(self, state_path: str, verbose: bool = False):
        super().__init__(state_path, "processed_news", verbose)

    def add_processed_report(
        self, obj_id: str, title: str, open_name: str = "", **extra: Any
    ) -> None:
        open_name = open_name or str(extra.pop("openName", ""))
        super().add_processed_report(obj_id, title, openName=open_name, **extra)


class NewsFetcher(BaseFetcher):
    """
    知丘公众号爬取器

    专门爬取 NEWS 类型文档，支持：
    - 公众号白名单过滤
    - 文章内容获取
    - 持久化去重
    - 多账号轮询
    """

    def __init__(self, config: Optional[NewsConfig] = None):
        self.config = config or NewsConfig()
        super().__init__(self.config)

        # 重写 _state_manager 的类型（保持向后兼容）
        if self.config.state_path:
            try:
                self._state_manager = NewsStateManager(self.config.state_path, self.config.verbose)
                if self.config.verbose:
                    print(f"[init] 状态管理器已初始化，已记录 {self._state_manager.get_processed_count()} 篇文章")
            except Exception as e:
                if self.config.verbose:
                    print(f"[warn] 初始化状态管理器失败: {e}，持久化去重将不可用")

    def _save_processed_item(self, obj_id: str, title: str, item: Dict[str, Any]):
        if self._state_manager is None:
            return
        open_name = item.get("openName", "")
        self._state_manager.add_processed_report(obj_id, title, openName=open_name)

    def _fetch_single_term(self, search_term: str):
        if self._logger:
            self._logger.info(f"正在爬取公众号: {search_term if search_term else '全部'}")

        json_data = self._search_homepage(search_term, "title")

        if not json_data:
            return {
                "term": search_term if search_term else "全部",
                "status": "failed",
                "error": "获取数据失败",
                "count": 0,
                "skipped_existing": 0,
                "new": 0,
            }, []

        output_json = os.path.join(self.config.output_dir, f"news_{self.config.starttime}.json")
        os.makedirs(self.config.output_dir, exist_ok=True)

        processor = NewsProcessor(self._client, self.config.allowed_accounts_path)
        df, new_news, skipped_count, _ = processor.process(
            json_data,
            output_json,
            state_manager=self._state_manager,
            skip_existing=self.config.skip_existing,
        )

        return {
            "term": search_term if search_term else "全部",
            "status": "success",
            "count": len(df),
            "output_file": output_json,
            "skipped_existing": skipped_count,
            "new": len(new_news),
        }, new_news

    def fetch(self, **kwargs) -> Dict[str, Any]:
        result = super().fetch(**kwargs)
        if "total" in result:
            result["total_news"] = result.pop("total")
        if "new" in result:
            result["new_news"] = result.pop("new")
        return result


def parse_args():
    parser = argparse.ArgumentParser(
        description="知丘公众号爬取工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 基础爬取（昨天的公众号文章）
  python news.py --config config.yaml

  # 爬取指定关键词
  python news.py --config config.yaml --search 宏观经济,股市

  # 使用日期限制
  python news.py --config config.yaml --date-limit DATE_LIMIT_WEEK

  # 使用持久化去重
  python news.py --config config.yaml --state-path ./state/news_state.json

  # 指定公众号白名单配置文件
  python news.py --config config.yaml --allowed-accounts ./my_allowed_accounts.json

公众号白名单配置查找优先级：
  1. --allowed-accounts 参数指定的路径
  2. 当前工作目录 ./allowed_accounts.json
  3. 用户配置目录 ~/.config/zq/allowed_accounts.json
  4. Skill 内置配置 {skill_dir}/config/allowed_accounts.json
  5. 默认内置列表
""",
    )

    parser.add_argument("--starttime", type=str, help="开始日期 (YYYY-MM-DD)，默认昨天")
    parser.add_argument("--endtime", type=str, help="结束日期 (YYYY-MM-DD)，默认昨天")

    parser.add_argument("--search", type=str, default="", help="搜索关键词，多个用逗号分隔")

    parser.add_argument("--output-dir", type=str, default="./output", help="输出目录 (默认: ./output)")
    parser.add_argument("--state-path", type=str, default=None, help="状态文件路径，用于持久化去重 (默认: None)")
    parser.add_argument(
        "--allowed-accounts",
        type=str,
        default=None,
        help="公众号白名单配置文件路径 (默认: 自动查找)",
    )
    parser.add_argument(
        "--skip-existing", action="store_true", default=True, help="跳过已存在的文章 (默认: True)"
    )

    parser.add_argument("--date-limit", type=str, default="", help="日期限制，如 DATE_LIMIT_WEEK (默认: 空)")
    parser.add_argument("--page", type=int, default=1, help="页码 (默认: 1)")
    parser.add_argument("--page-size", type=int, default=50, help="每页数量 (默认: 50)")
    parser.add_argument(
        "--fetch-all-pages", action="store_true", default=True, help="获取全部页 (默认: True)"
    )
    parser.add_argument("--max-pages", type=int, default=20, help="最大页数限制 (默认: 20)")

    parser.add_argument(
        "--rotate-account",
        action="store_true",
        default=True,
        help="每次请求按策略切换账号 (默认: True)",
    )
    parser.add_argument("--no-rotate-account", action="store_true", help="不自动切换账号")

    parser.add_argument("--config", type=str, required=True, help="配置文件路径 (包含凭证)")
    parser.add_argument("--verbose", action="store_true", default=True, help="显示详细输出 (默认: True)")

    return parser.parse_args()


def args_to_kwargs(args) -> Dict[str, Any]:
    kwargs = {}
    for key, value in vars(args).items():
        if value is not None:
            kwargs[key] = value
    # 处理 allowed-accounts 到 allowed_accounts_path 的映射
    if "allowed_accounts" in kwargs:
        kwargs["allowed_accounts_path"] = kwargs.pop("allowed_accounts")
    # 处理 rotate_account 特殊逻辑
    if args.no_rotate_account:
        kwargs["rotate_account_per_request"] = False
    elif args.rotate_account:
        kwargs["rotate_account_per_request"] = True
    # 移除 rotate_account 和 no_rotate_account
    kwargs.pop("rotate_account", None)
    kwargs.pop("no_rotate_account", None)
    return kwargs


def main_cli():
    args = parse_args()
    kwargs = args_to_kwargs(args)

    # 直接创建配置和 fetcher
    config = NewsConfig()
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)

    fetcher = NewsFetcher(config)
    result = fetcher.fetch()

    if result.get("success"):
        print(f"\n[OK] {result.get('message', '')}")
        return 0
    else:
        print(f"\n[FAIL] {result.get('message', '执行失败')}")
        return 1


if __name__ == "__main__":
    sys.exit(main_cli())
