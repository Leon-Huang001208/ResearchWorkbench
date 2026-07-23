#!/usr/bin/env python3
"""
修正事件时间为历史日期，这样 AKShare 能获取到价格数据
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_layer.repositories.base import SessionLocal
from data_layer.repositories.models import CanonicalEvent


def main():
    """修正事件时间"""
    db = SessionLocal()
    try:
        events = db.query(CanonicalEvent).all()

        # 把事件时间设置为 2024 年的历史日期
        base_date = datetime(2024, 5, 1, tzinfo=timezone.utc)

        for i, event in enumerate(events):
            event_time = base_date + timedelta(days=i)
            event.event_time = event_time
            # 同时更新 created_at 保持一致
            event.created_at = event_time

        db.commit()
        print(f"Fixed {len(events)} events with historical dates")

        # 打印修正后的事件
        print("\nUpdated events:")
        events = db.query(CanonicalEvent).order_by(CanonicalEvent.event_time).all()
        for event in events:
            print(f"  [{event.event_time.date()}] {event.event_type}: {event.summary[:40]}...")

        return 0

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
        return 1

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
