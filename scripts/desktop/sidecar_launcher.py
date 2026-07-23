"""
AlphaFoundry Sidecar Launcher
==============================
极简桥接器：找到项目源码的 Python，然后 exec backend_launcher.py。

此文件只使用 Python 标准库，打包后（约 300KB）永久稳定，
改项目源码后不需要重新打包 sidecar exe。

路径解析优先级：
  项目根目录：ALPHAFOUNDRY_PROJECT_ROOT 环境变量
            > exe 同级目录的 project_root.txt
            > 硬编码默认值 D:/Projects/AlphaFoundry
  Python 路径：ALPHAFOUNDRY_PYTHON 环境变量
            > USERPROFILE/AppData/Local/anaconda3/envs/alphafoundry/python.exe
            > HOME/AppData/Local/anaconda3/envs/alphafoundry/python.exe
            > USERPROFILE/anaconda3/envs/alphafoundry/python.exe
            > shutil.which("python3") / which("python")
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def _find_project_root() -> Path:
    """定位项目根目录。"""
    env_root = os.environ.get("ALPHAFOUNDRY_PROJECT_ROOT")
    if env_root:
        return Path(env_root)

    # exe 同级目录的 project_root.txt（安装时由 installer 写入）
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
    else:
        exe_dir = Path(__file__).parent

    hint_file = exe_dir / "project_root.txt"
    if hint_file.exists():
        root = Path(hint_file.read_text(encoding="utf-8").strip())
        if root.exists():
            return root

    # 硬编码默认值
    return Path("D:/Projects/AlphaFoundry")


def _find_python() -> str:
    """按优先级找 conda alphafoundry 环境的 Python。"""
    userprofile = os.environ.get("USERPROFILE", "")
    home = os.environ.get("HOME", "")

    candidates = [
        os.environ.get("ALPHAFOUNDRY_PYTHON"),
        str(Path(userprofile) / "AppData/Local/anaconda3/envs/alphafoundry/python.exe"),
        str(Path(home) / "AppData/Local/anaconda3/envs/alphafoundry/python.exe"),
        str(Path(userprofile) / "anaconda3/envs/alphafoundry/python.exe"),
        str(Path(home) / "anaconda3/envs/alphafoundry/python.exe"),
    ]

    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate

    # fallback：系统 PATH 里的 python
    return shutil.which("python3") or shutil.which("python") or sys.executable


def main() -> None:
    project_root = _find_project_root()
    python_bin = _find_python()

    # 告知 backend_launcher.py 项目在哪里
    os.environ["ALPHAFOUNDRY_PROJECT_ROOT"] = str(project_root)

    launcher = str(project_root / "scripts" / "desktop" / "backend_launcher.py")

    # Windows 上 os.execv 不真正替换进程（会退出导致 Tauri 认为 sidecar 崩溃）
    # 改用 subprocess.run 同步等待子进程结束，保持本进程存活
    import subprocess

    result = subprocess.run(
        [python_bin, launcher] + sys.argv[1:],
        env=os.environ.copy(),
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
