"""跨平台应用数据路径解析。

集中管理 Research Workbench 在不同操作系统下的数据目录约定，避免各模块
各自内联实现导致路径分叉（历史上有 ``APPDATA`` 与 ``LOCALAPPDATA``
混用的情况）。

约定：
- Windows: ``%LOCALAPPDATA%/Research Workbench``（机器本地，不随配置漫游）
- macOS:   ``~/Library/Application Support/Research Workbench``
- Linux:   ``$XDG_DATA_HOME/Research Workbench``（默认 ``~/.local/share/Research Workbench``）

所有路径均可被环境变量 ``RESEARCH_DESKTOP_DATA_DIR`` 整体覆盖。
"""

from __future__ import annotations

import logging
import os
import platform
from pathlib import Path

logger = logging.getLogger(__name__)

_APP_DIR_NAME = "Research Workbench"

# 允许整体覆盖应用数据根目录（与 core/settings/config.py 保持一致）
_DATA_DIR_OVERRIDE_ENV = "RESEARCH_DESKTOP_DATA_DIR"


def app_data_dir(roaming: bool = False) -> Path:
    """返回当前平台下的 Research Workbench 应用数据根目录。

    Args:
        roaming: 仅 Windows 生效。``True`` 使用 ``%APPDATA%``（随配置漫游），
            ``False`` 使用 ``%LOCALAPPDATA%``（机器本地，默认）。

    Returns:
        平台规范的应用数据目录 ``Path``。目录不保证已存在，调用方按需创建。
    """
    override = os.environ.get(_DATA_DIR_OVERRIDE_ENV)
    if override:
        return Path(override).expanduser()

    system = platform.system()
    if system == "Windows":
        env_var = "APPDATA" if roaming else "LOCALAPPDATA"
        fallback = Path.home() / "AppData" / ("Roaming" if roaming else "Local")
        base = Path(os.environ.get(env_var, fallback))
        return base / _APP_DIR_NAME
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / _APP_DIR_NAME
    # Linux 及其它类 Unix
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / _APP_DIR_NAME


def wind_workbook_dir() -> Path:
    """Wind 实时工作簿所在目录。"""
    return app_data_dir(roaming=False) / "wind"


def default_wind_workbook_path() -> Path:
    """Wind 实时工作簿默认路径。"""
    return wind_workbook_dir() / "Research Workbench_Wind_Realtime.xlsx"


def default_market_sector_cache_path() -> Path:
    """板块异动磁盘缓存默认路径。"""
    return app_data_dir(roaming=False) / "cache" / "market_sector_movers.json"


def legacy_macos_style_wind_workbook_path() -> Path:
    """旧的 macOS 风格工作簿路径（仅用于迁移检测）。

    历史版本将工作簿放在 ``~/Library/Application Support/Research Workbench/wind/``
    下，在 Windows 上会被解析到 ``C:\\Users\\<user>\\Library\\...`` 这种
    非规范目录。本函数返回该旧路径，供迁移逻辑检测并搬移到规范位置。
    """
    return (
        Path.home()
        / "Library"
        / "Application Support"
        / _APP_DIR_NAME
        / "wind"
        / "Research Workbench_Wind_Realtime.xlsx"
    )


def migrate_legacy_wind_workbook(target: Path) -> bool:
    """若旧 macOS 风格路径存在工作簿而目标路径不存在，则复制过去。

    工作簿是 ``wind_index_catalog.csv`` 的生成产物，即便不迁移也能由
    ``build_realtime_workbook()`` 重建，但重建后需要重新 prime Wind 公式
    （耗时数分钟）。迁移可省去这一步。

    Returns:
        ``True`` 表示执行了复制，``False`` 表示无需迁移。
    """
    try:
        legacy = legacy_macos_style_wind_workbook_path()
        if not legacy.exists() or target.exists():
            return False
        target.parent.mkdir(parents=True, exist_ok=True)
        import shutil

        shutil.copy2(legacy, target)
        logger.info(
            "Migrated legacy wind workbook: %s -> %s",
            legacy,
            target,
        )
        return True
    except OSError as exc:
        logger.warning("Failed to migrate legacy wind workbook to %s: %s", target, exc)
        return False
