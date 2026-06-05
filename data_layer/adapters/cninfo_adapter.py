"""巨潮资讯网数据适配器

将 CninfoCrawler 的输出转换为统一的 DocumentEnvelope 列表。
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from core.contracts import DocumentEnvelope
from core.contracts.pdf_conversion import ConversionResult
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
            trust_env=kwargs.get("trust_env", False),
            verbose=kwargs.get("verbose", False),
        )

        crawler = CninfoCrawler(config)
        result = crawler.execute()

        if not result.get("success"):
            logger.error(
                "CNINFO crawl failed",
                extra={
                    "message": result.get("message"),
                    "errors": result.get("errors", []),
                    "announcements": result.get("total_count", 0),
                },
            )

        announcements = result.get("announcements", [])
        if not announcements:
            return []
        envelopes: list[DocumentEnvelope] = []
        for ann in announcements:
            try:
                envelope = self.parse(
                    ann,
                    fetch_attachment_text=kwargs.get("fetch_attachment_text", False),
                    attachment_output_dir=kwargs.get("attachment_output_dir", output_dir),
                    attachment_timeout=kwargs.get("attachment_timeout", kwargs.get("timeout", 30)),
                    max_attachment_bytes=kwargs.get("max_attachment_bytes", 80 * 1024 * 1024),
                    preferred_converter=kwargs.get("preferred_converter", "auto"),
                )
                envelopes.append(envelope)
            except Exception as exc:
                logger.error(
                    "cninfo_announcement_parse_failed",
                    extra={
                        "announcement_id": ann.get("announcementId"),
                        "title": ann.get("announcementTitle"),
                        "error": str(exc),
                    },
                    exc_info=True,
                )

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
            return self._parse_dict(source, **kwargs)
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

    def _parse_dict(self, ann: dict[str, Any], **kwargs: Any) -> DocumentEnvelope:
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
        published_at, announcement_time_text = self._parse_announcement_time(announcement_time)

        # 构建文本内容
        raw_text = f"【{sec_code} {sec_name}】{title} ({announcement_time_text})"
        metadata = {
            "sec_code": sec_code,
            "sec_name": sec_name,
            "adjunct_url": adjunct_url,
            "announcement_time": announcement_time_text,
            "announcement_type": ann.get("announcementType", ""),
            "announcement_id": ann.get("announcementId", ""),
        }

        if kwargs.get("fetch_attachment_text"):
            raw_text = self._append_attachment_text(
                raw_text,
                metadata,
                adjunct_url=adjunct_url,
                output_dir=kwargs.get("attachment_output_dir", "./data/crawlers/cninfo"),
                timeout=int(kwargs.get("attachment_timeout", 30)),
                max_bytes=int(kwargs.get("max_attachment_bytes", 80 * 1024 * 1024)),
                preferred_converter=str(kwargs.get("preferred_converter", "auto")),
            )

        return DocumentEnvelope(
            doc_id=doc_id,
            source_type="filing",
            title=title or f"巨潮资讯网公告 {sec_code}",
            published_at=published_at,
            source_name="巨潮资讯网",
            language="zh",
            metadata=metadata,
            raw_text=raw_text,
            canonical_text=raw_text,
        )

    @staticmethod
    def _parse_announcement_time(value: Any) -> tuple[datetime | None, str]:
        """Parse CNINFO announcementTime from milliseconds, seconds, or text."""
        if value is None or value == "":
            return None, ""

        if isinstance(value, (int, float)):
            timestamp = float(value)
            if timestamp > 10_000_000_000:
                timestamp = timestamp / 1000
            try:
                parsed = datetime.fromtimestamp(timestamp)
                return parsed, parsed.strftime("%Y-%m-%d %H:%M:%S")
            except Exception as exc:
                logger.warning(
                    "cninfo_announcement_time_parse_failed",
                    extra={"value": value, "error": str(exc)},
                )
                return None, str(value)

        announcement_time = str(value).strip()
        parse_formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
        ]
        for fmt in parse_formats:
            try:
                parsed = datetime.strptime(announcement_time, fmt)
                if fmt == "%Y-%m-%d":
                    parsed = parsed.replace(hour=0, minute=0, second=0, microsecond=0)
                return parsed, parsed.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
        if len(announcement_time) >= 10:
            try:
                parsed = datetime.strptime(announcement_time[:10], "%Y-%m-%d").replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                return parsed, parsed.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
        logger.warning("cninfo_announcement_time_unparsed", extra={"value": announcement_time})
        return None, announcement_time

    def _append_attachment_text(
        self,
        base_text: str,
        metadata: dict[str, Any],
        *,
        adjunct_url: str,
        output_dir: str,
        timeout: int,
        max_bytes: int,
        preferred_converter: str,
    ) -> str:
        """Download CNINFO attachment and append extracted text when available."""
        attachment_url = self._absolute_attachment_url(adjunct_url)
        if not attachment_url:
            metadata["attachment_text_status"] = "no_attachment"
            return base_text
        if not attachment_url.lower().endswith(".pdf"):
            metadata["attachment_url"] = attachment_url
            metadata["attachment_text_status"] = "non_pdf_attachment"
            return base_text

        metadata["attachment_url"] = attachment_url
        try:
            pdf_path = self._download_attachment(
                attachment_url,
                output_dir,
                timeout=timeout,
                max_bytes=max_bytes,
            )
            if pdf_path is None:
                metadata["attachment_text_status"] = "download_failed"
                return base_text

            metadata["attachment_local_path"] = str(pdf_path)
            conversion = self._convert_attachment_to_text(
                pdf_path,
                preferred_converter=preferred_converter,
            )
            metadata["attachment_text_status"] = "success" if conversion.get("success") else "conversion_failed"
            metadata["attachment_text_strategy"] = conversion.get("strategy", "")
            if conversion.get("page_count") is not None:
                metadata["attachment_page_count"] = conversion.get("page_count")
            if conversion.get("quality_score") is not None:
                metadata["attachment_quality_score"] = conversion.get("quality_score")
            if conversion.get("error_message"):
                metadata["attachment_text_error"] = conversion.get("error_message")

            text = str(conversion.get("text") or "").strip()
            if not conversion.get("success") or not text:
                return base_text

            metadata["attachment_text_chars"] = len(text)
            metadata["content_source"] = "metadata_plus_attachment_text"
            return f"{base_text}\n\n# 公告附件正文\n\n{text}"
        except Exception as exc:
            logger.error(
                "cninfo_attachment_text_failed",
                extra={"attachment_url": attachment_url, "error": str(exc)},
                exc_info=True,
            )
            metadata["attachment_text_status"] = "error"
            metadata["attachment_text_error"] = str(exc)
            return base_text

    @staticmethod
    def _absolute_attachment_url(adjunct_url: str | None) -> str | None:
        """Return absolute CNINFO static attachment URL."""
        if not adjunct_url:
            return None
        url = adjunct_url.strip()
        if not url:
            return None
        if url.startswith("http://") or url.startswith("https://"):
            return url
        return "https://static.cninfo.com.cn/" + url.lstrip("/")

    def _download_attachment(
        self,
        url: str,
        output_dir: str,
        *,
        timeout: int,
        max_bytes: int,
    ) -> Path | None:
        """Download a CNINFO PDF attachment with a size guard."""
        try:
            import requests
        except ImportError:
            logger.warning("cninfo_attachment_requests_missing", extra={"url": url})
            return None

        start = time.time()
        target_dir = Path(output_dir) / "attachments"
        target_dir.mkdir(parents=True, exist_ok=True)
        parsed = urlparse(url)
        filename = Path(parsed.path).name or "cninfo_attachment.pdf"
        if not filename.lower().endswith(".pdf"):
            filename = f"{filename}.pdf"
        target_path = target_dir / filename

        try:
            session = requests.Session()
            session.trust_env = False
            with session.get(
                url,
                stream=True,
                timeout=timeout,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Referer": "https://www.cninfo.com.cn/",
                },
            ) as response:
                response.raise_for_status()
                total = 0
                with target_path.open("wb") as f:
                    for chunk in response.iter_content(chunk_size=64 * 1024):
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > max_bytes:
                            logger.warning(
                                "cninfo_attachment_too_large",
                                extra={"url": url, "max_bytes": max_bytes},
                            )
                            target_path.unlink(missing_ok=True)
                            return None
                        f.write(chunk)
            logger.info(
                "cninfo_attachment_downloaded",
                extra={
                    "url": url,
                    "path": str(target_path),
                    "duration_ms": int((time.time() - start) * 1000),
                },
            )
            return target_path
        except Exception as exc:
            logger.warning(
                "cninfo_attachment_download_failed",
                extra={"url": url, "error": str(exc)},
            )
            target_path.unlink(missing_ok=True)
            return None

    def _convert_attachment_to_text(
        self,
        path: Path,
        *,
        preferred_converter: str,
    ) -> dict[str, Any]:
        """Convert a downloaded PDF to text using the existing converter strategies."""
        strategies = self._candidate_converter_strategies(preferred_converter)
        last_error = ""
        for strategy in strategies:
            if not strategy.is_available():
                continue
            result = strategy.convert(str(path))
            normalized = self._conversion_to_dict(result)
            if normalized.get("success") and normalized.get("text"):
                return normalized
            last_error = str(normalized.get("error_message") or "empty conversion result")

        return {
            "success": False,
            "text": "",
            "strategy": preferred_converter,
            "error_message": last_error or "no available converter",
        }

    @staticmethod
    def _candidate_converter_strategies(preferred_converter: str) -> list[Any]:
        """Build converter strategy list in preferred order."""
        from ingestion.converters.markitdown import MarkItDownStrategy
        from ingestion.converters.raw_text import RawTextStrategy

        preferred = preferred_converter.lower()
        strategy_by_name = {
            "markitdown": MarkItDownStrategy,
            "raw_text": RawTextStrategy,
        }
        if preferred in strategy_by_name:
            return [strategy_by_name[preferred]()]
        return [MarkItDownStrategy(), RawTextStrategy()]

    @staticmethod
    def _conversion_to_dict(result: ConversionResult) -> dict[str, Any]:
        """Normalize ConversionResult into the metadata shape used by CNINFO."""
        text = (result.markdown or result.raw_text or "").strip()
        return {
            "success": result.success,
            "text": text,
            "strategy": result.strategy_used,
            "page_count": result.page_count,
            "quality_score": result.quality_score,
            "error_message": result.error_message,
        }
