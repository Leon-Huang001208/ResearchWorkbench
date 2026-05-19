#!/usr/bin/env python3
"""
全自动数据抓取服务：定时自动抓取财联社、中国证券网、知丘研报、股票行情等真实数据
防爬处理：随机UA、随机请求间隔、失败重试、超时控制
自动去重，避免重复入库
"""
import asyncio
import hashlib
import logging
import random
from datetime import datetime, timedelta
from typing import Set

import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fake_useragent import UserAgent

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# 全局去重集合，存储已抓取的内容哈希，防止重复入库
fetched_content_hash: Set[str] = set()
ua = UserAgent()

# 防爬配置
REQUEST_TIMEOUT = 15  # 请求超时时间（秒）
RETRY_TIMES = 3  # 失败重试次数
MIN_REQUEST_INTERVAL = 1  # 最小请求间隔（秒）
MAX_REQUEST_INTERVAL = 3  # 最大请求间隔（秒）


def get_random_headers() -> dict:
    """生成随机请求头，防爬"""
    return {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "DNT": "1",
    }


def get_content_hash(content: str) -> str:
    """生成内容哈希，用于去重"""
    return hashlib.md5(content.strip().encode("utf-8")).hexdigest()


async def fetch_with_retry(url: str, method: str = "GET", **kwargs) -> requests.Response:
    """带重试的请求，防爬"""
    headers = kwargs.pop("headers", {})
    headers.update(get_random_headers())

    for retry in range(RETRY_TIMES):
        try:
            # 随机等待
            await asyncio.sleep(random.uniform(MIN_REQUEST_INTERVAL, MAX_REQUEST_INTERVAL))

            if method.upper() == "GET":
                resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, **kwargs)
            elif method.upper() == "POST":
                resp = requests.post(url, headers=headers, timeout=REQUEST_TIMEOUT, **kwargs)
            else:
                raise ValueError(f"不支持的请求方法：{method}")

            resp.raise_for_status()
            return resp

        except Exception as e:
            wait_time = 2 ** (retry + 1)
            logger.warning(f"请求失败（第{retry+1}次重试，等待{wait_time}秒）：{url}, 错误：{e}")
            await asyncio.sleep(wait_time)

    logger.error(f"请求失败，已重试{RETRY_TIMES}次：{url}")
    raise Exception(f"请求失败：{url}")


async def ingest_cls_data():
    """抓取财联社电报数据"""
    logger.info("开始抓取财联社电报数据...")
    try:
        # 调用本地ingest接口
        resp = await fetch_with_retry(
            "http://127.0.0.1:8000/api/ingest/cls",
            method="POST",
            params={"days": 0.2},  # 抓取最近0.2天（约5小时）的内容
        )
        result = resp.json()
        logger.info(
            f"财联社数据抓取完成：{result.get('message', '')}，成功摄入{result.get('doc_ids', []).__len__()}条内容"
        )

    except Exception as e:
        logger.error(f"财联社数据抓取失败：{e}")


async def ingest_cnstock_data():
    """抓取中国证券网新闻数据"""
    logger.info("开始抓取中国证券网新闻数据...")
    try:
        resp = await fetch_with_retry(
            "http://127.0.0.1:8000/api/ingest/cnstock", method="POST", params={"channel": "证券"}
        )
        result = resp.json()
        logger.info(
            f"中国证券网数据抓取完成：{result.get('message', '')}，成功摄入{result.get('doc_ids', []).__len__()}条内容"
        )

    except Exception as e:
        logger.error(f"中国证券网数据抓取失败：{e}")


async def ingest_zq_data():
    """抓取知丘研报数据"""
    logger.info("开始抓取知丘研报数据...")
    try:
        resp = await fetch_with_retry(
            "http://127.0.0.1:8000/api/ingest/zq",
            method="POST",
            params={"doc_types": "REPORT", "days": 1},
        )
        result = resp.json()
        logger.info(
            f"知丘研报数据抓取完成：{result.get('message', '')}，成功摄入{result.get('doc_ids', []).__len__()}条内容"
        )

    except Exception as e:
        logger.error(f"知丘研报数据抓取失败：{e}")


async def ingest_stock_master():
    """同步股票列表到 stock_master 表"""
    logger.info("开始同步股票列表...")
    try:
        resp = await fetch_with_retry(
            "http://127.0.0.1:8000/api/market-data/stocks/sync",
            method="POST",
            params={"limit": 5000},
        )
        result = resp.json()
        logger.info(f"股票列表同步完成：fetched={result.get('fetched', 0)} saved={result.get('saved', 0)}")
    except Exception as e:
        logger.error(f"股票列表同步失败：{e}")


