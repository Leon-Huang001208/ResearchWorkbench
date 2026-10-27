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
import stat
import sys
import threading
import time
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlsplit

from core.observability import get_logger

from .datahub.security import directory, read_file, sync_directory, unlink_file, write_new
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
                if not isinstance(response, http.client.HTTPResponse):
                    raise rejected("research_source_framing_unsupported")
                declared = response.getheader("Content-Length")
                transfer = response.getheader("Transfer-Encoding")
                if transfer is not None:
                    if (
                        transfer.strip().lower() != "chunked"
                        or not response.chunked
                        or declared is not None
                    ):
                        raise rejected("research_source_framing_unsupported")
                    framing, declared_length = "chunked_stdlib", None
                elif declared is not None:
                    if not re.fullmatch(r"[0-9]+", declared.strip()):
                        raise rejected("research_source_framing_unsupported")
                    declared_length = int(declared)
                    if response.length != declared_length:
                        raise rejected("research_source_framing_unsupported")
                    if declared_length > MAX_BYTES:
                        raise rejected("research_source_size_limit")
                    framing = "content_length"
                else:
                    if response.chunked or response.length is not None:
                        raise rejected("research_source_framing_unsupported")
                    framing, declared_length = "close_delimited_eof", None
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
                if (
                    framing == "content_length"
                    and (len(raw) != declared_length or response.length != 0)
                    or framing == "chunked_stdlib"
                    and response.chunk_left is not None
                    or not response.isclosed()
                ):
                    log.warning("research_public_source_incomplete")
                    raise rejected("research_source_incomplete")
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
                    "capture": {
                        "schema": "research_web_http_capture_v1",
                        "framing": framing,
                        "declared_length": declared_length,
                        "response_body_bytes": len(raw),
                        "response_sha256": hashlib.sha256(raw).hexdigest(),
                        "content_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                        "utf8_bytes": len(text.encode("utf-8")),
                        "characters": len(text),
                        "final_url": current,
                    },
                }
            finally:
                connection.close()
        raise rejected("research_source_redirect_limit")
    except StoreError:
        raise
    except http.client.IncompleteRead:
        log.warning("research_public_source_incomplete")
        raise rejected("research_source_incomplete") from None
    except (OSError, UnicodeError, LookupError, ValueError, http.client.HTTPException):
        log.warning("research_public_source_fetch_failed")
        raise rejected("research_source_fetch_failed") from None


CAPTURE_SCHEMA = "research_web_capture_v1"
PROOF_SCHEMA = "research_web_capture_proof_v1"
MAX_CAPTURE_PROOF = 128 * 1024


