"""connectors 测试目录配置."""
import sys
from pathlib import Path

# 确保项目根目录在 Python path 中
_project_root = Path(__file__).resolve().parents[4]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
