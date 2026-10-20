"""Session-bound public HTTPS bodies, with pinned public DNS and immutable evidence."""

import asyncio
import contextlib
import hashlib
import http.client
import ipaddress
import json
import os
import re
import socket
import ssl
import sys
import threading
import time
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin, urlsplit

from core.observability import get_logger

from .datahub.security import directory, write_new
from .store import StoreError

log = get_logger(__name__)
MAX_BYTES = 2_000_000
MAX_TEXT = 200_000


def rejected(code):
    return StoreError("公开来源正文暂不可核验", code, 409)


def public_target(url):
    """Validate every redirect and pin every returned address before connecting."""
    try:
        parts = urlsplit(url)
        if (
            not isinstance(url, str)
            or len(url) > 4000
            or any(ord(c) < 33 or ord(c) == 127 for c in url)
            or parts.scheme != "https"
            or not parts.hostname
            or parts.username is not None
            or parts.password is not None
            or parts.port not in (None, 443)
            or "%" in parts.hostname
        ):
            raise ValueError("url")
        host = parts.hostname.encode("idna").decode("ascii")
        addresses = list(
            dict.fromkeys(
                row[4][0] for row in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            )
        )
        if not addresses or any(
            not ipaddress.ip_address(a).is_global
            or ipaddress.ip_address(a).is_multicast
            or ipaddress.ip_address(a).is_reserved
            for a in addresses
        ):
            raise ValueError("address")
        return host, sorted(addresses, key=lambda a: ipaddress.ip_address(a).version)
    except (ValueError, UnicodeError, OSError, TypeError):
        log.warning("research_public_source_target_denied")
        raise rejected("research_source_target_denied") from None


