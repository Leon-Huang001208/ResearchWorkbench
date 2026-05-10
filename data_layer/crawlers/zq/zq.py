#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zq.py - 知丘爬取统一入口

这是一个 CLI 包装器，根据 doc_types 参数调用对应的独立模块：
- REPORT → report.py
- NEWS → news.py
- ZQMEETING → meeting.py

使用方法：
    python zq.py --config config.yaml --search 建材 --doc-types REPORT,NEWS
"""
import argparse
import importlib
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

# 模块元数据：单一事实来源
_MODULE_METADATA = {
    "REPORT": ("report", "total_reports", "new_reports", "研报"),
    "NEWS": ("news", "total_news", "new_news", "公众号"),
    "ZQMEETING": ("meeting", "total_meetings", "new_meetings", "纪要"),
}


def _get_module_handler(doc_type: str):
    """
    获取文档类型对应的模块处理器信息

    Args:
        doc_type: 文档类型字符串（REPORT/NEWS/ZQMEETING）

    Returns:
        Optional[Tuple[str, List[str]]]: (模块名, [总数字段名, 新数字段名, 中文标签])，
            若不支持的类型返回 None
    """
    metadata = _MODULE_METADATA.get(doc_type)
    if metadata:
        module_name, total_key, new_key, label = metadata
        return (module_name, [total_key, new_key, label])
    return None


def _merge_results(results_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    合并多个模块的执行结果

    Args:
        results_list: 各模块返回的结果字典列表

    Returns:
        Dict[str, Any]: 合并后的结果
    """
    merged = {
        "success": True,
        "message": "",
        "terms": [],
        "output_dir": "",
        "errors": [],
        "skipped_existing": 0,
    }

    for _, total_key, new_key, _ in _MODULE_METADATA.values():
        merged[total_key] = 0
        merged[new_key] = 0

    success_count = 0
    total_count = 0

    for result in results_list:
        if not result:
            continue

        total_count += 1

        if "terms" in result:
            merged["terms"].extend(result["terms"])

        for _, total_key, new_key, _ in _MODULE_METADATA.values():
            if total_key in result:
                merged[total_key] += result[total_key]
            if new_key in result:
                merged[new_key] += result[new_key]
        if "skipped_existing" in result:
            merged["skipped_existing"] += result["skipped_existing"]

        if "errors" in result:
            merged["errors"].extend(result["errors"])

        if not merged["output_dir"] and "output_dir" in result:
            merged["output_dir"] = result["output_dir"]

        if result.get("success", False):
            success_count += 1

    parts = []
    for _, total_key, new_key, label in _MODULE_METADATA.values():
        if merged[total_key] > 0:
            parts.append(f"{label} {merged[total_key]} 篇（新 {merged[new_key]}）")

    if parts:
        merged["message"] = f"完成：成功 {success_count}/{total_count} 个模块，{', '.join(parts)}"
    else:
        merged["message"] = f"完成：成功 {success_count}/{total_count} 个模块"

    merged["success"] = success_count > 0 and success_count == total_count

    return merged


def _filter_kwargs_for_module(kwargs: Dict[str, Any], module_type: str) -> Dict[str, Any]:
    filtered = {}

    common_params = [
        "config",
        "config_path",
        "starttime",
        "endtime",
        "search",
        "output_dir",
        "verbose",
        "state_path",
        "skip_existing",
        "use_homepage_search",
        "date_limit",
        "page",
        "page_size",
        "fetch_all_pages",
        "max_pages",
        "rotate_account_per_request",
    ]

    for param in common_params:
        if param in kwargs and kwargs[param] is not None:
            filtered[param] = kwargs[param]

    if module_type == "REPORT":
        report_params = [
            "brokers",
            "doccolumns",
            "hyperSearchField",
            "prompt",
            "enable_core",
            "enable_viewpoint",
            "enable_companies",
            "enable_pdf",
            "ai_interval",
            "pdf_dir",
        ]
        for param in report_params:
            if param in kwargs and kwargs[param] is not None:
                filtered[param] = kwargs[param]

    elif module_type == "NEWS":
        if "allowed_accounts_path" in kwargs and kwargs["allowed_accounts_path"] is not None:
            filtered["allowed_accounts_path"] = kwargs["allowed_accounts_path"]

    return filtered


