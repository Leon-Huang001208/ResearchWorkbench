#!/usr/bin/env python3
"""
修正事件的 subject_ids 为 AKShare 能获取的股票代码
"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_layer.repositories.base import SessionLocal
from data_layer.repositories.models import CanonicalEvent


def main():
    """修正事件数据"""
    db = SessionLocal()
    try:
        events = db.query(CanonicalEvent).all()

        for i, event in enumerate(events):
            current_payload = event.payload or {}

            # 直接设置明确的股票代码
            if event.event_type == "earnings":
                current_payload["subject_ids"] = ["600519.SH"]  # 贵州茅台
            elif event.event_type == "policy":
                current_payload["subject_ids"] = ["000001.SZ"]  # 平安银行
            elif event.event_type == "industry":
                if "新能源" in event.summary or "比亚迪" in event.summary:
                    current_payload["subject_ids"] = ["002594.SZ"]  # 比亚迪
                else:
                    current_payload["subject_ids"] = ["601012.SH"]  # 隆基绿能

            event.payload = current_payload

        db.commit()
        print(f"Fixed {len(events)} events")

        # 打印修正后的事件
        print("\nFinal events:")
        events = db.query(CanonicalEvent).all()
        for event in events:
            print(f"  [{event.event_type}] {event.summary[:30]}... "
                  f"→ {event.payload.get('subject_ids', [])}")

        return 0

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
        return 1

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
