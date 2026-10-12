"""Host reconstruction preserves authenticated original bytes without model or control calls."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_workbench_entrypoint.hot import HotError
from research_workbench_entrypoint.hot_manager import HotManager

ID = "11111111-1111-4111-8111-111111111111"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


class EvidenceReadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name).resolve()
        self.manager = HotManager(root, root / "home", object())
        self.blob = ("原文🙂\x00" * 12000).encode()
        context = {"schemaVersion": 1, "cutoff": "2026-10-08T00:00:00Z", "timezone": "Asia/Shanghai"}
        self.manifest = {"schemaVersion": 1, "instanceId": ID, "briefId": ID, "version": 1, "materialIds": [ID],
                         "briefContext": context, "briefContentHash": hashlib.sha256(canonical(context)).hexdigest(),
                         "cutoff": context["cutoff"], "timezone": context["timezone"], "totalBytes": len(self.blob),
                         "objects": [{"key": "raw:" + ID, "filename": "raw-" + ID + ".bin", "format": "application/octet-stream",
                                      "bytes": len(self.blob), "contentHash": hashlib.sha256(self.blob).hexdigest()}]}
        material_key = "material:" + ID + ":1"
        full = b'{"materialId":"' + ID.encode() + b'","revision":1,"excerpt":"complete"}'
        self.blobs = {"raw:" + ID: self.blob, material_key: full}
        self.manifest["objects"].append({"key": material_key, "filename": "material-" + ID + "-r1.json",
                                         "format": "application/json", "bytes": len(full),
                                         "contentHash": hashlib.sha256(full).hexdigest()})
        self.manifest["totalBytes"] += len(full)
        self.manifest["materials"] = [{"materialId": ID, "revision": 1, "contentHash": "a" * 64,
                                        "normalizedObject": material_key, "rawObject": "raw:" + ID}]
        self.anchor_hash = self.manifest["briefContentHash"]
        self.calls = []

    def tearDown(self):
        self.temp.cleanup()

    def reply(self, port, owner, secret, operation, params):
        import base64
        self.calls.append((operation, params))
        digest = hashlib.sha256(canonical(self.manifest)).hexdigest()
        if operation == "brief.get":
            return {"briefId": ID, "version": 1, "contentHash": self.anchor_hash, "payload": self.manifest["briefContext"]}
        if operation == "research.evidence":
            blob = canonical(self.manifest)
            offset = params.get("offset", 0)
            chunk = blob[offset:offset + 32768]
            end = offset + len(chunk)
            return {"manifestHash": digest, "contentHash": digest, "offset": offset, "totalBytes": len(blob),
                    "dataBase64": base64.b64encode(chunk).decode(), "nextOffset": end if end < len(blob) else None}
        self.assertEqual(operation, "research.original")
        offset = params["offset"]
        blob = self.blobs[params["objectKey"]]
        chunk = blob[offset:offset + 32768]
        end = offset + len(chunk)
        return {"manifestHash": digest, "objectKey": params["objectKey"], "offset": offset,
                "totalBytes": len(blob), "contentHash": hashlib.sha256(blob).hexdigest(),
                "dataBase64": base64.b64encode(chunk).decode(), "nextOffset": end if end < len(blob) else None}

    def read(self, reply=None):
        with patch.object(self.manager, "_state", return_value={"port": 1, "owner": {"instanceId": ID}}), patch.object(self.manager, "_secret", return_value="fixture-reader"), patch("research_workbench_entrypoint.hot_manager.rpc", side_effect=reply or self.reply):
            return self.manager.research_evidence(ID, 1, [ID])

    def test_reconstructs_every_byte_and_queries_only_reader_methods(self):
        result = self.read()
        self.assertEqual(result["objects"]["raw:" + ID], self.blob)
        self.assertEqual(result["manifest"], self.manifest)
        self.assertGreater(len(self.calls), 2)
        self.assertTrue(all(params["version"] == 1 for _, params in self.calls))

    def test_corrupt_chunk_or_manifest_and_unselected_path_fail_closed(self):
        def corrupt(*args):
            value = self.reply(*args)
            if args[3] == "research.original":
                value["dataBase64"] = "Y29ycnVwdA=="
            return value
        with self.assertRaises(HotError):
            self.read(corrupt)
        self.manifest["objects"][0]["filename"] = "../../foreign"
        with self.assertRaises(HotError):
            self.read()

    def test_unverified_brief_or_oversize_and_invalid_selection_do_not_publish(self):
        self.manifest["briefContentHash"] = "0" * 64
        with self.assertRaises(HotError):
            self.read()
        for version, ids in [(0, [ID]), (1, []), (1, [ID, ID])]:
            with self.assertRaises(HotError):
                self.manager.research_evidence(ID, version, ids)
        self.assertFalse((self.manager.home / "sessions").exists())

    def test_manifest_uses_exact_producer_bytes_across_chunks_and_number_spellings(self):
        import base64
        self.manifest["briefContext"].update(number=1e-7, large="source " * 10000)
        self.anchor_hash = hashlib.sha256(canonical(self.manifest["briefContext"])).hexdigest()
        self.manifest["briefContentHash"] = self.anchor_hash
        wire = canonical(self.manifest).replace(b"1e-07", b"1e-7")
        digest = hashlib.sha256(wire).hexdigest()
        def producer(*args):
            if args[3] == "research.evidence":
                offset = args[4].get("offset", 0)
                part = wire[offset:offset + 32768]
                end = offset + len(part)
                return {"manifestHash": digest, "contentHash": digest, "offset": offset,
                        "totalBytes": len(wire), "dataBase64": base64.b64encode(part).decode(),
                        "nextOffset": end if end < len(wire) else None}
            result = self.reply(*args)
            if args[3] == "research.original":
                result["manifestHash"] = digest
            return result
        result = self.read(producer)
        self.assertEqual(result["manifestBytes"], wire)
        self.assertEqual(result["manifestHash"], digest)
        self.assertEqual(result["manifest"]["briefContext"]["number"], 1e-7)
