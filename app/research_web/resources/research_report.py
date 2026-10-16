"""Offline research artifacts sharing one payload and an embedded Chinese font."""

import hashlib
import html
import json
import logging
import os
import re
import shutil
import stat
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

log = logging.getLogger("research_web.report")


def source_id(url):
    return "web:" + hashlib.sha256(url.encode()).hexdigest()[:24]


def validate_payload(value):
    if not isinstance(value, dict) or not re.fullmatch(
        r"[a-f0-9]{24}", str(value.get("task_id", ""))
    ):
        raise ValueError("research_report_task_invalid")
    if not isinstance(value.get("title"), str) or not 1 <= len(value["title"]) <= 200:
        raise ValueError("research_report_title_invalid")
    sections, sources = value.get("sections"), value.get("sources", [])
    if not isinstance(sections, list) or not 1 <= len(sections) <= 50:
        raise ValueError("research_report_sections_invalid")
    if not isinstance(sources, list) or len(sources) > 200:
        raise ValueError("research_report_sources_invalid")
    ids = set()
    for item in sources:
        if not isinstance(item, dict) or not re.fullmatch(
            r"(?:web|file|dataset):[a-zA-Z0-9_-]{1,80}", str(item.get("id", ""))
        ):
            raise ValueError("research_report_source_invalid")
        if item["id"] in ids or not isinstance(item.get("title"), str) or len(item["title"]) > 1000:
            raise ValueError("research_report_source_duplicate_or_title")
        ids.add(item["id"])
        url = item.get("url")
        if url:
            if not isinstance(url, str) or len(url) > 4000 or any(ord(c) < 33 for c in url):
                raise ValueError("research_report_url_invalid")
            parts = urlsplit(url)
            if (
                parts.scheme not in {"http", "https"}
                or not parts.hostname
                or parts.username
                or parts.password
            ):
                raise ValueError("research_report_url_invalid")
    stage_ids = set()
    for item in sections:
        if not isinstance(item, dict) or any(
            not isinstance(item.get(k), str) for k in ("heading", "text")
        ):
            raise ValueError("research_report_section_invalid")
        if not item["heading"].strip() or len(item["heading"]) > 200 or len(item["text"]) > 100000:
            raise ValueError("research_report_section_size")
        stage = item.get("id")
        if stage is not None:
            if (
                not isinstance(stage, str)
                or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", stage)
                or stage in stage_ids
            ):
                raise ValueError("research_report_stage_invalid")
            stage_ids.add(stage)
        refs = item.get("citations", [])
        if (
            not isinstance(refs, list)
            or len(refs) > 200
            or any(not isinstance(ref, str) or ref not in ids for ref in refs)
        ):
            raise ValueError("research_report_citation_unknown")
    for key in ("required_sections", "missing"):
        values = value.get(key, [])
        if (
            not isinstance(values, list)
            or len(values) > 100
            or any(not isinstance(s, str) or len(s) > 10000 for s in values)
        ):
            raise ValueError("research_report_list_invalid")
    notes = value.get("notes", [])
    if not isinstance(notes, list) or len(notes) > 100:
        raise ValueError("research_report_notes_invalid")
    for note in notes:
        if (
            not isinstance(note, dict)
            or not isinstance(note.get("text"), str)
            or len(note["text"]) > 100000
        ):
            raise ValueError("research_report_note_invalid")
        refs = note.get("citations", [])
        if note.get("stage_id") is not None and note["stage_id"] not in stage_ids:
            raise ValueError("research_report_note_stage_unknown")
        if not isinstance(refs, list) or any(
            not isinstance(ref, str) or ref not in ids for ref in refs
        ):
            raise ValueError("research_report_note_citation_unknown")
    coverage = value.get("coverage", [])
    if not isinstance(coverage, list) or len(coverage) > 100:
        raise ValueError("research_report_coverage_invalid")
    for row in coverage:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("requirement_id"), str)
            or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", row["requirement_id"])
            or not isinstance(row.get("section_ids"), list)
            or len(row["section_ids"]) > 50
            or any(not isinstance(s, str) or s not in stage_ids for s in row["section_ids"])
            or not isinstance(row.get("excerpt"), str)
            or not 1 <= len(row["excerpt"]) <= 10000
        ):
            raise ValueError("research_report_coverage_invalid")
    claims = value.get("numeric_claims", [])
    if not isinstance(claims, list) or len(claims) > 200:
        raise ValueError("research_report_numeric_claim_invalid")
    claim_ids = set()
    for claim in claims:
        if (
            not isinstance(claim, dict)
            or not isinstance(claim.get("id"), str)
            or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", claim["id"])
            or claim["id"] in claim_ids
            or claim.get("section_id") not in stage_ids
            or any(
                not isinstance(claim.get(key), str) or not 1 <= len(claim[key]) <= 10000
                for key in ("text", "unit", "period")
            )
            or isinstance(claim.get("value"), bool)
            or not isinstance(claim.get("value"), (str, int, float))
            or claim.get("operation", "identity")
            not in {"identity", "sum", "difference", "ratio", "percent_change"}
            or not isinstance(claim.get("operands"), list)
            or not 1 <= len(claim["operands"]) <= 50
        ):
            raise ValueError("research_report_numeric_claim_invalid")
        claim_ids.add(claim["id"])
        for operand in claim["operands"]:
            if (
                not isinstance(operand, dict)
                or any(
                    not isinstance(operand.get(key), str) or not 1 <= len(operand[key]) <= 10000
                    for key in ("observation_id", "quote", "period", "unit")
                )
                or isinstance(operand.get("value"), bool)
                or not isinstance(operand.get("value"), (str, int, float))
            ):
                raise ValueError("research_report_numeric_claim_operand_invalid")
    if len(json.dumps(value, ensure_ascii=False).encode()) > 2_000_000:
        raise ValueError("research_report_size")
    return value