async def ingest_daily_bars():
    """同步日行情数据到 stock_daily_bar 表"""
    from datetime import date

    logger.info("开始同步日行情数据...")
    today = date.today().isoformat()
    try:
        resp = await fetch_with_retry(
            "http://127.0.0.1:8000/api/market-data/daily-bars/sync",
            method="POST",
            json={
                "symbols": ["600519.SH", "002594.SZ", "601012.SH", "600036.SH", "000858.SZ"],
                "start_date": today,
                "end_date": today,
            },
        )
        result = resp.json()
        logger.info(f"日行情同步完成：fetched={result.get('fetched', 0)} saved={result.get('saved', 0)}")
    except Exception as e:
        logger.error(f"日行情同步失败：{e}")


async def ingest_stock_snapshots():
    """生成资产快照（依赖 stock_master + stock_daily_bar 已有数据）"""
    logger.info("开始生成资产快照...")
    try:
        stocks = ["600519.SH", "002594.SZ", "601012.SH", "600036.SH", "000858.SZ"]
        for stock in stocks:
            try:
                resp = await fetch_with_retry(
                    "http://127.0.0.1:8000/api/assets/analyze",
                    method="POST",
                    json={"canonical_id": stock, "source": "auto"},
                )
                result = resp.json()
                if result.get("canonical_id"):
                    logger.info(f"成功更新股票{stock}的分析数据")
            except Exception as e:
                logger.warning(f"更新股票{stock}数据失败：{e}")
                continue
        logger.info("资产快照生成完成")
    except Exception as e:
        logger.error(f"资产快照生成失败：{e}")


async def health_check():
    """健康检查，确保服务正常运行"""
    try:
        resp = await fetch_with_retry("http://127.0.0.1:8000/health")
        if resp.json().get("status") == "ok":
            logger.info("服务健康检查正常")
        else:
            logger.warning("服务健康检查异常")
    except Exception as e:
        logger.error(f"健康检查失败：{e}，请检查web服务是否正常运行")


def run_scheduler():
    """启动定时任务调度器"""
    scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")

    # 任务调度配置
    # 财联社：每15分钟抓一次
    scheduler.add_job(
        ingest_cls_data, "interval", minutes=15, id="ingest_cls", next_run_time=datetime.now()
    )

    # 中国证券网：每30分钟抓一次
    scheduler.add_job(
        ingest_cnstock_data,
        "interval",
        minutes=30,
        id="ingest_cnstock",
        next_run_time=datetime.now() + timedelta(minutes=3),
    )

    # 知丘研报：每1小时抓一次
    scheduler.add_job(
        ingest_zq_data,
        "interval",
        hours=1,
        id="ingest_zq",
        next_run_time=datetime.now() + timedelta(minutes=6),
    )

    # 股票列表：每天下午15:15 同步
    scheduler.add_job(
        ingest_stock_master,
        "cron",
        hour=15,
        minute=15,
        id="ingest_stock_master",
    )

    # 日行情：每天下午15:30 同步
    scheduler.add_job(
        ingest_daily_bars,
        "cron",
        hour=15,
        minute=30,
        id="ingest_daily_bars",
    )

    # 资产快照：每天下午15:45 生成
    scheduler.add_job(
        ingest_stock_snapshots,
        "cron",
        hour=15,
        minute=45,
        id="ingest_stock_snapshots",
    )

    # 健康检查：每10分钟一次
    scheduler.add_job(
        health_check, "interval", minutes=10, id="health_check", next_run_time=datetime.now()
    )

    scheduler.start()
    logger.info("全自动数据抓取服务已启动，定时任务配置完成：")
    logger.info("- 财联社电报：每15分钟抓取一次")
    logger.info("- 中国证券网新闻：每30分钟抓取一次")
    logger.info("- 知丘研报：每1小时抓取一次")
    logger.info("- 股票列表同步：每天15:15")
    logger.info("- 日行情同步：每天15:30")
    logger.info("- 资产快照生成：每天15:45")
    logger.info("- 健康检查：每10分钟一次")

    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        logger.info("服务正在关闭...")
        scheduler.shutdown()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="全自动数据抓取服务")
    parser.add_argument("--daemon", action="store_true", help="后台运行")
    args = parser.parse_args()

    if args.daemon:
        import daemon

        with daemon.DaemonContext():
            run_scheduler()
    else:
        run_scheduler()
