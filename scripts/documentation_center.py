"""Render the curated documentation center without browser-side network access."""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

from documentation_markdown import render

CSS = """
:root{color-scheme:light dark;--bg:#fff;--panel:#f6f7f8;--fg:#20252b;--muted:#606b77;--line:#dfe4e9;--link:#0969a0;--active:#e8f2f8;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Segoe UI",sans-serif}
@media(prefers-color-scheme:dark){:root{--bg:#171a1e;--panel:#20252b;--fg:#e6ebef;--muted:#a7b1bd;--line:#343c46;--link:#78bce5;--active:#243b4c}}
:root[data-theme=light]{color-scheme:light;--bg:#fff;--panel:#f6f7f8;--fg:#20252b;--muted:#606b77;--line:#dfe4e9;--link:#0969a0;--active:#e8f2f8}
:root[data-theme=dark]{color-scheme:dark;--bg:#171a1e;--panel:#20252b;--fg:#e6ebef;--muted:#a7b1bd;--line:#343c46;--link:#78bce5;--active:#243b4c}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font-size:16px;line-height:1.75}a{color:var(--link);text-underline-offset:3px}button,input,select{font:inherit}button,select{color:var(--fg);background:var(--bg);border:1px solid var(--line);border-radius:5px;padding:5px 9px}a:focus-visible,input:focus-visible,button:focus-visible,select:focus-visible{outline:2px solid var(--link);outline-offset:3px}
.top{min-height:68px;position:sticky;top:0;z-index:10;background:var(--bg);border-bottom:1px solid var(--line);display:flex;align-items:center;gap:22px;padding:12px 28px}.brand{font-size:17px;font-weight:650;display:flex;align-items:center;gap:10px;text-decoration:none;color:var(--fg);white-space:nowrap}.brand img{width:23px;height:26px;object-fit:contain}@media(prefers-color-scheme:dark){.brand img{filter:invert(1)}}:root[data-theme=dark] .brand img{filter:invert(1)}:root[data-theme=light] .brand img{filter:none}
.version{font-size:12px;color:var(--muted)}.search-box{position:relative;max-width:520px;flex:1;margin-left:auto}.search-box input{width:100%;padding:8px 11px;background:var(--panel);border:1px solid var(--line);border-radius:5px;color:var(--fg);font-size:14px}.search-results{position:absolute;top:100%;right:0;left:0;max-height:65vh;overflow:auto;background:var(--bg);border:1px solid var(--line);padding:8px;box-shadow:0 12px 24px #0002}.search-results:empty{display:none}.search-results a{display:block;padding:9px;text-decoration:none;border-radius:3px;font-size:14px}.search-results a:hover{background:var(--panel)}.search-results small{display:block;color:var(--muted);font-size:12px}.search-results p{padding:8px;font-size:14px}
.layout{display:grid;grid-template-columns:248px minmax(0,820px) 200px;gap:38px;max-width:1440px;margin:auto;padding:0 28px}.sidebar{position:sticky;top:88px;height:calc(100vh - 100px);overflow:auto;padding:24px 10px 36px 0;font-size:14px}.sidebar details{margin:0 0 14px}.sidebar summary{cursor:pointer;font-weight:600;padding:5px 0}.sidebar a{display:block;text-decoration:none;color:var(--muted);padding:5px 10px;margin-top:2px;border-left:2px solid transparent}.sidebar a[aria-current=page]{background:var(--active);border-color:var(--link);color:var(--fg)}.sidebar .home{padding-left:0;margin-bottom:20px;color:var(--fg)}.sidebar-foot{margin-top:32px;padding-top:16px;border-top:1px solid var(--line)}
main{min-width:0;padding:30px 0 80px}.crumbs{font-size:13px;color:var(--muted);margin:0 0 22px}.crumbs a{text-decoration:none}h1{font-size:34px;line-height:1.3;letter-spacing:-.02em;font-weight:650;margin:0 0 15px}h2{font-size:23px;line-height:1.4;margin:40px 0 14px;padding-top:18px;border-top:1px solid var(--line)}h3{font-size:18px;line-height:1.45;margin:25px 0 10px}h2,h3,[id]{scroll-margin-top:108px}p{margin:12px 0}ul,ol{padding-left:24px}li{margin:7px 0}code{font:13px/1.6 ui-monospace,SFMono-Regular,Consolas,monospace;background:var(--panel);border-radius:3px;padding:2px 4px;overflow-wrap:anywhere}pre{padding:16px;background:var(--panel);border:1px solid var(--line);border-radius:5px;overflow:auto;max-width:100%}pre code{padding:0;white-space:pre;overflow-wrap:normal}blockquote{margin:20px 0;padding:8px 18px;border-left:3px solid var(--link);background:var(--panel);font-size:14px}.tw{max-width:100%;overflow:auto;border:1px solid var(--line);border-radius:5px;margin:18px 0}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:9px 12px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line);overflow-wrap:anywhere}th{background:var(--panel);font-weight:600}td code{white-space:normal;word-break:break-word}sub{display:block;color:var(--muted);font-size:12px}.verb{font:600 11px ui-monospace,monospace;color:var(--link);display:inline-block;min-width:48px}.ep-path{font-size:14px}.ep{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.intro{font-size:18px;max-width:650px;color:var(--muted);margin-bottom:28px}.starts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px;margin:30px 0 42px}.starts a{text-decoration:none;border-top:3px solid var(--link);padding-top:13px;color:var(--fg);font-weight:600}.starts small{font-size:13px;font-weight:400;color:var(--muted);display:block;margin-top:7px}.home-groups{display:grid;grid-template-columns:1fr 1fr;gap:12px 32px}.home-groups h2{font-size:20px}.home-groups ul{list-style:none;padding:0}.home-groups li{margin:16px 0}.home-groups a{font-weight:500;text-decoration:none}.home-groups small{display:block;font-size:13px;line-height:1.6;color:var(--muted)}.topics{display:grid;grid-template-columns:1fr 1fr 1fr;gap:25px;margin:28px 0}.topics a{text-decoration:none;font-weight:600}.topics p{font-size:14px;color:var(--muted);margin-top:5px}
.page-toc{position:sticky;top:100px;align-self:start;max-height:calc(100vh - 120px);overflow:auto;margin-top:37px;font-size:12px;border-left:1px solid var(--line);padding-left:16px}.page-toc strong{display:block;margin-bottom:10px;font-weight:600}.page-toc a{display:block;color:var(--muted);text-decoration:none;margin:8px 0;overflow-wrap:anywhere}.pager{display:flex;justify-content:space-between;gap:24px;border-top:1px solid var(--line);margin-top:48px;padding-top:20px;font-size:14px}.pager small{display:block;color:var(--muted)}.footer{font-size:12px;color:var(--muted);margin-top:35px}.menu{display:none}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}.skip{position:absolute;left:-9999px}.skip:focus{left:15px;top:10px;background:var(--bg);z-index:30}
@media(max-width:1200px){.layout{grid-template-columns:220px minmax(0,1fr);gap:28px}.page-toc{display:none}.version{display:none}}@media(max-width:760px){.top{gap:10px;padding:10px 16px;flex-wrap:wrap}.brand{font-size:16px}.menu{display:block}.search-box{order:4;flex-basis:100%;max-width:none}.top select{margin-left:auto}.layout{display:block;padding:0 20px}.sidebar{display:none;position:fixed;top:112px;left:0;bottom:0;width:280px;height:auto;background:var(--bg);border-right:1px solid var(--line);padding:20px;z-index:9}.sidebar.open{display:block}main{padding-top:22px}h1{font-size:29px}h2{font-size:21px}.starts,.home-groups,.topics{grid-template-columns:1fr}.starts{gap:20px}.topics{gap:12px}.pager{font-size:13px}.search-results{max-height:55vh}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
.search-results a{overflow-wrap:anywhere}
"""

