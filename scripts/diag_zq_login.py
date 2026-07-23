"""知丘账号登录诊断脚本（一次性运维工具）。

用途
----
当知丘数据源爬取全部失败、账号被 AccountManager 永久禁用时，用本脚本逐账号
实跑一次 ``ZhiQiuClient.login()``，分步骤打印卡点，定位是「密码错 / 账号被封」
还是「平台接口变更 / 网络 / 代理」问题。

安全说明
--------
- 只读：不写任何业务数据，不改账号状态文件。
- 复用 ``ZhiQiuClient`` 真实登录逻辑，会对知丘平台发起真实 HTTP 请求。
- 失败响应体保存到 ``logs/diag_zq_login_failed_<account>.html`` 供排查。

用法
----
    python scripts/diag_zq_login.py

依赖 ``.env`` 中的 ``ZQ_ACCOUNTS_JSON``。
"""

from __future__ import annotations

import json
import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# 确保项目根目录在 sys.path，便于 import 项目内模块
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# 加载 .env（与运行时一致）
try:
    from core.settings.config import load_dotenv  # type: ignore

    load_dotenv()
except Exception:
    # 兜底：用 python-dotenv 直接加载
    try:
        from dotenv import load_dotenv as _load_dotenv  # type: ignore

        _load_dotenv(_PROJECT_ROOT / ".env")
    except Exception:
        pass

from data_layer.crawlers.zq.zhiqiu.account_manager import AccountManager  # noqa: E402
from data_layer.crawlers.zq.zhiqiu.client import ZhiQiuClient  # noqa: E402

LOG_DIR = _PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
_LOG_FILE = LOG_DIR / f"diag_zq_login_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(_LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("diag_zq_login")


def load_accounts() -> Dict[str, Dict[str, str]]:
    """复用 AccountManager 的环境变量账号加载逻辑。"""
    accounts = AccountManager._load_accounts_from_env()
    if not accounts:
        logger.error("未加载到任何知丘账号，请检查 .env 中的 ZQ_ACCOUNTS_JSON")
    return accounts


def diagnose_one(account_name: str, creds: Dict[str, str]) -> Dict[str, Any]:
    """对单个账号分步诊断登录。

    返回结构化结果，便于汇总。所有异常都捕获，保证单账号失败不影响其他账号。
    """
    username = creds.get("username", "")
    password = creds.get("password", "")
    result: Dict[str, Any] = {
        "account": account_name,
        "username": username,
        "steps": {},
        "login_ok": False,
        "error": None,
    }

    if not username or not password:
        result["error"] = "账号缺少 username 或 password"
        logger.error(f"[{account_name}] {result['error']}")
        return result

    client = ZhiQiuClient(username, password)
    # 失败时 login() 会写 login_failed.html 到 cwd，重定向到 logs 避免污染
    failed_html = LOG_DIR / f"diag_zq_login_failed_{account_name}.html"
    original_cwd = Path.cwd()

    try:
        # 直接调用 login()，它内部已分步执行：首页取 cookie → loginPre.json 取公钥 → login.htm
        ok = client.login()
        result["login_ok"] = bool(ok)
        result["steps"]["final"] = "登录成功" if ok else "登录失败（未拿到 REPORT_SESSION_COOKIE）"
        if ok:
            logger.info(f"[{account_name}] ✅ 登录成功")
        else:
            logger.warning(f"[{account_name}] ❌ 登录失败，响应体见 {failed_html}")
            # login() 写的是 cwd 下的 login_failed.html，挪到 logs 并改名
            default_failed = original_cwd / "login_failed.html"
            if default_failed.exists():
                default_failed.replace(failed_html)
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        result["steps"]["exception"] = traceback.format_exc(limit=3)
        logger.error(f"[{account_name}] 登录抛异常: {e}", exc_info=True)

    return result


def main() -> int:
    logger.info("=" * 60)
    logger.info("知丘账号登录诊断开始")
    logger.info("=" * 60)

    accounts = load_accounts()
    if not accounts:
        return 1

    logger.info(f"共 {len(accounts)} 个账号待诊断：{list(accounts.keys())}")

    results: List[Dict[str, Any]] = []
    for name, creds in accounts.items():
        logger.info("-" * 40)
        results.append(diagnose_one(name, creds))

    # 汇总
    logger.info("=" * 60)
    logger.info("诊断汇总")
    logger.info("=" * 60)
    success = [r for r in results if r["login_ok"]]
    fail = [r for r in results if not r["login_ok"]]
    for r in results:
        status = "✅成功" if r["login_ok"] else "❌失败"
        extra = r.get("error") or r["steps"].get("final", "")
        logger.info(f"  {r['account']:16s} {status}  {extra}")
    logger.info(f"成功 {len(success)}/{len(results)}，失败 {len(fail)}/{len(results)}")

    if fail:
        logger.info("失败账号可能原因：密码错/账号被封/平台接口变更/网络代理问题。")
        logger.info("查看响应体：logs/diag_zq_login_failed_<account>.html")

    # 写结构化结果到 logs
    summary_path = LOG_DIR / f"diag_zq_login_summary_{datetime.now().strftime('%Y%m%d')}.json"
    try:
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(
                {"timestamp": datetime.now().isoformat(), "results": results},
                f,
                ensure_ascii=False,
                indent=2,
            )
        logger.info(f"结构化结果已写入 {summary_path}")
    except Exception as e:
        logger.error(f"写汇总文件失败: {e}")

    return 0 if not fail else 2


if __name__ == "__main__":
    sys.exit(main())
