"""PDF Artifact Repository — PDF 制品仓储"""
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from data_layer.repositories.models import PDFArtifactV1DB, PDFConversionV1DB
from core.observability import get_logger

logger = get_logger(__name__)


def add_pdf_artifact(db: Session, artifact: PDFArtifactV1DB) -> PDFArtifactV1DB:
    """添加 PDF 制品"""
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact


def get_pdf_by_id(db: Session, pdf_id: str) -> Optional[PDFArtifactV1DB]:
    """通过 ID 获取 PDF"""
    return db.query(PDFArtifactV1DB).filter(
        PDFArtifactV1DB.pdf_id == pdf_id
    ).first()


def get_pdf_by_doc_id(db: Session, doc_id: str) -> Optional[PDFArtifactV1DB]:
    """通过文档 ID 获取 PDF"""
    return db.query(PDFArtifactV1DB).filter(
        PDFArtifactV1DB.doc_id == doc_id
    ).first()


def get_pdf_by_hash(db: Session, file_hash: str) -> Optional[PDFArtifactV1DB]:
    """通过哈希获取 PDF"""
    return db.query(PDFArtifactV1DB).filter(
        PDFArtifactV1DB.file_hash_sha256 == file_hash
    ).first()


def get_pdfs_by_source(
    db: Session,
    source_type: str,
    source_name: Optional[str] = None,
    limit: int = 100
) -> list[PDFArtifactV1DB]:
    """按来源获取 PDFs"""
    query = db.query(PDFArtifactV1DB).filter(
        PDFArtifactV1DB.source_type == source_type
    )
    if source_name:
        query = query.filter(PDFArtifactV1DB.source_name == source_name)

    return query.order_by(
        PDFArtifactV1DB.fetch_timestamp.desc()
    ).limit(limit).all()


def add_conversion(db: Session, conversion: PDFConversionV1DB) -> PDFConversionV1DB:
    """添加转换记录"""
    db.add(conversion)
    db.commit()
    db.refresh(conversion)
    return conversion


def update_conversion_status(
    db: Session,
    conversion_id: str,
    status: str,
    error_log: Optional[str] = None,
    completed_at: Optional[datetime] = None
) -> Optional[PDFConversionV1DB]:
    """更新转换状态"""
    conversion = db.query(PDFConversionV1DB).filter(
        PDFConversionV1DB.conversion_id == conversion_id
    ).first()

    if conversion:
        conversion.status = status
        if error_log:
            conversion.error_log = error_log
        if completed_at:
            conversion.completed_at = completed_at
        db.commit()
        db.refresh(conversion)

    return conversion


def get_conversion_stats(db: Session) -> dict:
    """获取转换统计"""
    total_pdfs = db.query(PDFArtifactV1DB).count()

    status_stats = db.query(
        PDFConversionV1DB.status,
        func.count(PDFConversionV1DB.conversion_id)
    ).group_by(PDFConversionV1DB.status).all()

    by_status = {s[0]: s[1] for s in status_stats}

    pending = by_status.get("pending", 0)
    converted = by_status.get("success", 0)
    failed = by_status.get("error", 0)

    # 计算没有转换记录的 PDFs
    with_conversion = db.query(PDFConversionV1DB.pdf_id).distinct().count()
    no_conversion = total_pdfs - with_conversion
    pending += no_conversion

    return {
        "total_pdfs": total_pdfs,
        "pending_conversion": pending,
        "converted": converted,
        "failed_conversion": failed,
        "by_status": by_status
    }


def get_pending_conversions(db: Session, limit: int = 50) -> list[PDFConversionV1DB]:
    """获取待处理的转换"""
    return db.query(PDFConversionV1DB).filter(
        PDFConversionV1DB.status == "pending"
    ).order_by(
        PDFConversionV1DB.created_at.asc()
    ).limit(limit).all()
