"""Tests for CNINFO attachment text extraction."""
from pathlib import Path

import requests

from data_layer.adapters.cninfo_adapter import CninfoAdapter


def test_parse_dict_embeds_downloaded_attachment_text(monkeypatch, tmp_path):
    adapter = CninfoAdapter()
    pdf_path = tmp_path / "cninfo.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake test pdf")

    def fake_download(url, output_dir, *, timeout, max_bytes):
        assert url == "https://static.cninfo.com.cn/finalpage/2026-06-01/12345.PDF"
        assert Path(output_dir) == tmp_path
        assert timeout == 12
        assert max_bytes == 2048
        return pdf_path

    def fake_convert(path, preferred_converter):
        assert path == pdf_path
        assert preferred_converter == "raw_text"
        return {
            "success": True,
            "text": "公司实现营业收入100亿元，归母净利润15亿元。",
            "strategy": "raw_text",
            "page_count": 8,
            "quality_score": 0.72,
        }

    monkeypatch.setattr(adapter, "_download_attachment", fake_download, raising=False)
    monkeypatch.setattr(adapter, "_convert_attachment_to_text", fake_convert, raising=False)

    envelope = adapter.parse(
        {
            "secCode": "600519",
            "secName": "贵州茅台",
            "announcementTitle": "2025年年度报告",
            "announcementTime": "2026-06-01 10:00:00",
            "adjunctUrl": "finalpage/2026-06-01/12345.PDF",
            "announcementId": "12345",
        },
        fetch_attachment_text=True,
        attachment_output_dir=str(tmp_path),
        attachment_timeout=12,
        max_attachment_bytes=2048,
        preferred_converter="raw_text",
    )

    assert "公司实现营业收入100亿元" in envelope.canonical_text
    assert envelope.metadata["attachment_url"] == (
        "https://static.cninfo.com.cn/finalpage/2026-06-01/12345.PDF"
    )
    assert envelope.metadata["attachment_local_path"] == str(pdf_path)
    assert envelope.metadata["attachment_text_status"] == "success"
    assert envelope.metadata["attachment_text_strategy"] == "raw_text"
    assert envelope.metadata["attachment_page_count"] == 8
    assert envelope.metadata["attachment_text_chars"] > 0


def test_parse_dict_marks_attachment_download_failure(monkeypatch, tmp_path):
    adapter = CninfoAdapter()

    monkeypatch.setattr(
        adapter, "_download_attachment", lambda *args, **kwargs: None, raising=False
    )

    envelope = adapter.parse(
        {
            "secCode": "000858",
            "secName": "五粮液",
            "announcementTitle": "2025年半年度报告",
            "announcementTime": "2026-06-01 08:00:00",
            "adjunctUrl": "finalpage/2026-06-01/12346.PDF",
            "announcementId": "12346",
        },
        fetch_attachment_text=True,
        attachment_output_dir=str(tmp_path),
    )

    assert "2025年半年度报告" in envelope.canonical_text
    assert envelope.metadata["attachment_text_status"] == "download_failed"
    assert "attachment_local_path" not in envelope.metadata


def test_parse_dict_accepts_cninfo_millisecond_timestamp():
    adapter = CninfoAdapter()

    envelope = adapter.parse(
        {
            "secCode": "300446",
            "secName": "航天智造",
            "announcementTitle": "投资者关系活动记录表",
            "announcementTime": 1743609599000,
            "adjunctUrl": "finalpage/2025-04-02/1222994132.PDF",
            "announcementId": "1222994132",
        }
    )

    assert envelope.published_at is not None
    assert envelope.metadata["announcement_time"].startswith("2025-04-02")
    assert "投资者关系活动记录表" in envelope.canonical_text


def test_parse_dict_skips_non_pdf_attachment_text(monkeypatch, tmp_path):
    adapter = CninfoAdapter()
    monkeypatch.setattr(adapter, "_download_attachment", lambda *args, **kwargs: tmp_path)

    envelope = adapter.parse(
        {
            "secCode": "",
            "secName": "监管规则适用指引",
            "announcementTitle": "境外发行上市监管要求",
            "announcementTime": 1714492799000,
            "adjunctUrl": "finalpage/2024-04-30/cninfo1220016601.js",
            "announcementId": "cninfo1220016601",
        },
        fetch_attachment_text=True,
        attachment_output_dir=str(tmp_path),
    )

    assert envelope.metadata["attachment_text_status"] == "non_pdf_attachment"
    assert "公告附件正文" not in envelope.canonical_text


def test_download_attachment_ignores_env_proxy(monkeypatch, tmp_path):
    adapter = CninfoAdapter()
    sessions = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size):
            yield b"%PDF-1.4 fake"

    class Session:
        def __init__(self):
            self.trust_env = True
            sessions.append(self)

        def get(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(requests, "Session", Session)

    path = adapter._download_attachment(
        "https://static.cninfo.com.cn/finalpage/2025-06-05/1223789554.PDF",
        str(tmp_path),
        timeout=5,
        max_bytes=1024,
    )

    assert path is not None
    assert path.read_bytes() == b"%PDF-1.4 fake"
    assert sessions[0].trust_env is False
