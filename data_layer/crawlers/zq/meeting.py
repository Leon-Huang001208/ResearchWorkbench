#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
meeting.py - 知丘纪要爬取模块

专门用于爬取会议纪要的独立模块。

使用方法：
    python meeting.py --config config.yaml --search 建材
"""

import argparse
import sys
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .zhiqiu.base_fetcher import BaseConfig, BaseFetcher, BaseStateManager
from .zhiqiu.processors.meeting_processor import MeetingProcessor


@dataclass
class MeetingConfig(BaseConfig):
    """
    纪要爬取配置

    专注于 ZQMEETING 类型的配置。
    """

    # 重写基类的默认值
    use_homepage_search: bool = True
    date_limit: str = "CUSTOM"
    doc_type: str = "ZQMEETING"
    module_name: str = "meeting"
    module_label: str = "纪要"
    processed_key: str = "processed_meetings"


class MeetingStateManager(BaseStateManager):
    """
    纪要状态管理器 - 保持向后兼容
    """

    def __init__(self, state_path: str, verbose: bool = False):
        super().__init__(state_path, "processed_meetings", verbose)

    def add_processed_report(self, obj_id: str, title: str, **extra: Any) -> None:
        super().add_processed_report(obj_id, title, **extra)


class MeetingFetcher(BaseFetcher):
    """
    知丘纪要爬取器

    专门爬取 ZQMEETING 类型文档，支持：
    - 持久化去重
    - 多账号轮询
    """

    def __init__(self, config: Optional[MeetingConfig] = None):
        self.config = config or MeetingConfig()
        super().__init__(self.config)

        # 重写 _state_manager 的类型（保持向后兼容）
        if self.config.state_path:
            try:
                self._state_manager = MeetingStateManager(
                    self.config.state_path, self.config.verbose
                )
                if self.config.verbose:
                    print(f"[init] 状态管理器已初始化，已记录 {self._state_manager.get_processed_count()} 篇纪要")
            except Exception as e:
                if self.config.verbose:
                    print(f"[warn] 初始化状态管理器失败: {e}，持久化去重将不可用")

    def _fetch_single_term(self, search_term: str):
        if self._logger:
            self._logger.info(f"正在爬取纪要: {search_term if search_term else '全部'}")

        json_data = self._search_homepage(search_term, "title")
        if json_data is None:
            return None
        return self._process_search_result(json_data, MeetingProcessor, "meeting")

    def fetch(self, **kwargs) -> Dict[str, Any]:
        result = super().fetch(**kwargs)
        if "total" in result:
            result["total_meetings"] = result.pop("total")
        if "new" in result:
            result["new_meetings"] = result.pop("new")
        return result


def parse_args():
    parser = argparse.ArgumentParser(
        description="知丘纪要爬取工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 基础爬取（昨天的纪要）
  python meeting.py --config config.yaml

  # 爬取指定关键词
  python meeting.py --config config.yaml --search 建材,银行

  # 使用日期限制
  python meeting.py --config config.yaml --date-limit DATE_LIMIT_WEEK

  # 使用持久化去重
  python meeting.py --config config.yaml --state-path ./state/meeting_state.json
""",
    )

    parser.add_argument("--starttime", type=str, help="开始日期 (YYYY-MM-DD)，默认昨天")
    parser.add_argument("--endtime", type=str, help="结束日期 (YYYY-MM-DD)，默认昨天")

    parser.add_argument("--search", type=str, default="", help="搜索关键词，多个用逗号分隔")

    parser.add_argument("--output-dir", type=str, default="./output", help="输出目录 (默认: ./output)")
    parser.add_argument("--state-path", type=str, default=None, help="状态文件路径，用于持久化去重 (默认: None)")
    parser.add_argument(
        "--skip-existing", action="store_true", default=True, help="跳过已存在的纪要 (默认: True)"
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
    # 处理 fetch_all_pages 特殊逻辑
    if hasattr(args, "no_fetch_all_pages") and args.no_fetch_all_pages:
        kwargs["fetch_all_pages"] = False
    elif args.fetch_all_pages:
        kwargs["fetch_all_pages"] = True
    kwargs.pop("no_fetch_all_pages", None)
    # 处理 rotate_account 特殊逻辑
    if args.no_rotate_account:
        kwargs["rotate_account_per_request"] = False
    elif args.rotate_account:
        kwargs["rotate_account_per_request"] = True
    kwargs.pop("rotate_account", None)
    kwargs.pop("no_rotate_account", None)
    return kwargs


def main_cli():
    args = parse_args()
    kwargs = args_to_kwargs(args)

    # 直接创建配置和 fetcher
    config = MeetingConfig()
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)

    fetcher = MeetingFetcher(config)
    result = fetcher.fetch()

    if result.get("success"):
        print(f"\n[OK] {result.get('message', '')}")
        return 0
    else:
        print(f"\n[FAIL] {result.get('message', '执行失败')}")
        return 1


if __name__ == "__main__":
    sys.exit(main_cli())