class PublicConnection(http.client.HTTPSConnection):
    def __init__(self, host, address, timeout):
        super().__init__(host, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        # Numeric address is pinned; TLS still verifies the original host/SNI.
        raw = socket.create_connection((self.address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


def publication_evidence(text):
    """Recognize publication-labelled header dates, never URL years or data periods."""
    lines = text[:4000].splitlines()[:50]
    found = []
    stamp = r"(\d{4})[-/ ](\d{1,2})[-/](\d{1,2})"
    for index, line in enumerate(lines):
        labelled = re.fullmatch(
            r"\s*发布时间[：:]\s*" + stamp + r"(?:\s+\d{2}:\d{2}(?::\d{2})?)?\s*", line
        )
        byline = re.fullmatch(
            r"\s*" + stamp + r"\s+\d{2}:\d{2}(?::\d{2})?\s*(?:来源[：:].*)?", line
        )
        if (
            byline
            and "来源" not in line
            and not any(re.match(r"\s*来源[：:]", value) for value in lines[index + 1 : index + 3])
        ):
            byline = None
        match = labelled or byline
        if match:
            try:
                found.append(
                    {
                        "date": date(*map(int, match.groups())).isoformat(),
                        "kind": "publication_header",
                        "text": line,
                    }
                )
            except ValueError:
                log.info("research_source_publication_date_unavailable")
    return found


class BodyParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.ignored = 0
        self.date_evidence = []

    @property
    def published(self):
        dates = {
            row["date"] for row in [*self.date_evidence, *publication_evidence("".join(self.parts))]
        }
        if len(dates) > 1:
            log.info("research_source_publication_date_conflict")
        return next(iter(dates)) if len(dates) == 1 else None

    def handle_starttag(self, tag, attrs):
        attributes = {key.lower(): value for key, value in attrs}
        if tag in {"script", "style", "noscript", "template"}:
            self.ignored += 1
        if tag in {"p", "div", "tr", "li", "h1", "h2", "h3", "br", "td", "th"}:
            self.parts.append("\n")
        if tag == "meta" and (
            attributes.get("name") or attributes.get("property") or ""
        ).lower() in {
            "pubdate",
            "publishdate",
            "pubtime",
            "article:published_time",
            "date",
            "dc.date",
            "dcterms.issued",
            "datepublished",
        }:
            value = attributes.get("content") or ""
            match = re.match(r"^(\d{4})([-/])(\d{2})\2(\d{2})(?:$|[ T])", value)
            if match:
                try:
                    self.date_evidence.append(
                        {
                            "date": date(int(match[1]), int(match[3]), int(match[4])).isoformat(),
                            "kind": "publication_meta",
                            "text": value,
                        }
                    )
                except ValueError:
                    log.info("research_source_publication_date_unavailable")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "template"}:
            self.ignored = max(0, self.ignored - 1)
        if tag in {"p", "div", "tr", "li"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.ignored:
            self.parts.append(data)


def fetch_document(url):
    """No proxy, credentials, cookies, executable content, or unbounded redirects."""
    deadline = time.monotonic() + 20
    current = urldefrag(url)[0]
    try:
        for _ in range(3):
            host, addresses = public_target(current)
            if time.monotonic() >= deadline:
                raise TimeoutError
            connection = PublicConnection(host, addresses[0], max(0.1, deadline - time.monotonic()))
            try:
                parts = urlsplit(current)
                path = (parts.path or "/") + ("?" + parts.query if parts.query else "")
                connection.request(
                    "GET",
                    path,
                    headers={
                        "Accept": "text/html,text/plain",
                        "Accept-Encoding": "identity",
                        "User-Agent": "ResearchWorkbench/1.0 public-source-reader",
                    },
                )
                response = connection.getresponse()
                if response.status in {301, 302, 303, 307, 308}:
                    location = response.getheader("Location")
                    if not location:
                        raise rejected("research_source_redirect_invalid")
                    current = urljoin(current, location)
                    continue
                if response.status != 200:
                    raise rejected("research_source_http_unavailable")
                kind = response.getheader("Content-Type", "").split(";", 1)[0].lower()
                if kind not in {"text/html", "application/xhtml+xml", "text/plain"}:
                    raise rejected("research_source_content_unsupported")
                if response.getheader("Content-Encoding", "identity").lower() != "identity":
                    raise rejected("research_source_encoding_unsupported")
                raw = bytearray()
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError
                    if connection.sock:
                        connection.sock.settimeout(remaining)
                    chunk = response.read(16384)
                    if not chunk:
                        break
                    raw.extend(chunk)
                    if len(raw) > MAX_BYTES:
                        raise rejected("research_source_size_limit")
                charset = response.headers.get_content_charset()
                if not charset:
                    match = re.search(rb"charset\s*=\s*[\"']?([A-Za-z0-9_-]+)", raw[:4096])
                    charset = match[1].decode("ascii") if match else "utf-8"
                text = bytes(raw).decode(charset, errors="strict")
                parser = BodyParser()
                if kind != "text/plain":
                    parser.feed(text)
                    text = "\n".join(
                        line.strip() for line in "".join(parser.parts).splitlines() if line.strip()
                    )
                if not text.strip() or len(text) > MAX_TEXT:
                    raise rejected("research_source_body_unavailable")
                return {
                    "content": text,
                    "as_of": parser.published,
                    "date_evidence": [*parser.date_evidence, *publication_evidence(text)],
                    "final_url": current,
                    "response_sha256": hashlib.sha256(raw).hexdigest(),
                }
            finally:
                connection.close()
        raise rejected("research_source_redirect_limit")
    except StoreError:
        raise
    except (OSError, UnicodeError, LookupError, ValueError, http.client.HTTPException):
        log.warning("research_public_source_fetch_failed")
        raise rejected("research_source_fetch_failed") from None


def _stored_records(store, sid):
    """Validate Host provenance before classifying any input as an upload."""
    session = store.session(sid)
    records = session.get("web_evidence", {})
    file_map = session.get("files", {})
    if not isinstance(records, dict) or len(records) > 20 or not isinstance(file_map, dict):
        log.warning("research_web_source_metadata_changed")
        raise rejected("research_source_integrity_failed")
    for identifier, source in records.items():
        if (
            not isinstance(identifier, str)
            or not isinstance(source, dict)
            or not re.fullmatch(r"web:[a-f0-9]{24}", identifier)
            or source.get("id") != identifier
            or source.get("path") != "inputs/web-" + identifier[4:] + ".txt"
            or source.get("file_id") != hashlib.sha256(source["path"].encode()).hexdigest()[:24]
            or file_map.get(source["file_id"]) != source["path"]
            or not isinstance(source.get("sha256"), str)
            or not re.fullmatch(r"[a-f0-9]{64}", source["sha256"])
        ):
            log.warning("research_web_source_metadata_changed")
            raise rejected("research_source_integrity_failed")
    return list(records.values())


def upload_evidence_files(store, sid, files):
    """Host-fetched inputs keep their web identity, even when web scope is disabled."""
    web_ids = {source["file_id"] for source in _stored_records(store, sid)}
    result = [item for item in files if item.get("id") not in web_ids]
    if len(result) != len(files):
        log.info("research_web_upload_alias_excluded", count=len(files) - len(result))
    return result


def stored_sources(store, sid):
    """Only Host metadata and unchanged owned input bytes can certify acquisition."""
    result = []
    for source in _stored_records(store, sid):
        stream, _ = store.open_file(sid, source["file_id"])
        with stream:
            raw = stream.read(MAX_TEXT * 4 + 1)
        if len(raw) > MAX_TEXT * 4 or hashlib.sha256(raw).hexdigest() != source["sha256"]:
            log.warning("research_web_source_bytes_changed")
            raise rejected("research_source_integrity_failed")
        projected = dict(source)
        evidence = [
            *source.get("date_evidence", []),
            *publication_evidence(raw.decode("utf-8", errors="strict")),
        ]
        dates = {row["date"] for row in evidence}
        previous = source.get("as_of")
        if dates and previous not in {None, "", "unknown"}:
            dates.add(previous)
        projected.update(
            as_of=next(iter(dates)) if len(dates) == 1 else "unknown",
            date_evidence=evidence,
            date_status="conflict" if len(dates) > 1 else "known" if dates else "unknown",
        )
        result.append(projected)
    return result


async def fetch_owned_document(url, timeout=25):
    """An owned finite worker makes DNS/header/body timeout and cancellation final."""
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "app.research_web.research_web_sources",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except OSError:
        log.warning("research_public_source_worker_unavailable")
        raise rejected("research_source_fetch_failed") from None
    try:
        stdout, _ = await asyncio.wait_for(
            process.communicate(json.dumps({"url": url}).encode()), timeout
        )
        if len(stdout) > 1_000_000:
            raise rejected("research_source_size_limit")
        result = json.loads(stdout)
        if process.returncode != 0 or not isinstance(result.get("content"), str):
            raise rejected("research_source_fetch_failed")
        return result
    except (TimeoutError, ValueError, OSError):
        log.warning("research_public_source_worker_failed")
        raise rejected("research_source_fetch_failed") from None
    finally:
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.wait()


def request_state(service):
    if not hasattr(service, "source_requests"):
        service.source_requests, service.source_cancellations = {}, {}
    now = time.monotonic()
    service.source_cancellations = {
        key: expiry for key, expiry in service.source_cancellations.items() if expiry > now
    }
    return service.source_requests, service.source_cancellations


def cancel_source(service, sid, call_id):
    service.store.session(sid)
    requests, cancelled = request_state(service)
    key = (sid, call_id)
    if key not in cancelled and len(cancelled) >= 1024:
        raise rejected("research_source_count_limit")
    cancelled[key] = time.monotonic() + 60
    task = requests.get(key)
    if task is not None and not task.cancelling():
        task.cancel()
    log.info("research_public_source_cancelled", session_id=sid)
    return {"status": "cancelled"}


async def execute_source(service, sid, call_id, operation, source_id=None, search_activities=()):
    service.store.session(sid)
    requests, cancelled = request_state(service)
    key = (sid, call_id)
    if key in requests or key in cancelled:
        raise rejected("research_source_call_inactive")
    task = asyncio.create_task(read_source(service, sid, operation, source_id, search_activities))
    requests[key] = task
    try:
        return await task
    finally:
        requests.pop(key, None)


async def read_source(service, sid, operation, source_id=None, search_activities=()):
    if operation not in {"list", "read"} or (operation == "list") != (source_id is None):
        raise rejected("research_source_arguments_invalid")
    async with service.lock:
        row = service.store.session(sid)
        if "web" not in row.get("source_scope", ["web", "uploads", "datahub"]):
            raise rejected("research_source_scope_denied")
        if search_activities:
            from .research_evidence import evidence_index

            registered = {source["id"]: source for source in row.get("web_search_sources", [])}
            registered.update(
                {source["id"]: source for source in evidence_index([], [], search_activities)}
            )
            row["web_search_sources"] = list(registered.values())[-300:]
            service.store.save()
        detail = await service.detail(sid)
        sources = {
            source["id"]: source
            for source in detail["research_sources"]
            if source["id"].startswith("web:")
        }
        if operation == "list":
            return {"sources": list(sources.values())[:40]}
        if source_id not in sources:
            raise rejected("research_source_identity_unknown")
        selected = dict(sources[source_id])
        saved = row.get("web_evidence", {}).get(source_id)
        if saved:
            body = saved
        else:
            body = None
    try:
        document = None if body else await fetch_owned_document(selected["url"])
    except TimeoutError:
        log.warning("research_public_source_deadline_exceeded")
        raise rejected("research_source_fetch_failed") from None
    async with service.lock:
        row = service.store.session(sid)
        if "web" not in row.get("source_scope", ["web", "uploads", "datahub"]):
            raise rejected("research_source_scope_denied")
        records = row.setdefault("web_evidence", {})
        if source_id not in records:
            if len(records) >= 20:
                raise rejected("research_source_count_limit")
            raw = document["content"].encode("utf-8")
            name = "web-" + source_id.split(":", 1)[1] + ".txt"
            with directory(service.store.directory(sid), ("inputs",)) as folder:
                write_new(folder, name, raw)
            relative = "inputs/" + name
            fid = hashlib.sha256(relative.encode()).hexdigest()[:24]
            row["files"][fid] = relative
            records[source_id] = {
                "id": source_id,
                "title": selected["title"],
                "url": selected["url"],
                "state": "available",
                "file_id": fid,
                "path": relative,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "fetched_at": datetime.now(UTC).isoformat(),
                "as_of": document["as_of"] or "unknown",
                "date_evidence": document.get("date_evidence", []),
                "final_url": document["final_url"],
                "response_sha256": document["response_sha256"],
            }
            service.store.save()
            log.info("research_public_source_stored", session_id=sid)
        actual = next(
            source for source in stored_sources(service.store, sid) if source["id"] == source_id
        )
        stream, _ = service.store.open_file(sid, actual["file_id"])
        with stream:
            content = stream.read(MAX_TEXT * 4 + 1).decode("utf-8", errors="strict")
        # Refresh the existing read-only SDK inventory from independently held bytes.
        from .research_quality_service import latest_receipt, write_business_snapshot

        contract = latest_receipt(service, sid).get("research_contract")
        numeric = []
        if contract:
            from .research_web_numeric import web_numeric_observations

            write_business_snapshot(service, sid, contract)
            numeric = web_numeric_observations(
                {
                    "id": source_id,
                    "source_id": source_id,
                    "content": content,
                    "sha256": actual["sha256"],
                },
                scope=str(service.store.root)
                + ":"
                + sid
                + ":"
                + contract["task_id"]
                + ":"
                + contract["sha256"],
            )
        return {
            "source": actual,
            "observation_id": source_id,
            "content": content[:24000],
            "truncated": len(content) > 24000,
            "numeric_observations": [
                {
                    key: row[key]
                    for key in ("id", "metric", "period", "unit", "value", "source_ids", "content")
                }
                for row in numeric
            ],
            "numeric_claim_guidance": "实际提取结果也已写入resources/research_evidence.json；用load_business_evidence及select_business_evidence生成numeric_claims/notes/coverage，或report_plan选择这些id；派生计算用build_numeric_claim。未支持布局不产生声明；这些记录不代表质量通过。",
        }


if __name__ == "__main__":
    # Only the URL from the authenticated parent is read. Logs cannot corrupt
    # the bounded JSON channel or expose upstream material in application logs.
    # The reader also retires itself if its Host disappears during blocked DNS
    # or a slow header/body read. It never writes business data.
    watchdog = threading.Timer(25, lambda: os._exit(124))
    watchdog.daemon = True
    watchdog.start()
    try:
        request = json.loads(sys.stdin.buffer.read(32001))
        if set(request) != {"url"}:
            raise ValueError("invalid request")
        with contextlib.redirect_stdout(sys.stderr):
            document = fetch_document(request["url"])
        sys.stdout.write(json.dumps(document, ensure_ascii=False))
    except (StoreError, ValueError, TypeError, OSError, UnicodeError, RecursionError, KeyError):
        sys.stdout.write('{"error":"research_source_fetch_failed"}')
        raise SystemExit(1)
    finally:
        watchdog.cancel()
