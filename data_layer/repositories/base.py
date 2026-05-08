from contextlib import contextmanager
from typing import Any, List, Optional, TypeVar

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from core.observability import get_logger
from core.settings import settings

logger = get_logger(__name__)

# 创建引擎和会话工厂
engine = create_engine(settings.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 基类
Base = declarative_base()

def check_database_connection() -> None:
    """Check database connectivity on startup.
    
    Raises:
        RuntimeError: If connection fails with actionable error message.
    """
    try:
        # Test connection
        with engine.connect():
            logger.info(f"Successfully connected to database: {engine.dialect.name}")
    except OperationalError as e:
        if settings.DATABASE_URL.startswith("postgresql"):
            error_msg = (
                "Failed to connect to PostgreSQL database.\n"
                "Please check: \n"
                "1. Is PostgreSQL server running on localhost:5432?\n"
                "2. Is the database 'alphafoundry' created? (CREATE DATABASE alphafoundry;)\n"
                "3. Are the username/password correct in DATABASE_URL?\n"
                "4. If you want to use SQLite for demo, set DATABASE_URL=sqlite:///./data/alphafoundry.db in your .env\n"
                f"Original error: {str(e)}"
            )
        else:
            error_msg = (
                f"Failed to connect to database {engine.dialect.name}.\n"
                f"Check your DATABASE_URL configuration. Original error: {str(e)}"
            )
        logger.critical(error_msg)
        raise RuntimeError(error_msg) from e

# Run connection check on startup
check_database_connection()


def ensure_schema() -> None:
    """确保数据库 schema 与 ORM 模型一致。

    对于 SQLite，先 create_all 创建缺失的表，
    再对已有表检查并添加缺失的列（ALTER TABLE ADD COLUMN）。
    """
    # 导入所有模型以注册到 Base.metadata
    import data_layer.repositories.models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # 对 SQLite，检查已有表是否缺少列并自动补列
    if settings.DATABASE_URL.startswith("sqlite"):
        import sqlite3

        db_path = settings.DATABASE_URL.replace("sqlite:///", "")
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            for table in Base.metadata.sorted_tables:
                cursor.execute(f"PRAGMA table_info({table.name})")
                existing_cols = {row[1] for row in cursor.fetchall()}
                for col in table.columns:
                    if col.name not in existing_cols:
                        col_type = col.type.compile(dialect=engine.dialect)
                        nullable = "" if col.primary_key or not col.nullable else " DEFAULT NULL"
                        default_clause = ""
                        if col.server_default is not None:
                            default_clause = f" DEFAULT {col.server_default.arg}"
                        elif col.default is not None:
                            default_clause = f" DEFAULT '{col.default.arg}'"
                        elif not col.primary_key and col.nullable:
                            default_clause = " DEFAULT NULL"
                        sql = f"ALTER TABLE {table.name} ADD COLUMN {col.name} {col_type}{default_clause}"
                        logger.info(f"Adding missing column: {sql}")
                        try:
                            cursor.execute(sql)
                        except Exception as e:
                            logger.warning(f"Failed to add column {table.name}.{col.name}: {e}")
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Schema migration check failed: {e}")

T = TypeVar("T")


@contextmanager
def get_db() -> Any:
    """获取数据库会话的上下文管理器"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error("database error", error=str(e))
        db.rollback()
        raise
    finally:
        db.close()


class BaseRepository:
    """仓储基类"""

    def __init__(self, db: Session | None = None):
        self._db = db

    @property
    def db(self) -> Session:
        """获取数据库会话"""
        if self._db is None:
            raise RuntimeError("No database session available")
        return self._db

    @db.setter
    def db(self, value: Session) -> None:
        self._db = value
