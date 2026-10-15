"""Frozen brief projection reuses the reviewed report DOCX writer without a session."""
import io
import unittest
import zipfile
from docx import Document
from app.research_web.hot_documents import brief_docx, retain_brief_docx
from app.research_web.report_documents import build_docx_document


def saved():
    return {"briefId": "11111111-1111-4111-8111-111111111111", "version": 1, "contentHash": "a" * 64,
            "payload": {"schemaVersion": 1, "timezone": "Asia/Shanghai", "cutoff": "2026-10-09T00:00:00Z", "window": {"from": None, "to": None},
                        "channel": {"channel_id": "macro", "version": 1}, "limitations": ["Snapshot coverage only"],
                        "events": [{"canonicalId": "event", "revision": 1, "title": "Policy <literal>", "occurredAt": None, "effectiveAt": None,
                                    "judgments": [{"authority": "human", "event_revision": 1, "channel_version": 1, "applied_event_revision": 2, "applied_channel_version": 2, "inherited": True,
                                                   "judgment": {"relevance": 90, "importance": 80, "heat": 0, "informationIncrement": 0, "reason": "Review"}}],
                                    "reports": [{"materialId": "material", "revision": 1, "contentHash": "b" * 64, "title": "Source", "excerpt": "Literal {{标题}} & <xml>",
                                                 "excerptIsPartial": True, "publishedAt": None, "acquiredAt": "2026-10-08T00:00:00Z", "sourceUpdatedAt": None,
                                                 "state": "active", "sources": [{"operator": "Official"}], "url": "https://example.com/source"}]}]}}


class BriefDocxTests(unittest.TestCase):
    def test_one_shot_projection_does_not_load_legacy_settings_or_model_environment(self):
        import json
        import os
        from pathlib import Path
        import subprocess
        import sys
        code = "import json,sys;sys.modules['core']=None;from app.research_web.hot_periodic_report import render;r=render(json.load(sys.stdin));print(r['state'])"
        result = subprocess.run([sys.executable, '-c', code], input=json.dumps({"protocol": "rwb-hot-report/v1", "saved": saved()}),
                                text=True, capture_output=True, timeout=25, cwd=Path(__file__).resolve().parents[2],
                                env={key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "TMPDIR", "TMP", "TEMP"}})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'completed')

    def test_one_shot_report_uses_existing_word_mechanism_without_runtime(self):
        import base64
        import hashlib
        from app.research_web.hot_periodic_report import render
        value = saved()
        result = render({"protocol": "rwb-hot-report/v1", "saved": value})
        raw = base64.b64decode(result["data"], validate=True)
        self.assertEqual((result["state"], result["inputHash"]), ("completed", value["contentHash"]))
        self.assertEqual(result["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertIn("Policy <literal>", "\n".join(p.text for p in Document(io.BytesIO(raw)).paragraphs))
        with self.assertRaisesRegex(ValueError, "hot_periodic_report_invalid"):
            render({"protocol": "invalid", "saved": value})

    def test_day_precision_and_date_source_evidence_are_exported_without_midnight(self):
        value = saved()
        event = value["payload"]["events"][0]
        event["occurredAt"] = "2026-09-29"
        event["dateEvidence"] = {"occurred": {"value": "2026-09-29", "precision": "day", "timezone": "America/New_York",
                                             "evidence": {"id": "material-id", "revision": 1, "quote": "Agencies published letters"}}, "effective": None}
        doc = Document(io.BytesIO(brief_docx(value)))
        text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
        self.assertIn("2026-09-29（日精度）", text)
        self.assertIn("America/New_York", text)
        self.assertIn("Agencies published letters", text)
        self.assertNotIn("2026-09-29 00:00", text)
        event["occurredAt"] = "2026-02-30"
        with self.assertRaises(ValueError):
            brief_docx(value)

    def test_periodic_provenance_and_skipped_periods_are_preserved_in_word(self):
        value = saved()
        identifier = value["briefId"]
        value["payload"]["selection"] = {"kind": "periodic", "planId": identifier, "planVersion": 2, "runId": identifier, "missedPeriods": 3}
        text = "\n".join(p.text for p in Document(io.BytesIO(brief_docx(value))).paragraphs)
        self.assertIn("周期计划 " + identifier, text)
        self.assertIn("跳过周期 3", text)
        value["payload"]["selection"]["missedPeriods"] = True
        with self.assertRaises(ValueError):
            brief_docx(value)

    def test_docx_retains_provenance_unknowns_and_source_assertions(self):
        data = brief_docx(saved())
        document = Document(io.BytesIO(data))
        text = "\n".join(p.text for p in document.paragraphs)
        for expected in ["a" * 64, "b" * 64, "Asia/Shanghai", "人工判断", "来源摘录", "Literal {{标题}} & <xml>", "未知", "继承", "摘录截断"]:
            self.assertIn(expected, text)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertIsNone(archive.testzip())
            self.assertFalse(any("vbaProject" in name for name in archive.namelist()))

    def test_large_event_does_not_truncate_report_text_at_old_section_limit(self):
        value = saved()
        report = value["payload"]["events"][0]["reports"][0]
        value["payload"]["events"][0]["reports"] = [{**report, "materialId": str(i), "excerpt": "x" * 1000 + f" END-{i}"} for i in range(120)]
        data = brief_docx(value)
        text = "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
        self.assertIn("END-119", text)

    def test_invalid_identity_or_oversized_payload_rejects(self):
        value = saved();value["briefId"] = "../other"
        with self.assertRaises(ValueError):
            brief_docx(value)

    def test_shared_writer_preserves_locked_template_replacements(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "template.docx"
            template = Document();template.add_paragraph("{{标题}}")
            template.add_table(rows=1, cols=1).cell(0, 0).text = "{{market}}"
            template.save(path)
            projected = build_docx_document({"title": "Report", "as_of": "date", "summary": "", "sections": [], "missing": []}, {"标题": "Title", "market": "Evidence"}, path)
            self.assertEqual(projected.paragraphs[0].text, "Title")
            self.assertEqual(projected.tables[0].cell(0, 0).text, "Evidence")

    def test_private_artifact_survives_and_rejects_alias_directory(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as root:
            home = Path(root).resolve()
            data = brief_docx(saved())
            path = retain_brief_docx(home, saved(), data)
            self.assertEqual(path.read_bytes(), data)
            self.assertEqual(retain_brief_docx(home, saved(), data), path)
            self.assertFalse((home / "sessions").exists())
        with tempfile.TemporaryDirectory() as root:
            home = Path(root).resolve();(home / "hot").symlink_to(home)
            with self.assertRaises(ValueError):
                retain_brief_docx(home, saved(), b"data")
