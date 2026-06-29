from collections.abc import Generator
from types import TracebackType
from typing import TypeVar

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from core.observability import get_logger
from core.settings import settings

logger = get_logger(__name__)

# Create engine and session factory
engine = create_engine(settings.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Base class for ORM models
class Base(DeclarativeBase):
    """SQLAlchemy declarative base with mypy-visible type information."""

    pass


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


def ensure_schema() -> None:
    """Ensure database schema matches ORM models.

    For SQLite, first create all tables, then check and add missing columns (ALTER TABLE ADD COLUMN).
    """
    # Import all models to register to Base.metadata
    import data_layer.repositories.models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # For SQLite, check existing tables and add missing columns
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


def get_db() -> Generator[Session, None, None]:
    """Get database session for FastAPI dependency injection."""
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


def get_session() -> Session:
    """Return a raw SQLAlchemy session for scheduler and script compatibility."""
    return SessionLocal()


class db_session:
    """Database session context manager for direct use.

    Usage:
        with db_session() as db:
            ...
    """

    def __enter__(self) -> Session:
        self.db = SessionLocal()
        return self.db

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is None:
            self.db.commit()
        else:
            logger.error("database error", error=str(exc_val))
            self.db.rollback()
        self.db.close()


class BaseRepository:
    """Base repository class."""

    def __init__(self, db: Session | None = None):
        self._db = db

    @property
    def db(self) -> Session:
        """Get database session."""
        if self._db is None:
            raise RuntimeError("No database session available")
        return self._db

    @db.setter
    def db(self, value: Session) -> None:
        self._db = value
