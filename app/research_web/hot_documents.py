"""Project an authenticated, immutable Hot brief to the existing report DOCX writer."""
import io
import hashlib
import json
import os
import re
import stat
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from core.observability import get_logger
from .report_documents import build_docx_document

log = get_logger(__name__)


def retain_brief_docx(home: Path, saved: dict, data: bytes) -> Path:
    """Hash-addressed private Hot artifact, independent of research-session deletion."""
    temporary = None
    try:
        if (not re.fullmatch(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", saved.get("briefId", ""))
                or type(saved.get("version")) is not int or not 1 <= saved["version"] <= 1000000
                or not isinstance(data, bytes) or not 0 < len(data) <= 5 * 1024 * 1024
                or not home.is_absolute() or home.resolve(strict=True) != home):
            raise ValueError("hot_docx_artifact_invalid")
        for directory in [home / "hot", home / "hot" / "brief-artifacts"]:
            directory.mkdir(mode=0o700, exist_ok=True)
            info = directory.lstat()
            if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700
                    or directory.resolve(strict=True) != directory):
                raise ValueError("hot_docx_artifact_invalid")
        digest = hashlib.sha256(data).hexdigest()
        target = directory / f"{saved['briefId']}-v{saved['version']}-{digest}.docx"
        descriptor, name = tempfile.mkstemp(prefix=".docx-", dir=directory)
        temporary = Path(name)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError:
            pass
        temporary.unlink();temporary = None
        descriptor = os.open(target, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size != len(data)
                    or hashlib.sha256(stream.read(5 * 1024 * 1024 + 1)).hexdigest() != digest):
                raise ValueError("hot_docx_artifact_invalid")
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        log.info("hot_docx_artifact_retained")
        return target
    except Exception:
        log.warning("hot_docx_artifact_failed")
        raise
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def brief_docx(saved: dict) -> bytes:
    """Caller obtains saved input through Manager's signed/hash-verified brief read."""
    try:
        if (not isinstance(saved, dict) or not re.fullmatch(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", saved.get("briefId", ""))
                or type(saved.get("version")) is not int or not 1 <= saved["version"] <= 1000000
                or not re.fullmatch(r"[a-f0-9]{64}", saved.get("contentHash", ""))):
            raise ValueError("hot_docx_input_invalid")
        p = saved["payload"]
        if p["schemaVersion"] != 1 or not 1 <= len(p["events"]) <= 20 or len(json.dumps(p, ensure_ascii=False).encode()) > 524288:
            raise ValueError("hot_docx_input_invalid")
        zone = ZoneInfo(p["timezone"])
        def text(value):
            return "未知" if value is None else str(value)
        def time(value):
            if value is None:
                return "未知"
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("hot_docx_time_invalid")
            return parsed.astimezone(zone).strftime("%Y-%m-%d %H:%M:%S")
        identity = f"简报 {saved['briefId']} · 版本 {saved['version']} · 内容哈希 {saved['contentHash']}"
        if "selection" in p:
            selection = p["selection"]
            if (not isinstance(selection, dict) or set(selection) != {"kind", "planId", "planVersion", "runId", "missedPeriods"}
                    or selection["kind"] != "periodic" or type(selection["planVersion"]) is not int or selection["planVersion"] < 1
                    or type(selection["missedPeriods"]) is not int or selection["missedPeriods"] < 0
                    or any(not isinstance(selection[key], str) or not re.fullmatch(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", selection[key]) for key in ["planId", "runId"])):
                raise ValueError("hot_docx_selection_invalid")
            identity += f"\n周期计划 {selection['planId']} · 版本 {selection['planVersion']} · 运行 {selection['runId']} · 跳过周期 {selection['missedPeriods']}"
        sections = [{"id": "provenance", "title": "版本与选材依据", "content": "\n".join([
            identity, "显示时区：" + p["timezone"], f"频道 {p['channel']['channel_id']} · 配置版本 {p['channel']['version']}",
            "选材发布时间窗口：" + (time(p['window']['from']) if p['window']['from'] else "未指定") + " — " + (time(p['window']['to']) if p['window']['to'] else "未指定")])}]
        for index, event in enumerate(p["events"]):
            lines = ["事件摘要（归组结果）：" + event["title"], f"事件 {event['canonicalId']} · 版本 {event['revision']}",
                     "发生：" + time(event["occurredAt"]) + " · 生效：" + time(event["effectiveAt"])]
            for basis in event["judgments"]:
                j = basis["judgment"]
                lines += [{"human": "人工判断", "model": "模型推断", "rule": "规则判断"}[basis["authority"]],
                          f"相关性 {j['relevance']} · 研究重要性 {j['importance']} · 热度 {j['heat']} · 信息增量 {j['informationIncrement']}", j["reason"],
                          f"原事件/频道版本 {basis['event_revision']}/{basis['channel_version']} · 应用版本 {basis['applied_event_revision']}/{basis['applied_channel_version']} · " + ("继承判断" if basis["inherited"] else "当前版本判断")]
                details = (basis.get("ruleEvidence") or {}).get("details") or {}
                for source in details.get("coverage", []):
                    snapshot = source.get("snapshot") or {}
                    lines.append(f"原判断覆盖：{source['operator']} · " + ("启用" if source["enabled"] else "暂停") + f" · {snapshot.get('coverage', '无覆盖记录')} · {snapshot.get('parsedCount', '未知')} 条")
            for report in event["reports"]:
                lines += ["来源摘录（发布者陈述）：" + report["title"], report["excerpt"],
                          f"材料 {report['materialId']} · 版本 {report['revision']} · 内容哈希 {report['contentHash']} · 状态 {report['state']}",
                          "发表：" + time(report["publishedAt"]) + " · 取得：" + time(report["acquiredAt"]) + " · 来源更新时间：" + time(report.get("sourceUpdatedAt")),
                          "运营主体：" + "、".join(source['operator'] for source in report['sources']),
                          "摘录截断；全文按原材料版本读取。" if report["excerptIsPartial"] else "摘录不代表完整原文。",
                          "原始链接：" + report["url"]]
            # Preserve every character; split large bodies before the report normalizer's 100k section limit.
            content = "\n".join(lines)
            for part, offset in enumerate(range(0, len(content), 90000)):
                sections.append({"id": f"event-{index}-{part}", "title": f"事件 {index + 1}" + (f"（续 {part}）" if part else ""), "content": content[offset:offset + 90000]})
        if len(sections) > 80:
            raise ValueError("hot_docx_limit")
        payload = {"title": "热点与事件简报", "as_of": time(p["cutoff"]) + " · " + p["timezone"],
                   "summary": "归组摘要、发布者陈述与规则/模型/人工判断分别呈现；本次导出不创建研究会话或调用模型。",
                   "sections": sections, "missing": p["limitations"]}
        document = build_docx_document(payload, {})
        document.core_properties.identifier = saved["briefId"]
        document.core_properties.comments = identity
        output = io.BytesIO();document.save(output)
        data = output.getvalue()
        if len(data) > 5 * 1024 * 1024:
            raise ValueError("hot_docx_limit")
        log.info("hot_docx_projected")
        return data
    except Exception:
        log.warning("hot_docx_projection_failed")
        raise
