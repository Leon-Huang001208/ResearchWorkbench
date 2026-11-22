"""Zero-inference AIHOT evaluation preparation; Python standard library only."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import ipaddress
import json
import logging
import os
import re
import shutil
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from email.utils import parsedate_to_datetime
from html import escape, unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

PIN = "26d436497d9ddba9e7dd88eed255cfe0105ce368"
SOURCE_URL = f"https://raw.githubusercontent.com/KKKKhazix/AIHOT/{PIN}/industry/sources.json"
MAX_BYTES = 2 * 1024 * 1024
LOG = logging.getLogger("research_workbench.ai_news_eval")
TASKS = (
    "understand",
    "summarize-article",
    "group-pair",
    "prefilter",
    "selection-score",
    "translate-body",
    "story-digest",
)


class ArticleText(HTMLParser):
    """Version 1 deterministic visible text extraction; never executes HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool, bool]] = []
        self.main: list[str] = []
        self.body: list[str] = []
        self.language = "undeclared"

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "html":
            self.language = attributes.get("lang") or "undeclared"
        if tag in (
            "meta",
            "link",
            "img",
            "br",
            "hr",
            "input",
            "source",
            "wbr",
            "area",
            "base",
            "embed",
            "param",
            "track",
            "col",
        ):
            return
        selected = tag in ("main", "article") or any(
            name in (attributes.get("class") or "").split()
            for name in ("post-content", "entry-content", "article-content")
        )
        ignored = tag in ("script", "style", "nav", "header", "footer", "noscript", "svg")
        self.stack.append((tag, selected, ignored))

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data: str) -> None:
        if any(row[2] for row in self.stack) or not data.strip():
            return
        if any(row[0] == "body" for row in self.stack):
            self.body.append(data.strip())
        if any(row[1] for row in self.stack):
            self.main.append(data.strip())


def extracted_text(data: bytes) -> tuple[bytes, dict[str, Any]]:
    parser = ArticleText()
    parser.feed(data.decode("utf-8", errors="replace"))
    text = "\n".join(parser.main or parser.body)
    cjk = sum("\u4e00" <= char <= "\u9fff" for char in text)
    language = (
        "zh"
        if cjk >= 100 and cjk / max(1, len(text)) >= 0.1
        else "en" if parser.language.lower().startswith("en") else "unconfirmed"
    )
    return text.encode("utf-8"), {
        "extractor": "stdlib-htmlparser-v1",
        "selection": "article_main_or_content_class" if parser.main else "body_fallback",
        "visible_characters": len(text),
        "html_declared_language": parser.language,
        "language": language,
        "cjk_characters": cjk,
        "long_form": bool(parser.main and len(text) >= 3000),
    }


def balance(output: Path, raw: Path, base_output: Path, base_raw: Path, supplement: Path) -> None:
    """Freeze a new bilingual version without mutating any original source bytes."""
    validate(base_output, base_raw)
    if output.exists() or raw.exists():
        raise ValueError("Balanced version requires fresh directories")
    corpus = read_json(base_output / "corpus.json")
    extra = read_json(supplement)
    if extra["feed_provenance"]["url"] != "https://qwenlm.github.io/zh/blog/index.xml":
        raise ValueError("Unknown supplemental feed provenance")
    verify_artifact(Path(extra["feed_raw_root"]), extra["feed_provenance"])
    supplemental_feed = (
        Path(extra["feed_raw_root"]) / extra["feed_provenance"]["path"]
    ).read_bytes()
    feed_entries = {
        entry.findtext("link"): entry.findtext("pubDate")
        for entry in ET.fromstring(supplemental_feed).findall(".//item")
    }
    if any(
        row["url"] not in feed_entries or row["published_at"] != feed_entries[row["url"]]
        for row in extra["articles"]
    ):
        raise ValueError("Supplemental article provenance differs from frozen feed")
    raw.mkdir(parents=True)
    supplementary_record = artifact(
        raw,
        "feeds/supplemental-qwen-zh.xml",
        supplemental_feed,
        extra["feed_provenance"]["url"],
        extra["feed_provenance"]["final_url"],
        "application/xml",
    )
    for record in [corpus["source_catalog"], *corpus["feeds"]]:
        target = raw / record["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(base_raw / record["path"], target)
    documents: list[dict[str, Any]] = []
    failures = []
    for row in extra["articles"][:16]:
        if len(documents) >= 10:
            break
        try:
            data, final, media = fetch(row["url"])
            text, info = extracted_text(data)
            if media != "text/html" or info["language"] != "zh" or info["visible_characters"] < 500:
                raise ValueError("Chinese article body not confirmed")
            doc_id = f"article-zh-{len(documents) + 1:03d}"
            record = artifact(raw, f"articles/{doc_id}.html", data, row["url"], final, media)
            record.update(
                id=doc_id,
                source_id=row["source_id"],
                published_at=row["published_at"],
                publication_date_source=row["publication_date_source"],
                annotation_status="needs_review",
                input_kind="frozen_extracted_text",
                text_info=info,
            )
            record["text_artifact"] = artifact(
                raw, f"text/{doc_id}.txt", text, row["url"], final, "text/plain"
            )
            documents.append(record)
        except (OSError, ValueError) as error:
            failures.append(
                {"url": row["url"], "phase": "chinese_article", "error": type(error).__name__}
            )
    for original in corpus["documents"]:
        if len(documents) >= 50:
            break
        record = dict(original)
        data = (base_raw / record["path"]).read_bytes()
        text, info = extracted_text(data)
        if info["visible_characters"] < 500:
            failures.append(
                {
                    "url": record["url"],
                    "phase": "body_extraction",
                    "error": "InsufficientVisibleText",
                }
            )
            continue
        target = raw / record["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        record.update(
            input_kind="frozen_extracted_text",
            text_info=info,
            published_at=None,
            publication_date_source="not_extracted",
        )
        record["text_artifact"] = artifact(
            raw, f"text/{record['id']}.txt", text, record["url"], record["final_url"], "text/plain"
        )
        documents.append(record)
    for i, record in enumerate(documents):
        record["split"] = "holdout" if i % 5 == 4 else "tuning"
    write_json(
        output / "corpus.json",
        {
            "schema": 1,
            "upstream_commit": PIN,
            "source_catalog": corpus["source_catalog"],
            "feeds": [*corpus["feeds"], supplementary_record],
            "supplemental_catalog_sha256": digest(supplement.read_bytes()),
            "supplemental_catalog": str(supplement),
            "base_corpus_sha256": digest((base_output / "corpus.json").read_bytes()),
            "documents": documents,
            "failures": corpus["failures"] + failures,
            "coverage_status": "COMPLETE" if len(documents) == 50 else "INCOMPLETE",
            "inference_calls": 0,
            "stratification": {
                "zh": sum(d["text_info"]["language"] == "zh" for d in documents),
                "en": sum(d["text_info"]["language"] == "en" for d in documents),
                "long_form": sum(d["text_info"]["long_form"] for d in documents),
                "long_form_definition": "selected article/main/content-class visible text >=3000 Unicode characters; manual semantic review required",
            },
        },
    )
    LOG.info(
        "Balanced corpus frozen: %s/50; Chinese articles=%s",
        len(documents),
        sum(d["text_info"]["language"] == "zh" for d in documents),
    )


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def input_identity(document: dict[str, Any]) -> dict[str, Any]:
    source = document.get("text_artifact", document)
    identity = {"article_id": document["id"], "sha256": source["sha256"], "bytes": source["bytes"]}
    if "text_artifact" in document:
        identity["source_sha256"] = document["sha256"]
    return identity


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def public_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname or ""
    forbidden = ("aihot.news", "jina.ai", "x.com", "twitter.com", "weixin.qq.com")
    if (
        parsed.scheme != "https"
        or not host
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or parsed.query
        or any(host == item or host.endswith("." + item) for item in forbidden)
    ):
        raise ValueError("Only credential-free public HTTPS URLs without queries allowed")
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError("Non-public destination rejected")
    return url


class PublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> Any:
        public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url: str) -> tuple[bytes, str, str]:
    public_url(url)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "RWB-EvalCorpus/1.0",
            "Accept": "text/html,application/xml,text/xml,application/rss+xml,application/atom+xml,application/json",
        },
    )
    with urllib.request.build_opener(PublicRedirect()).open(request, timeout=12) as response:
        data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES or not data:
            raise ValueError("Empty or oversized response")
        return data, response.geturl(), response.headers.get_content_type()


