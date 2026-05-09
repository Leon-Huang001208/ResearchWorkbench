#!/usr/bin/env python3
"""
重置演示数据
"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from data_layer.repositories.base import SessionLocal


def main():
    """重置演示"""
    db = SessionLocal()
    try:
        print("Deleting existing signals and outcomes...")
        db.execute(text("DELETE FROM signal_outcome"))
        db.execute(text("DELETE FROM alpha_signal"))
        db.commit()

        print("✅ Demo reset complete!")

        return 0

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
        return 1

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
