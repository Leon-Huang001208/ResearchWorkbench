#!/usr/bin/env python3
"""
补充事件的 subject_ids，让它们能生成信号
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_layer.repositories.base import SessionLocal
from data_layer.repositories.models import CanonicalEvent


def main():
    """补充事件数据"""
    db = SessionLocal()
    try:
        events = db.query(CanonicalEvent).all()
        print(f"Found {len(events)} events")

        # 为每个事件补充合理的 subject_ids
        updates = []

        for event in events:
            current_payload = event.payload or {}

            if event.event_type == "earnings":
                # 茅台
                current_payload["subject_ids"] = ["600519.SH"]
            elif event.event_type == "policy":
                # 上证指数
                current_payload["subject_ids"] = ["000001.SH"]
            elif event.event_type == "industry":
                if "新能源" in event.summary or "比亚迪" in event.summary:
                    current_payload["subject_ids"] = ["002594.SZ"]
                elif "光伏" in event.summary:
                    current_payload["subject_ids"] = ["601012.SH"]
                else:
                    current_payload["subject_ids"] = ["000001.SH"]

            event.payload = current_payload
            updates.append(event.event_id)

        db.commit()
        print(f"Updated {len(updates)} events with subject_ids")

        # 打印更新后的事件
        print("\nUpdated events:")
        events = db.query(CanonicalEvent).all()
        for event in events:
            print(
                f"  [{event.event_type}] {event.event_id}: "
                f"{event.payload.get('subject_ids', [])}"
            )

        return 0

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
        return 1

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
