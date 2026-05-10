"""去重存储工具模块"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class DeduplicationStore:
    """通用去重存储类"""

    def __init__(self, state_path: str):
        self.state_path = Path(state_path)
        self.state: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """加载状态文件"""
        if self.state_path.exists():
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    self.state = json.load(f)
            except Exception:
                self.state = {}

        if "processed_items" not in self.state:
            self.state["processed_items"] = {}

    def _save(self) -> None:
        """保存状态文件"""
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def is_processed(self, item_id: str) -> bool:
        """检查项目是否已处理"""
        return str(item_id) in self.state["processed_items"]

    def mark_processed(self, item_id: str, title: str = "", content_preview: str = "") -> None:
        """标记项目为已处理"""
        self.state["processed_items"][str(item_id)] = {
            "first_seen": datetime.now().isoformat(),
            "title": title[:100] if title else "",
            "content_preview": content_preview[:200] if content_preview else "",
        }
        self._save()

    def get_count(self) -> int:
        """获取已处理的项目数量"""
        return len(self.state["processed_items"])
