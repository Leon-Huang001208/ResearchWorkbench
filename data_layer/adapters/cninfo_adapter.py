"""巨潮资讯网数据适配器

将 CninfoCrawler 的输出转换为统一的 DocumentEnvelope 列表。
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from core.contracts import DocumentEnvelope
from core.observability import get_logger
from data_layer.adapters.base import BaseDataAdapter
from data_layer.crawlers.cninfo.cninfo import CninfoConfig, CninfoCrawler

logger = get_logger(__name__)


class CninfoAdapter(BaseDataAdapter):
    """巨潮资讯网公告适配器"""

    def __init__(self) -> None:
        super().__init__(source_type="filing")

    def fetch(  # type: ignore[override]
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        plate: str = "",
        column: str = "",
        category: str = "",
        stock: str = "",
        output_dir: str = "./data/crawlers/cninfo",
        **kwargs: Any,
    ) -> list[DocumentEnvelope]:
        """爬取巨潮资讯网公告，返回 DocumentEnvelope 列表.

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            plate: 板块标识（szse / sse / bjse / all）
            column: API column 参数（已解析的板块值）
            category: API category 参数
            stock: 股票代码过滤
            output_dir: 输出目录
            **kwargs: 额外参数（max_pages, page_size, delay, verbose 等）

        Returns:
            list[DocumentEnvelope]: 公告信封列表
        """
        logger.info(
            f"Fetching CNINFO announcements: start_date={start_date}, end_date={end_date}, "
            f"plate={plate or 'all'}, category={category or 'all'}, stock={stock or 'any'}"
        )

        config = CninfoConfig(
            start_date=start_date,
            end_date=end_date,
            plate=plate,
            column=column,
            category=category,
            stock=stock,
            output_dir=output_dir,
            max_pages=kwargs.get("max_pages", 5),
            page_size=kwargs.get("page_size", 30),
            delay=kwargs.get("delay", 0.5),
            timeout=kwargs.get("timeout", 30),
            verbose=kwargs.get("verbose", False),
        )

        crawler = CninfoCrawler(config)
        result = crawler.execute()

        if not result.get("success"):
            logger.error(f"CNINFO crawl failed: {result.get('message')}")
            return []

        announcements = result.get("announcements", [])
        envelopes: list[DocumentEnvelope] = []
        for ann in announcements:
            envelope = self.parse(ann)
            envelopes.append(envelope)

        logger.info(f"Fetched {len(envelopes)} CNINFO announcements")
        return envelopes

    def parse(self, source: Any, **kwargs) -> DocumentEnvelope:  # type: ignore[no-untyped-def]
        """解析单条公告 (dict 或 file path).

        Args:
            source: 公告 dict 或文件路径.
            **kwargs: 额外参数.

        Returns:
            DocumentEnvelope: 解析后的文档信封.
        """
        if isinstance(source, dict):
            return self._parse_dict(source)
        elif isinstance(source, (str, Path)):
            with open(source, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return self.parse(data[0], **kwargs)
            elif isinstance(data, dict) and "announcements" in data:
                return self.parse(data["announcements"][0], **kwargs)
            else:
                return self.parse(data, **kwargs)
        else:
            raise ValueError(f"Unsupported source type for CNINFO adapter: {type(source)}")

    def _parse_dict(self, ann: dict[str, Any]) -> DocumentEnvelope:
        """从公告 dict 构建 DocumentEnvelope.

        Args:
            ann: 公告字典（来自 cninfo API）.

        Returns:
            DocumentEnvelope.
        """
        title = ann.get("announcementTitle", "") or ann.get("secName", "") or ""
        sec_code = ann.get("secCode", "")
        sec_name = ann.get("secName", "")
        announcement_time = ann.get("announcementTime", "")
        adjunct_url = ann.get("adjunctUrl", "")

        # 生成立等键 — 优先用 adjunctUrl，其次用代码+标题+时间
        id_source = adjunct_url or f"{sec_code}-{title}-{announcement_time}"
        doc_id = self._generate_idempotency_key(f"cninfo-{id_source}")

        # 解析发布时间
        published_at = None
        if announcement_time:
            announcement_time = announcement_time.strip()
            parse_formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d",
            ]
            for fmt in parse_formats:
                try:
                    published_at = datetime.strptime(announcement_time, fmt)
                    if fmt == "%Y-%m-%d":
                        published_at = published_at.replace(
                            hour=0, minute=0, second=0, microsecond=0
                        )
                    break
                except ValueError:
                    continue
            if not published_at and len(announcement_time) >= 10:
                try:
                    published_at = datetime.strptime(announcement_time[:10], "%Y-%m-%d").replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                except ValueError:
                    pass

        # 构建文本内容
        raw_text = f"【{sec_code} {sec_name}】{title} ({announcement_time})"

        return DocumentEnvelope(
            doc_id=doc_id,
            source_type="filing",
            title=title or f"巨潮资讯网公告 {sec_code}",
            published_at=published_at,
            source_name="巨潮资讯网",
            language="zh",
            metadata={
                "sec_code": sec_code,
                "sec_name": sec_name,
                "adjunct_url": adjunct_url,
                "announcement_type": ann.get("announcementType", ""),
                "announcement_id": ann.get("announcementId", ""),
            },
            raw_text=raw_text,
            canonical_text=raw_text,
        )
