"""Render the curated documentation center without browser-side network access."""

from __future__ import annotations

import html
import json
import posixpath
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

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
td:first-child{white-space:nowrap;overflow-wrap:normal}td:first-child code{white-space:nowrap}
.top{min-height:54px;padding:8px 28px;gap:20px}.top-links{display:flex;gap:24px;margin-left:auto;font-size:14px}.top-links a{text-decoration:none;color:var(--muted)}
.layout{max-width:1540px;padding:0;grid-template-columns:260px minmax(0,1fr) 220px;gap:0}
.sidebar{top:54px;height:calc(100vh - 54px);padding:24px 20px 32px;background:var(--panel);border-right:1px solid var(--line)}
.search-box{margin:0 0 24px;max-width:none}.search-box input{background:var(--bg);font-size:13px;padding:8px}.search-results{z-index:20;position:relative;margin-top:6px;max-height:45vh;box-shadow:none}
.sidebar .home{margin-bottom:14px}.sidebar details{margin-bottom:16px}.sidebar summary{font-size:13px;color:var(--fg)}.sidebar a{font-size:13px;padding:4px 10px;line-height:1.55}.sidebar-foot{margin-top:24px}.theme-control{display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:12px;color:var(--muted);margin-bottom:14px}.theme-control select{font-size:12px;padding:4px}
main{padding:30px 44px 64px}.crumbs{margin-bottom:18px;font-size:12px}h1{font-size:30px;line-height:1.3;margin-bottom:24px}h2{font-size:22px;margin:32px 0 12px;padding:0;border:0}h3{margin-top:24px}body{font-size:15px;line-height:1.7}p{margin:12px 0}li{margin:5px 0}pre{border-radius:2px;padding:14px}table{font-size:13px}.tw{border-radius:0}th,td{padding:8px 10px}.page-toc{top:80px;max-height:calc(100vh - 100px);margin:28px 20px 0 0;font-size:12px;padding-left:18px}.page-toc a{line-height:1.5}.page-toc a.current{color:var(--link);font-weight:600}.page-toc a.toc-sub{padding-left:12px}.footer{line-height:1.6}.pager{margin-top:40px}.home-groups h2{font-size:20px}
@media(min-width:1101px) and (max-width:1200px){.layout{grid-template-columns:230px minmax(0,1fr) 180px}.page-toc{display:block}main{padding-left:30px;padding-right:30px}}
@media(max-width:1100px){.layout{grid-template-columns:240px minmax(0,1fr)}.page-toc{display:none}.top-links{gap:16px}main{padding:28px 32px 60px}}
@media(max-width:760px){.top{min-height:54px;flex-wrap:nowrap;padding:8px 16px}.top-links{display:none}.layout{display:block}.sidebar{top:54px;height:calc(100vh - 54px);width:290px;padding:22px 20px}.search-box{margin:0 0 20px}.search-results{max-height:40vh}.brand{font-size:15px}main{padding:24px 20px 48px}h1{font-size:26px}h2{font-size:21px}.menu{margin-left:auto;order:3}.version{display:inline;font-size:11px}.starts{margin-top:22px}.page-toc{display:none}}
"""

THEME_SCRIPT = """
const themeMedia=matchMedia('(prefers-color-scheme: dark)');
let themePreference=new URLSearchParams(location.search).get('theme');
if(!['light','dark','auto'].includes(themePreference))themePreference='auto';
function applyTheme(){document.documentElement.dataset.theme=themePreference==='auto'?(themeMedia.matches?'dark':'light'):themePreference;}
applyTheme();
themeMedia.addEventListener('change',()=>{if(themePreference==='auto')applyTheme();});
"""

# Reference layout: global navigation, a section tree, and a quiet article column.
CSS += """
:root{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Helvetica Neue",Arial,"PingFang SC",sans-serif}
body{font-size:16px;line-height:1.65}.top{min-height:80px;padding:16px 32px;gap:24px;box-shadow:0 2px 4px #0000000b}.brand{font-size:18px;font-weight:600}.version{display:block;border:1px solid var(--line);padding:4px 8px;border-radius:3px;color:var(--link);font-size:13px;text-decoration:none;white-space:nowrap}.top-links{margin:0;gap:20px;flex:1;align-items:center}.top-links a{font-size:14px;white-space:nowrap}.search-box{position:relative;flex:0 1 240px;margin:0}.search-box input{font-size:14px;padding:7px 10px}.search-results{position:absolute;top:100%;left:0;right:0;min-width:270px;max-height:65vh;box-shadow:0 6px 16px #0002}.theme-control{margin:0}.theme-control label{display:none}.theme-control select{font-size:12px;padding:6px;max-width:110px}
:root[data-theme=dark] .brand img{filter:brightness(0) invert(1)}
.layout{max-width:none;grid-template-columns:240px minmax(0,1fr) 200px}.sidebar{background:var(--bg);top:80px;height:calc(100vh - 80px);padding:22px 20px 32px 32px}.sidebar summary{font-size:14px}.sidebar a{font-size:14px;line-height:1.65;padding:5px 10px}.sidebar .nav-child{padding-left:22px;font-size:13px}.sidebar .api-tree{margin:4px 0 12px 10px}.sidebar .api-tree summary{font-size:13px;font-weight:400;color:var(--muted)}main{padding:24px 32px 72px}h1{font-size:38px;font-weight:550;line-height:1.2;margin:0 0 26px}h2{font-size:26px;font-weight:600;margin:34px 0 16px}h3{font-size:21px}.crumbs{font-size:13px;margin-bottom:24px}.page-toc{top:104px;margin:24px 28px 0 0;padding-left:16px;font-size:13px;max-height:calc(100vh - 125px)}.page-toc strong{font-weight:500}.page-toc a{line-height:1.55}.home-page .layout{max-width:1184px;grid-template-columns:minmax(0,1fr) 180px;gap:32px}.home-page .sidebar{display:none}.home-page main{padding:34px 0 72px}.home-page .crumbs{display:none}.home-page h1{font-size:40px;font-weight:500;margin-bottom:20px}.home-page .catalogue{padding:0;list-style:none;margin-top:24px}.catalogue>li{margin:22px 0}.catalogue>li>a{font-weight:600}.catalogue ul{list-style:none;padding-left:24px;margin:8px 0}.catalogue li li{margin:6px 0}.catalogue a{text-decoration:underline}.release-status{max-width:960px}.release-status p{margin:18px 0}.design-banner{border-left:3px solid var(--link);padding:10px 16px;background:var(--panel)}
@media(min-width:1600px){.layout{max-width:1600px}.home-page .layout{max-width:1280px}}
@media(max-width:1200px){.top{gap:14px;padding:14px 24px}.top-links{gap:12px}.top-links a{font-size:13px}.search-box{flex-basis:190px}.layout{grid-template-columns:220px minmax(0,1fr)}.page-toc{display:none}.home-page .layout{display:block;max-width:980px}.home-page main{padding:30px 32px}}
@media(max-width:960px){.top-links{display:none}.search-box{margin-left:auto;flex-basis:260px}}
@media(max-width:760px){.top{min-height:110px;flex-wrap:wrap;padding:12px 16px;gap:12px}.version{font-size:11px}.menu{margin:0 0 0 auto;order:2}.theme-control{order:3}.search-box{flex-basis:100%;order:4;max-width:none;margin:0}.search-results{min-width:0}.layout{display:block}.sidebar,.home-page .sidebar{top:110px;height:calc(100vh - 110px);padding:20px;display:none}.sidebar.open,.home-page .sidebar.open{display:block}.home-page main,main{padding:24px 20px 48px}.home-page .layout{margin:0}.home-page h1,h1{font-size:30px}h2{font-size:23px}.brand{font-size:15px}.theme-control select{max-width:96px}.brand img{width:21px}.home-page .catalogue{margin-top:22px}}
.catalogue h2{font-size:18px;margin:20px 0 10px}.catalogue li{line-height:1.7}h2 code,h3 code{font-size:inherit;background:none;padding:0}h2,h3,[id]{scroll-margin-top:104px}
@media(max-width:760px){.version{display:none}h2,h3,[id]{scroll-margin-top:128px}}
"""

SCRIPT = """
const themeSelect=document.getElementById('theme');
themeSelect.value=themePreference;
function themedHref(href){
 const url=new URL(href,location.href);
 if(url.origin===new URL(location.href).origin&&url.pathname.startsWith(location.pathname.slice(0,location.pathname.lastIndexOf('/')+1))&&url.pathname.endsWith('.html')){
  url.searchParams.set('theme',themePreference);return url.pathname+url.search+url.hash;
 }
 return href;
}
function themeLinks(){document.querySelectorAll('a[href]').forEach(link=>{const href=link.getAttribute('href');if(!href.startsWith('#'))link.setAttribute('href',themedHref(href));});}
themeLinks();
const currentNav=document.querySelector('.sidebar a[aria-current="page"]');
if(currentNav&&matchMedia('(min-width:761px)').matches){const panel=document.getElementById('doc-sidebar'),item=currentNav.getBoundingClientRect(),bounds=panel.getBoundingClientRect();if(item.bottom>bounds.bottom-24)panel.scrollTop+=item.top-bounds.top-60;}
themeSelect.addEventListener('change',()=>{
 themePreference=themeSelect.value;applyTheme();themeLinks();
 const url=new URL(location.href);url.searchParams.set('theme',themePreference);
 try{history.replaceState(null,'',url.href);}catch{location.replace(url.href);}
});
const search=document.getElementById('doc-search'), results=document.getElementById('search-results');
const entries=JSON.parse(document.getElementById('search-data').textContent);
search.disabled=false;
search.addEventListener('input',()=>{
 const query=search.value.trim().toLowerCase();results.replaceChildren();
 if(!query)return;
 const matches=entries.filter(entry=>entry.text.toLowerCase().includes(query)).sort((a,b)=>Number(b.label.toLowerCase().includes(query))-Number(a.label.toLowerCase().includes(query))).slice(0,16);
 if(!matches.length){const p=document.createElement('p');p.textContent='没有匹配结果，试试接口名、字段名或任务关键词。';results.append(p);}
 for(const entry of matches){const link=document.createElement('a');link.href=themedHref(entry.href);link.textContent=entry.label;const caption=document.createElement('small');caption.textContent=entry.group;link.append(caption);results.append(link);}
});
document.addEventListener('keydown',event=>{if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='k'){event.preventDefault();search.focus();}if(event.key==='Escape'){results.replaceChildren();document.getElementById('doc-sidebar').classList.remove('open');document.getElementById('nav-toggle').setAttribute('aria-expanded','false');}});
document.getElementById('nav-toggle').addEventListener('click',event=>{const open=document.getElementById('doc-sidebar').classList.toggle('open');event.currentTarget.setAttribute('aria-expanded',String(open));});
const tocLinks=[...document.querySelectorAll('.page-toc a')];
if('IntersectionObserver' in window){const headings=tocLinks.map(link=>document.getElementById(decodeURIComponent(link.hash.slice(1)))).filter(Boolean);
 const observer=new IntersectionObserver(items=>{for(const item of items)if(item.isIntersecting)tocLinks.forEach(link=>{const active=decodeURIComponent(link.hash.slice(1))===item.target.id;link.classList.toggle('current',active);if(active)link.setAttribute('aria-current','location');else link.removeAttribute('aria-current');});},{rootMargin:'-60px 0px -65% 0px'});headings.forEach(heading=>observer.observe(heading));}
if(location.pathname.endsWith('/index.html')||location.pathname.endsWith('/')){
 const legacy=['overview','deployment','subsystems','flows','details','modules'];
 if(legacy.includes(location.hash.slice(1)))location.replace(themedHref('architecture.html'+location.hash));
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
        source = page.get("source")
        if source is not None:
            if (page["slug"], source) != (
                "design-weknora-datahub",
                "docs/manual/design-weknora-datahub.md",
            ) or not re.fullmatch(r"[a-f0-9]{40}", page.get("source_revision", "")):
                raise ValueError("Unregistered documentation source")
            markdown = read(root, source).split("\n", 1)[1]
            page["body"] = render(markdown)

            def source_link(match, revision=page["source_revision"]):
                href = html.unescape(match.group(1))
                url = urlsplit(href)
                if url.scheme or url.netloc or not url.path:
                    return match.group(0)
                target = posixpath.normpath(posixpath.join("docs/plans", url.path))
                if target.startswith(("../", "/")):
                    raise ValueError("Invalid design source link")
                return (
                    'href="https://github.com/Leon-Huang001208/ResearchWorkbench/blob/'
                    + revision
                    + "/"
                    + html.escape(target, quote=True)
                    + ("#" + html.escape(url.fragment, quote=True) if url.fragment else "")
                    + '"'
                )

            page["body"] = re.sub(r'href="([^"]+)"', source_link, page["body"])
            page["body"] = (
                '<blockquote><p>设计与实施记录：本页为用户指定的8765讨论稿2026-11-25快照，完整保留17节与历史候选记录，尚未全部部署。七域与12个候选工具是早期目标设计，后续目录扩展见原文落实表；当前可用工具请查<a href="reference-mcp.html">MCP工具参考</a>与实际授权发现结果。工程资料链接对齐主线7a3e5c43。</p></blockquote>'
                + page["body"]
            )
            continue
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
            re.finditer(r'<h([234])[^>]*id="([^"]+)"[^>]*>(.*?)</h\1>', page["body"], re.DOTALL)
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
        sidebar = '<a class="home" href="index.html">全部文档</a>'
        for group in groups:
            if page["group"] and group != page["group"]:
                continue
            links = [
                item
                for item in pages
                if item["group"] == group
                and not item["slug"].startswith("reference-api-")
                and item["slug"] != "api-manual"
            ]
            sidebar += "<details open" + "><summary>" + html.escape(group) + "</summary>"
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
                if item["slug"] == "reference-api":
                    sidebar += '<details class="api-tree" open><summary>API 业务域</summary>'
                    for domain in api["domains"]:
                        domain_slug = "reference-api-" + domain["slug"]
                        sidebar += (
                            '<a class="nav-child"'
                            + (' aria-current="page"' if slug == domain_slug else "")
                            + ' href="'
                            + domain_slug
                            + '.html">'
                            + html.escape(domain["title"])
                            + "</a>"
                        )
                    sidebar += "</details>"
            sidebar += "</details>"
        toc = []
        for heading in re.finditer(
            r'<h([23])[^>]*id="([^"]+)"[^>]*>(.*?)</h[23]>', content, re.DOTALL
        ):
            if page.get("source") and heading.group(1) != "2":
                continue
            toc.append(
                "<a"
                + (' class="toc-sub"' if heading.group(1) == "3" else "")
                + ' href="#'
                + heading.group(2)
                + '">'
                + html.escape(plain(heading.group(3)))
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
            + "</title><script>"
            + THEME_SCRIPT
            + "</script><style>"
            + CSS
            + '</style></head><body id="top"'
            + (' class="home-page"' if slug == "index" else "")
            + ">"
            '<a class="skip" href="#content">跳到正文</a><header class="top"><button class="menu" id="nav-toggle" aria-label="展开文档目录" aria-expanded="false" aria-controls="doc-sidebar">目录</button>'
            '<a class="brand" href="index.html">'
            + brand
            + 'RWB 文档</a><a class="version" href="documentation-version.html" aria-label="文档版本与范围">'
            + version
            + '</a><nav class="top-links" aria-label="文档栏目"><a href="getting-started.html">快速开始</a><a href="guide-data.html">使用指南</a><a href="reference-api.html">API 参考</a><a href="architecture-guide.html">架构与设计</a><a href="operations-guide.html">安装运维</a></nav>'
            '<div class="search-box"><label class="sr-only" for="doc-search">搜索文档</label><input id="doc-search" placeholder="搜索文档 · Ctrl K" type="search" disabled><div class="search-results" id="search-results" role="status" aria-live="polite"></div></div>'
            '<div class="theme-control"><label for="theme">阅读主题</label><select id="theme"><option value="auto">跟随系统</option><option value="light">浅色</option><option value="dark">深色</option></select></div></header>'
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
    content = '<p>RWB 提供数据与资料访问、研究技能及获准的 MCP 接入。本手册说明使用方法、接口与字段，以及实现边界。</p><div class="release-status"><p><strong>已发布参考：</strong>使用指南与接口参考描述现有入口；实际可用范围取决于当前账号的配置、授权和服务版本。</p><p><strong>设计与源码候选：</strong>七个业务域和12个候选工具收录在<a href="design-weknora-datahub.html">DataHub 工具与技能层设计</a>。待实现和未部署的内容不代表当前可调用能力。</p></div><ul class="catalogue">'
    for index, group in enumerate(groups):
        content += (
            '<li><h2 id="'
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
                    '<li><a href="' + page["slug"] + '.html">' + html.escape(page["title"]) + "</a>"
                )
                if page["slug"] == "reference-api":
                    content += (
                        "<ul>"
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
                content += "</li>"
        content += "</ul></li>"
    content += "</ul>"
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
