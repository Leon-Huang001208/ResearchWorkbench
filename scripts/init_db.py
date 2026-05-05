
"""
初始化数据库
创建所有表
"""
from pathlib import Path

from data_layer.repositories.base import Base, engine
from data_layer.repositories.models import (
    Entity,
    SourceDocument,
    Assertion,
    CanonicalEvent,
    ReasoningTrace,
    AssetSnapshot,
)

def init_db():
    """初始化数据库"""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")

if __name__ == "__main__":
    init_db()
