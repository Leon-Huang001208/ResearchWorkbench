"""
全量数据爬取脚本
- CLS: 拉近30天数据
- ZQ: 多关键词全量研报 + 公众号 + 会议纪要
"""

import json
import os
import sys
import time

# 确保项目根目录在 path 中
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from core.observability import get_logger

logger = get_logger(__name__)

OUTPUT_DIR = os.path.join(project_root, "data", "real")


def save_envelopes(envelopes: list, filename: str) -> int:
    """保存 envelopes 到 JSON 文件"""
    filepath = os.path.join(OUTPUT_DIR, filename)
    data = [e.model_dump(mode="json") for e in envelopes]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved {len(envelopes)} records to {filepath}")
    return len(envelopes)


def crawl_cls():
    """爬取 CLS 近30天数据"""
    logger.info("=" * 60)
    logger.info("Starting CLS crawl (30 days, max_pages=30)")
    logger.info("=" * 60)
    from data_layer.adapters.cls_adapter import CLSAdapter

    adapter = CLSAdapter()
    envelopes = adapter.fetch(days=30, max_pages=30)
    count = save_envelopes(envelopes, "cls_telegrams_30d.json")
    logger.info(f"CLS crawl completed: {count} records")
    return count


def crawl_zq_reports():
    """爬取 ZQ 全量研报（多关键词覆盖）"""
    logger.info("=" * 60)
    logger.info("Starting ZQ reports crawl (multiple keywords)")
    logger.info("=" * 60)
    from data_layer.adapters.zq_adapter import ZQAdapter

    adapter = ZQAdapter()
    keywords = ["A股", "市场", "宏观", "策略", "指数", "成长", "价值"]
    total = 0

    for keyword in keywords:
        logger.info(f"Fetching ZQ reports for keyword: {keyword}")
        try:
            envelopes = adapter.fetch(
                search=keyword,
                doc_types="REPORT",
                start_date="2026-04-01",
                enable_pdf=False,
            )
            count = save_envelopes(envelopes, f"zq_reports_{keyword}.json")
            total += count
            logger.info(f"Keyword '{keyword}': {count} records (total: {total})")
        except Exception as e:
            logger.error(f"Failed to fetch ZQ reports for keyword '{keyword}': {e}")

        # 反爬：每次请求间 sleep 3 秒
        time.sleep(3)

    logger.info(f"ZQ reports crawl completed: {total} records total")
    return total


def crawl_zq_news():
    """爬取 ZQ 公众号"""
    logger.info("=" * 60)
    logger.info("Starting ZQ news crawl")
    logger.info("=" * 60)
    from data_layer.adapters.zq_adapter import ZQAdapter

    adapter = ZQAdapter()
    try:
        envelopes = adapter.fetch(
            search="市场",
            doc_types="NEWS",
            start_date="2026-04-01",
        )
        count = save_envelopes(envelopes, "zq_news.json")
        logger.info(f"ZQ news crawl completed: {count} records")
    except Exception as e:
        logger.error(f"Failed to fetch ZQ news: {e}")
        count = 0
    return count


def crawl_zq_meetings():
    """爬取 ZQ 会议纪要"""
    logger.info("=" * 60)
    logger.info("Starting ZQ meetings crawl")
    logger.info("=" * 60)
    from data_layer.adapters.zq_adapter import ZQAdapter

    adapter = ZQAdapter()
    try:
        envelopes = adapter.fetch(
            search="会议",
            doc_types="ZQMEETING",
            start_date="2026-04-01",
        )
        count = save_envelopes(envelopes, "zq_meetings.json")
        logger.info(f"ZQ meetings crawl completed: {count} records")
    except Exception as e:
        logger.error(f"Failed to fetch ZQ meetings: {e}")
        count = 0
    return count


def main():
    """主入口"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    results = {}

    # 1. CLS
    results["cls"] = crawl_cls()
    time.sleep(3)

    # 2. ZQ 研报
    results["zq_reports"] = crawl_zq_reports()
    time.sleep(3)

    # 3. ZQ 公众号
    results["zq_news"] = crawl_zq_news()
    time.sleep(3)

    # 4. ZQ 会议纪要
    results["zq_meetings"] = crawl_zq_meetings()

    # 汇总
    logger.info("=" * 60)
    logger.info("CRAWL SUMMARY")
    logger.info("=" * 60)
    total = 0
    for source, count in results.items():
        logger.info(f"  {source}: {count} records")
        total += count
    logger.info(f"  TOTAL: {total} records")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