SCRIPT = """
const search=document.getElementById('doc-search'), results=document.getElementById('search-results');
const entries=JSON.parse(document.getElementById('search-data').textContent);
search.disabled=false;
search.addEventListener('input',()=>{
 const query=search.value.trim().toLowerCase();results.replaceChildren();
 if(!query)return;
 const matches=entries.filter(entry=>entry.text.toLowerCase().includes(query)).slice(0,16);
 if(!matches.length){const p=document.createElement('p');p.textContent='没有匹配结果，试试接口名、字段名或任务关键词。';results.append(p);}
 for(const entry of matches){const link=document.createElement('a');link.href=entry.href;link.textContent=entry.label;const caption=document.createElement('small');caption.textContent=entry.group;link.append(caption);results.append(link);}
});
document.addEventListener('keydown',event=>{if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='k'){event.preventDefault();search.focus();}if(event.key==='Escape'){results.replaceChildren();document.getElementById('doc-sidebar').classList.remove('open');document.getElementById('nav-toggle').setAttribute('aria-expanded','false');}});
document.getElementById('nav-toggle').addEventListener('click',event=>{const open=document.getElementById('doc-sidebar').classList.toggle('open');event.currentTarget.setAttribute('aria-expanded',String(open));});
document.getElementById('theme').addEventListener('change',event=>{if(event.target.value==='auto')delete document.documentElement.dataset.theme;else document.documentElement.dataset.theme=event.target.value;});
if(location.pathname.endsWith('/index.html')||location.pathname.endsWith('/')){
 const legacy=['overview','deployment','subsystems','flows','details','modules'];
 if(legacy.includes(location.hash.slice(1)))location.replace('architecture.html'+location.hash);
}
"""