def artifact(
    root: Path, relative: str, data: bytes, url: str, final_url: str, media_type: str
) -> dict[str, Any]:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
    return {
        "path": relative,
        "sha256": digest(data),
        "bytes": len(data),
        "url": url,
        "final_url": final_url,
        "media_type": media_type,
        "retrieved_at": datetime.now(UTC).isoformat(),
    }


def prepare(output: Path, raw: Path) -> None:
    if output.exists() or raw.exists():
        raise ValueError("Fresh output and raw directories required")
    data, final, media = fetch(SOURCE_URL)
    sources = json.loads(data)["sources"]
    raw.mkdir(parents=True)
    record = artifact(raw, "sources.json", data, SOURCE_URL, final, media)
    write_json(
        output / "plan.json",
        {
            "schema": 1,
            "upstream_commit": PIN,
            "source_catalog": record,
            "target_articles": 50,
            "target_relationship_cases": 20,
            "sources": [
                {"id": s["id"], "feed_url": s["config"]["feedUrl"]}
                for s in sources
                if s["kind"] == "rss"
            ],
            "inference_calls": 0,
        },
    )
    LOG.info("Prepared source catalog: %s sources", len(sources))


def feed_links(data: bytes) -> list[str]:
    root = ET.fromstring(data)
    links = []
    for entry in list(root.findall(".//item")) + list(
        root.findall("{http://www.w3.org/2005/Atom}entry")
    ):
        link = entry.find("link")
        if link is not None and link.text:
            links.append(link.text.strip())
        else:
            for child in entry.findall("{http://www.w3.org/2005/Atom}link"):
                if child.get("rel", "alternate") == "alternate" and child.get("href"):
                    links.append(str(child.get("href")))
                    break
    return links


def freeze(output: Path, raw: Path) -> None:
    plan = read_json(output / "plan.json")
    verify_artifact(raw, plan["source_catalog"])
    catalog = read_json(raw / plan["source_catalog"]["path"])
    expected = [
        {"id": s["id"], "feed_url": s["config"]["feedUrl"]}
        for s in catalog["sources"]
        if s["kind"] == "rss"
    ]
    if plan["upstream_commit"] != PIN or plan["sources"] != expected:
        raise ValueError("Plan differs from pinned source catalog")
    if (output / "corpus.json").exists():
        raise ValueError("Corpus already frozen; use a fresh session")
    feeds, candidates, failures = [], [], []
    for source in plan["sources"]:
        try:
            data, final, media = fetch(source["feed_url"])
            feeds.append(
                artifact(raw, f"feeds/{source['id']}.xml", data, source["feed_url"], final, media)
            )
            candidates.append((source["id"], feed_links(data)[:12]))
        except (OSError, ValueError, ET.ParseError) as error:
            failures.append(
                {"source_id": source["id"], "phase": "feed", "error": type(error).__name__}
            )
            LOG.warning("Feed unavailable: %s (%s)", source["id"], type(error).__name__)
    documents: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    seen_hashes: set[str] = set()
    for index in range(12):
        for source_id, links in candidates:
            if len(documents) >= 50:
                break
            if index >= len(links) or links[index] in seen_urls:
                continue
            url = links[index]
            seen_urls.add(url)
            try:
                data, final, media = fetch(url)
                if media not in ("text/html", "application/xhtml+xml", "text/plain"):
                    raise ValueError("Unsupported article media type")
                if digest(data) in seen_hashes or final in {d["final_url"] for d in documents}:
                    raise ValueError("Duplicate article bytes or final URL")
                seen_hashes.add(digest(data))
                doc_id = f"article-{len(documents) + 1:03d}"
                record = artifact(raw, f"articles/{doc_id}.html", data, url, final, media)
                record.update(
                    id=doc_id,
                    source_id=source_id,
                    split="holdout" if len(documents) % 5 == 4 else "tuning",
                    input_kind="raw_public_html",
                    annotation_status="needs_review",
                )
                documents.append(record)
                LOG.info("Frozen article %s from %s", len(documents), source_id)
            except (OSError, ValueError) as error:
                failures.append(
                    {
                        "source_id": source_id,
                        "url": url,
                        "phase": "article",
                        "error": type(error).__name__,
                    }
                )
    write_json(
        output / "corpus.json",
        {
            "schema": 1,
            "upstream_commit": PIN,
            "source_catalog": plan["source_catalog"],
            "feeds": feeds,
            "documents": documents,
            "failures": failures,
            "coverage_status": "COMPLETE" if len(documents) == 50 else "INCOMPLETE",
            "inference_calls": 0,
        },
    )
    LOG.info("Corpus frozen: %s/50; failures=%s", len(documents), len(failures))


def verify_artifact(raw: Path, record: dict[str, Any]) -> None:
    relative = Path(record["path"])
    base = raw.resolve()
    path = (base / relative).resolve()
    has_symlink = any(
        (base.joinpath(*relative.parts[:i])).is_symlink() for i in range(1, len(relative.parts) + 1)
    )
    if relative.is_absolute() or not path.is_relative_to(base) or has_symlink:
        raise ValueError("Artifact path escapes raw root")
    data = path.read_bytes()
    if len(data) != record["bytes"] or digest(data) != record["sha256"]:
        raise ValueError("Artifact integrity mismatch")


