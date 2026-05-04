from contextlib import contextmanager
from typing import Any, List, Optional, TypeVar

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from core.observability import get_logger
from core.settings import settings

logger = get_logger(__name__)

# 创建引擎和会话工厂
engine = create_engine(settings.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 基类
Base = declarative_base()

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