def plain(value):
    return html.unescape(re.sub(r"<[^>]+>", " ", value))


def read(root, name):
    candidate = root
    for part in Path(name).parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise ValueError("Documentation source alias is not supported")
    return candidate.read_text(encoding="utf-8")


def build(root, legacy):
    navigation = json.loads(read(root, "docs/manual/navigation.json"))
    api = json.loads(read(root, "docs/manual/api-reference.json"))
    pages = navigation["pages"]
    for page in pages:
        if not re.fullmatch(r"[a-z0-9-]+", page["slug"]):
            raise ValueError("Invalid documentation page name")
        page["body"] = render(read(root, f"docs/manual/pages/{page['slug']}.md")).replace(
            'href="../../../outputs/research-web-architecture/', 'href="'
        )
    for domain in api["domains"]:
        pages.append(
            {
                "slug": "reference-api-" + domain["slug"],
                "title": domain["title"],
                "group": "参考手册",
                "summary": "API 参数、默认值与已登记的响应定义。",
                "body": render(domain["markdown"]),
            }
        )
    manual_body = (
        '<h2 id="领域索引">领域索引</h2><ul>'
        + "".join(
            '<li><a href="reference-api-'
            + domain["slug"]
            + '.html">'
            + html.escape(domain["title"])
            + "</a></li>"
            for domain in api["domains"]
        )
        + "</ul>"
    )
    manual_body += "".join(render(domain["markdown"]) for domain in api["domains"])
    manual_body += '<a id="gaps"></a><h2 id="缺口清单">缺口清单</h2><p>当前记录 457 个业务参数说明与 7 个成功响应结构；其余 453 个操作的响应结构尚未登记。</p>'
    pages.append(
        {
            "slug": "api-manual",
            "title": "API 参考手册 · 单页兼容版",
            "group": "参考手册",
            "summary": "原有操作锚点保持可用。新读者建议按业务域查阅。",
            "body": manual_body,
        }
    )
    search = []
    for page in pages:
        if page["slug"] == "api-manual":
            continue
        search.append(
            {
                "label": page["title"],
                "group": page["group"],
                "href": page["slug"] + ".html",
                "text": page["title"] + " " + page["summary"],
            }
        )
        headings = list(
            re.finditer(r'<h([23])[^>]*id="([^"]+)"[^>]*>(.*?)</h\1>', page["body"], re.DOTALL)
        )
        for index, heading in enumerate(headings):
            end = headings[index + 1].start() if index + 1 < len(headings) else len(page["body"])
            search.append(
                {
                    "label": page["title"] + " · " + plain(heading.group(3)),
                    "group": page["group"],
                    "href": page["slug"] + ".html#" + heading.group(2),
                    "text": page["title"] + " " + plain(page["body"][heading.start() : end]),
                }
            )
    brand = ""
    brand_match = re.search(
        r'<img src="(data:image/png;base64,[A-Za-z0-9+/=]+)"',
        legacy["outputs/research-web-architecture/index.html"],
    )
    if brand_match:
        brand = '<img alt="" src="' + brand_match.group(1) + '">'
    groups = navigation["groups"]
    version = html.escape(navigation["version"])
    encoded_search = json.dumps(search, ensure_ascii=False).replace("<", "\\u003c")
    legacy_fragments = [
        value
        for value in re.findall(
            r'id="([^"]+)"', legacy["outputs/research-web-architecture/index.html"]
        )
        if value in {"overview", "deployment", "subsystems", "flows", "details", "modules"}
        or value.startswith("module-")
    ]

    def shell(page, content):
        slug = page["slug"]
        sidebar = '<a class="home" href="index.html">文档首页</a>'
        for group in groups:
            links = [
                item
                for item in pages
                if item["group"] == group
                and not item["slug"].startswith("reference-api-")
                and item["slug"] != "api-manual"
            ]
            sidebar += (
                "<details"
                + (" open" if group == page["group"] else "")
                + "><summary>"
                + html.escape(group)
                + "</summary>"
            )
            for item in links:
                active = ' aria-current="page"' if item["slug"] == slug else ""
                sidebar += (
                    "<a"
                    + active
                    + ' href="'
                    + item["slug"]
                    + '.html">'
                    + html.escape(item["title"])
                    + "</a>"
                )
                if item["slug"] == "reference-api" and (
                    slug.startswith("reference-api-") or slug == "api-manual"
                ):
                    sidebar += (
                        '<a aria-current="page" href="'
                        + slug
                        + '.html">↳ '
                        + html.escape(page["title"])
                        + "</a>"
                    )
            sidebar += "</details>"
        toc = []
        for heading in re.finditer(
            r'<h[23][^>]*id="([^"]+)"[^>]*>(.*?)</h[23]>', content, re.DOTALL
        ):
            toc.append(
                '<a href="#'
                + heading.group(1)
                + '">'
                + html.escape(plain(heading.group(2)))
                + "</a>"
            )
        siblings = [
            item
            for item in pages
            if item["group"] == page["group"] and item["slug"] != "api-manual"
        ]
        pager = ""
        if page in siblings:
            index = siblings.index(page)
            for direction, item in (
                ("上一篇", siblings[index - 1] if index else None),
                ("下一篇", siblings[index + 1] if index + 1 < len(siblings) else None),
            ):
                if item:
                    pager += (
                        '<a href="'
                        + item["slug"]
                        + '.html"><small>'
                        + direction
                        + "</small>"
                        + html.escape(item["title"])
                        + "</a>"
                    )
        crumbs = '<a href="index.html">RWB 文档</a>'
        if page["group"]:
            crumbs += " / " + html.escape(page["group"]) + " / " + html.escape(page["title"])
        return (
            '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            "<title>"
            + html.escape(page["title"])
            + ("" if slug == "index" else " · RWB 文档")
            + "</title><style>"
            + CSS
            + '</style></head><body id="top">'
            '<a class="skip" href="#content">跳到正文</a><header class="top"><button class="menu" id="nav-toggle" aria-label="展开文档目录" aria-expanded="false" aria-controls="doc-sidebar">目录</button>'
            '<a class="brand" href="index.html">'
            + brand
            + 'RWB 文档</a><span class="version">'
            + version
            + "</span>"
            '<div class="search-box"><label class="sr-only" for="doc-search">搜索文档</label><input id="doc-search" placeholder="搜索文档、接口或字段 · Ctrl K" type="search" disabled><div class="search-results" id="search-results" role="status" aria-live="polite"></div></div>'
            '<label class="sr-only" for="theme">阅读主题</label><select id="theme"><option value="auto">跟随系统</option><option value="light">浅色</option><option value="dark">深色</option></select></header>'
            '<div class="layout"><aside class="sidebar" id="doc-sidebar" aria-label="文档目录">'
            + sidebar
            + '<div class="sidebar-foot"><a href="glossary.html">术语表</a><a href="/">返回 Research Web</a></div></aside>'
            '<main id="content"><nav class="crumbs" aria-label="面包屑">'
            + crumbs
            + "</nav><h1>"
            + html.escape(page["title"])
            + "</h1>"
            + content
            + '<nav class="pager" aria-label="章节导航">'
            + pager
            + '</nav><footer class="footer">文档版本 '
            + version
            + ' · <a href="documentation-version.html">范围与更新说明</a></footer></main>'
            '<nav class="page-toc" aria-label="本页目录"><strong>本页目录</strong>'
            + "".join(toc[:30])
            + "</nav></div>"
            '<script type="application/json" id="search-data">'
            + encoded_search
            + "</script><script>"
            + SCRIPT.replace(
                "const legacy=['overview','deployment','subsystems','flows','details','modules'];",
                "const legacy=" + json.dumps(legacy_fragments) + ";",
            )
            + "</script></body></html>"
        )

    home = {"slug": "index", "title": "RWB 文档", "group": ""}
    content = '<p class="intro">从数据和资料出发，使用技能完成研究，并保留可复查的来源与交付文件。<br>按任务阅读指南，按接口查阅定义。</p>'
    content += '<div class="starts"><a href="getting-started.html">第一次使用<small>先了解基本概念，再完成第一个任务。</small></a><a href="#guides">按任务查指南<small>数据、技能与 MCP，各有一条清楚的路径。</small></a><a href="reference-api.html">查接口与字段<small>找到参数、默认值、结构和限制。</small></a></div>'
    content += '<div class="topics"><div><a href="guide-data.html">数据</a><p>了解能查什么、来源是否可用，以及怎样解释快照。</p></div><div><a href="guide-skills.html">Skill</a><p>选择研究方法，核对输入、依赖、版本和输出。</p></div><div><a href="guide-mcp.html">MCP</a><p>从外部客户端发现并调用获准的 RWB 能力。</p></div></div><div class="home-groups">'
    for index, group in enumerate(groups):
        content += (
            '<section><h2 id="'
            + ["start", "guides", "reference", "design", "operations"][index]
            + '">'
            + html.escape(group)
            + "</h2><ul>"
        )
        for page in pages:
            if (
                page["group"] == group
                and not page["slug"].startswith("reference-api-")
                and page["slug"] != "api-manual"
            ):
                content += (
                    '<li><a href="'
                    + page["slug"]
                    + '.html">'
                    + html.escape(page["title"])
                    + "</a><small>"
                    + html.escape(page["summary"])
                    + "</small></li>"
                )
        content += "</ul></section>"
    content += "</div>"
    content += (
        "<div hidden>"
        + "".join('<a id="' + html.escape(value) + '"></a>' for value in legacy_fragments)
        + "</div>"
    )
    output = {page["slug"] + ".html": shell(page, page["body"]) for page in pages}
    output["index.html"] = shell(home, content)
    output["architecture.html"] = legacy["outputs/research-web-architecture/index.html"]
    return output


if __name__ == "__main__":
    try:
        print(
            json.dumps(
                build(Path(sys.argv[1]).resolve(), json.loads(sys.stdin.readline())),
                ensure_ascii=False,
            )
        )
    except (OSError, ValueError, KeyError, IndexError) as error:
        print(f"Documentation build failed: {type(error).__name__}: {error}", file=sys.stderr)
        raise SystemExit(1) from error