def _capture_json(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode()


def _valid_capture(producer, source, raw=None):
    """Validate the trusted worker protocol, never a completeness field from a request."""
    try:
        if (
            not isinstance(producer, dict)
            or set(producer)
            != {
                "schema",
                "framing",
                "declared_length",
                "response_body_bytes",
                "response_sha256",
                "content_sha256",
                "utf8_bytes",
                "characters",
                "final_url",
            }
            or producer["schema"] != "research_web_http_capture_v1"
        ):
            return False
        if any(
            type(producer[key]) is not int or not 0 < producer[key] <= limit
            for key, limit in (
                ("response_body_bytes", MAX_BYTES),
                ("utf8_bytes", MAX_TEXT * 4),
                ("characters", MAX_TEXT),
            )
        ):
            return False
        framing, declared = producer["framing"], producer["declared_length"]
        if framing == "content_length":
            if type(declared) is not int or declared != producer["response_body_bytes"]:
                return False
        elif framing not in {"chunked_stdlib", "close_delimited_eof"} or declared is not None:
            return False
        if (
            producer["response_sha256"] != source["response_sha256"]
            or producer["content_sha256"] != source["sha256"]
            or producer["final_url"] != source["final_url"]
            or any(
                not isinstance(producer[key], str)
                or not re.fullmatch(r"[a-f0-9]{64}", producer[key])
                for key in ("response_sha256", "content_sha256")
            )
        ):
            return False
        if raw is not None:
            text = raw.decode("utf-8", errors="strict")
            if (
                not text.strip()
                or hashlib.sha256(raw).hexdigest() != producer["content_sha256"]
                or len(raw) != producer["utf8_bytes"]
                or len(text) != producer["characters"]
            ):
                return False
        return True
    except (KeyError, TypeError, ValueError, UnicodeError):
        return False


def capture_proof(root, sid, source, raw=None):
    """Metadata-only unless authorized raw bytes are supplied; never opens a body.

    A legacy cache has neither a new marker nor a private proof. Removing either
    half of a published new proof is an integrity failure, never a legacy fallback.
    """
    try:
        identifier = source["id"]
        if not re.fullmatch(r"web:[a-f0-9]{24}", identifier):
            raise ValueError("source identity")
        marked = "capture_schema" in source or "capture_proof" in source
        folder = root / ".control/source-captures"
        proof_raw = None
        if folder.exists() or folder.is_symlink():
            with directory(root, (".control", "source-captures"), private=True) as fd:
                has_session = sid in os.listdir(fd)
            if has_session:
                with directory(root, (".control", "source-captures", sid), private=True) as fd:
                    name = identifier[4:] + ".json"
                    if name in os.listdir(fd):
                        proof_raw = read_file(fd, name, private=True, limit=MAX_CAPTURE_PROOF)
        if (
            source.get("capture_schema") == "research_web_capture_unverified_v1"
            and "capture_proof" not in source
            and proof_raw is None
        ):
            return None
        if not marked and proof_raw is None:
            return None
        if (
            source.get("capture_schema") != CAPTURE_SCHEMA
            or proof_raw is None
            or source.get("capture_proof")
            != {"schema": PROOF_SCHEMA, "sha256": hashlib.sha256(proof_raw).hexdigest()}
        ):
            raise ValueError("proof reference changed")
        proof = json.loads(proof_raw)
        if (
            set(proof) != {"schema", "source_session_id", "source_record", "producer"}
            or proof["schema"] != PROOF_SCHEMA
            or proof["source_session_id"] != sid
            or proof["source_record"]
            != {key: value for key, value in source.items() if key != "capture_proof"}
            or _capture_json(proof) != proof_raw
            or not _valid_capture(proof["producer"], source, raw)
        ):
            raise ValueError("capture changed")
        return proof["producer"]
    except (StoreError, OSError, ValueError, TypeError, KeyError, UnicodeError):
        log.warning("research_source_capture_proof_rejected")
        raise rejected("research_source_capture_changed") from None


def source_file_identifier(row, relative):
    """Classify reserved captures without reading a body or trusting proof health."""
    relative = str(relative).replace("\\", "/")
    match = re.fullmatch(r"inputs/web-([a-f0-9]{24})\.txt", relative)
    if match:
        return "web:" + match[1]
    records = row.get("web_evidence", {})
    if isinstance(records, dict):
        for identifier, source in records.items():
            if isinstance(source, dict) and source.get("path") == relative:
                return identifier
    return None


def source_file_record(store, sid, relative):
    """Authorize selected published source metadata before any body open."""
    row = store.session(sid)
    relative = str(relative).replace("\\", "/")
    identifier = source_file_identifier(row, relative)
    if identifier is None:
        return None
    records = row.get("web_evidence", {})
    source = records.get(identifier) if isinstance(records, dict) else None
    fid = hashlib.sha256(relative.encode()).hexdigest()[:24]
    if (
        not isinstance(source, dict)
        or source.get("id") != identifier
        or source.get("path") != relative
        or source.get("file_id") != fid
        or row.get("files", {}).get(fid) != relative
    ):
        log.warning("research_source_file_unpublished")
        raise rejected("research_source_capture_unavailable")
    if "web" not in row.get("source_scope", ["uploads", "datahub", "web"]):
        log.warning("research_source_file_scope_denied")
        raise StoreError("网页正文需要当前来源权限", "research_source_scope_denied", 403)
    capture_proof(store.root, sid, source)
    return source


def verify_source_file_bytes(store, sid, source, raw):
    if source is not None:
        if len(raw) > MAX_TEXT * 4 or hashlib.sha256(raw).hexdigest() != source.get("sha256"):
            log.warning("research_source_file_changed")
            raise rejected("research_source_integrity_failed")
        capture_proof(store.root, sid, source, raw)


def _write_capture_body(folder, name, raw, ownership):
    """Remember exclusive creation even if write/flush/fsync later raises."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    handle = None
    try:
        parent = folder.stat() if isinstance(folder, Path) else os.fstat(folder)
        handle = (
            os.open(folder / name, flags, 0o600)
            if isinstance(folder, Path)
            else os.open(name, flags, 0o600, dir_fd=folder)
        )
        with os.fdopen(handle, "wb") as output:
            handle = None
            info = os.fstat(output.fileno())
            ownership.update(
                device=info.st_dev,
                inode=info.st_ino,
                parent_device=parent.st_dev,
                parent_inode=parent.st_ino,
            )
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
    except OSError:
        log.warning("research_source_capture_body_write_failed")
        raise rejected("research_source_capture_write_failed") from None
    finally:
        if handle is not None:
            os.close(handle)


def _rollback_capture_body(store, sid, name, ownership):
    """Never delete a pre-existing or replaced file, including cleanup failures."""
    if not ownership:
        return
    with directory(store.directory(sid), ("inputs",)) as folder:
        parent = folder.stat() if isinstance(folder, Path) else os.fstat(folder)
        try:
            info = (
                (folder / name).lstat()
                if isinstance(folder, Path)
                else os.stat(name, dir_fd=folder, follow_symlinks=False)
            )
        except FileNotFoundError:
            return
        if (
            (parent.st_dev, parent.st_ino)
            != (ownership["parent_device"], ownership["parent_inode"])
            or (info.st_dev, info.st_ino) != (ownership["device"], ownership["inode"])
            or not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
        ):
            log.warning("research_source_capture_cleanup_ownership_changed")
            return
        unlink_file(folder, name)
        sync_directory(folder)


def _publish_source(service, sid, selected, document):
    """Publish only after exclusive durable body/proof writes under the retention fence."""
    from .dossiers.lock import retention_lock

    store = service.store
    row = store.session(sid)
    identifier = selected["id"]
    raw = document["content"].encode("utf-8")
    relative = "inputs/web-" + identifier[4:] + ".txt"
    fid = hashlib.sha256(relative.encode()).hexdigest()[:24]
    source = {
        "id": identifier,
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
    producer = document.get("capture")
    if producer is not None and not _valid_capture(producer, source, raw):
        log.warning("research_source_capture_producer_rejected")
        raise rejected("research_source_capture_unverified")
    source["capture_schema"] = (
        CAPTURE_SCHEMA if producer is not None else "research_web_capture_unverified_v1"
    )
    with retention_lock(store.root):
        previous_files = dict(row["files"])
        previous_sources = dict(row.get("web_evidence", {}))
        ownership = {}
        try:
            if producer is not None:
                proof = {
                    "schema": PROOF_SCHEMA,
                    "source_session_id": sid,
                    "source_record": dict(source),
                    "producer": producer,
                }
                proof_raw = _capture_json(proof)
                if len(proof_raw) > MAX_CAPTURE_PROOF:
                    raise rejected("research_source_size_limit")
                with directory(
                    store.root, (".control", "source-captures", sid), create=True, private=True
                ) as folder:
                    name = identifier[4:] + ".json"
                    write_new(folder, name, proof_raw)
                    sync_directory(folder)
                    if read_file(folder, name, private=True, limit=MAX_CAPTURE_PROOF) != proof_raw:
                        raise rejected("research_source_capture_changed")
                source["capture_proof"] = {
                    "schema": PROOF_SCHEMA,
                    "sha256": hashlib.sha256(proof_raw).hexdigest(),
                }
            with directory(store.directory(sid), ("inputs",)) as folder:
                _write_capture_body(folder, relative.split("/")[-1], raw, ownership)
                sync_directory(folder)
                if read_file(folder, relative.split("/")[-1], limit=MAX_TEXT * 4) != raw:
                    raise rejected("research_source_capture_changed")
            row["files"][fid] = relative
            row.setdefault("web_evidence", {})[identifier] = source
            store.save()
        except Exception:
            row["files"] = previous_files
            row["web_evidence"] = previous_sources
            try:
                _rollback_capture_body(store, sid, relative.split("/")[-1], ownership)
            except (StoreError, OSError, ValueError, TypeError, KeyError) as cleanup_error:
                log.warning(
                    "research_source_capture_cleanup_failed",
                    error_type=type(cleanup_error).__name__,
                )
            log.warning("research_source_capture_publish_failed")
            raise
    log.info("research_public_source_stored capture_verified=%s", producer is not None)


def snapshot_capture_proofs(root):
    """Hash private proof metadata only; caller holds the existing retention fence."""
    folder = root / ".control/source-captures"
    present = folder.exists() or folder.is_symlink()
    index_path = root / "index.json"
    if not index_path.exists() and not index_path.is_symlink() and not present:
        return {}
    try:
        with directory(root) as fd:
            index = json.loads(read_file(fd, "index.json", limit=64 * 1024 * 1024))
        sessions = index.get("sessions", {})
        if not isinstance(sessions, dict):
            raise TypeError("source proof index invalid")
        files = {}
        for sid, row in sessions.items():
            sources = row.get("web_evidence", {}) if isinstance(row, dict) else {}
            if not isinstance(sources, dict):
                continue
            for source in sources.values():
                if isinstance(source, dict) and (
                    present or "capture_schema" in source or "capture_proof" in source
                ):
                    producer = capture_proof(root, sid, source)
                    if producer is not None:
                        name = "web-" + source["id"][4:] + ".txt"
                        relative = "inputs/" + name
                        fid = hashlib.sha256(relative.encode()).hexdigest()[:24]
                        if (
                            source.get("path") != relative
                            or source.get("file_id") != fid
                            or row.get("files", {}).get(fid) != relative
                        ):
                            raise ValueError("capture body identity changed")
                        # This is the explicit admin preservation fence, not a
                        # metadata list or a content API. Return only a digest.
                        with directory(root, ("sessions", sid, "inputs")) as body_fd:
                            body = read_file(body_fd, name, limit=MAX_TEXT * 4)
                        capture_proof(root, sid, source, body)
                        files[f"sessions/{sid}/{relative}"] = hashlib.sha256(body).hexdigest()
        if not present:
            return files
        with directory(root, (".control", "source-captures"), private=True) as fd:
            owners = os.listdir(fd)
        for sid in owners:
            if not re.fullmatch(r"[a-f0-9-]{36}", sid):
                raise ValueError("source proof owner invalid")
            with directory(root, (".control", "source-captures", sid), private=True) as fd:
                for name in os.listdir(fd):
                    if not re.fullmatch(r"[a-f0-9]{24}\.json", name):
                        raise ValueError("source proof file invalid")
                    raw = read_file(fd, name, private=True, limit=MAX_CAPTURE_PROOF)
                    files[f".control/source-captures/{sid}/{name}"] = hashlib.sha256(
                        raw
                    ).hexdigest()
        return files
    except (StoreError, OSError, ValueError, TypeError, KeyError):
        log.warning("research_source_capture_preservation_failed")
        raise RuntimeError("source_capture_preservation_failed") from None


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
        capture_proof(store.root, sid, source)
    return list(records.values())


def upload_evidence_files(store, sid, files):
    """Host-fetched inputs keep their web identity, even when web scope is disabled."""
    _stored_records(store, sid)
    row = store.session(sid)
    result = [
        item
        for item in files
        if not source_file_identifier(
            row, row.get("files", {}).get(item.get("id"), "inputs/" + item.get("name", ""))
        )
    ]
    if len(result) != len(files):
        log.info("research_web_upload_alias_excluded", count=len(files) - len(result))
    return result


def stored_sources(store, sid):
    """Only Host metadata and unchanged owned input bytes can certify acquisition."""
    result = []
    permitted = "web" in store.session(sid).get("source_scope", ["uploads", "datahub", "web"])
    for source in _stored_records(store, sid):
        if not permitted:
            # Revoked metadata remains visible to its owner; no body is opened.
            result.append({**source, "state": "revoked"})
            continue
        stream, _ = store.open_file(sid, source["file_id"])
        with stream:
            raw = stream.read(MAX_TEXT * 4 + 1)
        if len(raw) > MAX_TEXT * 4 or hashlib.sha256(raw).hexdigest() != source["sha256"]:
            log.warning("research_web_source_bytes_changed")
            raise rejected("research_source_integrity_failed")
        capture_proof(store.root, sid, source, raw)
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
        raw = result["content"].encode("utf-8")
        source = {
            "sha256": hashlib.sha256(raw).hexdigest(),
            "response_sha256": result.get("response_sha256"),
            "final_url": result.get("final_url"),
        }
        if not _valid_capture(result.get("capture"), source, raw):
            log.warning("research_public_source_worker_capture_unverified")
            raise rejected("research_source_capture_unverified")
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
    dossiers = getattr(service, "dossiers", None)
    if (
        dossiers is not None
        and operation == "list"
        and "web"
        not in service.store.session(sid).get("source_scope", ["uploads", "datahub", "web"])
        and not search_activities
    ):
        return {"sources": dossiers.registered_sources(sid)}
    if dossiers is not None and operation == "read":
        handle = (
            source_id
            if isinstance(source_id, str) and source_id.startswith("dossier:")
            else next(
                (
                    item["dossier_handle"]
                    for item in dossiers.registered_sources(sid)
                    if item["id"] == source_id
                ),
                None,
            )
        )
        if handle:
            async with service.lock:
                result = dossiers.read_handle(sid, handle)
                from .research_quality_service import latest_receipt, write_business_snapshot

                contract = latest_receipt(service, sid).get("research_contract")
                if contract:
                    write_business_snapshot(service, sid, contract)
                return result
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
            return {
                "sources": [
                    *list(sources.values())[:40],
                    *(dossiers.registered_sources(sid) if dossiers is not None else []),
                ]
            }
        if source_id not in sources:
            raise rejected("research_source_identity_unknown")
        selected = dict(sources[source_id])
        saved = row.get("web_evidence", {}).get(source_id)
        if not saved:
            # An orphaned immutable producer proof is unavailable, never a new
            # fetch/replacement opportunity or a legacy-cache downgrade.
            capture_proof(service.store.root, sid, {"id": source_id})
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
            _publish_source(service, sid, selected, document)
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
            "numeric_claim_guidance": "实际提取结果已写入resources/research_evidence.json。规范报告统一调用research_run_script(report_plan=数据配方)，不要手写Python payload/numeric_claims。sections的evidence_ids选本次实际id或唯一metric@period；派生值在calculations填写id、operation(percent_change/ratio/difference/sum/identity)、operands(实际观测id或metric@period)、decimal_places，章节以$计算id引用。系统独立计算并生成声明/笔记/coverage。summary仅在用户需要工作簿时提供，否则省略；格式由冻结用户要求确定。分析和跨版本可比性仍需证据，真实缺口保留missing，不支持布局不产生声明。",
        }


def worker_document_bytes(document):
    """Exact worker JSON protocol, including the producer manifest, without filtering."""
    try:
        return json.dumps(document, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError):
        log.warning("research_public_source_worker_encode_failed")
        raise rejected("research_source_capture_unverified") from None


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
        sys.stdout.buffer.write(worker_document_bytes(document))
    except (StoreError, ValueError, TypeError, OSError, UnicodeError, RecursionError, KeyError):
        sys.stdout.write('{"error":"research_source_fetch_failed"}')
        raise SystemExit(1)
    finally:
        watchdog.cancel()