def _bounded_bytes(path, maximum=16 * 1024 * 1024):
    if path.is_symlink() or not path.is_file():
        raise ValueError("research_report_archive_alias_or_missing")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as stream:
        opened = os.fstat(stream.fileno())
        original = path.lstat()
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (
            original.st_dev,
            original.st_ino,
        ):
            raise ValueError("research_report_archive_alias")
        body = stream.read(maximum + 1)
    if len(body) > maximum:
        raise ValueError("research_report_archive_size")
    return body


def _version_read(directory):
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("research_report_archive_alias")
    version = json.loads(_bounded_bytes(directory / "version.json", 2_000_000))
    if not isinstance(version, dict):
        raise TypeError("research_report_archive_changed")
    rows = version.get("files", [])
    if (
        not isinstance(rows, list)
        or not 1 <= len(rows) <= 4
        or any(not isinstance(row, dict) for row in rows)
    ):
        raise ValueError("research_report_archive_changed")
    for row in rows:
        name = row.get("stored_name")
        if not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9._-]{1,240}", name):
            raise ValueError("research_report_archive_changed")
        if hashlib.sha256(_bounded_bytes(directory / name)).hexdigest() != row.get("sha256"):
            raise ValueError("research_report_archive_changed")
    manifest = next((row for row in rows if row.get("name") == "research-report.json"), None)
    if not manifest:
        raise ValueError("research_report_archive_changed")
    raw = _bounded_bytes(directory / manifest["stored_name"], 2_000_000)
    report = validate_payload(json.loads(raw))
    archived_hashes = {row.get("name"): row.get("sha256") for row in rows}
    artifacts = report.get("artifacts", [])
    if not isinstance(artifacts, list) or any(not isinstance(row, dict) for row in artifacts):
        raise ValueError("research_report_archive_changed")
    missing = [row.get("name") for row in artifacts if row.get("name") not in archived_hashes]
    missing_formats = sorted(
        {"html", "docx", "pdf"}
        - {name.rsplit(".", 1)[-1] for name in archived_hashes if name != "research-report.json"}
    )
    snapshot = _snapshot_digest(archived_hashes, missing, missing_formats)
    identity = report["task_id"] + "-" + hashlib.sha256(raw).hexdigest()[:24] + "-" + snapshot[:12]
    if (
        report["task_id"] != version.get("task_id")
        or version.get("version_id") != identity
        or version.get("directory") != "report-versions/" + identity
        or (not directory.name.startswith(".pending-") and directory.name != identity)
        or version.get("missing_artifacts") != missing
        or version.get("missing_formats") != missing_formats
        or any(
            archived_hashes.get(row.get("name")) != row.get("sha256")
            for row in artifacts
            if row.get("name") not in missing
        )
    ):
        raise ValueError("research_report_archive_changed")
    return version


