#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知丘爬取基类模块

提供统一的基类，消除 report.py、news.py、meeting.py 之间的重复代码。
"""
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type, cast

from .account_manager import AccountManager
from .client import ZhiQiuClient
from .ejection_detector import AccountEjectionDetector, DetectionConfig
from .progress_tracker import ProgressStateManager

# 昨天日期作为默认值
YESTERDAY = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")


class BaseStateManager:
    """
    状态管理基类 - 处理持久化去重
    """

    def __init__(self, state_path: str, processed_key: str, verbose: bool = False):
        """
        初始化状态管理器

        Args:
            state_path: 状态文件路径
            processed_key: 存储已处理记录的键名（如 'processed_reports'）
            verbose: 是否显示详细输出
        """
        self.state_path = Path(state_path)
        self.processed_key = processed_key
        self.verbose = verbose
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        if self.state_path.exists():
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    state = cast(Dict[str, Any], json.load(f))
                    if "watermarks" not in state:
                        state["watermarks"] = {}
                    return state
            except Exception as e:
                if self.verbose:
                    print(f"[warn] 读取状态文件失败: {e}，使用空状态")
        return self._get_default_state()

    def _get_default_state(self) -> Dict[str, Any]:
        return {
            "version": "1.0",
            "last_updated": datetime.now().isoformat(),
            self.processed_key: {},
            "watermarks": {},  # {key: {"last_seen_id": "...", "last_seen_at": "..."}}
        }

    def save(self) -> None:
        self.state["last_updated"] = datetime.now().isoformat()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def is_report_processed(self, obj_id: str) -> bool:
        return obj_id in self.state[self.processed_key]

    def add_processed_report(self, obj_id: str, title: str, **extra: Any) -> None:
        record = {"first_seen": datetime.now().isoformat(), "title": title, **extra}
        self.state[self.processed_key][obj_id] = record

    def get_processed_count(self) -> int:
        return len(self.state[self.processed_key])

    # ============================================================
    # 水位线追踪功能
    # ============================================================

    def set_watermark(self, key: str, obj_id: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """设置水位线"""
        watermark = {
            "last_seen_id": str(obj_id),
            "last_seen_at": datetime.now().isoformat(),
        }
        if extra:
            watermark.update(extra)
        self.state["watermarks"][key] = watermark
        self.save()

    def get_watermark(self, key: str) -> Optional[Dict[str, Any]]:
        """获取水位线"""
        watermarks = cast(Dict[str, Dict[str, Any]], self.state["watermarks"])
        return watermarks.get(key)

    def has_reached_watermark(self, key: str, obj_id: str) -> bool:
        """检查是否已达到水位线"""
        watermark = self.get_watermark(key)
        if not watermark:
            return False
        return str(obj_id) == watermark.get("last_seen_id")

    def clear_watermark(self, key: str) -> None:
        """清除指定的水位线"""
        if key in self.state["watermarks"]:
            del self.state["watermarks"][key]
            self.save()


@dataclass
class BaseConfig:
    """
    配置基类 - 包含通用配置项
    """

    # 基础配置
    config_path: str = ""
    starttime: str = ""
    endtime: str = ""
    search: str = ""
    output_dir: str = "./output"
    verbose: bool = True
    state_path: Optional[str] = None
    skip_existing: bool = True
    stop_on_known: bool = True  # 遇到已处理记录时停止抓取（增量模式）

    # 搜索接口配置
    use_homepage_search: bool = True
    date_limit: str = ""
    doc_type: str = ""  # 如 "REPORT", "NEWS", "ZQMEETING"
    page: int = 1
    page_size: int = 100
    fetch_all_pages: bool = True
    max_pages: int = 20

    # 账号切换配置
    rotate_account_per_request: bool = True

    # 模块标识（用于日志和状态管理）
    module_name: str = ""
    module_label: str = ""
    processed_key: str = ""

    # 从配置文件加载的原始数据
    _raw_config: Dict = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if not self.starttime:
            self.starttime = YESTERDAY
        if not self.endtime:
            self.endtime = YESTERDAY


class BaseFetcher:
    """
    爬取器基类 - 包含通用逻辑
    """

    def __init__(self, config: Optional[BaseConfig] = None):
        self.config = config or BaseConfig()
        self._initialized = False
        self._client: Optional[ZhiQiuClient] = None
        self._logger: Optional[logging.Logger] = None
        self._state_manager: Optional[BaseStateManager] = None

        if self.config.state_path and self.config.processed_key:
            try:
                self._state_manager = BaseStateManager(
                    self.config.state_path, self.config.processed_key, self.config.verbose
                )
                if self.config.verbose:
                    print(f"[init] 状态管理器已初始化，已记录 {self._state_manager.get_processed_count()} 条记录")
            except Exception as e:
                if self.config.verbose:
                    print(f"[warn] 初始化状态管理器失败: {e}，持久化去重将不可用")

        self._account_manager: Optional[AccountManager] = None
        self._progress_manager: Optional[ProgressStateManager] = None
        self._ejection_detector: Optional[AccountEjectionDetector] = None

    def initialize(self) -> bool:
        self._setup_logging()

        if self._logger:
            self._logger.info(f"初始化 {self.config.module_label}爬取器")
        elif self.config.verbose:
            print(f"[init] 初始化 {self.config.module_label}爬取器")

        if self.config.config_path:
            self._load_config_file()

        self._init_advanced_components()
        self._initialized = True
        return True

    def _init_advanced_components(self) -> None:
        cfg = self.config._raw_config

        try:
            if self.config.config_path:
                self._account_manager = AccountManager(
                    self.config.config_path, module_identifier=self.config.module_name
                )
                if self._logger:
                    self._logger.info("账号管理器已初始化")
        except Exception as e:
            if self._logger:
                self._logger.warning(f"初始化账号管理器失败: {e}")

        try:
            progress_cfg = cfg.get("progress_tracking", {})
            if progress_cfg.get("enabled", True):
                state_file = progress_cfg.get("state_file", "./progress_state.json")
                if self.config.config_path and not os.path.isabs(state_file):
                    state_file = os.path.join(os.path.dirname(self.config.config_path), state_file)
                self._progress_manager = ProgressStateManager(
                    state_file=state_file,
                    auto_save=progress_cfg.get("enabled", True),
                    save_interval=progress_cfg.get("save_interval", 10),
                )
                if self._logger:
                    self._logger.info("进度追踪器已初始化")
        except Exception as e:
            if self._logger:
                self._logger.warning(f"初始化进度追踪器失败: {e}")

        try:
            eject_cfg = cfg.get("ejection_detection", {})
            detection_config = DetectionConfig()
            if "check_responses" in eject_cfg:
                detection_config.check_responses = eject_cfg["check_responses"]
            if "error_keywords" in eject_cfg:
                detection_config.error_keywords = eject_cfg["error_keywords"]
            if "max_consecutive_errors" in eject_cfg:
                detection_config.max_consecutive_errors = eject_cfg["max_consecutive_errors"]
            self._ejection_detector = AccountEjectionDetector(detection_config)
            if self._logger:
                self._logger.info("顶出检测器已初始化")
        except Exception as e:
            if self._logger:
                self._logger.warning(f"初始化顶出检测器失败: {e}")

    def _load_config_file(self) -> None:
        try:
            import yaml

            with open(self.config.config_path, "r", encoding="utf-8") as f:
                self.config._raw_config = cast(Dict[str, Any], yaml.safe_load(f) or {})

            # config.yaml 只负责提供：
            # 1. 账号凭证 (accounts)
            # 2. 账号轮换配置 (account_rotation)
            # 3. 进度追踪配置 (progress_tracking)
            # 4. 顶出检测配置 (ejection_detection)
            #
            # 搜索相关配置完全由各模块的默认值和参数控制，不从 config.yaml 加载
            # 这样确保 zq.py 和独立模块的配置逻辑统一

        except ImportError:
            if self.config.verbose:
                print("[warn] pyyaml not installed, skipping config file")
        except Exception as e:
            if self.config.verbose:
                print(f"[warn] config file load failed: {e}")

    def _setup_logging(self) -> None:
        if self._logger is not None and self._logger.handlers:
            return

        log_dir = Path(self.config.output_dir) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{self.config.module_name}_{self.config.starttime}.log"

        self._logger = logging.getLogger(self.config.module_name)
        self._logger.setLevel(logging.INFO)

        if not self._logger.handlers:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            console_handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            self._logger.addHandler(file_handler)
            self._logger.addHandler(console_handler)
            self._logger.propagate = False

    def _login(self, credentials: Dict[str, Any], account_name: Optional[str] = None) -> bool:
        username = credentials.get("username")
        password = credentials.get("password")

        if account_name and self._logger:
            self._logger.info(f"使用账号: {account_name} ({username})")

        if not username or not password:
            if self._logger:
                self._logger.error("缺少账号凭证")
            return False

        self._client = ZhiQiuClient(username, password)
        return bool(self._client.login())

    def _test_login(self) -> bool:
        if not self._client:
            return False
        result = self._client.check_login_status()
        return bool(result.get("success", False))

    def _handle_account_ejection(self, current_account: str) -> Optional[str]:
        account_manager = self._account_manager
        if not account_manager:
            if self._logger:
                self._logger.error("账号管理器未初始化，无法切换账号")
            return None

        if self._logger:
            self._logger.warning("检测到账号被顶出，尝试切换账号...")

        account_manager.record_failure(current_account, lock_seconds=300)
        account_manager.release_account(current_account)

        accounts = self.config._raw_config.get("accounts", {})
        max_attempts = len(accounts) if accounts else 3

        for attempt in range(max_attempts):
            next_account = account_manager.acquire_account()
            if not next_account:
                if self._logger:
                    self._logger.error("没有更多可用账号")
                return None

            if self._logger:
                self._logger.info(f"尝试切换到账号: {next_account} (尝试 {attempt + 1}/{max_attempts})")

            credentials = account_manager.get_account_credentials(next_account)
            if credentials is None or not self._login(credentials, next_account):
                if self._logger:
                    self._logger.warning(f"账号 {next_account} 登录失败")
                account_manager.record_failure(next_account, lock_seconds=60)
                account_manager.release_account(next_account)
                continue

            if self._test_login():
                if self._logger:
                    self._logger.info(f"账号 {next_account} 登录成功")
                account_manager.record_success(next_account)

                if self._progress_manager:
                    self._progress_manager.update_last_account(next_account)

                if self._ejection_detector:
                    self._ejection_detector.reset()

                return str(next_account)

            if self._logger:
                self._logger.warning(f"账号 {next_account} 也无法使用")
            account_manager.release_account(next_account)

        if self._logger:
            self._logger.error("所有账号都无法使用")
        return None

    def _log_feature_status(self) -> None:
        if not self._logger:
            return
        self._logger.info("=" * 50)
        self._logger.info(f"{self.config.module_label}爬取配置:")
        self._logger.info(f"  - 日期限制: {self.config.date_limit or '未设置'}")
        self._logger.info(f"  - 文档类型: {self.config.doc_type}")
        if self._state_manager:
            self._logger.info(f"  - 持久化去重: 启用 (已记录 {self._state_manager.get_processed_count()} 条)")
        else:
            self._logger.info("  - 持久化去重: 关闭")
        if self._account_manager:
            self._logger.info("  - 账号管理: 启用")
        if self._progress_manager:
            self._logger.info("  - 进度追踪: 启用")
        if self._ejection_detector:
            self._logger.info("  - 顶出检测: 启用")
        self._logger.info("=" * 50)

    def fetch(self, **kwargs: Any) -> Dict[str, Any]:
        if not self._initialized:
            self.initialize()

        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

        if "state_path" in kwargs and self.config.processed_key:
            self._state_manager = None
            if self.config.state_path:
                try:
                    self._state_manager = BaseStateManager(
                        self.config.state_path, self.config.processed_key, self.config.verbose
                    )
                    if self.config.verbose:
                        print(
                            f"[init] 状态管理器已初始化，已记录 {self._state_manager.get_processed_count()} 条记录"
                        )
                except Exception as e:
                    if self.config.verbose:
                        print(f"[warn] 初始化状态管理器失败: {e}，持久化去重将不可用")

        if self.config.verbose and not self._logger:
            print(f"[start] 开始爬取{self.config.module_label}: {self.config.search or '全部'}")

        if self._logger:
            self._logger.info(f"开始爬取{self.config.module_label}: {self.config.search or '全部'}")

        account_manager = self._account_manager
        if not account_manager:
            return {"success": False, "message": "账号管理器未初始化", "errors": ["需要配置文件以使用账号管理"]}

        return self._fetch_with_account_lease(account_manager)

    def _fetch_with_account_lease(self, account_manager: AccountManager) -> Dict[str, Any]:
        results: Dict[str, Any] = {
            "success": True,
            "message": "",
            "terms": [],
            "output_dir": self.config.output_dir,
            "errors": [],
            "skipped_existing": 0,
            "total": 0,
            "new": 0,
        }

        all_new_items: List[Dict[str, Any]] = []
        leased_account: Optional[str] = None

        try:
            leased_account = account_manager.acquire_account()
            if not leased_account:
                return {"success": False, "message": "获取账号失败", "errors": ["没有可用的账号"]}

            login_success = False
            for attempt in range(3):
                credentials = account_manager.get_account_credentials(leased_account)
                if credentials is not None and self._login(credentials, leased_account):
                    login_success = True
                    account_manager.record_success(leased_account)
                    break
                if self._logger:
                    self._logger.warning(f"登录失败，尝试切换账号 (尝试 {attempt + 1}/3)")
                account_manager.record_failure(leased_account, lock_seconds=60)
                account_manager.release_account(leased_account)
                leased_account = account_manager.acquire_account()
                if not leased_account:
                    break

            if not login_success:
                return {"success": False, "message": "登录失败", "errors": ["无法登录知丘平台，请检查凭证"]}

            self._log_feature_status()

            search_val = self.config.search or ""
            if isinstance(search_val, str):
                search_terms = [s.strip() for s in search_val.split(",") if s.strip()]
            else:
                search_terms = []
            if not search_terms:
                search_terms = [""]

            for i, term in enumerate(search_terms, 1):
                term_name = term if term else "全部"
                if self._logger:
                    self._logger.info(f"进度: {i}/{len(search_terms)} - {term_name}")

                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        if self.config.rotate_account_per_request and i > 1:
                            new_account = account_manager.acquire_account()
                            if new_account and new_account != leased_account:
                                if leased_account:
                                    account_manager.release_account(leased_account)
                                leased_account = new_account
                                credentials = account_manager.get_account_credentials(
                                    leased_account
                                )
                                if credentials is None or not self._login(
                                    credentials, leased_account
                                ):
                                    if self._logger:
                                        self._logger.warning("账号切换后登录失败")
                                    continue

                        term_result, new_items = self._fetch_single_term(term)
                        results["terms"].append(term_result)
                        results["total"] += term_result.get("count", 0)
                        results["skipped_existing"] += term_result.get("skipped_existing", 0)
                        results["new"] += term_result.get("new", 0)
                        all_new_items.extend(new_items)
                        break
                    except Exception as e:
                        if self._ejection_detector and self._ejection_detector.check_response(
                            exception=e
                        ):
                            if self._logger:
                                self._logger.warning(f"检测到账号被顶出 (处理 '{term_name}' 时)")
                            if leased_account is None:
                                break
                            new_account = self._handle_account_ejection(leased_account)
                            if new_account:
                                leased_account = new_account
                                if self._logger:
                                    self._logger.info(
                                        f"账号切换成功，重试处理 '{term_name}' (尝试 {attempt + 1}/{max_retries})"
                                    )
                                continue
                            if self._logger:
                                self._logger.error(f"无法切换账号，终止处理 '{term_name}'")
                            results["terms"].append(
                                {"term": term_name, "status": "error", "error": "无法切换账号"}
                            )
                            results["errors"].append(f"{term_name}: 无法切换账号")
                            break
                        else:
                            if self._logger:
                                self._logger.error(f"处理 '{term_name}' 时出错: {e}")
                            results["terms"].append(
                                {"term": term_name, "status": "error", "error": str(e)}
                            )
                            results["errors"].append(f"{term_name}: {str(e)}")
                            break

            if self._state_manager and all_new_items:
                if self.config.verbose:
                    print(f"[state] 正在记录 {len(all_new_items)} 条记录到状态文件...")
                for item in all_new_items:
                    obj_id = item.get("OBJID") or item.get("id")
                    if obj_id is None:
                        continue
                    title = str(item.get("title", ""))
                    self._save_processed_item(str(obj_id), title, item)
                self._state_manager.save()
                if self.config.verbose:
                    print(f"[state] 状态文件已更新，共记录 {self._state_manager.get_processed_count()} 条记录")

            success_count = sum(1 for t in results["terms"] if t.get("status") == "success")
            results[
                "message"
            ] = f'完成: 成功 {success_count}/{len(search_terms)}，共 {results["total"]} 条{self.config.module_label} (新: {results["new"]}，跳过: {results["skipped_existing"]})'

            if self.config.verbose:
                print(f"[done] {results['message']}")

            return results

        finally:
            if leased_account and self._account_manager:
                account_manager.release_account(leased_account)

    # 以下为子类需要重写的钩子方法

    def _save_processed_item(self, obj_id: str, title: str, item: Dict[str, Any]) -> None:
        """
        保存已处理项目的钩子方法，子类可重写以保存额外字段

        Args:
            obj_id: 项目 ID
            title: 项目标题
            item: 完整项目数据
        """
        if self._state_manager:
            self._state_manager.add_processed_report(obj_id, title)

    def _search_homepage(
        self, search_term: str, hyper_search_fields: str = "title"
    ) -> Optional[Dict[str, Any]]:
        """
        通用的首页搜索方法

        Args:
            search_term: 搜索词
            hyper_search_fields: 搜索字段

        Returns:
            搜索结果 JSON 数据
        """
        if self._client is None:
            return None

        if self.config.fetch_all_pages:
            if self.config.date_limit == "CUSTOM":
                return cast(
                    Dict[str, Any],
                    self._client.search_homepage_all_pages(
                        search=search_term,
                        date_limit=self.config.date_limit,
                        start_date=self.config.starttime,
                        end_date=self.config.endtime,
                        doc_types=self.config.doc_type,
                        page_size=self.config.page_size,
                        hyper_search_fields=hyper_search_fields,
                        sort_by_time=True,
                        max_pages=self.config.max_pages,
                    ),
                )
            else:
                return cast(
                    Dict[str, Any],
                    self._client.search_homepage_all_pages(
                        search=search_term,
                        date_limit=self.config.date_limit,
                        doc_types=self.config.doc_type,
                        page_size=self.config.page_size,
                        hyper_search_fields=hyper_search_fields,
                        sort_by_time=True,
                        max_pages=self.config.max_pages,
                    ),
                )
        else:
            if self.config.date_limit == "CUSTOM":
                return cast(
                    Dict[str, Any],
                    self._client.search_homepage(
                        search=search_term,
                        date_limit=self.config.date_limit,
                        start_date=self.config.starttime,
                        end_date=self.config.endtime,
                        doc_types=self.config.doc_type,
                        page=self.config.page,
                        page_size=self.config.page_size,
                        hyper_search_fields=hyper_search_fields,
                        sort_by_time=True,
                    ),
                )
            else:
                return cast(
                    Dict[str, Any],
                    self._client.search_homepage(
                        search=search_term,
                        date_limit=self.config.date_limit,
                        doc_types=self.config.doc_type,
                        page=self.config.page,
                        page_size=self.config.page_size,
                        hyper_search_fields=hyper_search_fields,
                        sort_by_time=True,
                    ),
                )

    def _process_search_result(
        self,
        json_data: Dict[str, Any],
        processor_class: Type[Any],
        output_prefix: str,
        watermark_key: Optional[str] = None,
        **processor_kwargs: Any,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        通用的搜索结果处理方法

        Args:
            json_data: 搜索结果
            processor_class: 处理器类
            output_prefix: 输出文件前缀
            watermark_key: 水位线标识键
            **processor_kwargs: 处理器额外参数

        Returns:
            (term_result_dict, new_items_list)
        """
        if not json_data:
            return {
                "term": self.config.search or "全部",
                "status": "failed",
                "error": "获取数据失败",
                "count": 0,
                "skipped_existing": 0,
                "new": 0,
            }, []

        output_json = os.path.join(
            self.config.output_dir, f"{output_prefix}_{self.config.starttime}.json"
        )
        os.makedirs(self.config.output_dir, exist_ok=True)

        processor = processor_class(self._client)
        df, new_items, skipped_count, _ = processor.process(
            json_data,
            output_json,
            state_manager=self._state_manager,
            skip_existing=self.config.skip_existing,
            stop_on_known=self.config.stop_on_known,
            watermark_key=watermark_key,
            **processor_kwargs,
        )

        return {
            "term": self.config.search or "全部",
            "status": "success",
            "count": len(df),
            "output_file": output_json,
            "skipped_existing": skipped_count,
            "new": len(new_items),
        }, new_items

    def _fetch_single_term(self, search_term: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        获取单个搜索词的结果，必须由子类重写

        Args:
            search_term: 搜索词

        Returns:
            (term_result_dict, new_items_list)
        """
        raise NotImplementedError("_fetch_single_term must be implemented by subclass")
