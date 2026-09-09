"""Generate actual deliverables from an analyst-created JSON input; no fabricated defaults."""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from research_helpers import write_deliverables


def main():
    try:
        data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        result = write_deliverables(
            "outputs", data["title"], data["sections"], data["rows"], data["sources"]
        )
        print(json.dumps({key: str(value) for key, value in result.items()}, ensure_ascii=False))
    except (OSError, ValueError, KeyError, IndexError) as exc:
        logging.getLogger("research.skill").error("delivery_failed type=%s", type(exc).__name__)
        raise


if __name__ == "__main__":
    main()
