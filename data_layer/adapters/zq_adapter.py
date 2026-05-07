"""知丘数据适配器"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from core.contracts import DocumentEnvelope
from core.observability import get_logger
from data_layer.adapters.base import BaseDataAdapter

logger = get_logger(__name__)


class ZQAdapter(BaseDataAdapter):
    """知丘数据适配器 (研报/公众号/纪要)"""

    def __init__(self):
        super().__init__(source_type="report")

    def fetch(
        self,
        search: str = "",
        doc_types: str = "REPORT",
        start_date: str | None = None,
        end_date: str | None = None,
        output_dir: str = "./data/crawlers/zq",
        **kwargs
    ) -> list[DocumentEnvelope]:
        """爬取知丘内容,返回 DocumentEnvelope 列表"""
        logger.info(
            f"Fetching ZQ content: search={search}, doc_types={doc_types}, start_date={start_date}, end_date={end_date}, output_dir={output_dir}"
        )

        # Config path: use the one in data_layer/crawlers/zq
        config_path = kwargs.get(
            "config_path",
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "crawlers",
                "zq",
                "config.yaml"
            )
        )

        # Parse doc_types into list
        doc_type_list = [dt.strip() for dt in doc_types.split(",") if dt.strip()]

        envelopes = []

        for doc_type in doc_type_list:
            try:
                if doc_type == "REPORT":
                    envelopes.extend(self._fetch_reports(search, start_date, end_date, output_dir, config_path, **kwargs))
                elif doc_type == "NEWS":
                    envelopes.extend(self._fetch_news(search, start_date, end_date, output_dir, config_path, **kwargs))
                elif doc_type == "ZQMEETING":
                    envelopes.extend(self._fetch_meetings(search, start_date, end_date, output_dir, config_path, **kwargs))
                else:
                    logger.warning(f"Unsupported ZQ doc type: {doc_type}")
            except Exception as e:
                logger.error(f"Failed to fetch ZQ {doc_type}: {e}", exc_info=True)

        logger.info(f"Fetched {len(envelopes)} ZQ documents")
        return envelopes

    def _fetch_reports(
        self,
        search: str,
        start_date: str | None,
        end_date: str | None,
        output_dir: str,
        config_path: str,
        **kwargs
    ) -> list[DocumentEnvelope]:
        """Fetch ZQ reports"""
        from data_layer.crawlers.zq.report import ReportFetcher, ReportConfig

        config = ReportConfig(
            config_path=config_path,
            starttime=start_date,
            endtime=end_date,
            search=search,
            output_dir=output_dir,
            state_path=kwargs.get("state_path"),
            skip_existing=kwargs.get("skip_existing", True),
            verbose=kwargs.get("verbose", True),
            enable_viewpoint=kwargs.get("enable_viewpoint", False),
            enable_companies=kwargs.get("enable_companies", False),
            enable_core=kwargs.get("enable_core", False),
            enable_pdf=kwargs.get("enable_pdf", False),
        )

        fetcher = ReportFetcher(config)
        result = fetcher.fetch()

        if not result.get("success"):
            logger.error(f"ZQ report fetch failed: {result.get('message')}")
            return []

        # Read output file
        output_file = None
        for term_result in result.get("terms", []):
            output_file = term_result.get("output_file")
            if output_file:
                break

        if not output_file:
            logger.warning("No output file from ZQ report fetcher")
            return []

        return self._parse_json_output(output_file, "report")

    def _fetch_news(
        self,
        search: str,
        start_date: str | None,
        end_date: str | None,
        output_dir: str,
        config_path: str,
        **kwargs
    ) -> list[DocumentEnvelope]:
        """Fetch ZQ news (公众号)"""
        from data_layer.crawlers.zq.news import NewsFetcher, NewsConfig

        config = NewsConfig(
            config_path=config_path,
            starttime=start_date,
            endtime=end_date,
            search=search,
            output_dir=output_dir,
            state_path=kwargs.get("state_path"),
            skip_existing=kwargs.get("skip_existing", True),
            verbose=kwargs.get("verbose", True),
        )

        fetcher = NewsFetcher(config)
        result = fetcher.fetch()

        if not result.get("success"):
            logger.error(f"ZQ news fetch failed: {result.get('message')}")
            return []

        # Read output file
        output_file = None
        for term_result in result.get("terms", []):
            output_file = term_result.get("output_file")
            if output_file:
                break

        if not output_file:
            logger.warning("No output file from ZQ news fetcher")
            return []

        return self._parse_json_output(output_file, "news")

    def _fetch_meetings(
        self,
        search: str,
        start_date: str | None,
        end_date: str | None,
        output_dir: str,
        config_path: str,
        **kwargs
    ) -> list[DocumentEnvelope]:
        """Fetch ZQ meetings (纪要)"""
        from data_layer.crawlers.zq.meeting import MeetingFetcher, MeetingConfig

        config = MeetingConfig(
            config_path=config_path,
            starttime=start_date,
            endtime=end_date,
            search=search,
            output_dir=output_dir,
            state_path=kwargs.get("state_path"),
            skip_existing=kwargs.get("skip_existing", True),
            verbose=kwargs.get("verbose", True),
        )

        fetcher = MeetingFetcher(config)
        result = fetcher.fetch()

        if not result.get("success"):
            logger.error(f"ZQ meeting fetch failed: {result.get('message')}")
            return []

        # Read output file
        output_file = None
        for term_result in result.get("terms", []):
            output_file = term_result.get("output_file")
            if output_file:
                break

        if not output_file:
            logger.warning("No output file from ZQ meeting fetcher")
            return []

        return self._parse_json_output(output_file, "meeting")

    def _parse_json_output(self, file_path: str, doc_type: str) -> list[DocumentEnvelope]:
        """Parse ZQ JSON output file into DocumentEnvelopes"""
        envelopes = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Data is usually a list of items
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict) and "reports" in data:
                items = data["reports"]
            else:
                items = []

            for item in items:
                envelope = self.parse(item, doc_type=doc_type)
                envelopes.append(envelope)
        except Exception as e:
            logger.error(f"Failed to parse ZQ output file {file_path}: {e}", exc_info=True)

        return envelopes

    def parse(self, source: Any, **kwargs) -> DocumentEnvelope:
        """解析知丘单条内容 (dict or file path)"""
        doc_type = kwargs.get("doc_type", "report")

        if isinstance(source, dict):
            # Parse from dict
            obj_id = source.get("OBJID", source.get("id", ""))
            title = source.get("title", "")
            content = (
                source.get("coreViewpoint", "")
                or source.get("content", "")
                or source.get("summary", "")
            )
            date_str = source.get("date", "")
            published_at = None
            if date_str:
                try:
                    published_at = datetime.fromisoformat(date_str)
                except ValueError:
                    try:
                        published_at = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        pass

            # Determine source type and name
            if doc_type == "report":
                source_type = "report"
                source_name = source.get("brokerName", "知丘研报")
            elif doc_type == "news":
                source_type = "news"
                source_name = source.get("openName", "知丘公众号")
            else:
                source_type = "report"
                source_name = "知丘纪要"

            return DocumentEnvelope(
                doc_id=self._generate_idempotency_key(f"zq-{doc_type}-{obj_id}"),
                source_type=source_type,
                title=title,
                published_at=published_at,
                source_name=source_name,
                language="zh",
                metadata={
                    "obj_id": obj_id,
                    "doc_type": doc_type,
                    "author": source.get("author", ""),
                    "companies": source.get("focusCompaniesParsed", []),
                },
                raw_text=json.dumps(source, ensure_ascii=False),
                canonical_text=content,
            )
        elif isinstance(source, (str, Path)):
            # Parse from file path
            with open(source, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return self.parse(data[0], **kwargs)
            else:
                return self.parse(data, **kwargs)
        else:
            raise ValueError(f"Unsupported source type for ZQ adapter: {type(source)}")
