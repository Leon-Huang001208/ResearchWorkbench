"""
初始化数据库
创建所有表
"""
import sys
from pathlib import Path

# 把项目根目录加入 path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_layer.repositories.base import Base, engine


def init_db():
    """初始化数据库"""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")


if __name__ == "__main__":
    init_db()