def validate(output: Path, raw: Path) -> dict[str, Any]:
    corpus = read_json(output / "corpus.json")
    if corpus["upstream_commit"] != PIN or corpus["inference_calls"] != 0:
        raise ValueError("Unexpected provenance or inference claim")
    docs = corpus["documents"]
    if not 0 <= len(docs) <= 50 or corpus["coverage_status"] != (
        "COMPLETE" if len(docs) == 50 else "INCOMPLETE"
    ):
        raise ValueError("Coverage claim differs from actual document count")
    if corpus["source_catalog"]["url"] != SOURCE_URL:
        raise ValueError("Source catalog provenance mismatch")
    if len({d["id"] for d in docs}) != len(docs) or len({d["sha256"] for d in docs}) != len(docs):
        raise ValueError("Duplicate document identity")
    for record in [corpus["source_catalog"], *corpus["feeds"], *docs]:
        verify_artifact(raw, record)
    for document in docs:
        if "text_artifact" in document:
            verify_artifact(raw, document["text_artifact"])
            text, info = extracted_text((raw / document["path"]).read_bytes())
            if digest(text) != document["text_artifact"]["sha256"] or info != document["text_info"]:
                raise ValueError("Extracted body or stratification differs from source")
    if "stratification" in corpus:
        for key, expected in {
            "zh": sum(d["text_info"]["language"] == "zh" for d in docs),
            "en": sum(d["text_info"]["language"] == "en" for d in docs),
            "long_form": sum(d["text_info"]["long_form"] for d in docs),
        }.items():
            if corpus["stratification"][key] != expected:
                raise ValueError("Stratification count differs from extracted bodies")
    if corpus.get("split_policy") == "reference_event_groups_v1":
        spec_path = Path(corpus["reference_spec_path"])
        if digest(spec_path.read_bytes()) != corpus["reference_spec_sha256"]:
            raise ValueError("Reference specification hash mismatch")
        specification = read_json(spec_path)
        if set(specification["articles"]) != {d["id"] for d in docs}:
            raise ValueError("Reference specification article coverage mismatch")
        groups: dict[str, str] = {}
        for document in docs:
            group, split = document["event_group"], document["split"]
            selected = specification["articles"][document["id"]]
            if selected["event_group"] != group or selected["split"] != split:
                raise ValueError("Split differs from frozen reference specification")
            if split not in ("tuning", "holdout") or groups.get(group, split) != split:
                raise ValueError("Event group split leakage")
            groups[group] = split
    elif any(d["split"] != ("holdout" if i % 5 == 4 else "tuning") for i, d in enumerate(docs)):
        raise ValueError("Unknown split")
    if (output / "annotations.json").exists():
        annotations = read_json(output / "annotations.json")
        by_id = {d["id"]: d for d in docs}
        annotated_ids = [row["article_id"] for row in annotations["articles"]]
        if len(annotated_ids) != len(docs) or set(annotated_ids) != set(by_id):
            raise ValueError("Article annotation coverage mismatch")
        for annotation in annotations["articles"]:
            document = by_id[annotation["article_id"]]
            if (
                annotation["sha256"] != document["sha256"]
                or annotation["split"] != document["split"]
            ):
                raise ValueError("Article annotation identity mismatch")
            if annotations.get("reference_status") == "proposed_reference":
                if (
                    not annotation["entities"]
                    or not annotation["events"]
                    or not annotation["fact_spans"]
                ):
                    raise ValueError("Proposed reference annotation cannot be blank")
                text = (raw / document["text_artifact"]["path"]).read_bytes()
                for fact in annotation["fact_spans"]:
                    start, end = fact["byte_span"]
                    if (
                        not (0 <= start < end <= len(text))
                        or text[start:end].decode("utf-8") != fact["text"]
                        or fact["text_sha256"] != document["text_artifact"]["sha256"]
                    ):
                        raise ValueError("Proposed fact differs from frozen body")
                for entity in annotation["entities"]:
                    start, end = entity["byte_span"]
                    if (
                        not (0 <= start < end <= len(text))
                        or text[start:end].decode("utf-8") != entity["name"]
                    ):
                        raise ValueError("Proposed entity differs from frozen body")
                fact_ids = {fact["id"] for fact in annotation["fact_spans"]}
                if len(fact_ids) != len(annotation["fact_spans"]) or any(
                    event["fact_id"] not in fact_ids for event in annotation["events"]
                ):
                    raise ValueError("Proposed event has no unique source fact")
        by_annotation = {row["article_id"]: row for row in annotations["articles"]}
        identities = set()
        for case in annotations["relationships"]:
            evidence = [by_id[ref["article_id"]] for ref in case["evidence"]]
            if len(evidence) != 2 or len({r["id"] for r in evidence}) != 2:
                raise ValueError("Relationship needs two distinct source documents")
            if any(r["split"] != case["split"] for r in evidence):
                raise ValueError("Split leakage")
            if any(ref["sha256"] != by_id[ref["article_id"]]["sha256"] for ref in case["evidence"]):
                raise ValueError("Evidence hash mismatch")
            if annotations.get("reference_status") == "proposed_reference":
                relation_map = {
                    "same_event": "SAME_OCCURRENCE",
                    "follow_up": "SAME_STORY",
                    "unrelated": "UNRELATED",
                }
                if (
                    case.get("engine_relation") != relation_map.get(case["relationship_label"])
                    or case.get("label_status") != "proposed_reference"
                    or not case.get("rationale")
                    or annotations["gold_approved"] is not False
                ):
                    raise ValueError("Reference relationship status or rationale invalid")
                for ref in case["evidence"]:
                    facts = {
                        fact["id"]: fact for fact in by_annotation[ref["article_id"]]["fact_spans"]
                    }
                    fact = facts[ref["fact_id"]]
                    if ref["text_evidence"] != {
                        "text_sha256": fact["text_sha256"],
                        "byte_span": fact["byte_span"],
                    }:
                        raise ValueError("Relationship fact evidence mismatch")
            for ref in case["evidence"]:
                source = (raw / by_id[ref["article_id"]]["path"]).read_bytes()
                span = ref["excerpt_byte_span"]
                if (
                    not (0 <= span[0] < span[1] <= len(source))
                    or source[span[0] : span[1]].decode("utf-8") != ref["excerpt"]
                ):
                    raise ValueError("Evidence excerpt differs from source bytes")
            identity = tuple(sorted(r["id"] for r in evidence))
            if identity in identities:
                raise ValueError("Duplicate relationship pair")
            identities.add(identity)
        if len(docs) == 50 and len(identities) != 20:
            raise ValueError("Relationship case coverage mismatch")
    if (output / "run-template.json").exists():
        result = read_json(output / "run-template.json")
        if result["status"] != "NOT_RUN" or result["scoring_status"] != "MANUAL_REQUIRED":
            raise ValueError("Preparation cannot certify a model run")
        if result["corpus_sha256"] != digest((output / "corpus.json").read_bytes()) or result[
            "annotations_sha256"
        ] != digest((output / "annotations.json").read_bytes()):
            raise ValueError("Result template input binding mismatch")
        if result["upstream_commit"] != PIN or [run["lane"] for run in result["runs"]] != [
            "cloud",
            "local",
        ]:
            raise ValueError("Result provenance or comparison lanes mismatch")
        expected_inputs = [input_identity(d) for d in docs]
        for run in result["runs"]:
            if run["input_artifacts"] != expected_inputs:
                raise ValueError("Exact model inputs mismatch")
            if (
                run["status"] != "NOT_RUN"
                or run["outputs"]
                or any(value is not None for value in run["metrics"].values())
            ):
                raise ValueError("Unexecuted model results must remain null")
    return {
        "integrity": "PASS",
        "articles": len(docs),
        "target_articles": 50,
        "coverage": corpus["coverage_status"],
        "model_quality": "NOT_RUN",
        "inference_calls": 0,
        "stratification": corpus.get("stratification"),
    }


