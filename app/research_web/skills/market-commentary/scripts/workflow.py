"""Rank source-backed market items and generate deliverables without network access."""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from research_helpers import write_deliverables

IMPACT_TERMS = {
    "央行": 5,
    "利率": 5,
    "监管": 4,
    "停牌": 4,
    "业绩": 3,
    "并购": 3,
    "涨价": 2,
    "事故": 3,
    "制裁": 4,
    "政策": 3,
    "订单": 2,
}


def _timestamp(row):
    value = row.get("published_at") or row.get("time") or row.get("date") or ""
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except ValueError:
        return 0


def rank(rows):
    """Return a deterministic ordering with visible scores and no inferred facts."""
    ranked = []
    for position, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        text = " ".join(str(row.get(key, "")) for key in ("title", "summary", "content"))
        score = sum(weight for term, weight in IMPACT_TERMS.items() if term in text)
        if row.get("source_url") or row.get("url"):
            score += 2
        ranked.append({**row, "selection_score": score, "source_position": position})
    return sorted(
        ranked, key=lambda row: (-row["selection_score"], -_timestamp(row), row["source_position"])
    )


def main():
    try:
        data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        rows = rank(data["rows"])
        result = write_deliverables(
            "outputs", data["title"], data["sections"], rows, data["sources"]
        )
        print(json.dumps({key: str(value) for key, value in result.items()}, ensure_ascii=False))
    except (OSError, ValueError, KeyError, IndexError) as exc:
        logging.getLogger("research.skill").error(
            "market_commentary_delivery_failed type=%s", type(exc).__name__
        )
        raise


if __name__ == "__main__":
    main()
