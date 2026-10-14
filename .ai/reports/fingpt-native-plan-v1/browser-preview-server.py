"""Task-owned, GET-only UI preview; exposes a fixed resource allowlist."""

import json
import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORT = Path(__file__).resolve().parent
logging.basicConfig(filename=REPORT / "logs/browser-preview-server.log", level=logging.INFO)
log = logging.getLogger("native_plan_preview")
ROUTES = {
    "/": (REPORT / "browser-preview.html", "text/html; charset=utf-8"),
    "/fixtures": (REPORT / "browser-fixtures.json", "application/json"),
    **{f"/ui/{name}": (ROOT / "app/research_web/ui" / name, mime) for name, mime in [
        ("views.mjs", "text/javascript"), ("core.mjs", "text/javascript"),
        ("markdown.mjs", "text/javascript"), ("styles.css", "text/css"),
    ]},
}


class Preview(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        pass  # explicit safe status logs below; no raw paths or request text

    def do_GET(self):
        try:
            resource = ROUTES.get(self.path)
            if resource is None:
                self.send_error(404)
                log.info("preview_response status=404")
                return
            path, mime = resource
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            log.info("preview_response status=200")
        except OSError as error:
            log.error("preview_response_failed kind=%s", type(error).__name__)
            self.send_error(500)


server = ThreadingHTTPServer(("127.0.0.1", 0), Preview)
state = {"pid": os.getpid(), "port": server.server_port, "root": str(REPORT), "status": "running"}
(REPORT / "browser-server.json").write_text(json.dumps(state), encoding="utf-8")
print(json.dumps(state), flush=True)
try:
    server.serve_forever()
except KeyboardInterrupt:
    log.info("preview_interrupted")
finally:
    server.server_close()
    state["status"] = "stopped"
    (REPORT / "browser-server.json").write_text(json.dumps(state), encoding="utf-8")
    log.info("preview_stopped")
