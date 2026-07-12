import json
import logging
import os
import re
from pathlib import Path
from types import TracebackType
from typing import Any, Dict, Optional, cast

import requests

from .anti_scrape import AntiScrapeConfig, AntiScrapeManager, get_manager
from .utils import rsa_encrypt

# HTTP 超时常量，防止 TCP 死连接导致无限阻塞
DEFAULT_TIMEOUT = 30
SEARCH_TIMEOUT = 60


class ZhiQiuClient:
    """知丘客户端：登录、研报搜索、AI问答、PDF下载"""

    TARGET_BROKERS = {
        "国金证券": "2",
        "申万宏源研究": "3",
        "招商证券": "4",
        "国泰海通": "7",
        "长江证券": "9",
        "光大证券": "13",
        "广发证券": "14",
        "华泰证券": "16",
        "平安证券": "21",
        "兴业证券": "24",
        "银河证券": "25",
        "中信证券": "26",
        "国信证券": "28",
        "东方证券": "29",
        "中信建投": "87",
        "中泰证券": "107",
        "国投证券": "109",
        "华福证券": "182",
        "天风证券": "193",
        "东方财富证券": "196",
        "野村东方国际": "505",
    }

    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
    BASE_URL = "https://www.kanzhiqiu.com"

    # AI 提问模板预设
    PROMPT_CORE_VIEWPOINT = "提取该研报的核心观点，分点列出"
    PROMPT_FOCUS_COMPANIES = "提取该研报中重点关注、推荐或分析的上市公司名称，列出股票代码和公司名称"
    PROMPT_SUMMARY = "提取该研报对{{search}}未来发展的核心预期与策略建议"

    def __init__(
        self,
        username: str,
        password: str,
        anti_scrape_config: Optional[AntiScrapeConfig] = None,
        request_timeout: float = DEFAULT_TIMEOUT,
        failure_dump_path: str | Path | None = "login_failed.html",
    ):
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.trust_env = False  # 禁用系统代理，避免 SSL EOF 错误
        self._logged_in = False
        self.request_timeout = request_timeout
        self.failure_dump_path = Path(failure_dump_path) if failure_dump_path is not None else None
        self.logger = logging.getLogger(__name__)
        # 反爬管理器
        self.anti_scrape: AntiScrapeManager = get_manager(anti_scrape_config)

    def login(self) -> bool:
        """RSA加密登录"""
        # 访问首页获取cookie
        self.anti_scrape.before_request(is_ai_request=False)
        headers = self.anti_scrape.get_headers({"user-agent": self.USER_AGENT})
        self.session.get(
            f"{self.BASE_URL}/newreport/index.htm", headers=headers, timeout=self.request_timeout
        )
        self.anti_scrape.after_success()

        # 获取RSA公钥
        self.anti_scrape.before_request(is_ai_request=False)
        headers = self.anti_scrape.get_headers(
            {
                "user-agent": self.USER_AGENT,
                "referer": f"{self.BASE_URL}/newreport/index.htm",
                "x-requested-with": "XMLHttpRequest",
            }
        )
        pre_resp = self.session.post(
            f"{self.BASE_URL}/user/loginPre.json", headers=headers, timeout=self.request_timeout
        )
        if pre_resp.status_code != 200:
            self.logger.error(f"loginPre.json 请求失败，状态码: {pre_resp.status_code}")
            return False

        pub_key_pem = pre_resp.text.strip()
        if not pub_key_pem:
            self.logger.error("loginPre.json 返回空内容")
            self.anti_scrape.after_failure()
            return False

        # RSA加密并登录
        login_data = {
            "signonForwardAction": "/newreport/index.htm",
            "login_submit": "1",
            "enc": "rsa",
            "username": rsa_encrypt(self.username, pub_key_pem),
            "password": rsa_encrypt(self.password, pub_key_pem),
            "username_f": "",
            "password_f": "",
            "j_captcha_response": "",
            "remember_name": "1",
            "btn_submit": "买方用户email方式登录成功",
        }

        self.anti_scrape.before_request(is_ai_request=False)
        headers = self.anti_scrape.get_headers(
            {
                "user-agent": self.USER_AGENT,
                "origin": self.BASE_URL,
                "referer": f"{self.BASE_URL}/newreport/index.htm",
                "content-type": "application/x-www-form-urlencoded",
            }
        )
        resp = self.session.post(
            f"{self.BASE_URL}/user/login.htm",
            data=login_data,
            headers=headers,
            allow_redirects=True,
            timeout=self.request_timeout,
        )

        if "REPORT_SESSION_COOKIE" in self.session.cookies:
            self.logger.info("登录成功")
            self._logged_in = True
            self.anti_scrape.after_success()
            return True

        if self.failure_dump_path is not None:
            self.logger.error("登录失败，响应已保存到诊断文件")
            self.failure_dump_path.write_text(resp.text, encoding="utf-8")
        else:
            self.logger.error("登录失败")
        self.anti_scrape.after_failure()
        return False

    def close(self) -> None:
        """关闭底层 HTTP 会话。"""
        self.session.close()

    def __enter__(self) -> "ZhiQiuClient":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def docqa(self, obj_id: str, query: str) -> str:
        """AI问答：提取研报核心观点"""
        # AI 请求前的延迟
        self.anti_scrape.before_request(is_ai_request=True)

        headers = self.anti_scrape.get_headers(
            {
                "accept": "text/event-stream",
                "content-type": "application/json; charset=UTF-8",
                "origin": self.BASE_URL,
                "referer": f"{self.BASE_URL}/newweb/zqpdf/pdf.html?fileid={obj_id}&docType=REPORT",
                "user-agent": self.USER_AGENT,
            },
            obj_id=obj_id,
            is_pdf=False,
        )

        response = self.session.post(
            f"{self.BASE_URL}/semantics/docqa.json",
            headers=headers,
            json={"query": query, "docId": obj_id, "docType": "REPORT", "history": []},
            stream=True,
            timeout=30,
        )

        self.logger.info(f"提问 {obj_id}: {query[:30]}...")
        result = ""
        try:
            for raw_line in response.iter_lines(decode_unicode=True):
                line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
                line = line.strip()
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    obj = json.loads(data_str)
                    if obj.get("type") == "append-text":
                        result += obj.get("response", "")
                    elif obj.get("type") == "state" and "失败" in str(obj.get("message", "")):
                        self.logger.warning(f"服务端错误: {obj}")
                        self.anti_scrape.after_failure()
                        break
                except json.JSONDecodeError:
                    pass
            self.anti_scrape.after_success()
        except Exception as e:
            self.logger.error(f"流处理异常: {e}")
            self.anti_scrape.after_failure()
        finally:
            response.close()

        return result

    def search_reports(
        self,
        starttime: str,
        endtime: str,
        search: str = "",
        doccolumns: str = "3",
        brokers: str = "",
        hyperSearchField: str = "title",
    ) -> dict | None:
        """看研报搜索：fulltext_report_news_search.json"""
        if not self._logged_in:
            raise RuntimeError("未登录，请先调用 login()")

        payload = {
            "starttime": starttime,
            "endtime": endtime,
            "page": "1",
            "pageSize": "100",
            "search": search,
            "doccolumns": doccolumns,
            "brokers": brokers,
            "hyperSearchField": hyperSearchField,
            "sortByTime": "true",
            "newsDealSpecialDocColumn": "true",
            "timeOut": "200",
        }

        self.anti_scrape.before_request(is_ai_request=False)

        headers = self.anti_scrape.get_headers(
            {
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "origin": self.BASE_URL,
                "referer": f"{self.BASE_URL}/newreport/newReportSearch.htm",
                "user-agent": self.USER_AGENT,
                "x-requested-with": "XMLHttpRequest",
            }
        )

        response = self.session.post(
            f"{self.BASE_URL}/newsadapter/fulltextsearch/fulltext_report_news_search.json",
            headers=headers,
            data=payload,
            timeout=SEARCH_TIMEOUT,
        )

        if response.status_code != 200:
            self.logger.error(f"请求失败，状态码: {response.status_code}")
            self.anti_scrape.after_failure()
            return None

        try:
            json_data = cast(Dict[str, Any], response.json())
            count = len(json_data.get("reports", {}).get("reportAttachMap", {}))
            self.logger.info(f"研报数量: {count}")
            self.anti_scrape.after_success()
            return json_data
        except Exception as e:
            self.logger.error(f"JSON 解析失败: {e}")
            self.anti_scrape.after_failure()
            return None

    def extract_core_viewpoint(self, obj_id: str) -> str:
        """提取研报核心观点（使用固定 prompt）"""
        return self.docqa(obj_id, self.PROMPT_CORE_VIEWPOINT)

    def extract_focus_companies(self, obj_id: str) -> str:
        """提取重点关注的上市公司"""
        return self.docqa(obj_id, self.PROMPT_FOCUS_COMPANIES)

    def download_pdf(self, obj_id: str, save_path: str) -> bool:
        """
        下载研报 PDF 到本地

        Args:
            obj_id: 研报 OBJID
            save_path: 保存路径（包含文件名）

        Returns: 是否下载成功
        """
        try:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            # 如果文件已存在，跳过下载
            if os.path.exists(save_path):
                self.logger.info(f"PDF 已存在，跳过: {save_path}")
                return True

            pdf_page_url = f"{self.BASE_URL}/newweb/zqpdf/pdf.html?fileid={obj_id}&docType=REPORT"

            # 尝试多种下载 URL 模式（用户提供的格式放第一位）
            download_urls = [
                f"{self.BASE_URL}/imageserver/report/download.htm?id={obj_id}",
                f"{self.BASE_URL}/newsadapter/download/reportAttach.htm?objId={obj_id}",
                f"{self.BASE_URL}/newweb/zqpdf/downloadPdf.json?fileid={obj_id}",
            ]

            self.logger.info(f"尝试下载 PDF: {obj_id} -> {save_path}")

            for i, download_url in enumerate(download_urls, 1):
                try:
                    self.logger.info(f"尝试 URL {i}/{len(download_urls)}: {download_url}")

                    # PDF 下载前的延迟
                    self.anti_scrape.before_request(is_ai_request=False)

                    headers = self.anti_scrape.get_headers(
                        {
                            "user-agent": self.USER_AGENT,
                            "referer": pdf_page_url,
                            "accept": "application/pdf,*/*",
                        },
                        obj_id=obj_id,
                        is_pdf=True,
                    )

                    resp = self.session.get(download_url, headers=headers, stream=True, timeout=60)

                    if resp.status_code == 200:
                        # 检查是否为 PDF（前几个字节应该是 %PDF）
                        content_start = resp.content[:4] if len(resp.content) >= 4 else b""
                        if content_start.startswith(b"%PDF"):
                            with open(save_path, "wb") as f:
                                for chunk in resp.iter_content(chunk_size=8192):
                                    f.write(chunk)
                            self.logger.info(f"PDF 下载成功: {save_path}")
                            self.anti_scrape.after_success()
                            return True
                        else:
                            self.logger.warning(f"URL {i} 返回内容不是 PDF，开始字节: {content_start!r}")
                    else:
                        self.logger.warning(f"URL {i} 返回状态码: {resp.status_code}")

                except Exception as e:
                    self.logger.warning(f"URL {i} 尝试失败: {e}")
                    self.anti_scrape.after_failure()
                    continue

            self.logger.warning(f"所有 PDF 下载 URL 都失败: {obj_id}")
            return False

        except Exception as e:
            self.logger.error(f"PDF 下载异常 {obj_id}: {e}")
            return False

    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名中的非法字符"""
        invalid_chars = r'[<>:"/\\|?*]'
        filename = re.sub(invalid_chars, "_", filename)
        # 限制文件名长度
        if len(filename) > 200:
            name, ext = os.path.splitext(filename)
            filename = name[:190] + ext
        return filename

    def check_login_status(self) -> dict:
        """检查登录状态是否有效"""
        try:
            # 通过访问搜索页面验证登录状态
            self.anti_scrape.before_request(is_ai_request=False)
            headers = self.anti_scrape.get_headers(
                {"user-agent": self.USER_AGENT, "referer": f"{self.BASE_URL}/newreport/index.htm"}
            )

            response = self.session.get(
                f"{self.BASE_URL}/newreport/newReportSearch.htm", headers=headers, timeout=30
            )

            self.anti_scrape.after_success()

            # 检查是否包含登录相关的关键词
            text = response.text
            is_logged_in = "REPORT_SESSION_COOKIE" in self.session.cookies

            if is_logged_in and response.status_code == 200:
                return {"success": True, "status_code": 200}
            else:
                return {"success": False, "status_code": response.status_code, "text": text}
        except Exception as e:
            self.anti_scrape.after_failure()
            return {"success": False, "error": str(e)}

    def search_homepage(
        self,
        search: str = "",
        date_limit: str = "",
        start_date: str = "",
        end_date: str = "",
        doc_types: str = "REPORT",
        page: int = 1,
        page_size: int = 50,
        hyper_search_fields: str = "title",
        sort_by_time: bool = True,
    ) -> dict | None:
        """
        首页搜索：fulltext_search.json

        Args:
            search: 搜索关键词
            date_limit: 日期限制 (DATE_LIMIT_YEAR, DATE_LIMIT_3MONTH 等)
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            doc_types: 文档类型，逗号分隔 (NEWS:公众号, CJAUTONEWS:新闻, CJCAST:快讯, IMPNEWS:重要舆情, EVENTNODENEWS:产业事件, REPORT:研究报告, INVESTOR:问答, ZQMEETING:纪要)
            page: 页码
            page_size: 每页数量
            hyper_search_fields: 搜索字段 (title, all)
            sort_by_time: 是否按时间排序

        Returns:
            JSON数据，格式与 search_reports() 保持一致
        """
        if not self._logged_in:
            raise RuntimeError("未登录，请先调用 login()")

        self.anti_scrape.before_request(is_ai_request=False)

        # 构建 multipart/form-data
        form_data = {
            "search": search,
            "page": str(page),
            "pageSize": str(page_size),
            "highlightLevel": "1",
            "boostReduction": "true",
            "hyperSearchFields": hyper_search_fields,
            "timeOut": "200",
            "sortByTime": "true" if sort_by_time else "false",
            "clickFrom": "0",
            "errorCollect": "true",
        }

        # 日期参数处理
        if date_limit:
            form_data["dateLimit"] = date_limit
            if date_limit == "CUSTOM":
                # CUSTOM 模式需要设置 startDate 和 endDate
                if start_date:
                    form_data["startDate"] = start_date
                if end_date:
                    form_data["endDate"] = end_date
            # 非 CUSTOM 模式，startDate/endDate 置空（不添加）
        else:
            # 没有 dateLimit 时，按旧逻辑处理（兼容）
            if start_date:
                form_data["startDate"] = start_date
            if end_date:
                form_data["endDate"] = end_date

        # 文档类型
        if doc_types:
            if isinstance(doc_types, list):
                form_data["type"] = ",".join(doc_types)
            else:
                form_data["type"] = str(doc_types)

        headers = self.anti_scrape.get_headers(
            {
                "user-agent": self.USER_AGENT,
                "origin": self.BASE_URL,
                "referer": f"{self.BASE_URL}/newreport/newReportSearch.htm",
                "x-requested-with": "XMLHttpRequest",
            }
        )

        # 使用 requests 的 files 参数发送 multipart/form-data
        # 注意：这里用 files 但实际上是发送表单字段
        files = {k: (None, v) for k, v in form_data.items()}

        response = self.session.post(
            f"{self.BASE_URL}/newsadapter/fulltextsearch/fulltext_search.json",
            headers=headers,
            files=files,
            timeout=SEARCH_TIMEOUT,
        )

        if response.status_code != 200:
            self.logger.error(f"新接口请求失败，状态码: {response.status_code}")
            self.anti_scrape.after_failure()
            return None

        try:
            json_data = cast(Dict[str, Any], response.json())
            # 总是尝试转换格式，确保与旧接口兼容
            json_data = self._convert_new_format(json_data)

            # 统计报告数量
            report_attach_map = json_data.get("reports", {}).get("reportAttachMap", {})
            count = len(report_attach_map)
            self.logger.info(f"新接口研报数量: {count}")
            self.anti_scrape.after_success()
            return json_data
        except Exception as e:
            self.logger.error(f"新接口JSON解析失败: {e}")
            self.anti_scrape.after_failure()
            return None

    def _convert_new_format(self, new_data: dict) -> dict:
        """
        将新接口返回格式转换为旧格式，保持兼容性

        Args:
            new_data: 新接口返回的JSON数据

        Returns:
            兼容旧格式的数据
        """
        self.logger.debug("转换新接口格式")

        # 新接口已经有兼容的结构，只需要确保 reports 是一个对象
        # 新接口返回的数据中，顶层就有 reportAttachMap 和 reports
        if "reportAttachMap" in new_data or "reports" in new_data:
            # 保持与旧接口兼容的结构
            return {
                "reports": {
                    "reportAttachMap": new_data.get("reportAttachMap", {}),
                    "reports": new_data.get("reports", []),
                }
            }

        # 兜底返回
        return (
            new_data
            if "reports" in new_data
            else {"reports": {"reportAttachMap": {}, "reports": []}}
        )

    def search_homepage_all_pages(
        self,
        search: str = "",
        date_limit: str = "",
        start_date: str = "",
        end_date: str = "",
        doc_types: str = "REPORT",
        page_size: int = 50,
        hyper_search_fields: str = "title",
        sort_by_time: bool = True,
        max_pages: int = 20,
    ) -> dict:
        """
        获取全部页的内容，直到遇到重复或没有更多数据

        Args:
            search: 搜索关键词
            date_limit: 日期限制
            start_date: 开始日期
            end_date: 结束日期
            doc_types: 文档类型
            page_size: 每页数量
            hyper_search_fields: 搜索字段
            sort_by_time: 是否按时间排序
            max_pages: 最大页数限制

        Returns:
            合并后的JSON数据
        """
        all_reports = []
        seen_ids = set()
        page = 1
        consecutive_empty = 0

        while page <= max_pages:
            self.logger.info(f"正在获取第 {page} 页...")

            result = self.search_homepage(
                search=search,
                date_limit=date_limit,
                start_date=start_date,
                end_date=end_date,
                doc_types=doc_types,
                page=page,
                page_size=page_size,
                hyper_search_fields=hyper_search_fields,
                sort_by_time=sort_by_time,
            )

            if not result:
                self.logger.warning(f"第 {page} 页获取失败，停止")
                break

            # 获取当前页的报告列表
            reports = result.get("reports", {}).get("reports", [])

            if not reports:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    self.logger.info(f"连续 {consecutive_empty} 页空数据，停止")
                    break
                page += 1
                continue

            consecutive_empty = 0
            has_duplicate = False
            new_reports_count = 0

            for report in reports:
                # 获取报告ID
                report_id = report.get("id") or report.get("objId") or report.get("OBJID")

                if not report_id:
                    continue

                # 检查是否重复
                if report_id in seen_ids:
                    self.logger.debug(f"遇到重复ID: {report_id}，停止")
                    has_duplicate = True
                    break

                seen_ids.add(report_id)
                all_reports.append(report)
                new_reports_count += 1

            self.logger.info(f"第 {page} 页获取了 {new_reports_count} 条新数据")

            if has_duplicate:
                self.logger.info("遇到重复内容，停止")
                break

            page += 1

        self.logger.info(f"总共获取了 {len(all_reports)} 条数据，共 {page - 1} 页")

        # 构建返回数据
        return {"reports": {"reportAttachMap": {}, "reports": all_reports}}

    def get_meeting_detail(self, obj_id: str) -> dict | None:
        """
        获取纪要详情内容

        Args:
            obj_id: 纪要 OBJID

        Returns:
            纪要详情JSON数据
        """
        if not self._logged_in:
            raise RuntimeError("未登录，请先调用 login()")

        self.anti_scrape.before_request(is_ai_request=False)

        form_data = {"id": str(obj_id), "exData": "true"}

        headers = self.anti_scrape.get_headers(
            {
                "user-agent": self.USER_AGENT,
                "origin": self.BASE_URL,
                "referer": f"{self.BASE_URL}/newweb/zqsite/#/intelligentMeetingDetail?id={obj_id}",
                "x-requested-with": "XMLHttpRequest",
            }
        )

        files = {k: (None, v) for k, v in form_data.items()}

        try:
            response = self.session.post(
                f"{self.BASE_URL}/meeting/getMeetingDetail.json",
                headers=headers,
                files=files,
                timeout=DEFAULT_TIMEOUT,
            )

            if response.status_code != 200:
                self.logger.error(f"获取纪要详情失败，状态码: {response.status_code}")
                self.anti_scrape.after_failure()
                return None

            json_data = cast(Dict[str, Any], response.json())
            self.anti_scrape.after_success()
            return json_data

        except Exception as e:
            self.logger.error(f"获取纪要详情异常 {obj_id}: {e}")
            self.anti_scrape.after_failure()
            return None
