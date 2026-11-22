"""Pure reference contracts: declarations never grant execution or evidence trust."""

import hashlib
import importlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class ScenariosCatalogTest(unittest.TestCase):
    def setUp(self):
        try:
            self.api = importlib.import_module("app.research_web.scenarios")
        except ModuleNotFoundError:
            self.fail("scenario catalog read API is not implemented")

    def inputs(self, scenario_id="company-onepager"):
        kind = "industry" if scenario_id == "industry-onepager" else "stock"
        values = {
            "subject": {"kind": kind, "identity": "600600.SH" if kind == "stock" else "SW:801080"},
            "as_of": "2026-10-26",
            "question": "核对驱动、证据与风险",
            "material_ids": ["material-1"],
        }
        if scenario_id == "historical-review":
            values["window_start"] = "2026-01-01"
        return values

    def qualified(self, scenario_id="company-onepager"):
        contract = self.api.get_scenario(scenario_id)
        caps = {key: {"owner_id": "alice", "available": True} for key in contract["capability_ids"]}
        evidence = {
            key: {"owner_id": "alice", "eligible": True} for key in contract["required_data"]
        }
        return {
            "capability_qualification": caps,
            "evidence_eligibility": evidence,
            "owner_id": "alice",
        }

    def test_frozen_counts_identities_and_authority(self):
        catalog = self.api.read_catalog()
        self.assertEqual("1.0.0", catalog["version"])
        self.assertEqual(62, len(catalog["skills"]))
        self.assertEqual(78, len(catalog["tools"]))
        self.assertEqual(9, len([t for t in catalog["tools"] if t["group"] == "pack"]))
        self.assertEqual(140, len({r["id"] for r in catalog["skills"] + catalog["tools"]}))
        self.assertEqual("static_reference_only", catalog["authority"])
        for row in catalog["skills"] + catalog["tools"]:
            self.assertEqual("unverified", row["status"])
            self.assertFalse(row["callable"])
            self.assertFalse(row["runtime_verified"])
            self.assertFalse(row["quality_passed"])
            self.assertTrue(row["dependencies"]["data"])
            self.assertTrue(row["dependencies"]["permission"])
            self.assertTrue(row["dependencies"]["schema"])

    def test_hashes_and_source_scope(self):
        catalog = self.api.read_catalog()
        for source in catalog["sources"]:
            self.assertRegex(source["raw_sha256"], r"^[a-f0-9]{64}$")
            self.assertEqual("2026-10-26", source["observed_on"])
        skills_source, tools_source = catalog["sources"]
        self.assertEqual("catalog_names_only", skills_source["scope"])
        self.assertEqual("https://seek-alpha.cn/skills", skills_source["url"])
        self.assertEqual("https://seek-alpha.cn/api/mcp/tools-meta", tools_source["url"])
        self.assertEqual(12, catalog["metadata_counts"]["groups"])
        self.assertEqual(10, catalog["metadata_counts"]["tiers"])
        self.assertTrue(all(len(t["raw_definition_sha256"]) == 64 for t in catalog["tools"]))

    def test_reference_identity_matches_original_source_signatures(self):
        catalog = self.api.read_catalog()

        def digest(value):
            raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            return hashlib.sha256(raw.encode()).hexdigest()

        self.assertEqual(
            "4c406e8667e111954832e72a4bb91ef0f669ce7c0a0358c144c012abc2249d2b",
            digest([row["name"] for row in catalog["skills"]]),
        )
        signature = [
            [
                row["name"],
                row["group"],
                row["cost"],
                row["internal"],
                [[p["name"], p["type"]] for p in row["parameters"]],
            ]
            for row in catalog["tools"]
        ]
        self.assertEqual(
            "cb00788176ec747ef892123c47e0ed51a85f63c1fd0b2acee417bfb0fb5acf5b",
            digest(signature),
        )
        self.assertEqual(
            "c83ac616eba372132b39ef4816149b188256cf9583a027beef5750ff9be46e3f",
            digest([row["raw_definition_sha256"] for row in catalog["tools"]]),
        )
        self.assertEqual(
            [
                "b6832ef98ee84d5b6f344d37c07a8268067876f361c48c4fcdbbf6c13ec1664f",
                "b1b474d8a3a9698f7c8976aa28d5f64b7d48530376a1207257cfab6916a64763",
            ],
            [row["raw_sha256"] for row in catalog["sources"]],
        )

    def test_read_and_selection_only_open_reference_files_readonly(self):
        original_open = Path.open
        opened = []

        def checked_open(path, mode="r", *args, **kwargs):
            self.assertEqual("rb", mode)
            opened.append(path.name)
            return original_open(path, mode, *args, **kwargs)

        qualified = self.qualified()
        with patch.object(Path, "open", checked_open), patch("socket.create_connection") as network:
            self.api.read_catalog()
            self.api.read_scenarios()
            self.api.select_scenario("company-onepager", self.inputs(), **qualified)
            network.assert_not_called()
        self.assertEqual({"baseline.json", "contracts.json"}, set(opened))

    def test_historical_window_and_capability_flags_are_strict(self):
        values = self.inputs("historical-review")
        values["window_start"] = "2026-10-27"
        with self.assertRaises(self.api.ScenarioError):
            self.api.select_scenario(
                "historical-review", values, **self.qualified("historical-review")
            )
        for flag in (False, None, "true", 1):
            qualified = self.qualified()
            for row in qualified["capability_qualification"].values():
                row["available"] = flag
            result = self.api.select_scenario("company-onepager", self.inputs(), **qualified)
            self.assertFalse(result["eligible_for_draft"])

    def test_unknown_evidence_is_not_qualification(self):
        qualified = self.qualified()
        qualified["evidence_eligibility"]["unknown-data"] = {"owner_id": "alice", "eligible": True}
        with self.assertRaises(self.api.ScenarioError) as caught:
            self.api.select_scenario("company-onepager", self.inputs(), **qualified)
        self.assertEqual("scenario_qualification_invalid", caught.exception.code)

    def test_oversized_catalog_and_io_errors_have_stable_codes(self):
        with patch.object(Path, "open", side_effect=PermissionError("private path")):
            with self.assertRaises(self.api.ScenarioError) as caught:
                self.api.read_catalog()
            self.assertEqual("scenario_catalog_unreadable", caught.exception.code)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "oversized.json"
            path.write_bytes(b"x" * (512 * 1024 + 1))
            with self.assertRaises(self.api.ScenarioError) as caught:
                self.api.read_catalog(path)
            self.assertEqual("scenario_baseline_invalid", caught.exception.code)

    def test_catalog_returns_independent_copies(self):
        first = self.api.read_catalog()
        first["tools"][0]["name"] = "tampered"
        self.assertEqual("query_my_credits", self.api.read_catalog()["tools"][0]["name"])
        first = self.api.get_scenario("company-onepager")
        first["required_data"].clear()
        self.assertTrue(self.api.get_scenario("company-onepager")["required_data"])

    def test_proprietary_internal_bundle_and_cost_boundaries(self):
        catalog = self.api.read_catalog()
        tools = {row["name"]: row for row in catalog["tools"]}
        proprietary = {name for name, row in tools.items() if row["proprietary"]}
        self.assertEqual(
            {"technical_analysis", "run_morphology", "etf_view", "query_morphology_signals"},
            proprietary,
        )
        self.assertEqual("internal_only", tools["query_financial_db"]["access"])
        self.assertTrue(tools["query_financial_db"]["internal"])
        self.assertEqual("deferred", tools["query_financial_db"]["route"])
        self.assertEqual(200, tools["generate_video"]["cost"])
        self.assertIn("100", " ".join(tools["generate_video"]["caveats"]))
        self.assertIn("300", " ".join(tools["generate_video"]["caveats"]))
        self.assertEqual(20, tools["submit_deep_research"]["cost"])
        self.assertTrue(tools["submit_deep_research"]["caveats"])
        for name in ("get_research_status", "list_research_tasks", "stop_research"):
            self.assertEqual(1, tools[name]["cost"])
        for row in tools.values():
            self.assertIn(
                row["route"], {"reuse", "native", "managed_mcp", "declared_dependency", "deferred"}
            )

    def test_first_eight_selection_never_sends_or_certifies(self):
        expected = {
            "company-onepager",
            "industry-onepager",
            "fundamentals",
            "technicals",
            "news-query",
            "news-transmission",
            "research-prep",
            "historical-review",
        }
        self.assertEqual(expected, {r["id"] for r in self.api.read_scenarios()})
        for scenario_id in expected:
            with self.subTest(scenario_id=scenario_id):
                result = self.api.select_scenario(
                    scenario_id, self.inputs(scenario_id), **self.qualified(scenario_id)
                )
                self.assertTrue(result["eligible_for_draft"])
                self.assertFalse(result["auto_send"])
                self.assertFalse(result["frozen"])
                self.assertFalse(result["send_authorized"])
                self.assertFalse(result["runtime_verified"])
                self.assertFalse(result["quality_passed"])
                self.assertTrue(result["contract"]["expected_artifacts"])
                self.assertTrue(result["contract"]["coverage"])

    def test_qualification_missing_unknown_and_foreign_fail_closed(self):
        qualified = self.qualified()
        qualified["capability_qualification"] = {}
        result = self.api.select_scenario("company-onepager", self.inputs(), **qualified)
        self.assertFalse(result["eligible_for_draft"])
        self.assertIn("capability_missing", {r["code"] for r in result["missing"]})
        qualified = self.qualified()
        for row in qualified["capability_qualification"].values():
            row["owner_id"] = "bob"
        result = self.api.select_scenario("company-onepager", self.inputs(), **qualified)
        self.assertIn("capability_foreign", {r["code"] for r in result["missing"]})
        qualified = self.qualified()
        qualified["capability_qualification"]["made-up-capability"] = {
            "owner_id": "alice",
            "available": True,
        }
        with self.assertRaises(self.api.ScenarioError) as caught:
            self.api.select_scenario("company-onepager", self.inputs(), **qualified)
        self.assertEqual("scenario_qualification_invalid", caught.exception.code)

    def test_evidence_missing_foreign_false_and_bool_coercion(self):
        for value in (
            None,
            {"owner_id": "bob", "eligible": True},
            {"owner_id": "alice", "eligible": False},
            {"owner_id": "alice", "eligible": "true"},
        ):
            qualified = self.qualified()
            key = next(iter(qualified["evidence_eligibility"]))
            qualified["evidence_eligibility"][key] = value
            result = self.api.select_scenario("company-onepager", self.inputs(), **qualified)
            self.assertFalse(result["eligible_for_draft"])
            self.assertTrue(result["missing"])

    def test_news_query_allows_topic_and_no_materials(self):
        values = self.inputs()
        values["subject"] = {"kind": "topic", "identity": "半导体出口政策"}
        values["material_ids"] = []
        result = self.api.select_scenario("news-query", values, **self.qualified("news-query"))
        self.assertTrue(result["eligible_for_draft"])
        self.assertEqual([], result["inputs"]["material_ids"])

    def test_invalid_input_rejected_without_echo(self):
        bad_inputs = [
            None,
            {},
            {**self.inputs(), "as_of": "2026-02-30"},
            {**self.inputs(), "question": ""},
            {**self.inputs(), "file_path": "/private/secret"},
            {**self.inputs(), "material_ids": ["https://private.example/secret"]},
            {**self.inputs(), "subject": {"kind": "stock", "identity": "http://evil"}},
            {**self.inputs(), "subject": {"kind": "topic", "identity": "不适用"}},
        ]
        for values in bad_inputs:
            with self.subTest(values=values):
                with self.assertRaises(self.api.ScenarioError) as caught:
                    self.api.select_scenario("company-onepager", values, **self.qualified())
                self.assertEqual("scenario_inputs_invalid", caught.exception.code)
                self.assertNotIn("secret", str(caught.exception))

    def test_missing_materials_are_explicit_gaps(self):
        values = self.inputs()
        values["material_ids"] = []
        result = self.api.select_scenario("company-onepager", values, **self.qualified())
        self.assertFalse(result["eligible_for_draft"])
        self.assertIn("materials_missing", {r["code"] for r in result["missing"]})

    def test_unknown_scenario_and_untrusted_qualification_input(self):
        with self.assertRaises(self.api.ScenarioError) as caught:
            self.api.get_scenario("made-up")
        self.assertEqual("scenario_unknown", caught.exception.code)
        with self.assertRaises(self.api.ScenarioError):
            self.api.select_scenario(
                "company-onepager",
                self.inputs(),
                capability_qualification=None,
                evidence_eligibility={},
                owner_id="alice",
            )
        with self.assertRaises(self.api.ScenarioError):
            self.api.select_scenario(
                "company-onepager",
                self.inputs(),
                capability_qualification={},
                evidence_eligibility={},
                owner_id="",
            )

    def test_missing_corrupt_or_rehashed_invalid_baseline(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "catalog.json"
            with self.assertRaises(self.api.ScenarioError) as caught:
                self.api.read_catalog(target)
            self.assertEqual("scenario_catalog_unreadable", caught.exception.code)
            target.write_text("{}", encoding="utf-8")
            with self.assertRaises(self.api.ScenarioError) as caught:
                self.api.read_catalog(target)
            self.assertEqual("scenario_baseline_invalid", caught.exception.code)

    def test_errors_use_project_logging_without_inputs(self):
        with (
            self.assertLogs("app.research_web.scenarios.catalog", level="WARNING") as logged,
            self.assertRaises(self.api.ScenarioError),
        ):
            self.api.get_scenario("PRIVATE-SECRET")
        self.assertIn("scenario_unknown", " ".join(logged.output))
        self.assertNotIn("PRIVATE-SECRET", " ".join(logged.output))


if __name__ == "__main__":
    unittest.main()