def _snapshot_digest(hashes, missing, formats):
    return hashlib.sha256(
        json.dumps(
            {"hashes": hashes, "missing_artifacts": missing, "missing_formats": formats},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def archive_report_version(output, expected_task_id=None):
    """Verify and atomically retain the current payload and all published bytes."""
    output = Path(output)
    if output.is_symlink():
        raise ValueError("research_report_archive_alias")
    current = output / "research-report.json"
    if not current.exists() and not current.is_symlink():
        return None
    try:
        raw = _bounded_bytes(current, 2_000_000)
        payload = validate_payload(json.loads(raw))
        if expected_task_id is not None and payload["task_id"] != expected_task_id:
            raise ValueError("research_report_archive_task_mismatch")
        artifacts = payload.get("artifacts", [])
        if (
            not isinstance(artifacts, list)
            or len(artifacts) > 3
            or any(
                not isinstance(row, dict) or not isinstance(row.get("name"), str)
                for row in artifacts
            )
            or len({row["name"].rsplit(".", 1)[-1] for row in artifacts}) != len(artifacts)
            or not {row["name"].rsplit(".", 1)[-1] for row in artifacts}.issubset(
                {"html", "docx", "pdf"}
            )
        ):
            raise ValueError("research_report_archive_artifact_invalid")
        bodies = {"research-report.json": raw}
        missing = []
        for artifact in artifacts:
            name = artifact.get("name")
            if not isinstance(name, str) or not re.fullmatch(
                r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,149}", name
            ):
                raise ValueError("research_report_archive_artifact_invalid")
            if not (output / name).exists() and not (output / name).is_symlink():
                missing.append(name)
                continue
            body = _bounded_bytes(output / name)
            if hashlib.sha256(body).hexdigest() != artifact.get("sha256"):
                raise ValueError("research_report_archive_artifact_changed")
            bodies[name] = body
        digest = hashlib.sha256(raw).hexdigest()
        hashes = {name: hashlib.sha256(body).hexdigest() for name, body in bodies.items()}
        missing_formats = sorted(
            {"html", "docx", "pdf"}
            - {name.rsplit(".", 1)[-1] for name in bodies if name != "research-report.json"}
        )
        snapshot = _snapshot_digest(hashes, missing, missing_formats)
        version_id = payload["task_id"] + "-" + digest[:24] + "-" + snapshot[:12]
        archive = output / "report-versions"
        if archive.is_symlink():
            raise ValueError("research_report_archive_alias")
        archive.mkdir(exist_ok=True)
        target = archive / version_id
        version = {
            "task_id": payload["task_id"],
            "version_id": version_id,
            "directory": "report-versions/" + version_id,
            "missing_artifacts": missing,
            "missing_formats": missing_formats,
            "files": [
                {
                    "name": name,
                    "stored_name": version_id + "-" + name,
                    "sha256": hashlib.sha256(body).hexdigest(),
                }
                for name, body in bodies.items()
            ],
        }
        if target.exists() or target.is_symlink():
            existing = _version_read(target)
            if existing != version:
                raise ValueError("research_report_archive_changed")
            return existing
        pending = Path(tempfile.mkdtemp(prefix=".pending-", dir=archive))
        try:
            for row in version["files"]:
                destination = pending / row["stored_name"]
                with destination.open("xb") as stream:
                    stream.write(bodies[row["name"]])
                    stream.flush()
                    os.fsync(stream.fileno())
                destination.chmod(0o444)
            (pending / "version.json").write_text(json.dumps(version), encoding="utf-8")
            (pending / "version.json").chmod(0o444)
            _version_read(pending)
            try:
                pending.rename(target)
            except OSError:
                if not target.exists() or _version_read(target) != version:
                    raise
        finally:
            if pending.exists():
                shutil.rmtree(pending)
        log.info("research_report_version_archived files=%d", len(version["files"]))
        return version
    except OSError as exc:
        log.warning("research_report_archive_failed type=%s", type(exc).__name__)
        raise ValueError("research_report_archive_io_failed") from None
    except (ValueError, TypeError, KeyError, RecursionError) as exc:
        log.warning("research_report_archive_failed type=%s", type(exc).__name__)
        raise


def list_report_versions(output, limit=20):
    """Project bounded verified versions; never treat old quality claims as trusted."""
    output = Path(output)
    archive = output / "report-versions"
    if archive.is_symlink() or output.is_symlink():
        raise ValueError("research_report_archive_alias")
    if not archive.exists():
        return []
    if not isinstance(limit, int) or not 1 <= limit <= 20:
        raise ValueError("research_report_archive_limit_invalid")
    versions = []
    for path in sorted(archive.iterdir(), key=lambda item: item.name, reverse=True):
        if path.name.startswith("."):
            continue
        try:
            version = _version_read(path)
            manifest = next(
                row for row in version["files"] if row["name"] == "research-report.json"
            )
            versions.append(
                {
                    **version,
                    "report": json.loads(_bounded_bytes(path / manifest["stored_name"], 2_000_000)),
                    "quality": "incomplete",
                }
            )
        except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
            log.warning("research_report_version_invalid type=%s", type(exc).__name__)
            versions.append(
                {
                    "version_id": path.name,
                    "quality": "invalid",
                    "issues": ["report_archive_invalid"],
                }
            )
        if len(versions) >= limit:
            break
    return versions


def report_blocks(payload):
    """The same text/version is consumed by all three renderers."""
    blocks = [(payload["title"], True)]
    if payload.get("as_of"):
        blocks.append(("研究截止时间：" + str(payload["as_of"]), False))
    for section in payload["sections"]:
        blocks.extend([(section["heading"], True), (section["text"], False)])
        if section.get("citations"):
            blocks.append(("引用：" + ", ".join(section["citations"]), False))
    blocks.append(("来源与证据", True))
    for source in payload.get("sources", []):
        blocks.append(
            (source["id"] + " · " + source["title"] + " " + str(source.get("url", "")), False)
        )
    missing = list(payload.get("missing", []))
    headings = {s["heading"] for s in payload["sections"]}
    missing.extend(
        "未覆盖要求：" + s for s in payload.get("required_sections", []) if s not in headings
    )
    if missing:
        blocks.append(("缺口与限制（研究质量未通过）", True))
        blocks.extend((text, False) for text in missing)
    return blocks


def render_pdf(path, payload):
    path = Path(path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent / path
    try:
        previous_directory = os.getcwd()
    except PermissionError:
        previous_directory = str(Path(__file__).resolve().parent.parent)
    try:
        # ReportLab initializes paths from CWD. Only the already writable output
        # directory is readable under Seatbelt; session-root grants stay closed.
        os.chdir(path.parent)
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

        font = Path(__file__).with_name("fonts") / "NotoSansSC-Regular.ttf"
        if font.is_symlink() or not font.is_file():
            raise ValueError("research_pdf_font_missing")
        pdfmetrics.registerFont(TTFont("ResearchCJK", str(font)))
        styles = {
            True: ParagraphStyle(
                "heading",
                fontName="ResearchCJK",
                fontSize=15,
                leading=22,
                wordWrap="CJK",
                spaceBefore=12,
                keepWithNext=True,
            ),
            False: ParagraphStyle(
                "body",
                fontName="ResearchCJK",
                fontSize=10,
                leading=17,
                wordWrap="CJK",
                splitLongWords=True,
            ),
        }
        story = []
        for text, heading in report_blocks(payload):
            if any(
                ord(char) not in pdfmetrics.getFont("ResearchCJK").face.charToGlyph
                for char in text
                if char not in "\n\r\t"
            ):
                raise ValueError("research_pdf_glyph_missing")
            story.extend(
                [Paragraph(html.escape(text).replace("\n", "<br/>"), styles[heading]), Spacer(1, 6)]
            )
        SimpleDocTemplate(
            str(path),
            pagesize=A4,
            title=payload["title"],
            leftMargin=42,
            rightMargin=42,
            topMargin=42,
            bottomMargin=42,
        ).build(story)
        log.info("research_pdf_rendered")
        return Path(path)
    except Exception as exc:
        log.error("research_pdf_render_failed type=%s", type(exc).__name__)
        raise
    finally:
        os.chdir(previous_directory)


def write_research_report(output, payload):
    import pdfplumber
    from docx import Document

    try:
        validate_payload(payload)
        output = Path(output)
        output.mkdir(parents=True, exist_ok=True)
        stem = "research-report-" + uuid4().hex[:12]
        paths = {kind: output / (stem + "." + kind) for kind in ("html", "docx", "pdf")}
        paths["json"] = output / "research-report.json"
        if any(p.is_symlink() for p in paths.values()):
            raise ValueError("research_report_output_alias")
        archive_report_version(output)
        blocks = report_blocks(payload)
        doc = Document()
        for text, heading in blocks:
            doc.add_heading(text, level=1) if heading else doc.add_paragraph(text)
        doc.save(paths["docx"])
        body = "".join(
            f'<{"h2" if heading else "p"}>{html.escape(text)}</{"h2" if heading else "p"}>'
            for text, heading in blocks
        )
        paths["html"].write_text(
            '<!doctype html><html lang="zh"><meta charset="utf-8"><title>'
            + html.escape(payload["title"])
            + "</title><body>"
            + body
            + "</body></html>",
            encoding="utf-8",
        )
        render_pdf(paths["pdf"], payload)
        Document(paths["docx"])
        with pdfplumber.open(paths["pdf"]) as pdf:
            if not pdf.pages or not any((p.extract_text() or "").strip() for p in pdf.pages):
                raise ValueError("research_pdf_empty")
        published = {
            **payload,
            "artifacts": [
                {"name": paths[k].name, "sha256": hashlib.sha256(paths[k].read_bytes()).hexdigest()}
                for k in ("html", "docx", "pdf")
            ],
        }
        manifest = output / (stem + ".json")
        manifest.write_text(json.dumps(published, ensure_ascii=False), encoding="utf-8")
        manifest.replace(paths["json"])
        log.info("research_report_rendered formats=3")
        return paths
    except Exception as exc:
        log.error("research_report_failed type=%s", type(exc).__name__)
        raise