def evidence_reference(document: dict[str, Any], raw: Path) -> dict[str, Any]:
    """Return a short exact title/paragraph span, not a semantic relationship label."""
    data = (raw / document["path"]).read_bytes()
    match = re.search(rb"<title[^>]*>([^<]+)", data, re.IGNORECASE)
    if match is None:
        match = re.search(rb"<p[^>]*>([^<]+)", data, re.IGNORECASE)
    if match is None:
        raise ValueError("No title or paragraph excerpt available; manual selection needed")
    excerpt = match.group(1)[:120].decode("utf-8", errors="ignore")
    words = list(re.finditer(r"\S+", excerpt))
    if len(words) > 8:
        excerpt = excerpt[: words[7].end()]
    return {
        "article_id": document["id"],
        "sha256": document["sha256"],
        "excerpt": excerpt,
        "excerpt_byte_span": [match.start(1), match.start(1) + len(excerpt.encode("utf-8"))],
        "excerpt_kind": "title_or_paragraph_candidate",
        "byte_spans": [],
    }


def literal_span(document: dict[str, Any], raw: Path, literal: str) -> dict[str, Any]:
    """Locate a manually selected literal, retaining exact frozen UTF-8 bytes."""
    source = document["text_artifact"]
    data = (raw / source["path"]).read_bytes()
    needle = literal.encode("utf-8")
    start = data.find(needle)
    if start < 0 or not needle:
        raise ValueError(f"Reference literal absent from {document['id']}")
    return {"text_sha256": source["sha256"], "byte_span": [start, start + len(needle)]}


def selected_claim(selection: dict[str, Any], document: dict[str, Any], raw: Path) -> str:
    if "claim_anchor" in selection:
        return str(selection["claim_anchor"])
    data = (raw / document["text_artifact"]["path"]).read_bytes()
    start, end = selection["claim_byte_span"]
    if not 0 <= start < end <= len(data) or digest(data[start:end]) != selection["claim_sha256"]:
        raise ValueError("Selected source claim span/hash mismatch")
    return data[start:end].decode("utf-8")


def proposed_references(
    docs: list[dict[str, Any]], raw: Path, specification: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_id = {document["id"]: document for document in docs}
    if set(specification["articles"]) != set(by_id):
        raise ValueError("Reference specification does not cover exact corpus")
    articles = []
    for document in docs:
        selection = specification["articles"][document["id"]]
        claim = selected_claim(selection, document, raw)
        fact_id = f"fact-{document['id']}"
        fact = {
            "id": fact_id,
            "text": claim,
            **literal_span(document, raw, claim),
            "attribution": "source_reported_claim_not_independently_verified",
            "status": "proposed_reference",
        }
        extra_facts = [
            {
                "id": f"{fact_id}-extra-{i}",
                "text": anchor,
                **literal_span(document, raw, anchor),
                "attribution": "source_reported_claim_not_independently_verified",
                "status": "proposed_reference",
            }
            for i, anchor in enumerate(selection.get("additional_claim_anchors", []), 1)
        ]
        for i, span_selection in enumerate(selection.get("additional_claim_spans", []), 1):
            literal = selected_claim(span_selection, document, raw)
            extra_facts.append(
                {
                    "id": f"{fact_id}-extra-{i}",
                    "text": literal,
                    **literal_span(document, raw, literal),
                    "attribution": "source_reported_claim_not_independently_verified",
                    "status": "proposed_reference",
                }
            )
        articles.append(
            {
                "article_id": document["id"],
                "sha256": document["sha256"],
                "split": document["split"],
                "entities": [
                    {
                        "name": selection["entity"],
                        "entity_type": "named_subject",
                        **literal_span(document, raw, selection["entity"]),
                        "status": "proposed_reference",
                    }
                ],
                "events": [
                    {
                        "event_type": "source_reported_claim",
                        "fact_id": fact_id,
                        "status": "proposed_reference",
                    }
                ],
                "fact_spans": [fact, *extra_facts],
                "summary_factuality": None,
                "status": "needs_review",
            }
        )
    pairs: list[dict[str, Any]] = []
    for selection in specification["relationships"]:
        left, right = [by_id[selection[key]] for key in ("left", "right")]
        if left["split"] != right["split"]:
            raise ValueError("Proposed relationship crosses split")
        evidence = []
        for document in (left, right):
            reference = evidence_reference(document, raw)
            short = re.match(r"\S+", reference["excerpt"])
            if short:
                reference["excerpt"] = short.group()
                reference["excerpt_byte_span"][1] = reference["excerpt_byte_span"][0] + len(
                    short.group().encode("utf-8")
                )
            reference.update(
                fact_id=f"fact-{document['id']}",
                text_evidence=literal_span(
                    document,
                    raw,
                    selected_claim(specification["articles"][document["id"]], document, raw),
                ),
            )
            evidence.append(reference)
        pairs.append(
            {
                "id": f"relation-{len(pairs) + 1:03d}",
                "split": left["split"],
                "evidence": evidence,
                "relationship_label": selection["label"],
                "engine_relation": selection["engine_relation"],
                "label_status": "proposed_reference",
                "status": "needs_review",
                "reviewer": None,
                "rationale": selection["reason"],
            }
        )
    return articles, pairs


def reference(output: Path, raw: Path, base_output: Path, specification_path: Path) -> None:
    validate(base_output, raw)
    if output.exists():
        raise ValueError("Reference version requires a fresh output directory")
    corpus = read_json(base_output / "corpus.json")
    specification = read_json(specification_path)
    replacements = {
        row["replace_article_id"]: row for row in specification.get("replacement_documents", [])
    }
    corpus["documents"] = [
        dict(replacements.get(document["id"], document)) for document in corpus["documents"]
    ]
    for document in replacements.values():
        verify_artifact(raw, document)
        verify_artifact(raw, document["text_artifact"])
    for document in corpus["documents"]:
        selected = specification["articles"][document["id"]]
        document.update(event_group=selected["event_group"], split=selected["split"])
    corpus.update(
        split_policy="reference_event_groups_v1",
        reference_spec_path=str(specification_path),
        reference_spec_sha256=digest(specification_path.read_bytes()),
        reference_base_corpus_sha256=digest((base_output / "corpus.json").read_bytes()),
    )
    for key in ("zh", "en", "long_form"):
        corpus["stratification"][key] = sum(
            (
                document["text_info"]["long_form"]
                if key == "long_form"
                else document["text_info"]["language"] == key
            )
            for document in corpus["documents"]
        )
    proposed_references(corpus["documents"], raw, specification)
    write_json(output / "corpus.json", corpus)
    template(output, raw, specification)
    LOG.info(
        "Proposed references frozen: %s articles and %s relationships; human review required",
        len(corpus["documents"]),
        len(specification["relationships"]),
    )


def template(output: Path, raw: Path, specification: dict[str, Any] | None = None) -> None:
    validate(output, raw)
    corpus = read_json(output / "corpus.json")
    docs = corpus["documents"]
    pairs: list[dict[str, Any]] = []
    for split, target in (("tuning", 14), ("holdout", 6)):
        members = [d for d in docs if d["split"] == split]
        candidate_pairs = [(members[i], members[i + 1]) for i in range(0, len(members) - 1, 2)]
        candidate_pairs += [(members[i], members[i + 2]) for i in range(len(members) - 2)]
        for left, right in candidate_pairs[:target]:
            pairs.append(
                {
                    "id": f"relation-{len(pairs) + 1:03d}",
                    "split": split,
                    "evidence": [evidence_reference(d, raw) for d in (left, right)],
                    "relationship_label": None,
                    "status": "needs_review",
                    "reviewer": None,
                    "rationale": None,
                }
            )
    proposed_articles = None
    if specification is not None:
        proposed_articles, pairs = proposed_references(docs, raw, specification)
    write_json(
        output / "annotations.json",
        {
            "status": "needs_review",
            "gold_approved": False,
            "reference_status": "proposed_reference" if specification else "blank_template",
            "articles": (
                proposed_articles
                if proposed_articles is not None
                else [
                    {
                        "article_id": d["id"],
                        "sha256": d["sha256"],
                        "split": d["split"],
                        "entities": None,
                        "events": None,
                        "fact_spans": None,
                        "summary_factuality": None,
                        "status": "needs_review",
                    }
                    for d in docs
                ]
            ),
            "relationships": pairs,
            "allowed_relationship_labels": [
                "same_event",
                "follow_up",
                "related_topic",
                "unrelated",
            ],
            "required_review": (
                "Source-grounded proposed references require independent human review and adjudication; they are not approved gold."
                if specification
                else "Human reviewers must select balanced cases and evidence spans; current pairs are unlabelled structural candidates, not gold."
            ),
        },
    )
    write_json(
        output / "run-template.json",
        {
            "status": "NOT_RUN",
            "scoring_status": "MANUAL_REQUIRED",
            "upstream_commit": PIN,
            "corpus_sha256": digest((output / "corpus.json").read_bytes()),
            "annotations_sha256": digest((output / "annotations.json").read_bytes()),
            "runs": [
                {
                    "lane": lane,
                    "model_id": None,
                    "model_revision": None,
                    "model_file_sha256": None,
                    "quantization": None,
                    "runtime_version": None,
                    "prompt_sha256": None,
                    "prompt_bytes": None,
                    "input_artifacts": [input_identity(d) for d in docs],
                    "decoding_parameters": None,
                    "hardware": None,
                    "status": "NOT_RUN",
                    "outputs": [],
                    "metrics": {
                        key: None
                        for key in (
                            "entity_precision",
                            "entity_recall",
                            "relationship_macro_f1",
                            "summary_factuality",
                            "latency_seconds",
                            "cost",
                            "tokens",
                        )
                    },
                }
                for lane in ("cloud", "local")
            ],
        },
    )


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def pinned_prompt(
    project: Path, name: str, stack: tuple[str, ...] = ()
) -> tuple[str, dict[str, str]]:
    """Expand only hash-verified partials from the exact vendored upstream pin."""
    if not re.fullmatch(r"[a-z][a-z-]*", name) or name in stack or len(stack) > 20:
        raise ValueError("Invalid or cyclic prompt partial")
    manifest = read_json(project / "services/ai_news/upstream.json")
    if manifest["commit"] != PIN:
        raise ValueError("Prompt upstream pin mismatch")
    relative = f"industry/prompts/{name}.md"
    data = (project / "services/ai_news/vendor/aihot" / relative).read_bytes()
    if digest(data) != manifest["files"][relative]:
        raise ValueError("Pinned prompt bytes mismatch")
    sources = {relative: digest(data)}

    def partial(match: re.Match[str]) -> str:
        text, hashes = pinned_prompt(project, match.group(1), (*stack, name))
        sources.update(hashes)
        return text

    return re.sub(r"\{\{>\s*([a-z-]+)\s*\}\}", partial, data.decode("utf-8")), sources


def check_endpoint(lane: str, endpoint: str) -> None:
    parsed = urllib.parse.urlsplit(endpoint)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Endpoint cannot contain credentials, query, or fragment")
    if lane == "local":
        if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "::1"):
            raise ValueError("Local adapter requires an explicit loopback HTTP endpoint")
    elif lane == "cloud":
        if parsed.scheme != "https" or not parsed.hostname or parsed.port not in (None, 443):
            raise ValueError("Cloud adapter requires public HTTPS")
    else:
        raise ValueError("Unknown inference lane")
    if not parsed.path.endswith("/chat/completions"):
        raise ValueError("Only OpenAI-compatible chat/completions is supported")


