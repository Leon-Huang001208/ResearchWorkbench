"""巨潮资讯网数据适配器

将 CninfoCrawler 的输出转换为统一的 DocumentEnvelope 列表。
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from core.contracts import DocumentEnvelope
from core.observability import get_logger
from data_layer.adapters.base import BaseDataAdapter
from data_layer.crawlers.cninfo.cninfo import CninfoConfig, CninfoCrawler
from data_layer.repositories.base import SessionLocal
from data_layer.repositories.models import PDFArtifactV1DB
from data_layer.repositories.pdf_artifact_repository import (
    add_pdf_artifact,
    get_pdf_by_hash,
)

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
        """Download CNINFO attachment and register it as a pending PDF artifact.

        下载公告附件 PDF 后注册到 ``pdf_artifact_v1``（``parse_status="pending"``），
        由 CrawlScheduler 异步调用 PDFConversionService 走 MinerU→MarkItDown→RawText
        三级降级管线。本方法不再就地转换，PDF 正文由路径 A 异步填充到独立 DocumentV1。

        Returns:
            base_text 原样返回（PDF 正文不再内联）。注册结果写入 metadata 供下游追踪。
        """
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

            pdf_id = self._register_pdf_artifact(
                pdf_path,
                announcement_id=str(metadata.get("announcement_id") or ""),
                sec_code=str(metadata.get("sec_code") or ""),
                sec_name=str(metadata.get("sec_name") or ""),
                attachment_url=attachment_url,
            )
            if pdf_id is None:
                metadata["attachment_text_status"] = "already_registered"
                return base_text

            metadata["attachment_text_status"] = "registered_pending"
            metadata["attachment_pdf_id"] = pdf_id
            metadata["content_source"] = "metadata_plus_attachment_pending"
            return base_text
        except Exception as exc:
            logger.error(
                "cninfo_attachment_register_failed",
                extra={"attachment_url": attachment_url, "error": str(exc)},
                exc_info=True,
            )
            metadata["attachment_text_status"] = "error"
            metadata["attachment_text_error"] = str(exc)
            return base_text

    @staticmethod
    def _register_pdf_artifact(
        pdf_path: Path,
        *,
        announcement_id: str,
        sec_code: str,
        sec_name: str,
        attachment_url: str,
    ) -> str | None:
        """计算哈希、去重、注册 PDFArtifactV1DB(parse_status=pending)。

        参照 ZQ 研报爬虫 ``report_processor.py`` 的做法。已存在同哈希记录时返回 None。

        Returns:
            新注册 artifact 的 pdf_id；已存在则返回 None。
        """
        import hashlib

        file_bytes = pdf_path.read_bytes()
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        file_size = len(file_bytes)
        file_name = pdf_path.name

        # 相对路径（\\→/），对齐 ZQ 约定，供 PDFConversionService 读取
        try:
            relative_path = str(pdf_path.resolve().relative_to(Path.cwd().resolve()))
        except ValueError:
            relative_path = str(pdf_path)
        relative_path = relative_path.replace("\\", "/")

        db = SessionLocal()
        try:
            existing = get_pdf_by_hash(db, file_hash)
            if existing is not None:
                logger.info(
                    "cninfo_attachment_already_registered",
                    extra={"file_hash": file_hash, "pdf_id": existing.pdf_id},
                )
                return None

            import uuid

            pdf_id = f"pdf_{uuid.uuid4().hex[:12]}"
            artifact = PDFArtifactV1DB(
                pdf_id=pdf_id,
                source_obj_id=announcement_id or None,
                file_path=relative_path,
                file_name=file_name,
                file_size_bytes=file_size,
                file_hash_sha256=file_hash,
                source_type="cninfo_filings",
                source_name="巨潮资讯网",
                source_url=attachment_url,
                fetch_timestamp=datetime.now(timezone.utc),
                parse_status="pending",
                pdf_metadata={
                    "sec_code": sec_code,
                    "sec_name": sec_name,
                    "announcement_id": announcement_id,
                },
            )
            add_pdf_artifact(db, artifact)
            logger.info(
                "cninfo_attachment_registered",
                extra={"pdf_id": pdf_id, "file_hash": file_hash, "path": relative_path},
            )
            return pdf_id
        finally:
            db.close()

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
