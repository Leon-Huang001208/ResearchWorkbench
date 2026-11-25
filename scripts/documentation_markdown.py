"""Minimal, dependency-free Markdown -> HTML for the API manual sample.

Supports: ATX headings, fenced code, GFM tables, blockquotes, lists,
inline code, bold, links, and raw HTML anchors.
"""

from __future__ import annotations

import html
import re

FOOTNOTES = False


def inline(text: str) -> str:
    # Protect code spans first so **bold** inside them is never interpreted,
    # but still allow **bold** that *wraps* a code span.
    spans: list[str] = []

    def hold(match: re.Match) -> str:
        spans.append("<code>" + html.escape(match.group(1).replace("\\|", "|")) + "</code>")
        return f"\x00{len(spans) - 1}\x00"

    text = re.sub(r"`([^`]+)`", hold, text)
    # Protect the few inline tags the generator emits itself.
    tags: list[str] = []

    def hold_tag(match: re.Match) -> str:
        tags.append(match.group(1))
        return f"\x03{len(tags) - 1}\x03"

    text = re.sub(r"(</?sub>)", hold_tag, text)
    text = html.escape(text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    if FOOTNOTES:
        # Code spans are already placeholder-protected, so a bare [n] here is
        # always a footnote marker (202[2] included).
        text = re.sub(
            r"\[(\d{1,2})\](?![(\(\[\d])", r'<sup class="fn"><a href="#n\1">\1</a></sup>', text
        )
    text = re.sub(r"\x03(\d+)\x03", lambda match: tags[int(match.group(1))], text)
    return re.sub(r"\x00(\d+)\x00", lambda match: spans[int(match.group(1))], text)


def slug(text: str) -> str:
    text_value = re.sub(r"<[^>]+>", "", text)
    text_value = re.sub(r"[`*]", "", text_value).strip().lower()
    text_value = re.sub(r"[^\w\u4e00-\u9fff -]", "", text_value)
    return re.sub(r"\s+", "-", text_value)


def render(md: str) -> str:
    global FOOTNOTES
    FOOTNOTES = bool(re.search(r"^##\s+Notes\s*$", md, re.MULTILINE))
    lines = md.split("\n")
    out, line_index = [], 0
    in_code = False
    lang = ""
    code: list[str] = []
    while line_index < len(lines):
        line = lines[line_index]
        if line.startswith("```"):
            if in_code:
                raw = "\n".join(code)
                if lang == "sig":
                    esc = html.escape(raw)
                    esc = re.sub(
                        r"^(GET|POST|PUT|PATCH|DELETE|HEAD)(\s+)",
                        r'<span class="m">\1</span>\2',
                        esc,
                    )
                    esc = re.sub(r"(/api/research[^\s]*)", r'<span class="p">\1</span>', esc)
                    out.append('<div class="sig">' + esc + "</div>")
                else:
                    out.append("<pre><code>" + html.escape(raw) + "</code></pre>")
                code, in_code, lang = [], False, ""
            else:
                in_code = True
                lang = line[3:].strip()
            line_index += 1
            continue
        if in_code:
            code.append(line)
            line_index += 1
            continue
        if not line.strip():
            line_index += 1
            continue
        if line.startswith(("<a id=", "<a name=")):
            out.append(line)
            line_index += 1
            continue
        match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if match:
            level = len(match.group(1))
            raw = match.group(2)
            hid = slug(raw)
            endpoint = re.match(r"^(GET|POST|PUT|PATCH|DELETE|HEAD)\s+(/\S*)$", raw)
            if level in (2, 3) and endpoint:
                out.append(
                    f'<h{level} class="ep h{level}" id="{hid}"><span class="verb v-{endpoint.group(1).lower()}">'
                    f'{endpoint.group(1)}</span><code class="ep-path">{html.escape(endpoint.group(2))}</code></h{level}>'
                )
            else:
                out.append(f'<h{level} id="{hid}">{inline(raw)}</h{level}>')
            line_index += 1
            continue
        if line.startswith(">"):
            buf = []
            while line_index < len(lines) and lines[line_index].startswith(">"):
                buf.append(lines[line_index].lstrip("> ").rstrip())
                line_index += 1
            out.append(
                "<blockquote><p>" + "<br>".join(inline(x) for x in buf) + "</p></blockquote>"
            )
            continue
        if re.fullmatch(r"-{3,}", line.strip()):
            out.append("<hr>")
            line_index += 1
            continue
        if line.startswith("|"):
            rows = []
            while line_index < len(lines) and lines[line_index].startswith("|"):
                rows.append(lines[line_index])
                line_index += 1

            # Split on unescaped pipes only: \| stays inside the cell.
            def split_row(row_text: str) -> list[str]:
                body = row_text.strip()
                body = body.removeprefix("|")
                if body.endswith("|") and not body.endswith("\\|"):
                    body = body[:-1]
                cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", body)]
                return [cell.replace("\\|", "|") for cell in cells]

            parsed = [split_row(row_text) for row_text in rows]
            width = max((len(row_text) for row_text in parsed), default=0)
            # A column is "narrow" when every cell in it is short.
            narrow = [
                all(
                    len(re.sub(r"`|\*\*", "", row_text[cell])) <= 24
                    and "`" not in row_text[cell]
                    and "enum:" not in row_text[cell]
                    for row_text in parsed
                    if cell < len(row_text)
                )
                for cell in range(width)
            ]
            out.append('<div class="tw"><table>')
            for row_index, cells in enumerate(parsed):
                if row_index == 1 and all(re.fullmatch(r":?-{2,}:?", cell) for cell in cells):
                    continue
                tag = "th" if row_index == 0 else "td"
                tds = "".join(
                    "<{tag}{css_class}>{text}</{tag}>".format(
                        tag=tag,
                        css_class=' class="nw"' if narrow[column_index] else "",
                        text=inline(cell),
                    )
                    for column_index, cell in enumerate(cells)
                )
                out.append("<tr>" + tds + "</tr>")
            out.append("</table></div>")
            continue
        if re.match(r"^\s*\d+\.\s+", line):
            ordered = []
            while line_index < len(lines):
                if re.match(r"^\s*\d+\.\s+", lines[line_index]):
                    ordered.append(re.sub(r"^\s*\d+\.\s+", "", lines[line_index]))
                elif ordered and lines[line_index].startswith("   ") and lines[line_index].strip():
                    ordered[-1] += " " + lines[line_index].strip()
                else:
                    break
                line_index += 1
            items = "".join(
                f'<li id="n{column_index + 1}">{inline(text_value)}</li>'
                for column_index, text_value in enumerate(ordered)
            )
            out.append(f'<ol class="notes">{items}</ol>')
            continue
        if re.match(r"^\s*[-*]\s+", line):
            out.append("<ul>")
            while line_index < len(lines) and re.match(r"^\s*[-*]\s+", lines[line_index]):
                out.append("<li>" + inline(re.sub(r"^\s*[-*]\s+", "", lines[line_index])) + "</li>")
                line_index += 1
            out.append("</ul>")
            continue
        out.append("<p>" + inline(line) + "</p>")
        line_index += 1
    if in_code:
        out.append("<pre><code>" + html.escape("\n".join(code)) + "</code></pre>")
    return "\n".join(out)
