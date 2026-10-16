"""Convert publisher HTML into inert reading nodes; never forward executable HTML."""

import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from core.observability import get_logger

log = get_logger(__name__)
TAGS = frozenset(
    [
        "p",
        "br",
        "hr",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "strong",
        "b",
        "em",
        "i",
        "u",
        "s",
        "del",
        "blockquote",
        "pre",
        "code",
        "ul",
        "ol",
        "li",
        "table",
        "thead",
        "tbody",
        "tfoot",
        "tr",
        "th",
        "td",
        "figure",
        "figcaption",
        "details",
        "summary",
        "a",
        "img",
        "span",
        "sup",
        "sub",
        "div",
    ]
)
BLOCKED = frozenset(
    [
        "script",
        "style",
        "iframe",
        "object",
        "embed",
        "svg",
        "math",
        "form",
        "template",
        "noscript",
        "video",
        "audio",
    ]
)


def reading_href(value: str) -> str | None:
    if not isinstance(value, str) or re.search(r"[\s\\\x00-\x1f\x7f]", value):
        return None
    if re.fullmatch(r"#sec-\d{1,5}", value):
        return value
    try:
        parsed = urlsplit(urljoin("https://aihot.news/", value))
    except ValueError:
        return None
    if parsed.scheme not in {"https", "http"} or parsed.username or parsed.password:
        return None
    if parsed.netloc == "aihot.news":
        match = re.fullmatch(
            r"/(items|story|topics)/([A-Za-z0-9_-]{1,80})(/original)?/?", parsed.path
        )
        if match:
            kind = {"items": "item", "story": "story", "topics": "topic"}[match[1]]
            return f"#/aihot/{kind}/{match[2]}" + ("?lang=original" if match[3] else "")
    return parsed.geturl()


class ReadingParser(HTMLParser):
    def __init__(self, image):
        super().__init__(convert_charrefs=True)
        self.root: list[dict] = []
        self.stack: list[tuple[str, list[dict]]] = [("", self.root)]
        self.blocked: list[str] = []
        self.image = image
        self.count = 0

    def append(self, node):
        self.count += 1
        if self.count > 30000 or len(self.stack) > 64:
            raise ValueError("AIHOT reading structure exceeds limit")
        self.stack[-1][1].append(node)

    def handle_starttag(self, tag, attributes):
        if tag in BLOCKED:
            if tag == "embed":
                return
            self.blocked.append(tag)
            return
        if self.blocked or tag not in TAGS:
            return
        raw = dict(attributes)
        attrs = {}
        if tag == "a":
            href = reading_href(raw.get("href"))
            if href:
                attrs["href"] = href
        if re.fullmatch(r"sec-\d{1,5}", raw.get("id") or ""):
            attrs["id"] = raw["id"]
        if tag == "img":
            src = self.image(raw.get("src"))
            if not src:
                return
            attrs = {"src": src, "alt": (raw.get("alt") or "")[:1000]}
        node = {"tag": tag, "attrs": attrs, "children": []}
        self.append(node)
        if tag not in {"img", "br", "hr"}:
            self.stack.append((tag, node["children"]))

    def handle_endtag(self, tag):
        if self.blocked:
            if tag == self.blocked[-1]:
                self.blocked.pop()
            return
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data):
        if not self.blocked:
            self.append({"text": data})


def reading_tree(value: str, image) -> list[dict]:
    parser = ReadingParser(image)
    try:
        parser.feed(value)
        parser.close()
    except (ValueError, RecursionError) as exc:
        log.warning("aihot_reading_body_invalid")
        raise ValueError("invalid AIHOT reading body") from exc
    return parser.root