def _run_single_module(doc_type: str, kwargs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        filtered_kwargs = _filter_kwargs_for_module(kwargs, doc_type)
        handler = _get_module_handler(doc_type)

        if handler:
            module_name, _ = handler

            # 导入模块并直接调用其 CLI 逻辑
            module = importlib.import_module(f"data_layer.crawlers.zq.{module_name}")

            # 创建配置对象
            config_class = None
            fetcher_class = None
            if module_name == "report":
                config_class = getattr(module, "ReportConfig")
                fetcher_class = getattr(module, "ReportFetcher")
            elif module_name == "news":
                config_class = getattr(module, "NewsConfig")
                fetcher_class = getattr(module, "NewsFetcher")
            elif module_name == "meeting":
                config_class = getattr(module, "MeetingConfig")
                fetcher_class = getattr(module, "MeetingFetcher")

            if config_class and fetcher_class:
                config = config_class()
                for key, value in filtered_kwargs.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
                fetcher = fetcher_class(config)
                return fetcher.fetch()
        else:
            return {
                "success": False,
                "message": f"不支持的文档类型: {doc_type}",
                "errors": [f"不支持的文档类型: {doc_type}"],
                "terms": [],
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"{doc_type} 模块执行失败: {str(e)}",
            "errors": [f"{doc_type} 模块执行失败: {str(e)}"],
            "terms": [],
        }


def parse_args():
    parser = argparse.ArgumentParser(
        description="知丘研报爬取统一入口（调用独立模块）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 爬取研报和公众号
  python zq.py --config config.yaml --search 建材 --doc-types REPORT,NEWS

  # 爬取全部三种类型
  python zq.py --config config.yaml --search 建材 --doc-types REPORT,NEWS,ZQMEETING

  # 使用首页搜索和日期限制
  python zq.py --config config.yaml --search 宏观经济 --use-homepage-search --date-limit DATE_LIMIT_WEEK
""",
    )

    parser.add_argument("--starttime", type=str, help="开始日期 (YYYY-MM-DD)，默认昨天")
    parser.add_argument("--endtime", type=str, help="结束日期 (YYYY-MM-DD)，默认昨天")

    parser.add_argument("--search", type=str, default="", help="搜索关键词，多个用逗号分隔")
    parser.add_argument("--brokers", type=str, default="", help="券商ID列表，逗号分隔（仅REPORT）")
    parser.add_argument("--doccolumns", type=str, default="", help="报告类型（仅REPORT）")
    parser.add_argument(
        "--hyperSearchField",
        type=str,
        default="title",
        choices=["title", "all"],
        help="搜索范围（仅REPORT）",
    )
    parser.add_argument("--prompt", type=str, default="", help="AI提问模板（仅REPORT）")

    parser.add_argument("--enable-core", action="store_true", default=False, help="启用原有核心摘要提取")
    parser.add_argument("--enable-viewpoint", action="store_true", default=False, help="启用核心观点提取")
    parser.add_argument("--enable-companies", action="store_true", default=False, help="启用关注公司提取")
    parser.add_argument("--enable-pdf", action="store_true", default=False, help="启用 PDF 下载")

    parser.add_argument("--ai-interval", type=int, default=10, help="AI 请求间隔秒数（仅REPORT）")
    parser.add_argument("--pdf-dir", type=str, default="pdfs", help="PDF 保存子目录名（仅REPORT）")
    parser.add_argument("--output-dir", type=str, default="./output", help="输出根目录")
    parser.add_argument("--state-path", type=str, default=None, help="状态文件路径，用于持久化去重")
    parser.add_argument("--allowed-accounts", type=str, default=None, help="公众号白名单配置文件路径（仅NEWS）")
    parser.add_argument("--skip-existing", action="store_true", default=True, help="跳过已存在的内容")

    parser.add_argument("--use-homepage-search", action="store_true", default=False, help="使用首页搜索")
    parser.add_argument("--date-limit", type=str, default="", help="日期限制，如 DATE_LIMIT_WEEK")
    parser.add_argument(
        "--doc-types", type=str, default="REPORT", help="文档类型，逗号分隔：REPORT,NEWS,ZQMEETING"
    )
    parser.add_argument("--page", type=int, default=1, help="页码")
    parser.add_argument("--page-size", type=int, default=50, help="每页数量")
    parser.add_argument("--fetch-all-pages", action="store_true", default=False, help="获取全部页")
    parser.add_argument("--max-pages", type=int, default=20, help="最大页数限制")

    parser.add_argument("--rotate-account", action="store_true", default=True, help="每次请求按策略切换账号")
    parser.add_argument("--no-rotate-account", action="store_true", help="不自动切换账号")

    parser.add_argument("--config", type=str, required=True, help="配置文件路径（包含凭证）")
    parser.add_argument("--verbose", action="store_true", default=True, help="显示详细输出")

    return parser.parse_args()


def args_to_kwargs(args) -> Dict[str, Any]:
    kwargs = {}
    for key, value in vars(args).items():
        if value is not None:
            kwargs[key] = value
    if "allowed_accounts" in kwargs:
        kwargs["allowed_accounts_path"] = kwargs.pop("allowed_accounts")
    return kwargs


def main_cli():
    args = parse_args()
    kwargs = args_to_kwargs(args)

    # 处理 doc_types
    doc_types = kwargs.pop("doc_types", "REPORT")
    if isinstance(doc_types, str):
        doc_types = [t.strip() for t in doc_types.split(",") if t.strip()]

    # 处理账号轮换
    rotate = kwargs.pop("no_rotate_account", False)
    if rotate:
        kwargs["rotate_account_per_request"] = False
    else:
        kwargs["rotate_account_per_request"] = kwargs.pop("rotate_account", True)

    kwargs.pop("allowed_accounts_path", None)

    if len(doc_types) == 1:
        results = [_run_single_module(doc_types[0], kwargs.copy())]
    else:
        results = []
        with ThreadPoolExecutor(max_workers=len(doc_types)) as executor:
            future_to_type = {
                executor.submit(_run_single_module, dt, kwargs.copy()): dt for dt in doc_types
            }
            for future in as_completed(future_to_type):
                results.append(future.result())

    result = _merge_results(results)

    if result.get("success"):
        print(f"\n[OK] {result.get('message', '')}")
        return 0
    else:
        print(f"\n[FAIL] {result.get('message', '执行失败')}")
        return 1


if __name__ == "__main__":
    sys.exit(main_cli())
