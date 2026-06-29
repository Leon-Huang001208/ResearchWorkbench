from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from data_layer.repositories.models import Base, DocumentV1DB


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


class _FakeFetcher:
    def __init__(self, content="这是补抓到的中国证券网正文。"):
        self.content = content
        self.calls = []

    def fetch(self, *, article_id, url):
        self.calls.append({"article_id": article_id, "url": url})
        return {"source": "新华社", "content_text": self.content}


def _add_doc(db_session, *, doc_id="doc-cnstock", source_type="cnstock", content=None):
    title = "热点问答｜梅洛尼与特朗普为何突然翻脸"
    doc = DocumentV1DB(
        doc_id=doc_id,
        doc_type="news",
        source_type=source_type,
        title=title,
        summary=None,
        content=content or title,
        doc_metadata={},
        source_metadata={},
        classification={},
        quality={},
        evidence_profile={},
        timeliness={},
        processing={},
        review={},
        extra={},
        source_name="中国证券网",
        source_url="https://www.cnstock.com/commonDetail/732999",
        language="zh",
        content_hash=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(doc)
    db_session.commit()
    return doc


def test_refresh_cnstock_content_fetches_and_updates_document(db_session):
    from services.crawl_feed_content_service import CrawlFeedContentService

    fetcher = _FakeFetcher()
    _add_doc(db_session)

    result = CrawlFeedContentService(db_session, fetcher=fetcher).refresh_content("doc-cnstock")

    assert result["success"] is True
    assert result["cached"] is False
    assert result["has_content"] is True
    assert result["source_name"] == "新华社"
    assert "补抓到的中国证券网正文" in result["content"]
    assert fetcher.calls == [
        {
            "article_id": "732999",
            "url": "https://www.cnstock.com/commonDetail/732999",
        }
    ]

    saved = db_session.get(DocumentV1DB, "doc-cnstock")
    assert "补抓到的中国证券网正文" in saved.content
    assert saved.source_name == "新华社"
    assert saved.extra["content_refresh"]["status"] == "success"


def test_refresh_cnstock_content_uses_cached_body_when_present(db_session):
    from services.crawl_feed_content_service import CrawlFeedContentService

    fetcher = _FakeFetcher()
    _add_doc(
        db_session,
        content="热点问答｜梅洛尼与特朗普为何突然翻脸\n这是已经存在的正文。",
    )

    result = CrawlFeedContentService(db_session, fetcher=fetcher).refresh_content("doc-cnstock")

    assert result["success"] is True
    assert result["cached"] is True
    assert "已经存在的正文" in result["content"]
    assert fetcher.calls == []


def test_refresh_content_rejects_unsupported_source(db_session):
    from services.crawl_feed_content_service import CrawlFeedContentService

    fetcher = _FakeFetcher()
    _add_doc(db_session, doc_id="doc-cls", source_type="cls")

    result = CrawlFeedContentService(db_session, fetcher=fetcher).refresh_content("doc-cls")

    assert result["success"] is False
    assert result["reason"] == "unsupported_source"
    assert fetcher.calls == []
