#!/usr/bin/env python3
"""
定时任务：每小时自动从已批准事件生成候选信号
"""
import sys
from core.services.event_auto_signal_generator import EventAutoSignalGenerator

def main():
    generator = EventAutoSignalGenerator()
    count = generator.process_approved_events()
    print(f"Auto generated {count} signals from approved events")
    return 0

if __name__ == "__main__":
    sys.exit(main())
