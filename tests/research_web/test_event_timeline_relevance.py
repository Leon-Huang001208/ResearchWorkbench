"""Market context is an explicit heuristic; unknown candidates are never discarded."""

import io
import json
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from app.research_web.event_timeline import TimelineService
from app.research_web.event_timeline.relevance import candidate_relevance
from app.research_web.event_timeline.sources import parse
from app.research_web.store import Store


def gdelt_row(**columns):
    row = ["" for _ in range(58)]
    for index, value in {
        0: "123",
        1: "20260102",
        2: "202601",
        3: "2026",
        6: "Actor A",
        16: "Actor B",
        26: "010",
        28: "01",
        **{int(key): value for key, value in columns.items()},
    }.items():
        row[index] = value
    archived = io.BytesIO()
    with zipfile.ZipFile(archived, "w") as archive:
        archive.writestr("20260102.export.CSV", "\t".join(row))
    return parse("gdelt", archived.getvalue())["events"][0]


class EventRelevanceTests(unittest.TestCase):
    def test_official_us_macro_marks_potential_transmission_separately(self):
        result = candidate_relevance("fed_fomc")
        states = result["relevance"]["assessments"]
        self.assertEqual(states["US"]["status"], "direct")
        self.assertEqual(states["CN"]["status"], "potential")
        self.assertEqual(states["HK"]["status"], "potential")
        self.assertFalse(result["relevance"]["price_impact_verified"])
        self.assertTrue(result["relevance"]["requires_manual_review"])

    def test_validated_actor_columns_map_cross_market_without_geo_code_guessing(self):
        event = gdelt_row(**{"7": "CHN", "17": "USA", "37": "CH", "44": "US", "51": "HK"})
        self.assertEqual(event["markets"], ["CN", "US"])
        states = event["relevance"]["assessments"]
        self.assertEqual(states["CN"]["status"], "direct")
        self.assertEqual(states["US"]["status"], "direct")
        self.assertEqual(states["HK"]["status"], "unknown")
        geo = next(
            item
            for item in event["relevance"]["basis"]
            if item["field"] == "geographic_country_codes"
        )
        self.assertFalse(geo["used_for_market_mapping"])
        self.assertEqual(geo["value"]["ActionGeo_CountryCode"], "HK")
        self.assertIn("FIPS", geo["scheme"])

    def test_unknown_candidate_survives_without_matching_actor_names(self):
        event = gdelt_row(
            **{
                "6": "USA markets and China",
                "16": "Hong Kong",
                "7": "FRA",
                "17": "GBR",
                "37": "US",
                "51": "CH",
            }
        )
        self.assertEqual(event["markets"], [])
        self.assertEqual(event["external_id"], "123")
        self.assertEqual(event["original_fields"][7], "FRA")
        self.assertTrue(
            all(item["status"] == "unknown" for item in event["relevance"]["assessments"].values())
        )

    def test_invalid_actor_scheme_and_inconsistent_cameo_root_do_not_match(self):
        event = gdelt_row(**{"7": "US", "17": "USA-news", "26": "190", "28": "01"})
        self.assertEqual(event["markets"], [])
        self.assertTrue(
            all(item["status"] == "unknown" for item in event["relevance"]["assessments"].values())
        )
        event_basis = next(
            item for item in event["relevance"]["basis"] if item["field"] == "EventCode"
        )
        self.assertFalse(event_basis["root_consistent"])

    def test_severe_cameo_is_global_potential_not_verified_price_impact(self):
        event = gdelt_row(**{"7": "RUS", "17": "UKR", "26": "190", "28": "19"})
        self.assertEqual(event["markets"], ["CN", "US", "HK"])
        self.assertTrue(
            all(
                item["status"] == "potential" for item in event["relevance"]["assessments"].values()
            )
        )
        self.assertFalse(event["relevance"]["independent_evidence"])
        self.assertFalse(event["relevance"]["price_impact_verified"])

    def test_ucdp_risk_context_preserves_native_country_id_without_iso_mapping(self):
        row = {
            "id": 7,
            "country": "United States",
            "country_id": 2,
            "date_start": "2020-01-01",
            "date_end": "2020-01-01",
            "date_prec": 1,
            "type_of_violence": 2,
        }
        event = parse("ucdp", json.dumps({"Result": [row]}).encode())["events"][0]
        self.assertEqual(event["markets"], [])
        self.assertEqual(event["original_fields"]["country_id"], 2)
        row["type_of_violence"] = 1
        potential = parse("ucdp", json.dumps({"Result": [row]}).encode())["events"][0]
        self.assertTrue(
            all(
                item["status"] == "potential"
                for item in potential["relevance"]["assessments"].values()
            )
        )
        invalid = candidate_relevance("ucdp", violence_type=True)
        self.assertEqual(invalid["markets"], [])

    def test_empty_timeline_exposes_actual_five_source_states_without_writes(self):
        with TemporaryDirectory(prefix="rwb-event-relevance-") as temporary:
            service = TimelineService(
                SimpleNamespace(store=Store(Path(temporary).resolve() / "personal"))
            )
            before = set(service.records.root.rglob("*"))
            response = service.timeline()
            self.assertEqual(len(response["sources"]), 5)
            self.assertTrue(all(source["enabled"] is False for source in response["sources"]))
            self.assertEqual(before, set(service.records.root.rglob("*")))


if __name__ == "__main__":
    unittest.main()
