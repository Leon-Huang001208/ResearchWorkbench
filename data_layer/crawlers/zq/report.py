#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
report.py - 知丘研报爬取模块

专门用于爬取券商研报的独立模块，支持 AI 提取和 PDF 下载。

使用方法：
    python report.py --config config.yaml --search 建材
"""
import argparse
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .zhiqiu.base_fetcher import BaseConfig, BaseFetcher, BaseStateManager
from .zhiqiu.processors.report_processor import ReportProcessor

# 默认券商列表
DEFAULT_BROKERS = "2,3,4,7,9,13,14,16,21,24,25,26,28,29,87,107,109,182,193,196,505"


@dataclass
class ReportConfig(BaseConfig):
    """
    研报爬取配置

    专注于 REPORT 类型的配置，包含 AI 和 PDF 相关配置。
    """

    # 研报特有配置
    brokers: str = DEFAULT_BROKERS
    doccolumns: str = ""
    hyperSearchField: str = "title"
    prompt: str = "提取该研报对{search}未来发展的核心预期与策略建议"
    enable_core: bool = False
    enable_viewpoint: bool = False
    enable_companies: bool = False
    enable_pdf: bool = False
    ai_interval: int = 10
    pdf_dir: str = "pdfs"

    # 重写基类的默认值
    use_homepage_search: bool = False
    doc_type: str = "REPORT"
    module_name: str = "report"
    module_label: str = "研报"
    processed_key: str = "processed_reports"


class ReportStateManager(BaseStateManager):
    """
    研报状态管理器 - 保持向后兼容
    """

    def __init__(self, state_path: str, verbose: bool = False):
        super().__init__(state_path, "processed_reports", verbose)

    def add_processed_report(self, obj_id: str, title: str, pdf_name: str = ""):
        super().add_processed_report(obj_id, title, pdfNAME=pdf_name)


class ReportFetcher(BaseFetcher):
    """
    知丘研报爬取器

    专门爬取 REPORT 类型文档，支持：
    - AI 核心观点提取
    - AI 关注公司提取
    - PDF 下载
    - 持久化去重
    - 多账号轮询
    """

    def __init__(self, config: Optional[ReportConfig] = None):
        self.config = config or ReportConfig()
        super().__init__(self.config)

        # 重写 _state_manager 的类型（保持向后兼容）
        if self.config.state_path:
            try:
                self._state_manager = ReportStateManager(
                    self.config.state_path, self.config.verbose
                )
                if self.config.verbose:
                    print(f"[init] 状态管理器已初始化，已记录 {self._state_manager.get_processed_count()} 篇研报")
            except Exception as e:
                if self.config.verbose:
                    print(f"[warn] 初始化状态管理器失败: {e}，持久化去重将不可用")

    def _log_feature_status(self):
        if not self._logger:
            return
        self._logger.info("=" * 50)
        self._logger.info("研报爬取配置:")
        if self.config.use_homepage_search:
            self._logger.info("  - 搜索接口: 首页搜索")
            self._logger.info(f"  - 日期限制: {self.config.date_limit or '未设置'}")
        else:
            self._logger.info("  - 搜索接口: 看研报搜索")
        self._logger.info("  - 文档类型: REPORT")
        self._logger.info(f"  - 核心摘要提取: {'启用' if self.config.enable_core else '关闭'}")
        self._logger.info(f"  - 核心观点提取: {'启用' if self.config.enable_viewpoint else '关闭'}")
        self._logger.info(f"  - 关注公司提取: {'启用' if self.config.enable_companies else '关闭'}")
        self._logger.info(f"  - PDF 下载: {'启用' if self.config.enable_pdf else '关闭'}")
        self._logger.info(f"  - AI 请求间隔: {self.config.ai_interval}秒")
        if self._state_manager:
            self._logger.info(f"  - 持久化去重: 启用 (已记录 {self._state_manager.get_processed_count()} 篇)")
        else:
            self._logger.info("  - 持久化去重: 关闭")
        if self._account_manager:
            self._logger.info("  - 账号管理: 启用")
        if self._progress_manager:
            self._logger.info("  - 进度追踪: 启用")
        if self._ejection_detector:
            self._logger.info("  - 顶出检测: 启用")
        self._logger.info("=" * 50)

    def _save_processed_item(self, obj_id: str, title: str, item: Dict[str, Any]):
        pdf_name = item.get("pdfNAME", "")
        self._state_manager.add_processed_report(obj_id, title, pdf_name)

    def _fetch_single_term(self, search_term: str):
        if self._logger:
            self._logger.info(f"正在爬取研报: {search_term if search_term else '全部'}")

        if self.config.use_homepage_search:
            json_data = self._search_homepage(search_term, self.config.hyperSearchField)
        else:
            json_data = self._client.search_reports(
                search=search_term,
                starttime=self.config.starttime,
                endtime=self.config.endtime,
                doccolumns=self.config.doccolumns,
                brokers=self.config.brokers,
                hyperSearchField=self.config.hyperSearchField,
            )

        if not json_data:
            return {
                "term": search_term if search_term else "全部",
                "status": "failed",
                "error": "获取数据失败",
                "count": 0,
                "skipped_existing": 0,
                "new": 0,
            }, []

        output_json = os.path.join(self.config.output_dir, f"report_{self.config.starttime}.json")
        os.makedirs(self.config.output_dir, exist_ok=True)

        prompt = self.config.prompt.format(search=search_term if search_term else "全部")

        processor = ReportProcessor(self._client)
        df, new_reports, skipped_count = processor.process(
            json_data,
            output_json,
            prompt=prompt,
            enable_core=self.config.enable_core,
            enable_viewpoint=self.config.enable_viewpoint,
            enable_companies=self.config.enable_companies,
            enable_pdf=self.config.enable_pdf,
            pdf_dir=self.config.pdf_dir,
            ai_interval=self.config.ai_interval,
            output_dir=self.config.output_dir,
            state_manager=self._state_manager,
            skip_existing=self.config.skip_existing,
        )

        return {
            "term": search_term if search_term else "全部",
            "status": "success",
            "count": len(df),
            "output_file": output_json,
            "skipped_existing": skipped_count,
            "new": len(new_reports),
        }, new_reports

    def fetch(self, **kwargs) -> Dict[str, Any]:
        # 调用基类 fetch，然后转换结果字段以保持向后兼容
        result = super().fetch(**kwargs)
        # 转换字段名以保持向后兼容
        if "total" in result:
            result["total_reports"] = result.pop("total")
        if "new" in result:
            result["new_reports"] = result.pop("new")
        return result


def parse_args():
    parser = argparse.ArgumentParser(
        description="知丘研报爬取工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 基础爬取（不使用 AI）
  python report.py --config config.yaml

  # 爬取单个行业 + 启用核心观点提取
  python report.py --config config.yaml --search 建材 --enable-viewpoint

  # 爬取多个行业 + 启用全部 AI 功能 + PDF 下载
  python report.py --config config.yaml --search "建材,银行" --enable-core --enable-viewpoint --enable-companies --enable-pdf

  # 指定券商和 AI 间隔
  python report.py --config config.yaml --search 建材 --brokers "2,3,4,7" --enable-viewpoint --ai-interval 15
""",
    )

    parser.add_argument("--starttime", type=str, help="开始日期 (YYYY-MM-DD)，默认昨天")
    parser.add_argument("--endtime", type=str, help="结束日期 (YYYY-MM-DD)，默认昨天")

    parser.add_argument("--search", type=str, default="", help="搜索关键词，多个用逗号分隔")
    parser.add_argument("--brokers", type=str, default=DEFAULT_BROKERS, help="券商ID列表，逗号分隔")
    parser.add_argument("--doccolumns", type=str, default="", help="报告类型")
    parser.add_argument(
        "--hyperSearchField", type=str, default="title", choices=["title", "all"], help="搜索范围"
    )
    parser.add_argument("--prompt", type=str, default="提取该研报对{search}未来发展的核心预期与策略建议", help="AI提问模板")

    parser.add_argument(
        "--enable-core", action="store_true", default=False, help="启用原有核心摘要提取 (默认: 关闭)"
    )
    parser.add_argument(
        "--enable-viewpoint", action="store_true", default=False, help="启用核心观点提取 (默认: 关闭)"
    )
    parser.add_argument(
        "--enable-companies", action="store_true", default=False, help="启用关注公司提取 (默认: 关闭)"
    )
    parser.add_argument(
        "--enable-pdf", action="store_true", default=False, help="启用 PDF 下载 (默认: 关闭)"
    )

    parser.add_argument("--ai-interval", type=int, default=10, help="AI 请求间隔秒数 (默认: 10)")
    parser.add_argument("--pdf-dir", type=str, default="pdfs", help="PDF 保存子目录名 (默认: pdfs)")
    parser.add_argument("--output-dir", type=str, default="./output", help="输出目录 (默认: ./output)")
    parser.add_argument("--state-path", type=str, default=None, help="状态文件路径，用于持久化去重 (默认: None)")
    parser.add_argument(
        "--skip-existing", action="store_true", default=True, help="跳过已存在的研报 (默认: True)"
    )

    parser.add_argument(
        "--use-homepage-search", action="store_true", default=False, help="使用首页搜索 (默认: False=看研报搜索)"
    )
    parser.add_argument("--date-limit", type=str, default="", help="日期限制，如 DATE_LIMIT_WEEK (默认: 空)")
    parser.add_argument("--page", type=int, default=1, help="页码 (默认: 1)")
    parser.add_argument("--page-size", type=int, default=50, help="每页数量 (默认: 50)")
    parser.add_argument(
        "--fetch-all-pages", action="store_true", default=True, help="获取全部页 (默认: True)"
    )
    parser.add_argument("--max-pages", type=int, default=20, help="最大页数限制 (默认: 20)")

    parser.add_argument(
        "--rotate-account", action="store_true", default=True, help="每次请求按策略切换账号 (默认: True)"
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
    # 移除 no_fetch_all_pages，ReportConfig 没有这个字段
    kwargs.pop("no_fetch_all_pages", None)
    # 处理 rotate_account 特殊逻辑
    if args.no_rotate_account:
        kwargs["rotate_account_per_request"] = False
    elif args.rotate_account:
        kwargs["rotate_account_per_request"] = True
    # 移除 rotate_account 和 no_rotate_account，ReportConfig 使用 rotate_account_per_request
    kwargs.pop("rotate_account", None)
    kwargs.pop("no_rotate_account", None)
    return kwargs


def main_cli():
    args = parse_args()
    kwargs = args_to_kwargs(args)

    # 直接创建配置和 fetcher
    config = ReportConfig()
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)

    fetcher = ReportFetcher(config)
    result = fetcher.fetch()

    if result.get("success"):
        print(f"\n[OK] {result.get('message', '')}")
        return 0
    else:
        print(f"\n[FAIL] {result.get('message', '执行失败')}")
        return 1


if __name__ == "__main__":
    sys.exit(main_cli())
