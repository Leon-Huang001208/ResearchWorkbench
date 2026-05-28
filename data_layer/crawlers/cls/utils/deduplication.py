"""去重存储工具模块"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


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
        if "watermarks" not in self.state:
            self.state["watermarks"] = {}

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

    # ============================================================
    # 水位线追踪功能
    # ============================================================

    def set_watermark(self, key: str, item_id: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """
        设置水位线 - 记录最后一次抓取时看到的 item_id

        Args:
            key: 水位线标识（如 source_type, channel 等）
            item_id: 最后看到的已存在的 item_id
            extra: 额外信息（可选）
        """
        watermark = {
            "last_seen_id": str(item_id),
            "last_seen_at": datetime.now().isoformat(),
        }
        if extra:
            watermark.update(extra)
        self.state["watermarks"][key] = watermark
        self._save()

    def get_watermark(self, key: str) -> Optional[Dict[str, Any]]:
        """
        获取水位线

        Args:
            key: 水位线标识

        Returns:
            水位线信息，如不存在返回 None
        """
        return self.state["watermarks"].get(key)

    def has_reached_watermark(self, key: str, item_id: str) -> bool:
        """
        检查是否已达到水位线

        Args:
            key: 水位线标识
            item_id: 当前检查的 item_id

        Returns:
            是否达到水位线（即当前 item_id 与记录的水位线相同）
        """
        watermark = self.get_watermark(key)
        if not watermark:
            return False
        return str(item_id) == watermark.get("last_seen_id")

    def remove_stale(self, valid_ids: set) -> int:
        """删除不在 valid_ids 中的已处理条目

        Args:
            valid_ids: 当前数据库中存在的 source_doc_id 集合

        Returns:
            int: 删除的条目数
        """
        stale = [k for k in self.state["processed_items"] if str(k) not in valid_ids]
        for k in stale:
            del self.state["processed_items"][k]
        if stale:
            self._save()
        return len(stale)

    def clear_watermark(self, key: str) -> None:
        """清除指定的水位线"""
        if key in self.state["watermarks"]:
            del self.state["watermarks"][key]
            self._save()

    def get_all_watermarks(self) -> Dict[str, Dict[str, Any]]:
        """获取所有水位线"""
        return self.state["watermarks"]