def document_title_time(document: dict[str, Any], raw: Path) -> tuple[str, datetime | None]:
    data = (raw / document["path"]).read_bytes()
    title = re.search(rb"<title[^>]*>([^<]+)", data, re.IGNORECASE)
    published = document.get("published_at")
    if not published:
        meta = re.search(
            rb'<meta\s+property=["\x27]article:published_time["\x27]\s+content=["\x27]([^"\x27]+)',
            data,
            re.IGNORECASE,
        )
        published = meta.group(1).decode() if meta else None
    at = None
    if published:
        try:
            at = datetime.fromisoformat(published)
        except ValueError:
            at = parsedate_to_datetime(published)
        if at.tzinfo is None:
            raise ValueError("Publication timestamp lacks timezone")
        at = at.astimezone(ZoneInfo("Asia/Shanghai"))
    return unescape(title.group(1).decode()) if title else "未注明", at


def task_payload(
    task: str, inputs: list[dict[str, Any]], selected: list[dict[str, Any]], output: Path, raw: Path
) -> str:
    """Original editor field shapes with explicitly untruncated frozen text."""
    catalog = read_json(raw / read_json(output / "corpus.json")["source_catalog"]["path"])
    sources = {source["id"]: source for source in catalog["sources"]}
    records: list[dict[str, Any]] = []
    for document, value in zip(selected, inputs, strict=True):
        title, at = document_title_time(document, raw)
        source = sources.get(
            document["source_id"], {"name": document["source_id"], "kind": "html", "tier": None}
        )
        records.append(
            {
                "document": document,
                "title": title,
                "at": at,
                "source": source,
                "text": value["content"],
            }
        )
    first = records[0]
    at = first["at"]
    if task in ("prefilter", "understand"):
        source = first["source"]
        lines = [
            f"【来源】{source['name']}（{source['kind']}，tier={source.get('tier') or '未分级'}）"
        ]
        if source.get("tags"):
            lines.append(f"【来源标签】{', '.join(source['tags'])}")
        if at:
            lines.append(f"【发布时间】{at.astimezone(UTC).isoformat()}")
        lines.extend(
            [
                f"【原文链接】{selected[0]['url']}",
                f"【标题】{first['title']}",
                "",
                "【正文】",
                first["text"],
                "",
                "【材料质量】完整正文（抓自原始网页）",
            ]
        )
        context = "\n".join(lines)
        return (
            json.dumps(context, ensure_ascii=False)
            if task == "prefilter"
            else "请按系统规则理解以下单篇材料，一次返回全部六个字段。\n\n" + context
        )
    if task == "selection-score":
        return "\n\n".join(
            [
                "请按系统规则评估以下单篇材料所代表的事件。只输出 attentionScore。",
                "【发布时间（北京时间）】\n"
                + (at.isoformat() if at else "未知（收录时间不代表发布时间）"),
                f"【标题】\n{first['title']}",
                f"【完整正文】\n{first['text']}",
            ]
        )
    if task == "translate-body":
        return json.dumps(
            {"segments": ["<p>" + escape(line) + "</p>" for line in first["text"].split("\n")]},
            ensure_ascii=False,
        )
    if task == "group-pair":
        descriptions = []
        for index, record in enumerate(records):
            when = record["at"].strftime("%Y-%m-%d %H:%M") if record["at"] else "未知"
            descriptions.append(
                f"【报道 {'AB'[index]}】\n标题：{record['title']}\n来源：{record['source']['name']}｜发布时间：{when}\n摘要：（无）\n【原文证据】\n{record['text']}\n【原文证据结束】"
            )
        return "\n\n".join(descriptions) + "\n\n这两篇报道是什么关系？"
    if task == "story-digest":
        annotations = read_json(output / "annotations.json")
        pair = {d["id"] for d in selected}
        if annotations.get("reference_status") != "proposed_reference" or not any(
            {ref["article_id"] for ref in case["evidence"]} == pair
            and case.get("engine_relation") in ("SAME_OCCURRENCE", "SAME_STORY")
            for case in annotations["relationships"]
        ):
            raise ValueError(
                "Story digest unsupported without an explicit same-story reference pair"
            )
        if any(record["at"] is None for record in records):
            raise ValueError("Story digest unsupported without source publication timestamps")
        by_annotation = {row["article_id"]: row for row in annotations["articles"]}
        lines = []
        for record in sorted(records, key=lambda row: row["at"]):
            annotation = by_annotation[record["document"]["id"]]
            fact = annotation["fact_spans"][0]
            evidence = {
                "subject": annotation["entities"][0]["name"],
                "action": None,
                "object": None,
                "conditions": None,
                "evidence": fact["text"],
                "extractedConditions": [],
                "extractedEvidence": fact["text"],
            }
            lines.append(
                f"【新】报道 {record['document']['id']}｜事实 {fact['id']}｜{record['at'].strftime('%Y-%m-%d %H:%M')}｜{record['source']['name']}｜{record['title']}｜{fact['text']}\n事实条件与来源证据：{json.dumps(evidence, ensure_ascii=False)}"
            )
        return (
            f"事件当前标题：{first['title']}\n报道（按时间，标【新】的是上一版之后的新报道）：\n"
            + "\n".join(lines)
        )
    return json.dumps(inputs, ensure_ascii=False)


