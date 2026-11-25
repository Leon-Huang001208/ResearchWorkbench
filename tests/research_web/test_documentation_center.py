"""Content, compatibility and offline lookup contracts for the static docs."""

import ast
import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "outputs/research-web-architecture"


class Document(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.links = []
        self.operations = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "a" and "href" in attrs:
            self.links.append(attrs["href"])
        if tag == "h3" and "ep" in attrs.get("class", "").split():
            self.operations.append(attrs["id"])


def approved_names():
    source = ast.parse((ROOT / "app/research_web/documentation.py").read_text())
    declaration = next(
        node
        for node in source.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "DOCUMENT_NAMES"
            for target in node.targets
        )
    )
    return {node.value + ".html" for node in declaration.value.args[0].generators[0].iter.elts}


def center_names():
    registry = json.loads((ROOT / "docs/manual/navigation.json").read_text())
    snapshot = json.loads((ROOT / "docs/manual/api-reference.json").read_text())
    return (
        {"index.html", "api-manual.html", "architecture.html"}
        | {page["slug"] + ".html" for page in registry["pages"]}
        | {"reference-api-" + domain["slug"] + ".html" for domain in snapshot["domains"]}
    )


def document(name):
    parsed = Document()
    parsed.feed((ARTIFACTS / name).read_text())
    return parsed


def test_center_pages_are_finite_readable_and_registered():
    assert center_names() <= approved_names()
    for name in center_names():
        content = (ARTIFACTS / name).read_text()
        assert len(content.encode()) <= 4 * 1024 * 1024
        if name != "architecture.html":
            assert 'aria-label="面包屑"' in content
            assert 'aria-label="本页目录"' in content
            assert 'href="/"' in content
            ids = document(name).ids
            assert len(ids) == len(set(ids)), name


def test_center_links_and_legacy_fragments_have_destinations():
    failures = []
    for name in center_names():
        for target in document(name).links:
            url = urlsplit(target)
            if url.scheme or url.netloc or url.path.startswith("/"):
                continue
            filename = unquote(url.path) or name
            if filename not in approved_names():
                failures.append((name, target, "unregistered"))
            elif not (ARTIFACTS / filename).is_file():
                failures.append((name, target, "missing"))
            elif url.fragment and unquote(url.fragment) not in document(filename).ids:
                failures.append((name, target, "fragment"))
    assert failures == []
    aliases = {
        "overview",
        "deployment",
        "subsystems",
        "flows",
        "details",
        "modules",
        "module-frameworks",
        "module-integrations",
    }
    assert aliases <= set(document("index.html").ids) & set(document("architecture.html").ids)


def test_one_snapshot_preserves_all_operation_anchors():
    snapshot = json.loads((ROOT / "docs/manual/api-reference.json").read_text())
    operations = []
    for domain in snapshot["domains"]:
        anchors = document("reference-api-" + domain["slug"] + ".html").operations
        assert len(anchors) == domain["operations"]
        operations.extend(anchors)
    assert len(operations) == 460
    assert operations == document("api-manual.html").operations


def test_design_contains_business_domains_tools_and_source_status():
    content = (ARTIFACTS / "design-weknora-datahub.html").read_text()
    for name in (
        "stock_data",
        "fund_data",
        "index_data",
        "bond_data",
        "financial_docs",
        "economic_data",
        "analytics_data",
        "get_stock_kline",
        "get_stock_quote",
        "get_stock_financials",
        "get_stock_activity",
        "adjustment_base_date",
    ):
        assert name in content
    assert "12个候选工具" in content and "尚未全部部署" in content
    assert "41-工具面" in document("design-weknora-datahub.html").ids
    assert "12-工具输入契约12-个" in document("design-weknora-datahub.html").ids
    assert "17-资产观察首条接入的源码候选" in document("design-weknora-datahub.html").ids
    assert "7a3e5c43239fb39c84df75e2afa8b7d27c7b3292" in content


def test_search_is_inline_and_includes_body_fields_and_tools():
    content = (ARTIFACTS / "index.html").read_text()
    match = re.search(
        r'<script type="application/json" id="search-data">(.*?)</script>', content, re.DOTALL
    )
    assert match and "</script" not in match.group(1)
    entries = json.loads(match.group(1))
    for query in ("rwb_dataset_read", "idempotency-key", "query_id", "callable"):
        assert any(query in entry["text"].lower() for entry in entries), query
    assert all(urlsplit(entry["href"]).path in center_names() for entry in entries)
    script = content.split("<script>")[-1].split("</script>")[0]
    for network_call in ("fetch(", "XMLHttpRequest", "WebSocket", "localStorage"):
        assert network_call not in script


def test_guide_routes_match_registered_http_operations():
    from app.research_web.main import create_app

    paths = create_app().openapi()["paths"]
    for path in (
        "/api/research/data/catalog",
        "/api/research/capabilities",
        "/api/research/capabilities/{cid}",
    ):
        assert "get" in paths[path]
    data = (ROOT / "docs/manual/pages/guide-data.md").read_text()
    skills = (ROOT / "docs/manual/pages/guide-skills.md").read_text()
    assert 'fetch("/api/research/data/catalog")' in data
    assert 'fetch("/api/research/capabilities?kind=skill")' in skills


def test_mcp_reference_names_match_the_released_tool_definitions():
    source = ast.parse((ROOT / "app/research_web/mcp_facade/tools.py").read_text())
    names = {
        node.name
        for node in ast.walk(source)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("rwb_")
    }
    reference = (ROOT / "docs/manual/pages/reference-mcp.md").read_text()
    documented = set(re.findall(r"\b(rwb_[a-z_]+)\b", reference))
    assert documented == names


def test_builder_consumes_one_json_line_without_waiting_for_pipe_eof(tmp_path):
    legacy = {"outputs/research-web-architecture/index.html": '<h1 id="overview">Architecture</h1>'}
    with (tmp_path / "generated.json").open("wb") as output:
        process = subprocess.Popen(
            [sys.executable, str(ROOT / "scripts/documentation_center.py"), str(ROOT)],
            stdin=subprocess.PIPE,
            stdout=output,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            process.stdin.write(json.dumps(legacy) + "\n")
            process.stdin.flush()
            assert process.wait(timeout=20) == 0, process.stderr.read()
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
            process.stdin.close()
            process.stderr.close()
    generated = json.loads((tmp_path / "generated.json").read_text())
    assert "guide-data.html" in generated
