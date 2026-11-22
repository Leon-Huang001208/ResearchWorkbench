"""Auditable source-context heuristics; no price-impact or causality assertion."""

import re

MARKETS = ("CN", "US", "HK")
ACTOR_MARKETS = {"CHN": "CN", "USA": "US", "HKG": "HK"}
SEVERE_ROOTS = {"18", "19", "20"}


def candidate_relevance(
    source,
    *,
    actor_codes=(),
    event_code=None,
    root_code=None,
    violence_type=None,
    native_codes=None,
):
    assessments = {
        market: {"status": "unknown", "reason": "source_context_not_sufficient"}
        for market in MARKETS
    }
    basis = []
    if source in {"fed_fomc", "bls_cpi", "bls_jobs"}:
        assessments["US"] = {"status": "direct", "reason": "us_official_macro_release_or_meeting"}
        for market in ("CN", "HK"):
            assessments[market] = {
                "status": "potential",
                "reason": "potential_global_macro_transmission_requires_review",
            }
        basis.append(
            {"field": "source", "value": source, "scheme": "fixed_official_source_identity"}
        )
    elif source == "gdelt":
        for position, code in enumerate(actor_codes, 1):
            valid = isinstance(code, str) and re.fullmatch(r"[A-Z]{3}", code) is not None
            basis.append(
                {
                    "field": f"Actor{position}CountryCode",
                    "value": code,
                    "scheme": "CAMEO_actor_country_code",
                    "valid": valid,
                }
            )
            market = ACTOR_MARKETS.get(code) if valid else None
            if market is not None:
                assessments[market] = {"status": "direct", "reason": f"actor_country_code_{code}"}
        valid_event = (
            isinstance(event_code, str) and re.fullmatch(r"\d{3,4}", event_code) is not None
        )
        prefix = event_code[:2] if valid_event else None
        root_consistent = not root_code or root_code == prefix
        basis.append(
            {
                "field": "EventCode",
                "value": event_code,
                "scheme": "CAMEO_event_code",
                "root": root_code,
                "root_consistent": root_consistent,
            }
        )
        if valid_event and root_consistent and prefix in SEVERE_ROOTS:
            for market in MARKETS:
                if assessments[market]["status"] == "unknown":
                    assessments[market] = {
                        "status": "potential",
                        "reason": f"potential_global_escalation_cameo_root_{prefix}_requires_review",
                    }
        if native_codes is not None:
            basis.append(
                {
                    "field": "geographic_country_codes",
                    "value": native_codes,
                    "scheme": "GDELT_1_geographic_FIPS_country_code",
                    "used_for_market_mapping": False,
                }
            )
    elif source == "ucdp":
        valid = (
            isinstance(violence_type, int)
            and not isinstance(violence_type, bool)
            and violence_type in {1, 2, 3}
        )
        basis.append(
            {
                "field": "type_of_violence",
                "value": violence_type,
                "scheme": "UCDP_GED_26.1_violence_type",
                "valid": valid,
            }
        )
        if valid and violence_type == 1:
            for market in MARKETS:
                assessments[market] = {
                    "status": "potential",
                    "reason": "state_based_conflict_risk_context_requires_market_review",
                }
        if native_codes is not None:
            basis.append(
                {
                    "field": "country_id",
                    "value": native_codes,
                    "scheme": "UCDP_Gleditsch_Ward_country_id",
                    "used_for_market_mapping": False,
                }
            )
    return {
        "markets": [market for market in MARKETS if assessments[market]["status"] != "unknown"],
        "relevance": {
            "schema": "event-market-relevance-v1",
            "method": "deterministic_source_context",
            "rules_version": "2026-11-04.1",
            "assessments": assessments,
            "basis": basis,
            "requires_manual_review": True,
            "price_impact_verified": False,
            "independent_evidence": False,
        },
    }
