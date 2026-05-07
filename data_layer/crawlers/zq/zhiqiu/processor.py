
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知丘数据处理器（向后兼容版本）

这个文件保持向后兼容性，内部使用新的处理器模块。
所有旧的接口都保留，新代码应该直接使用 processors/ 目录下的模块。
"""
import os
from typing import Optional, Dict, Any, List, Tuple

from .processors.base import DOC_TYPE_NAMES, _clean_html
from .processors.news_processor import (
    DEFAULT_ALLOWED_OPEN_NAMES,
    _get_allowed_open_names,
    _is_allowed_open_name,
    NewsProcessor
)
from .processors.report_processor import (
    _is_valid_core,
    _is_valid_companies,
    _parse_companies,
    _is_prompt_needed,
    ReportProcessor
)
from .processors.meeting_processor import MeetingProcessor
from .utils import parse_timestamp, extract_text_from_html, clean_unwanted_content


class _CompatibleProcessor:
    """
    兼容旧接口的处理器，将请求分发到新的处理器
    """

    def __init__(self, client, allowed_accounts_path: Optional[str] = None):
        self.client = client
        self.news_processor = NewsProcessor(client, allowed_accounts_path)
        self.report_processor = ReportProcessor(client)
        self.meeting_processor = MeetingProcessor(client)
        self.allowed_accounts_path = allowed_accounts_path

    def process(self, data: Dict[str, Any], output_file: str, **kwargs) -> Tuple[Any, List[Dict], int]:
        doc_types = set()
        reports_list = data.get('reports', [])
        if isinstance(reports_list, dict):
            inner_reports = reports_list.get('reports', [])
            for r in inner_reports:
                dt = r.get('docType', '') or r.get('type', '')
                if dt:
                    doc_types.add(dt)
        else:
            for r in reports_list:
                dt = r.get('docType', '') or r.get('type', '')
                if dt:
                    doc_types.add(dt)

        if not doc_types or len(doc_types) > 1:
            return self._process_mixed(data, output_file, **kwargs)
        elif 'NEWS' in doc_types:
            return self.news_processor.process(data, output_file, **kwargs)
        elif 'REPORT' in doc_types:
            return self.report_processor.process(data, output_file, **kwargs)
        elif 'ZQMEETING' in doc_types:
            return self.meeting_processor.process(data, output_file, **kwargs)
        else:
            return self._process_mixed(data, output_file, **kwargs)

    def _process_mixed(self, data: Dict[str, Any], output_file: str, **kwargs) -> Tuple[Any, List[Dict], int]:
        reports_list = data.get('reports', [])
        if isinstance(reports_list, dict):
            inner_reports = reports_list.get('reports', [])
            if reports_list.get('reportAttachMap'):
                return self._process_old_format(data, output_file, **kwargs)
            else:
                data = {'reports': inner_reports}
                return self._process_new_format(data, output_file, **kwargs)
        else:
            return self._process_new_format(data, output_file, **kwargs)

    def _process_old_format(self, data: Dict[str, Any], output_file: str, **kwargs) -> Tuple[Any, List[Dict], int]:
        reports_data = data.get('reports', {}) if isinstance(data.get('reports'), dict) else {}
        attach_map = reports_data.get('reportAttachMap', {})
        reports_map = {r['id']: r for r in reports_data.get('reports', []) if r.get('id')}

        results = []
        new_reports = []
        skipped_count = 0

        state_manager = kwargs.get('state_manager')
        skip_existing = kwargs.get('skip_existing', True)

        for doc_id, attachments in attach_map.items():
            report = reports_map.get(doc_id)
            for attachment in attachments:
                obj_id = attachment.get('OBJID')
                if state_manager and skip_existing and obj_id:
                    if state_manager.is_report_processed(obj_id):
                        skipped_count += 1
                        continue

                item = _build_item_report(
                    attachment, report, self.client,
                    kwargs.get('prompt', ''),
                    enable_core=kwargs.get('enable_core', False),
                    enable_viewpoint=kwargs.get('enable_viewpoint', False),
                    enable_companies=kwargs.get('enable_companies', False),
                    enable_pdf=kwargs.get('enable_pdf', False),
                    pdf_root_dir=kwargs.get('pdf_root_dir', 'pdfs'),
                    ai_interval=kwargs.get('ai_interval', 10)
                )
                results.append(item)
                new_reports.append(item)

        if output_file:
            import os
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            import json
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

        self.client.logger.info(f"已处理 {len(results)} 条研报（跳过 {skipped_count} 条），保存至 {output_file}")

        import pandas as pd
        return pd.DataFrame(results), new_reports, skipped_count

    def _process_new_format(self, data: Dict[str, Any], output_file: str, **kwargs) -> Tuple[Any, List[Dict], int]:
        reports_list = data.get('reports', [])

        results = []
        new_reports = []
        skipped_count = 0

        state_manager = kwargs.get('state_manager')
        skip_existing = kwargs.get('skip_existing', True)

        for report in reports_list:
            doc_type = report.get('docType', '') or report.get('type', '')
            obj_id = report.get('id') or report.get('objId')

            if state_manager and skip_existing and obj_id:
                if state_manager.is_report_processed(str(obj_id)):
                    skipped_count += 1
                    continue

            if doc_type == 'NEWS':
                open_name = report.get('openName', '')
                if not _is_allowed_open_name(open_name, self.allowed_accounts_path):
                    self.client.logger.debug(f"跳过未允许的公众号: {open_name}")
                    continue
                item = self.news_processor.build_item(report)
            elif doc_type == 'REPORT':
                item = self.report_processor.build_item(report, **kwargs)
            elif doc_type == 'ZQMEETING':
                item = self.meeting_processor.build_item(report, **kwargs)
            else:
                item = _build_item_generic(report, self.client, kwargs.get('prompt', ''),
                                        kwargs.get('enable_core', False),
                                        kwargs.get('enable_viewpoint', False),
                                        kwargs.get('enable_companies', False))

            if item:
                results.append(item)
                new_reports.append(item)

        if output_file:
            import os
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            import json
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

        self.client.logger.info(f"已处理 {len(results)} 条记录（跳过 {skipped_count} 条），保存至 {output_file}")

        import pandas as pd
        return pd.DataFrame(results), new_reports, skipped_count


def process_reports(
    client,
    data: dict,
    output_file: str,
    prompt: str,
    enable_core: bool = False,
    enable_viewpoint: bool = False,
    enable_companies: bool = False,
    enable_pdf: bool = False,
    pdf_dir: str = "pdfs",
    ai_interval: int = 10,
    output_dir: Optional[str] = None,
    state_manager: Optional[Any] = None,
    skip_existing: bool = True,
    allowed_accounts_path: Optional[str] = None
) -> Tuple[Any, List[Dict], int]:
    processor = _CompatibleProcessor(client, allowed_accounts_path)

    if output_dir is None:
        output_dir = os.path.dirname(output_file) if output_file else "."
    pdf_root_dir = os.path.join(output_dir, pdf_dir)

    return processor.process(
        data,
        output_file,
        prompt=prompt,
        enable_core=enable_core,
        enable_viewpoint=enable_viewpoint,
        enable_companies=enable_companies,
        enable_pdf=enable_pdf,
        pdf_root_dir=pdf_root_dir,
        ai_interval=ai_interval,
        output_dir=output_dir,
        state_manager=state_manager,
        skip_existing=skip_existing
    )




def _build_item_report(
    attachment: dict,
    report: Optional[dict],
    client,
    prompt: str,
    enable_core: bool = False,
    enable_viewpoint: bool = False,
    enable_companies: bool = False,
    enable_pdf: bool = False,
    pdf_root_dir: str = "pdfs",
    ai_interval: int = 10
) -> dict:
    item = {
        'OBJID': attachment.get('OBJID'),
        'DOCID': attachment.get('DOCID'),
        'pdfNAME': attachment.get('NAME'),
    }

    if not report:
        return {**item, 'brokerName': '', 'author': '', 'docType': '', 'title': '',
                'viewpoint': '', 'core': '', 'coreViewpoint': '',
                'focusCompanies': '', 'focusCompaniesParsed': [],
                'pdfPath': '', 'date': ''}

    broker = report.get('brokerName', '')
    obj_id = attachment.get('OBJID')

    core = ''
    core_viewpoint = ''
    focus_companies = ''
    focus_companies_parsed = []
    pdf_path = ''

    date_str = parse_timestamp(report)
    is_target_broker = broker in client.TARGET_BROKERS

    if is_target_broker:
        if enable_core and _is_prompt_needed(prompt):
            core = client.docqa(obj_id, prompt)

        if enable_viewpoint:
            core_viewpoint = client.extract_core_viewpoint(obj_id)

        if enable_companies:
            focus_companies = client.extract_focus_companies(obj_id)
            if _is_valid_companies(focus_companies):
                focus_companies_parsed = _parse_companies(focus_companies)

    if enable_pdf and obj_id:
        pdf_filename = client._sanitize_filename(attachment.get('NAME', f'{obj_id}.pdf'))
        if not pdf_filename.lower().endswith('.pdf'):
            pdf_filename += '.pdf'

        broker_subdir = client._sanitize_filename(broker) if broker else 'unknown'
        pdf_save_dir = os.path.join(pdf_root_dir, broker_subdir)
        pdf_full_path = os.path.join(pdf_save_dir, pdf_filename)

        if client.download_pdf(obj_id, pdf_full_path):
            pdf_path = os.path.join(pdf_root_dir, broker_subdir, pdf_filename)
            pdf_path = pdf_path.replace('\\', '/')

    item.update({
        'brokerName': broker,
        'author': _clean_html(report.get('author', '')),
        'docType': report.get('docTypeName', ''),
        'docTypeName': '研报',
        'title': _clean_html(report.get('title', '')),
        'viewpoint': report.get('view_point', ''),
        'core': core,
        'coreViewpoint': core_viewpoint,
        'focusCompanies': focus_companies,
        'focusCompaniesParsed': focus_companies_parsed,
        'pdfPath': pdf_path,
        'date': date_str
    })
    return item


def _build_item_from_report(
    report: dict,
    client,
    prompt: str,
    enable_core: bool,
    enable_viewpoint: bool,
    enable_companies: bool,
    enable_pdf: bool,
    pdf_root_dir: str,
    ai_interval: int
) -> Optional[dict]:
    obj_id = report.get('id') or report.get('objId')
    if not obj_id:
        return None

    date_str = parse_timestamp(report)
    item = {
        'OBJID': str(obj_id),
        'DOCID': str(report.get('docId', '')) if report.get('docId') else '',
        'pdfNAME': report.get('title', ''),
        'brokerName': report.get('brokerName', '') or report.get('source', ''),
        'author': _clean_html(report.get('author', '')),
        'docType': 'REPORT',
        'docTypeName': '研报',
        'title': _clean_html(report.get('title', '')),
        'viewpoint': report.get('viewPoint', '') or report.get('summary', ''),
        'core': '',
        'coreViewpoint': '',
        'focusCompanies': '',
        'focusCompaniesParsed': [],
        'pdfPath': '',
        'url': '',
        'date': date_str
    }

    broker = item['brokerName']
    is_target_broker = broker in client.TARGET_BROKERS

    if is_target_broker:
        if enable_core and _is_prompt_needed(prompt):
            item['core'] = client.docqa(str(obj_id), prompt)

        if enable_viewpoint:
            item['coreViewpoint'] = client.extract_core_viewpoint(str(obj_id))

        if enable_companies:
            item['focusCompanies'] = client.extract_focus_companies(str(obj_id))
            if _is_valid_companies(item['focusCompanies']):
                item['focusCompaniesParsed'] = _parse_companies(item['focusCompanies'])

    if enable_pdf and obj_id:
        pdf_filename = client._sanitize_filename(report.get('title', f'{obj_id}.pdf'))
        if not pdf_filename.lower().endswith('.pdf'):
            pdf_filename += '.pdf'

        broker_subdir = client._sanitize_filename(broker) if broker else 'unknown'
        pdf_save_dir = os.path.join(pdf_root_dir, broker_subdir)
        pdf_full_path = os.path.join(pdf_save_dir, pdf_filename)

        if client.download_pdf(str(obj_id), pdf_full_path):
            item['pdfPath'] = os.path.join(pdf_root_dir, broker_subdir, pdf_filename)
            item['pdfPath'] = item['pdfPath'].replace('\\', '/')

    return item


def _build_item_from_news(
    report: dict,
    client,
    prompt: str,
    enable_core: bool,
    enable_viewpoint: bool,
    enable_companies: bool
) -> Optional[dict]:
    obj_id = report.get('id') or report.get('objId')
    if not obj_id:
        return None

    internal_url = f"https://www.kanzhiqiu.com/newsadapter/newcjnews/read_news.htm?id={obj_id}"
    external_url = report.get('url', '')
    content = _fetch_news_content(client, internal_url, external_url)

    date_str = parse_timestamp(report)

    return {
        'OBJID': str(obj_id),
        'docType': 'NEWS',
        'docTypeName': '公众号',
        'title': _clean_html(report.get('title', '')),
        'url': internal_url,
        'externalUrl': external_url,
        'content': content,
        'date': date_str,
        'openName': report.get('openName', '')
    }


def _fetch_news_content(client, internal_url: str, external_url: str) -> str:
    content = ""

    try:
        client.anti_scrape.before_request(is_ai_request=False)
        headers = client.anti_scrape.get_headers({
            "user-agent": client.USER_AGENT,
            "referer": f"{client.BASE_URL}/"
        })
        resp = client.session.get(internal_url, headers=headers, timeout=30)
        client.anti_scrape.after_success()

        if resp.status_code == 200:
            content = extract_text_from_html(resp.text)
            if content and len(content.strip()) > 50:
                return content
    except Exception as e:
        client.logger.debug(f"从内部链接获取内容失败: {e}")

    if external_url:
        try:
            client.anti_scrape.before_request(is_ai_request=False)
            headers = client.anti_scrape.get_headers({
                "user-agent": client.USER_AGENT
            })
            resp = client.session.get(external_url, headers=headers, timeout=30)
            client.anti_scrape.after_success()

            if resp.status_code == 200:
                content = extract_text_from_html(resp.text)
                if content and len(content.strip()) > 50:
                    return content
        except Exception as e:
            client.logger.debug(f"从外部链接获取内容失败: {e}")

    return content or ""


def _build_item_from_meeting(
    report: dict,
    client,
    prompt: str,
    enable_core: bool,
    enable_viewpoint: bool,
    enable_companies: bool
) -> Optional[dict]:
    obj_id = report.get('id') or report.get('objId')
    if not obj_id:
        return None

    internal_url = f"https://www.kanzhiqiu.com/newweb/zqsite/#/intelligentMeetingDetail?id={obj_id}"
    date_str = parse_timestamp(report)

    return {
        'OBJID': str(obj_id),
        'DOCID': str(report.get('docId', '')) if report.get('docId') else '',
        'pdfNAME': '',
        'brokerName': report.get('source', '') or report.get('brokerName', ''),
        'author': _clean_html(report.get('author', '')),
        'docType': 'ZQMEETING',
        'docTypeName': '纪要',
        'title': _clean_html(report.get('title', '')),
        'viewpoint': report.get('summary', '') or report.get('viewPoint', ''),
        'core': '',
        'coreViewpoint': '',
        'focusCompanies': '',
        'focusCompaniesParsed': [],
        'pdfPath': '',
        'url': internal_url,
        'externalUrl': report.get('url', ''),
        'date': date_str
    }


def _build_item_generic(
    report: dict,
    client,
    prompt: str,
    enable_core: bool,
    enable_viewpoint: bool,
    enable_companies: bool
) -> Optional[dict]:
    obj_id = report.get('id') or report.get('objId')
    if not obj_id:
        return None

    doc_type = report.get('docType', '') or report.get('type', '')
    doc_type_name = DOC_TYPE_NAMES.get(doc_type, doc_type)
    date_str = parse_timestamp(report)

    return {
        'OBJID': str(obj_id),
        'DOCID': str(report.get('docId', '')) if report.get('docId') else '',
        'pdfNAME': '',
        'brokerName': report.get('source', '') or report.get('brokerName', ''),
        'author': _clean_html(report.get('author', '')),
        'docType': doc_type,
        'docTypeName': doc_type_name,
        'title': _clean_html(report.get('title', '')),
        'viewpoint': report.get('summary', '') or report.get('viewPoint', ''),
        'core': '',
        'coreViewpoint': '',
        'focusCompanies': '',
        'focusCompaniesParsed': [],
        'pdfPath': '',
        'url': report.get('url', ''),
        'date': date_str
    }


__all__ = [
    'process_reports',
    'DOC_TYPE_NAMES',
    'DEFAULT_ALLOWED_OPEN_NAMES',
    '_get_allowed_open_names',
    '_is_allowed_open_name',
    '_is_valid_core',
    '_is_valid_companies',
    '_parse_companies',
    '_build_item_report',
    '_build_item_from_report',
    '_build_item_from_news',
    '_build_item_from_meeting',
    '_build_item_generic',
    '_clean_html',
]

