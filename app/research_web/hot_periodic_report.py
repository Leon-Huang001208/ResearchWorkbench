"""One-shot deterministic report projection on private stdin; no Runtime or model."""
import base64
from contextlib import redirect_stdout
import hashlib
import json
import logging
import sys

log = logging.getLogger(__name__)
PROTOCOL = "rwb-hot-report/v1"


def render(packet):
    if not isinstance(packet, dict) or set(packet) != {"protocol", "saved"} or packet["protocol"] != PROTOCOL:
        raise ValueError("hot_periodic_report_invalid")
    from .hot_documents import brief_docx
    data = brief_docx(packet["saved"])
    return {"protocol": PROTOCOL, "state": "completed", "inputHash": packet["saved"]["contentHash"],
            "format": "docx", "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "data": base64.b64encode(data).decode("ascii")}


def main():
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    try:
        raw = sys.stdin.buffer.read(1048577)
        if len(raw) > 1048576:
            raise ValueError("hot_periodic_report_limit")
        # Dependency logging must never become part of the machine response.
        with redirect_stdout(sys.stderr):
            result = render(json.loads(raw))
        log.info("hot_periodic_report_completed")
        sys.stdout.write(json.dumps(result, separators=(",", ":")) + "\n")
        return 0
    except Exception:
        log.warning("hot_periodic_report_failed")
        sys.stdout.write(json.dumps({"protocol": PROTOCOL, "state": "failed", "code": "hot_periodic_report_failed"}) + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