def prepare_request(
    output: Path,
    raw: Path,
    config: dict[str, Any],
    article_ids: list[str],
    prompt_name: str,
    project: Path,
) -> dict[str, Any]:
    """Freeze one bounded request. This function has no inference transport."""
    validate(output, raw)
    allowed_config = {
        "lane",
        "endpoint",
        "model_id",
        "model_revision",
        "quantization",
        "runtime_version",
        "hardware",
        "max_output_tokens",
        "max_input_bytes",
        "input_usd_per_million",
        "output_usd_per_million",
        "pricing_date",
        "max_cost_usd",
        "model_file_sha256",
        "api_key_env",
    }
    if set(config) - allowed_config:
        raise ValueError("Unknown run configuration fields rejected")
    if prompt_name not in TASKS:
        raise ValueError("Unsupported evaluation task")
    if len(article_ids) != (2 if prompt_name in ("group-pair", "story-digest") else 1) or len(
        set(article_ids)
    ) != len(article_ids):
        raise ValueError("Task article count mismatch")
    for field in (
        "lane",
        "endpoint",
        "model_id",
        "model_revision",
        "quantization",
        "runtime_version",
        "hardware",
        "max_output_tokens",
        "max_input_bytes",
        "input_usd_per_million",
        "output_usd_per_million",
        "pricing_date",
        "max_cost_usd",
    ):
        if field not in config or config[field] is None or config[field] == "":
            raise ValueError(f"Exact run metadata required: {field}")
    check_endpoint(config["lane"], config["endpoint"])
    if config["lane"] == "local" and not re.fullmatch(
        r"[a-f0-9]{64}", config.get("model_file_sha256", "")
    ):
        raise ValueError("Local weights require an exact SHA-256")
    if config["lane"] == "cloud" and not re.fullmatch(
        r"[A-Z][A-Z0-9_]*", config.get("api_key_env", "")
    ):
        raise ValueError("Cloud adapter requires an environment variable name, never a key value")
    if any("key" in key.lower() and key != "api_key_env" for key in config):
        raise ValueError("Secret fields cannot enter frozen request metadata")
    prompt, hashes = pinned_prompt(project, prompt_name)
    corpus = read_json(output / "corpus.json")
    documents = {d["id"]: d for d in corpus["documents"]}
    selected = [documents[article_id] for article_id in article_ids]
    if len({document["split"] for document in selected}) != 1:
        raise ValueError("Mixed tuning/holdout request forbidden")
    inputs = []
    for document in selected:
        record = document.get("text_artifact", document)
        verify_artifact(raw, record)
        inputs.append(
            {
                "article_id": document["id"],
                "url": document["url"],
                "content": (raw / record["path"]).read_text(encoding="utf-8"),
            }
        )
    render_values: dict[str, str] = {}
    if "{{siteName}}" in prompt:
        relative = "site/site.ts"
        site_bytes = (project / "services/ai_news/vendor/aihot" / relative).read_bytes()
        manifest = read_json(project / "services/ai_news/upstream.json")
        if digest(site_bytes) != manifest["files"][relative]:
            raise ValueError("Pinned site identity bytes mismatch")
        name = re.search(r'\bname:\s*"([^"\n]+)"', site_bytes.decode())
        if name is None:
            raise ValueError("Pinned site name cannot be resolved")
        render_values["siteName"] = name.group(1)
        hashes[relative] = digest(site_bytes)
    if prompt_name == "summarize-article":
        document = selected[0]
        title = re.search(
            rb"<title[^>]*>([^<]+)", (raw / document["path"]).read_bytes(), re.IGNORECASE
        )
        published = document.get("published_at")
        render_values.update(
            publishedDate=(
                parsedate_to_datetime(published)
                .astimezone(ZoneInfo("Asia/Shanghai"))
                .date()
                .isoformat()
                if published
                else "未注明"
            ),
            today=datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat(),
            sourceName=document["source_id"],
            identity="身份信息未提供；仅依据正文",
            title=unescape(title.group(1).decode()) if title else "未注明",
            body=inputs[0]["content"],
        )

    def fill(match: re.Match[str]) -> str:
        if match.group(1) not in render_values:
            raise ValueError("Unresolved pinned prompt variable")
        return render_values[match.group(1)]

    prompt = re.sub(r"\{\{\s*([A-Za-z][\w.-]*)\s*\}\}", fill, prompt)
    body = {
        "model": config["model_id"],
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": task_payload(prompt_name, inputs, selected, output, raw)},
        ],
        "temperature": 0,
        "max_tokens": config["max_output_tokens"],
        "stream": False,
    }
    input_bytes = len(canonical(body["messages"]))
    if (
        type(config["max_output_tokens"]) is not int
        or config["max_output_tokens"] <= 0
        or type(config["max_input_bytes"]) is not int
        or not 0 < input_bytes <= config["max_input_bytes"]
    ):
        raise ValueError("Input or output budget invalid; no silent truncation")
    input_price, output_price, budget = [
        Decimal(str(config[key]))
        for key in ("input_usd_per_million", "output_usd_per_million", "max_cost_usd")
    ]
    if any(not value.is_finite() or value < 0 for value in (input_price, output_price, budget)):
        raise ValueError("Invalid price or monetary budget")
    # A deliberately conservative byte budget, not a certified provider tokenizer.
    token_reservation = input_bytes + 1024
    reserved = (
        token_reservation * input_price + config["max_output_tokens"] * output_price
    ) / Decimal(1000000)
    if reserved > budget:
        raise ValueError("Conservative request reservation exceeds monetary budget")
    return {
        "schema": 1,
        "status": "PREPARED_NOT_SENT",
        "upstream_commit": PIN,
        "corpus_sha256": digest((output / "corpus.json").read_bytes()),
        "corpus_manifest_path": str((output / "corpus.json").resolve()),
        "raw_root": str(raw.resolve()),
        "task": prompt_name,
        "config": config,
        "prompt_sha256": digest(prompt.encode()),
        "prompt_source_hashes": hashes,
        "prompt_render_values": render_values,
        "builder_profile": "standalone_full_text_microtask_v1",
        "builder_script_sha256": digest(Path(__file__).read_bytes()),
        "frozen_input_data": inputs,
        "user_payload_sha256": digest(body["messages"][1]["content"].encode("utf-8")),
        "inputs": [{**input_identity(d), "split": d["split"]} for d in selected],
        "input_split": selected[0]["split"],
        "input_bytes": input_bytes,
        "input_token_reservation": token_reservation,
        "reserved_cost_usd": str(reserved),
        "body": body,
        "quality_status": "NOT_RUN",
    }


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Connect to one validated numeric address while verifying the original SNI host."""

    def __init__(self, hostname: str, address: Any) -> None:
        self.address = address
        self.tls_context = ssl.create_default_context()
        super().__init__(hostname, port=443, timeout=30, context=self.tls_context)

    def connect(self) -> None:
        raw = socket.socket(self.address[0], self.address[1], self.address[2])
        try:
            raw.settimeout(30)
            raw.connect(self.address[4])
            self.sock = self.tls_context.wrap_socket(raw, server_hostname=self.host)
        except (OSError, ValueError):
            raw.close()
            raise


def compatible_http_transport(request: dict[str, Any]) -> bytes:
    """Only called after durable single-request authorization; never retries."""
    config = request["config"]
    check_endpoint(config["lane"], config["endpoint"])
    parsed = urllib.parse.urlsplit(config["endpoint"])
    hostname = str(parsed.hostname)
    connection: http.client.HTTPConnection
    if config["lane"] == "cloud":
        addresses = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
            raise ValueError("Cloud inference address is not public")
        connection = PinnedHTTPSConnection(hostname, addresses[0])
    else:
        connection = http.client.HTTPConnection(hostname, port=parsed.port or 80, timeout=30)
    headers = {"Content-Type": "application/json"}
    if config["lane"] == "cloud":
        key = os.environ.get(config["api_key_env"])
        if not key:
            raise ValueError("Authorized cloud credential is not configured")
        headers["Authorization"] = "Bearer " + key
    try:
        connection.request("POST", parsed.path, body=canonical(request["body"]), headers=headers)
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError("Inference HTTP status rejected; redirects are never followed")
        data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("Inference response exceeds bounded limit")
        return data
    finally:
        connection.close()


def durable_receipt(path: Path, value: dict[str, Any], initial: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    target = path if initial else path.with_suffix(".updating")
    with target.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    if not initial:
        os.replace(target, path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def execute_request(
    request_path: Path,
    authorization_path: Path | None,
    receipt_path: Path,
    transport: Callable[[dict[str, Any]], bytes] | None = None,
    ledger_root: Path | None = None,
) -> dict[str, Any]:
    """Execute at most once; a durable UNKNOWN receipt permanently fences retries."""
    if authorization_path is None or transport is None:
        raise ValueError(
            "Inference disabled: independent authorization and explicit transport required"
        )
    request_bytes = request_path.read_bytes()
    request = json.loads(request_bytes)
    authorization = read_json(authorization_path)
    config = request["config"]
    expiry = datetime.fromisoformat(authorization["expires_at"])
    if (
        authorization.get("permission") != "APPROVED"
        or not authorization.get("approval_id")
        or authorization.get("scope") != "ai-news-model-eval-single-request"
        or authorization["request_sha256"] != digest(request_bytes)
        or authorization["max_requests"] != 1
        or expiry.tzinfo is None
        or expiry <= datetime.now(UTC)
    ):
        raise ValueError("Independent authorization does not cover this exact request")
    if (
        request["upstream_commit"] != PIN
        or request["status"] != "PREPARED_NOT_SENT"
        or request["quality_status"] != "NOT_RUN"
        or config["pricing_date"] != datetime.now(UTC).date().isoformat()
    ):
        raise ValueError("Request provenance/status or current-day pricing invalid")
    if request["builder_script_sha256"] != digest(Path(__file__).read_bytes()):
        raise ValueError("Prepared request builder revision changed")
    manifest_path = Path(request["corpus_manifest_path"])
    if digest(manifest_path.read_bytes()) != request["corpus_sha256"]:
        raise ValueError("Prepared corpus changed before dispatch")
    validate(manifest_path.parent, Path(request["raw_root"]))
    actual_documents = {row["id"]: row for row in read_json(manifest_path)["documents"]}
    for identity in request["inputs"]:
        document = actual_documents[identity["article_id"]]
        if identity != {**input_identity(document), "split": document["split"]}:
            raise ValueError("Input corpus identity or split mismatch")
    if (
        request["input_bytes"] != len(canonical(request["body"]["messages"]))
        or digest(request["body"]["messages"][0]["content"].encode()) != request["prompt_sha256"]
        or request["body"]["model"] != config["model_id"]
        or request["body"]["max_tokens"] != config["max_output_tokens"]
        or request["body"]["stream"] is not False
    ):
        raise ValueError("Frozen request body differs from bound metadata")
    if (
        digest(request["body"]["messages"][1]["content"].encode("utf-8"))
        != request["user_payload_sha256"]
    ):
        raise ValueError("Frozen user payload mismatch")
    embedded_inputs = request["frozen_input_data"]
    splits = {row["split"] for row in request["inputs"]}
    if splits != {request["input_split"]} or request["input_split"] not in ("tuning", "holdout"):
        raise ValueError("Mixed or unbound tuning/holdout request forbidden")
    if len(embedded_inputs) != len(request["inputs"]):
        raise ValueError("Embedded request input coverage mismatch")
    for embedded, frozen in zip(embedded_inputs, request["inputs"], strict=True):
        data = embedded["content"].encode("utf-8")
        if (
            embedded["article_id"] != frozen["article_id"]
            or len(data) != frozen["bytes"]
            or digest(data) != frozen["sha256"]
        ):
            raise ValueError("Embedded request input bytes mismatch")
    if (
        request["input_bytes"] > authorization["max_input_bytes"]
        or config["max_output_tokens"] > authorization["max_output_tokens"]
        or Decimal(request["reserved_cost_usd"]) > Decimal(str(authorization["max_cost_usd"]))
    ):
        raise ValueError("Authorization budget exceeded")
    check_endpoint(config["lane"], config["endpoint"])
    receipt = {
        "status": "DISPATCHING",
        "request_sha256": digest(request_bytes),
        "authorization_sha256": digest(authorization_path.read_bytes()),
        "approval_id": authorization["approval_id"],
        "quality_status": "NOT_SCORED",
        "attempts": 1,
        "response_sha256": None,
        "usage": None,
        "cost_usd": None,
    }
    ledger = (
        ledger_root
        if ledger_root is not None
        else Path(__file__).resolve().parents[1] / "logs/ai-news-eval/dispatch-ledger"
    )
    fence = ledger / f"{digest(request_bytes)}.dispatch.json"
    durable_receipt(fence, receipt, initial=True)
    durable_receipt(receipt_path, receipt, initial=True)
    try:
        response_bytes = transport(request)
        response_path = receipt_path.with_suffix(".response.json")
        with response_path.open("xb") as stream:
            stream.write(response_bytes)
            stream.flush()
            os.fsync(stream.fileno())
        receipt["response_sha256"] = digest(response_bytes)
        response = json.loads(response_bytes)
        usage = response["usage"]
        if request["task"] == "translate-body":
            translations = json.loads(response["choices"][0]["message"]["content"])["t"]
            segments = json.loads(request["body"]["messages"][1]["content"])["segments"]
            if (
                not isinstance(translations, list)
                or len(translations) != len(segments)
                or any(not isinstance(value, str) or not value.strip() for value in translations)
            ):
                raise ValueError("Full-body translation segment coverage incomplete")
        if (
            response["model"] != config["model_id"]
            or not isinstance(response["choices"][0]["message"]["content"], str)
            or response["choices"][0].get("finish_reason") != "stop"
            or any(
                type(usage[k]) is not int or usage[k] < 0
                for k in ("prompt_tokens", "completion_tokens")
            )
        ):
            raise ValueError("Response model, output, or usage cannot be verified")
        cost = (
            usage["prompt_tokens"] * Decimal(str(config["input_usd_per_million"]))
            + usage["completion_tokens"] * Decimal(str(config["output_usd_per_million"]))
        ) / Decimal(1000000)
        if (
            usage["prompt_tokens"] > request["input_token_reservation"]
            or usage["completion_tokens"] > config["max_output_tokens"]
            or cost > Decimal(request["reserved_cost_usd"])
        ):
            raise ValueError("Response exceeds reserved budget; reconciliation required")
        receipt.update(status="COMPLETED", usage=usage, cost_usd=str(cost))
    except Exception as error:  # noqa: BLE001 - persist unknown dispatch, then raise; never retry.
        receipt.update(status="UNKNOWN_DO_NOT_RETRY", error_type=type(error).__name__)
        durable_receipt(receipt_path, receipt)
        durable_receipt(fence, receipt)
        LOG.error("Inference outcome unknown; receipt preserved and retry forbidden")
        raise ValueError(
            "Inference outcome unknown; inspect persistent receipt; do not retry"
        ) from None
    durable_receipt(receipt_path, receipt)
    durable_receipt(fence, receipt)
    LOG.info("Authorized single request completed; quality remains NOT_SCORED")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation",
        choices=(
            "prepare",
            "freeze",
            "validate",
            "template",
            "balance",
            "reference",
            "request",
            "execute",
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--base-output", type=Path)
    parser.add_argument("--base-raw", type=Path)
    parser.add_argument("--chinese-sources", type=Path)
    parser.add_argument("--reference-spec", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--article-id", action="append", default=[])
    parser.add_argument("--prompt", choices=TASKS)
    parser.add_argument("--request-file", type=Path)
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--allow-network", action="store_true")
    args = parser.parse_args()
    try:
        log_dir = Path(__file__).resolve().parents[1] / "logs/ai-news-eval"
        log_dir.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            handlers=[
                logging.FileHandler(log_dir / "preparation.log", encoding="utf-8"),
                logging.StreamHandler(sys.stderr),
            ],
            format="%(asctime)s %(name)s %(levelname)s %(message)s",
        )
        if args.operation in ("request", "execute"):
            project = Path(__file__).resolve().parents[1]
            if args.request_file is None or not args.request_file.resolve().is_relative_to(
                (project / "logs/ai-news-eval").resolve()
            ):
                raise ValueError("Frozen request must stay in private logs/ai-news-eval")
            if args.operation == "request":
                if args.config is None or args.prompt is None:
                    raise ValueError("request requires --config --prompt and task article IDs")
                request = prepare_request(
                    args.output,
                    args.raw,
                    read_json(args.config),
                    args.article_id,
                    args.prompt,
                    project,
                )
                write_json(args.request_file, request)
                print(
                    json.dumps(
                        {
                            "status": "PREPARED_NOT_SENT",
                            "request_sha256": digest(args.request_file.read_bytes()),
                            "reserved_cost_usd": request["reserved_cost_usd"],
                            "inference_calls": 0,
                        }
                    )
                )
            else:
                validate(args.output, args.raw)
                if (
                    not args.allow_network
                    or args.receipt is None
                    or not args.receipt.resolve().is_relative_to(
                        (project / "logs/ai-news-eval").resolve()
                    )
                ):
                    raise ValueError(
                        "execute requires explicit network flag and private receipt path"
                    )
                prepared = read_json(args.request_file)
                if prepared["corpus_sha256"] != digest((args.output / "corpus.json").read_bytes()):
                    raise ValueError("Prepared request corpus binding mismatch")
                result = execute_request(
                    args.request_file, args.authorization, args.receipt, compatible_http_transport
                )
                print(
                    json.dumps(
                        {"status": result["status"], "quality_status": result["quality_status"]}
                    )
                )
        elif args.operation == "reference":
            if not args.base_output or not args.reference_spec:
                raise ValueError("reference requires --base-output --reference-spec")
            reference(args.output, args.raw, args.base_output, args.reference_spec)
        elif args.operation == "balance":
            if not all((args.base_output, args.base_raw, args.chinese_sources)):
                raise ValueError("balance requires --base-output --base-raw --chinese-sources")
            balance(args.output, args.raw, args.base_output, args.base_raw, args.chinese_sources)
        elif args.operation == "validate":
            print(json.dumps(validate(args.output, args.raw)))
        else:
            {"prepare": prepare, "freeze": freeze, "template": template}[args.operation](
                args.output, args.raw
            )
        return 0
    except (OSError, ValueError, KeyError, TypeError, ArithmeticError) as error:
        LOG.error("Evaluation preparation failed: %s", type(error).__name__)
        print(f"ERROR: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
