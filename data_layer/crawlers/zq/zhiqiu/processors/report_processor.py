#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
研报数据处理器

专门处理 REPORT 类型（研报）数据的模块。
"""

import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from ..pdf_utils import PDFMetadata, calculate_file_hash, get_file_size, save_pdf_metadata
from ..utils import parse_timestamp
from .base import BaseProcessor, _clean_html


def _is_valid_core(core: str) -> bool:
    """
    判断核心观点是否有效

    Args:
        core: 核心观点文本

    Returns:
        是否有效
    """
    if not core or not core.strip():
        return False
    invalid_keywords = [
        "我没找到答案",
        "没有找到答案",
        "未找到答案",
        "无法找到",
        "没有相关内容",
        "未找到相关",
    ]
    core_lower = core.lower()
    if any(kw in core_lower for kw in invalid_keywords):
        return False
    lines = [line.strip() for line in core.split("\n") if line.strip()]
    if len(lines) < 3 or len(core.strip()) < 100:
        return False
    return True


def _is_valid_companies(companies_text: str) -> bool:
    """
    判断公司提取结果是否有效

    Args:
        companies_text: 公司信息文本

    Returns:
        是否有效
    """
    if not companies_text or not companies_text.strip():
        return False
    invalid_keywords = ["没找到", "未找到", "无法找到", "没有相关"]
    return not any(kw in companies_text for kw in invalid_keywords)


def _parse_companies(companies_text: str) -> List[Dict[str, str]]:
    """
    解析 AI 返回的公司信息

    支持多种格式：
    - "东方雨虹(002271)"
    - "海螺水泥：600585"
    - "中国巨石 600176"

    Args:
        companies_text: 公司信息文本

    Returns:
        公司信息列表，格式：[{"name": "公司名", "code": "股票代码"}, ...]
    """
    results = []
    if not companies_text or not companies_text.strip():
        return results

    pattern1 = r"\*\*([^*]{2,})\*\*[^0-9]*?(\d{5,6})"
    pattern2 = r"([^\s\d*_]{2,})[^0-9]*?(\d{5,6})"

    seen_codes = set()

    for match in re.finditer(pattern1, companies_text):
        name = match.group(1).strip()
        code = match.group(2).strip()
        if code and code not in seen_codes and len(name) >= 2:
            seen_codes.add(code)
            results.append({"name": name, "code": code})

    for match in re.finditer(pattern2, companies_text):
        name = match.group(1).strip()
        code = match.group(2).strip()
        if len(name) < 2 or any(kw in name for kw in ["指数", "成分股", "股票", "代码", "公司"]):
            continue
        if code and code not in seen_codes:
            seen_codes.add(code)
            results.append({"name": name, "code": code})

    return results


def _is_prompt_needed(prompt: str) -> bool:
    """
    判断是否需要使用 prompt（非空且有实际内容）

    Args:
        prompt: 提示词

    Returns:
        是否需要使用
    """
    if not prompt:
        return False
    prompt_stripped = prompt.strip()
    return len(prompt_stripped) > 0 and prompt_stripped != "{search}"


class ReportProcessor(BaseProcessor):
    """
    研报数据处理器

    专门处理 REPORT 类型文档，包括：
    - AI 核心观点提取
    - AI 关注公司提取
    - PDF 下载
    """

    def __init__(self, client):
        super().__init__(client)
        self.attach_map = {}
        self.reports_map = {}

    def process(
        self,
        data: Dict[str, Any],
        output_file: str,
        prompt: str = "",
        enable_core: bool = False,
        enable_viewpoint: bool = False,
        enable_companies: bool = False,
        enable_pdf: bool = False,
        pdf_dir: str = "pdfs",
        ai_interval: int = 10,
        output_dir: Optional[str] = None,
        state_manager: Optional[Any] = None,
        skip_existing: bool = True,
        stop_on_known: bool = True,
        watermark_key: Optional[str] = None,
        **kwargs,
    ) -> Tuple[pd.DataFrame, List[Dict], int, bool]:
        """
        处理研报数据

        Args:
            data: 原始 JSON 数据
            output_file: 输出 JSON 文件路径
            prompt: AI 提问模板
            enable_core: 是否启用核心摘要提取
            enable_viewpoint: 是否启用核心观点提取
            enable_companies: 是否启用关注公司提取
            enable_pdf: 是否启用 PDF 下载
            pdf_dir: PDF 保存子目录名
            ai_interval: AI 请求间隔秒数
            output_dir: 输出根目录
            state_manager: 状态管理器（可选，用于去重）
            skip_existing: 是否跳过已存在的条目
            stop_on_known: 遇到已处理记录时是否停止
            watermark_key: 水位线标识键
            **kwargs: 其他参数

        Returns:
            (DataFrame, new_reports_list, skipped_count, stopped_by_watermark)
        """
        if output_dir is None:
            output_dir = os.path.dirname(output_file) if output_file else "."

        # 判断数据格式
        reports_list = data.get("reports", [])
        if isinstance(reports_list, dict):
            self.attach_map = reports_list.get("reportAttachMap", {})
            self.reports_map = {r["id"]: r for r in reports_list.get("reports", []) if r.get("id")}
            return self._process_old_format(
                output_file,
                prompt,
                enable_core,
                enable_viewpoint,
                enable_companies,
                enable_pdf,
                os.path.join(output_dir, pdf_dir),
                ai_interval,
                output_dir,
                state_manager,
                skip_existing,
                stop_on_known,
                watermark_key,
            )
        else:
            return self._process_new_format(
                data,
                output_file,
                prompt,
                enable_core,
                enable_viewpoint,
                enable_companies,
                enable_pdf,
                os.path.join(output_dir, pdf_dir),
                ai_interval,
                output_dir,
                state_manager,
                skip_existing,
                stop_on_known,
                watermark_key,
            )

    def build_item(self, report: Dict[str, Any], **kwargs) -> Optional[Dict[str, Any]]:
        """
        构建研报条目（新格式）

        Args:
            report: 原始数据
            **kwargs: 其他参数

        Returns:
            研报条目字典
        """
        return self._build_item_from_report(report, **kwargs)

    def _process_old_format(
        self,
        output_file: str,
        prompt: str,
        enable_core: bool,
        enable_viewpoint: bool,
        enable_companies: bool,
        enable_pdf: bool,
        pdf_root_dir: str,
        ai_interval: int,
        output_dir: Optional[str],
        state_manager: Optional[Any],
        skip_existing: bool,
        stop_on_known: bool = True,
        watermark_key: Optional[str] = None,
    ) -> Tuple[pd.DataFrame, List[Dict], int, bool]:
        """
        处理旧格式数据（看研报搜索）
        """
        results = []
        new_reports = []
        skipped_count = 0
        stopped_by_watermark = False
        first_new_obj_id: Optional[str] = None

        for doc_id, attachments in self.attach_map.items():
            report = self.reports_map.get(doc_id)
            for attachment in attachments:
                obj_id = attachment.get("OBJID")

                if state_manager and skip_existing and obj_id:
                    if state_manager.is_report_processed(obj_id):
                        skipped_count += 1
                        if stop_on_known:
                            stopped_by_watermark = True
                            self.client.logger.info(f"[水位线] 遇到已知研报 {obj_id}，停止抓取")
                            break
                        continue

                item = self._build_item_report(
                    attachment,
                    report,
                    prompt,
                    enable_core=enable_core,
                    enable_viewpoint=enable_viewpoint,
                    enable_companies=enable_companies,
                    enable_pdf=enable_pdf,
                    pdf_root_dir=pdf_root_dir,
                    ai_interval=ai_interval,
                    output_dir=output_dir,
                )
                results.append(item)
                new_reports.append(item)

                # 记录第一个新项目作为水位线
                if first_new_obj_id is None and obj_id:
                    first_new_obj_id = obj_id

            if stopped_by_watermark:
                break

        # 设置水位线
        if state_manager and first_new_obj_id and watermark_key:
            state_manager.set_watermark(watermark_key, first_new_obj_id)
            self.client.logger.info(f"[水位线] 设置水位线为 {first_new_obj_id}")

        if output_file:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

        self.client.logger.info(f"已处理 {len(results)} 条研报 (跳过 {skipped_count} 条)，保存至 {output_file}")
        return pd.DataFrame(results), new_reports, skipped_count, stopped_by_watermark

    def _process_new_format(
        self,
        data: Dict[str, Any],
        output_file: str,
        prompt: str,
        enable_core: bool,
        enable_viewpoint: bool,
        enable_companies: bool,
        enable_pdf: bool,
        pdf_root_dir: str,
        ai_interval: int,
        output_dir: Optional[str],
        state_manager: Optional[Any],
        skip_existing: bool,
        stop_on_known: bool = True,
        watermark_key: Optional[str] = None,
    ) -> Tuple[pd.DataFrame, List[Dict], int, bool]:
        """
        处理新格式数据（首页搜索）
        """
        reports_list = data.get("reports", [])

        results = []
        new_reports = []
        skipped_count = 0
        stopped_by_watermark = False
        first_new_obj_id: Optional[str] = None

        for report in reports_list:
            doc_type = report.get("docType", "") or report.get("type", "")

            if doc_type != "REPORT":
                continue

            obj_id = report.get("id") or report.get("objId")
            if state_manager and skip_existing and obj_id:
                if state_manager.is_report_processed(str(obj_id)):
                    skipped_count += 1
                    if stop_on_known:
                        stopped_by_watermark = True
                        self.client.logger.info(f"[水位线] 遇到已知研报 {obj_id}，停止抓取")
                        break
                    continue

            item = self._build_item_from_report(
                report,
                prompt,
                enable_core,
                enable_viewpoint,
                enable_companies,
                enable_pdf,
                pdf_root_dir,
                ai_interval,
                output_dir=output_dir,
            )
            if item:
                results.append(item)
                new_reports.append(item)

                # 记录第一个新项目作为水位线
                if first_new_obj_id is None and obj_id:
                    first_new_obj_id = str(obj_id)

        # 设置水位线
        if state_manager and first_new_obj_id and watermark_key:
            state_manager.set_watermark(watermark_key, first_new_obj_id)
            self.client.logger.info(f"[水位线] 设置水位线为 {first_new_obj_id}")

        if output_file:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

        self.client.logger.info(f"已处理 {len(results)} 条研报 (跳过 {skipped_count} 条)，保存至 {output_file}")
        return pd.DataFrame(results), new_reports, skipped_count, stopped_by_watermark

    def _build_item_report(
        self,
        attachment: Dict[str, Any],
        report: Optional[Dict[str, Any]],
        prompt: str,
        enable_core: bool = False,
        enable_viewpoint: bool = False,
        enable_companies: bool = False,
        enable_pdf: bool = False,
        pdf_root_dir: str = "pdfs",
        ai_interval: int = 10,
        output_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        构建单条研报数据（旧格式）
        """
        item = {
            "OBJID": attachment.get("OBJID"),
            "DOCID": attachment.get("DOCID"),
            "pdfNAME": attachment.get("NAME"),
        }

        if not report:
            return {
                **item,
                "brokerName": "",
                "author": "",
                "docType": "",
                "title": "",
                "viewpoint": "",
                "core": "",
                "coreViewpoint": "",
                "focusCompanies": "",
                "focusCompaniesParsed": [],
                "pdfPath": "",
                "date": "",
            }

        broker = report.get("brokerName", "")
        obj_id = attachment.get("OBJID")

        core = ""
        core_viewpoint = ""
        focus_companies = ""
        focus_companies_parsed = []
        pdf_path = ""

        date_str = parse_timestamp(report)

        is_target_broker = broker in self.client.TARGET_BROKERS

        if is_target_broker:
            if enable_core and _is_prompt_needed(prompt):
                core = self.client.docqa(obj_id, prompt)

            if enable_viewpoint:
                core_viewpoint = self.client.extract_core_viewpoint(obj_id)

            if enable_companies:
                focus_companies = self.client.extract_focus_companies(obj_id)
                if _is_valid_companies(focus_companies):
                    focus_companies_parsed = _parse_companies(focus_companies)

        if enable_pdf and obj_id:
            pdf_result = self._download_and_record_pdf_old_format(
                attachment=attachment,
                report=report,
                pdf_root_dir=pdf_root_dir,
                output_dir=os.path.dirname(pdf_root_dir) if pdf_root_dir else None,
            )
            if pdf_result:
                pdf_path = pdf_result["relative_path"]
                item["pdfPath"] = pdf_path
                item["pdfHash"] = pdf_result["hash"]
                item["pdfSize"] = pdf_result["size"]

        item.update(
            {
                "brokerName": broker,
                "author": _clean_html(report.get("author", "")),
                "docType": report.get("docTypeName", ""),
                "docTypeName": "研报",
                "title": _clean_html(report.get("title", "")),
                "viewpoint": report.get("view_point", ""),
                "core": core,
                "coreViewpoint": core_viewpoint,
                "focusCompanies": focus_companies,
                "focusCompaniesParsed": focus_companies_parsed,
                "date": date_str,
            }
        )
        return item

    def _build_item_from_report(
        self,
        report: Dict[str, Any],
        prompt: str = "",
        enable_core: bool = False,
        enable_viewpoint: bool = False,
        enable_companies: bool = False,
        enable_pdf: bool = False,
        pdf_root_dir: str = "pdfs",
        ai_interval: int = 10,
        output_dir: Optional[str] = None,
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """
        从首页搜索的 REPORT 类型构建条目
        """
        obj_id = report.get("id") or report.get("objId")
        if not obj_id:
            return None

        date_str = parse_timestamp(report)

        item = {
            "OBJID": str(obj_id),
            "DOCID": str(report.get("docId", "")) if report.get("docId") else "",
            "pdfNAME": report.get("title", ""),
            "brokerName": report.get("brokerName", "") or report.get("source", ""),
            "author": _clean_html(report.get("author", "")),
            "docType": "REPORT",
            "docTypeName": "研报",
            "title": _clean_html(report.get("title", "")),
            "viewpoint": report.get("viewPoint", "") or report.get("summary", ""),
            "core": "",
            "coreViewpoint": "",
            "focusCompanies": "",
            "focusCompaniesParsed": [],
            "pdfPath": "",
            "url": "",
            "date": date_str,
        }

        broker = item["brokerName"]
        is_target_broker = broker in self.client.TARGET_BROKERS

        if is_target_broker:
            if enable_core and _is_prompt_needed(prompt):
                item["core"] = self.client.docqa(str(obj_id), prompt)

            if enable_viewpoint:
                item["coreViewpoint"] = self.client.extract_core_viewpoint(str(obj_id))

            if enable_companies:
                item["focusCompanies"] = self.client.extract_focus_companies(str(obj_id))
                if _is_valid_companies(item["focusCompanies"]):
                    item["focusCompaniesParsed"] = _parse_companies(item["focusCompanies"])

        if enable_pdf and obj_id:
            pdf_result = self._download_and_record_pdf(
                obj_id=str(obj_id),
                title=report.get("title", ""),
                broker=broker,
                pdf_root_dir=pdf_root_dir,
                output_dir=os.path.dirname(pdf_root_dir) if pdf_root_dir else None,
            )
            if pdf_result:
                item["pdfPath"] = pdf_result["relative_path"]
                item["pdfHash"] = pdf_result["hash"]
                item["pdfSize"] = pdf_result["size"]

        return item

    def _download_and_record_pdf(
        self,
        obj_id: str,
        title: str,
        broker: str,
        pdf_root_dir: str,
        output_dir: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        下载 PDF 并记录元数据（PDF 优先工作流）

        Args:
            obj_id: 文档 ID
            title: 文档标题
            broker: 券商名称
            pdf_root_dir: PDF 保存根目录
            output_dir: 输出根目录（用于保存元数据）

        Returns:
            {relative_path, hash, size} 或 None（失败）
        """
        pdf_filename = self.client._sanitize_filename(title or f"{obj_id}.pdf")
        if not pdf_filename.lower().endswith(".pdf"):
            pdf_filename += ".pdf"

        broker_subdir = self.client._sanitize_filename(broker) if broker else "unknown"
        pdf_save_dir = os.path.join(pdf_root_dir, broker_subdir)
        pdf_full_path = os.path.join(pdf_save_dir, pdf_filename)

        # 下载 PDF
        if not self.client.download_pdf(obj_id, pdf_full_path):
            self.client.logger.warning(f"PDF 下载失败，仅保留元数据: {obj_id}")
            return None

        # 计算哈希和大小
        try:
            file_hash = calculate_file_hash(pdf_full_path, "sha256")
            file_size = get_file_size(pdf_full_path)
        except Exception as e:
            self.client.logger.warning(f"计算 PDF 哈希失败: {e}")
            file_hash = ""
            file_size = 0

        # 构建相对路径
        relative_path = os.path.join(pdf_root_dir, broker_subdir, pdf_filename)
        relative_path = relative_path.replace("\\", "/")

        # 保存元数据
        if output_dir:
            try:
                metadata = PDFMetadata(
                    obj_id=obj_id,
                    file_path=relative_path,
                    file_hash=file_hash,
                    file_size=file_size,
                    title=title,
                    broker=broker,
                    source_url=f"{self.client.BASE_URL}/newweb/zqpdf/pdf.html?fileid={obj_id}",
                )
                save_pdf_metadata(metadata, output_dir)
            except Exception as e:
                self.client.logger.warning(f"保存 PDF 元数据失败: {e}")

        # 注册到数据库，使 PDFConversionService 可以发现并转换它
        try:
            from data_layer.repositories.base import SessionLocal
            from data_layer.repositories.models import PDFArtifactV1DB
            from data_layer.repositories.pdf_artifact_repository import add_pdf_artifact

            db = SessionLocal()
            try:
                artifact = PDFArtifactV1DB(
                    pdf_id=f"pdf_{uuid.uuid4().hex[:12]}",
                    source_obj_id=obj_id,
                    file_path=relative_path,
                    file_name=pdf_filename,
                    file_size_bytes=file_size,
                    file_hash_sha256=file_hash,
                    source_type="zhiqiu_reports",
                    source_name="知丘",
                    source_broker=broker,
                    source_url=(f"{self.client.BASE_URL}/newweb/zqpdf/pdf.html?fileid={obj_id}"),
                    fetch_timestamp=datetime.now(timezone.utc),
                    parse_status="pending",
                )
                add_pdf_artifact(db, artifact)
            finally:
                db.close()
        except Exception as e:
            self.client.logger.warning(f"注册 PDF 制品到数据库失败: {e}")

        return {
            "relative_path": relative_path,
            "hash": file_hash,
            "size": file_size,
        }

    def _download_and_record_pdf_old_format(
        self,
        attachment: Dict[str, Any],
        report: Dict[str, Any],
        pdf_root_dir: str,
        output_dir: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        旧格式的 PDF 下载和元数据记录

        Args:
            attachment: 附件数据
            report: 研报数据
            pdf_root_dir: PDF 保存根目录
            output_dir: 输出根目录

        Returns:
            {relative_path, hash, size} 或 None
        """
        obj_id = attachment.get("OBJID")
        if not obj_id:
            return None

        title = attachment.get("NAME", report.get("title", ""))
        broker = report.get("brokerName", "")

        return self._download_and_record_pdf(
            obj_id=obj_id,
            title=title,
            broker=broker,
            pdf_root_dir=pdf_root_dir,
            output_dir=output_dir,
        )
