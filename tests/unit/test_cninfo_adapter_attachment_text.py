"""Tests for CNINFO attachment PDF registration (路径 B 统一到路径 A).

改造后：下载公告附件 PDF → 计算 SHA-256 → 去重 → 注册 PDFArtifactV1DB(parse_status=pending)，
由 CrawlScheduler 异步走 PDFConversionService 三级降级。不再就地转换。
"""

from pathlib import Path

import requests

from data_layer.adapters import cninfo_adapter as cninfo_mod
from data_layer.adapters.cninfo_adapter import CninfoAdapter
from data_layer.repositories.models import PDFArtifactV1DB


def test_parse_dict_registers_pdf_artifact_pending(monkeypatch, tmp_path, db_session):
    """下载成功后注册 artifact(parse_status=pending)，不内联正文，metadata 标记正确。"""
    adapter = CninfoAdapter()
    pdf_path = tmp_path / "cninfo.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake test pdf")

    def fake_download(url, output_dir, *, timeout, max_bytes):
        assert url == "https://static.cninfo.com.cn/finalpage/2026-06-01/12345.PDF"
        assert Path(output_dir) == tmp_path
        assert timeout == 12
        assert max_bytes == 2048
        return pdf_path

    monkeypatch.setattr(adapter, "_download_attachment", fake_download, raising=False)
    monkeypatch.setattr(cninfo_mod, "SessionLocal", lambda: db_session)

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

    # 正文不再内联
    assert "公告附件正文" not in envelope.canonical_text
    assert envelope.metadata["attachment_url"] == (
        "https://static.cninfo.com.cn/finalpage/2026-06-01/12345.PDF"
    )
    assert envelope.metadata["attachment_local_path"] == str(pdf_path)
    assert envelope.metadata["attachment_text_status"] == "registered_pending"

    pdf_id = envelope.metadata["attachment_pdf_id"]
    assert pdf_id.startswith("pdf_")

    # DB 中确实注册了一条 pending artifact
    artifact = db_session.query(PDFArtifactV1DB).filter_by(pdf_id=pdf_id).one()
    assert artifact.parse_status == "pending"
    assert artifact.source_type == "cninfo_filings"
    assert artifact.source_name == "巨潮资讯网"
    assert artifact.source_obj_id == "12345"
    assert artifact.source_url == ("https://static.cninfo.com.cn/finalpage/2026-06-01/12345.PDF")
    assert artifact.file_hash_sha256  # 非空
    assert artifact.file_size_bytes == len(b"%PDF-1.4 fake test pdf")
    assert "\\" not in artifact.file_path  # 相对路径用正斜杠
    assert artifact.pdf_metadata["sec_code"] == "600519"


def test_parse_dict_dedupes_already_registered_attachment(monkeypatch, tmp_path, db_session):
    """同哈希 PDF 已注册时跳过，metadata 标记 already_registered。"""
    adapter = CninfoAdapter()
    pdf_path = tmp_path / "cninfo.pdf"
    content = b"%PDF-1.4 fake test pdf"
    pdf_path.write_bytes(content)

    monkeypatch.setattr(adapter, "_download_attachment", lambda *a, **k: pdf_path, raising=False)
    monkeypatch.setattr(cninfo_mod, "SessionLocal", lambda: db_session)

    # 第一次：注册
    env1 = adapter.parse(
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
    )
    assert env1.metadata["attachment_text_status"] == "registered_pending"

    # 第二次：同哈希，应跳过
    env2 = adapter.parse(
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
    )
    assert env2.metadata["attachment_text_status"] == "already_registered"
    assert "attachment_pdf_id" not in env2.metadata

    # DB 中仍只有一条
    assert db_session.query(PDFArtifactV1DB).count() == 1


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
