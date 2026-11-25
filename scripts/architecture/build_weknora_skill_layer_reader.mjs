#!/usr/bin/env node
// Render one reviewed Markdown plan into a self-contained HTML reader with a
// fixed left-hand table of contents. No external Markdown dependency and no
// network assets, so the page opens offline from the repository.

import { mkdir, readFile, rename, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(here, '..', '..');
const sourcePath = path.join(
  projectRoot,
  'docs',
  'plans',
  '2026-11-24-weknora-datahub-skill-layer.md',
);
const outputDir = path.join(projectRoot, 'outputs', 'weknora-datahub-skill-layer');
const outputPath = path.join(outputDir, 'index.html');

const escapeHtml = (value) =>
  String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

const slugify = (text) => {
  const plain = text
    .replaceAll('`', '')
    .replaceAll('：', '')
    .replaceAll('、', '')
    .toLowerCase();
  return plain
    .replace(/[^\p{L}\p{N}\-_ ]/gu, '')
    .trim()
    .replaceAll(' ', '-');
};

function inline(value) {
  let text = escapeHtml(value);
  text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
  text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  // Internal anchors only; external links are rendered as plain text so the
  // page never navigates off-document by accident.
  text = text.replace(/\[([^\]]+)\]\(#([^)]+)\)/g, '<a href="#$2">$1</a>');
  text = text.replace(/\[([^\]]+)\]\((?!https?:)[^)]+\)/g, '$1');
  text = text.replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g, '<a href="$2" rel="noreferrer">$1</a>');
  return text;
}

function isTableSeparator(line) {
  return /^\|?[\s:|-]+\|[\s:|-]*$/.test(line) && line.includes('-');
}

function splitRow(line) {
  const body = line.replace(/^\|/, '').replace(/\|$/, '');
  const cells = [];
  let cell = '';
  for (let index = 0; index < body.length; index += 1) {
    const char = body[index];
    // "\|" is an escaped pipe inside a Markdown table cell, not a separator.
    if (char === '\\' && body[index + 1] === '|') {
      cell += '|';
      index += 1;
      continue;
    }
    if (char === '|') {
      cells.push(cell.trim());
      cell = '';
      continue;
    }
    cell += char;
  }
  cells.push(cell.trim());
  return cells;
}

function renderTable(lines) {
  const header = splitRow(lines[0]);
  const rows = lines.slice(2).map(splitRow);
  const head = header.map((cell) => `<th>${inline(cell)}</th>`).join('');
  const body = rows
    .map((row) => `<tr>${row.map((cell) => `<td>${inline(cell)}</td>`).join('')}</tr>`)
    .join('\n');
  return `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function renderMarkdown(markdown) {
  const lines = markdown.split(/\r?\n/);
  const html = [];
  const toc = [];
  let index = 0;
  let headingIndex = 0;
  let inCode = false;
  let code = [];
  let inList = false;
  // The HTML reader supplies its own fixed sidebar, so the in-page "导航"
  // table and quick jumps would be duplicated. Skip until the next h2.
  let inNavigationSection = false;

  const closeList = () => {
    if (inList) {
      html.push('</ul>');
      inList = false;
    }
  };

  while (index < lines.length) {
    const line = lines[index];

    if (line.startsWith('```')) {
      if (inCode) {
        html.push(`<pre><code>${escapeHtml(code.join('\n'))}</code></pre>`);
        code = [];
        inCode = false;
      } else {
        closeList();
        inCode = true;
      }
      index += 1;
      continue;
    }
    if (inCode) {
      code.push(line);
      index += 1;
      continue;
    }

    const heading = /^(#{1,4})\s+(.*)$/.exec(line);
    if (heading) {
      closeList();
      const level = heading[1].length;
      const text = heading[2].trim();
      if (level === 2) {
        inNavigationSection = text === '导航';
        if (inNavigationSection) {
          index += 1;
          continue;
        }
      }
      if (inNavigationSection) {
        index += 1;
        continue;
      }
      headingIndex += 1;
      // ASCII-only ids keep file:// deep links reliable even though headings
      // are Chinese; the visible text and sidebar label stay unchanged.
      const id = `s-${headingIndex}`;
      if (level === 2 || level === 3) toc.push({ level, text, id });
      html.push(`<h${level} id="${id}">${inline(text)}</h${level}>`);
      index += 1;
      continue;
    }

    if (inNavigationSection) {
      index += 1;
      continue;
    }

    if (line.startsWith('|') && lines[index + 1] && isTableSeparator(lines[index + 1])) {
      closeList();
      const block = [line];
      index += 1;
      while (index < lines.length && lines[index].startsWith('|')) {
        block.push(lines[index]);
        index += 1;
      }
      html.push(renderTable(block));
      continue;
    }

    if (/^[-*]\s+/.test(line)) {
      if (!inList) {
        html.push('<ul>');
        inList = true;
      }
      html.push(`<li>${inline(line.replace(/^[-*]\s+/, ''))}</li>`);
      index += 1;
      continue;
    }

    if (/^\d+\.\s+/.test(line)) {
      closeList();
      const items = [];
      // Items may be separated by blank lines and continued on indented or
      // wrapped lines; keep them in the same ordered list until a new block
      // type appears.
      while (index < lines.length && /^\d+\.\s+/.test(lines[index])) {
        let item = lines[index].replace(/^\d+\.\s+/, '');
        index += 1;
        while (index < lines.length) {
          const next = lines[index];
          if (next.trim() === '') {
            let lookahead = index + 1;
            while (lookahead < lines.length && lines[lookahead].trim() === '') lookahead += 1;
            if (lookahead < lines.length && /^\d+\.\s+/.test(lines[lookahead])) {
              index = lookahead;
              break;
            }
            break;
          }
          if (
            /^(#{1,4})\s+/.test(next) ||
            next.startsWith('|') ||
            next.startsWith('```') ||
            next.startsWith('>') ||
            /^[-*]\s+/.test(next) ||
            /^\d+\.\s+/.test(next)
          ) {
            break;
          }
          item += ` ${next.trim()}`;
          index += 1;
        }
        items.push(`<li>${inline(item)}</li>`);
        while (index < lines.length && lines[index].trim() === '') index += 1;
      }
      html.push(`<ol>${items.join('')}</ol>`);
      continue;
    }

    if (line.startsWith('>')) {
      closeList();
      html.push(`<blockquote>${inline(line.replace(/^>\s?/, ''))}</blockquote>`);
      index += 1;
      continue;
    }

    if (line.trim() === '') {
      closeList();
      index += 1;
      continue;
    }

    if (/^(Status|Host|Task|Baseline|平台|任务|基线):\s+/.test(line)) {
      closeList();
      const items = [];
      while (index < lines.length && /^(Status|Host|Task|Baseline|平台|任务|基线):\s+/.test(lines[index])) {
        const [key, ...rest] = lines[index].split(':');
        items.push(`<div><dt>${escapeHtml(key.trim())}</dt><dd>${inline(rest.join(':').trim())}</dd></div>`);
        index += 1;
      }
      html.push(`<dl class="doc-meta">${items.join('')}</dl>`);
      continue;
    }

    closeList();
    // Join wrapped Markdown lines into one paragraph instead of emitting a
    // separate paragraph per physical line.
    const paragraph = [line];
    index += 1;
    while (index < lines.length) {
      const next = lines[index];
      if (
        next.trim() === '' ||
        /^(#{1,4})\s+/.test(next) ||
        next.startsWith('|') ||
        next.startsWith('```') ||
        next.startsWith('>') ||
        /^[-*]\s+/.test(next) ||
        /^\d+\.\s+/.test(next)
      ) {
        break;
      }
      paragraph.push(next.trim());
      index += 1;
    }
    html.push(`<p>${inline(paragraph.join(' '))}</p>`);
  }
  if (inCode) html.push(`<pre><code>${escapeHtml(code.join('\n'))}</code></pre>`);
  closeList();
  return { html: html.join('\n'), toc };
}

function renderToc(toc) {
  return toc
    .map(
      (item) =>
        `<a class="toc-level-${item.level}" href="#${item.id}">${escapeHtml(item.text)}</a>`,
    )
    .join('\n');
}

function renderPage(title, body, toc) {
  return `<!DOCTYPE html>
<html lang="zh-CN" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${escapeHtml(title)}</title>
<style>
:root{color-scheme:dark;--bg:#0f1115;--panel:#161a21;--line:#2a303a;--text:#e6e9ef;--muted:#9aa4b2;--accent:#7aa2f7}
html[data-theme="light"]{color-scheme:light;--bg:#f7f8fa;--panel:#fff;--line:#dde1e7;--text:#1c2027;--muted:#5b636e;--accent:#2f6feb}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
.layout{display:grid;grid-template-columns:300px minmax(0,1fr);min-height:100vh}
.sidebar{position:sticky;top:0;height:100vh;overflow-y:auto;background:var(--panel);border-right:1px solid var(--line);padding:20px 16px 40px}
.sidebar h1{font-size:15px;line-height:1.4;margin:0 0 4px;color:var(--text)}
.sidebar .meta{font-size:12px;color:var(--muted);margin:0 0 16px}
.search{width:100%;padding:7px 9px;margin-bottom:14px;background:var(--bg);border:1px solid var(--line);border-radius:6px;color:var(--text);font:inherit;font-size:13px}
.toc{display:flex;flex-direction:column;gap:2px}
.toc a{display:block;color:var(--muted);text-decoration:none;font-size:13px;padding:3px 8px;border-radius:5px;border-left:2px solid transparent}
.toc a:hover{color:var(--text);background:var(--bg)}
.toc a.active{color:var(--accent);border-left-color:var(--accent);background:var(--bg)}
.toc-level-3{padding-left:22px}
.theme{position:fixed;right:16px;bottom:16px;z-index:10;background:var(--panel);border:1px solid var(--line);color:var(--text);border-radius:999px;padding:7px 14px;cursor:pointer;font:inherit;font-size:13px}
main{padding:40px clamp(20px,4vw,64px) 96px;max-width:1080px}
h1,h2,h3,h4{line-height:1.35;margin:1.8em 0 .6em}
h1{font-size:28px;margin-top:0}
h2{font-size:22px;padding-bottom:6px;border-bottom:1px solid var(--line)}
h3{font-size:18px}
h4{font-size:16px}
p{margin:.7em 0}
a{color:var(--accent)}
code{background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:1px 5px;font:13px ui-monospace,SFMono-Regular,Menlo,monospace}
pre{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:14px 16px;overflow:auto}
pre code{background:none;border:0;padding:0;font-size:13px;line-height:1.55}
.table-wrap{overflow-x:auto;margin:1em 0}
.doc-meta{display:flex;flex-wrap:wrap;gap:6px 22px;margin:.6em 0 1.1em;font-size:13px}
.doc-meta>div{display:flex;gap:6px}
.doc-meta dt{color:var(--muted)}
.doc-meta dd{margin:0}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{border:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}
th{background:var(--panel);white-space:nowrap}
blockquote{margin:1em 0;padding:.2em 1em;border-left:3px solid var(--accent);color:var(--muted)}
ul,ol{padding-left:1.5em}
@media (max-width:860px){.layout{grid-template-columns:1fr}.sidebar{position:relative;height:auto;max-height:none}main{padding-top:20px}}
</style>
</head>
<body>
<div class="layout">
<aside class="sidebar">
<h1>${escapeHtml(title)}</h1>
<p class="meta">设计与实施计划 · 左侧固定目录</p>
<input class="search" type="search" placeholder="筛选章节…" aria-label="筛选章节">
<nav class="toc" aria-label="文档目录">
${toc}
</nav>
</aside>
<main>
${body}
</main>
</div>
<button class="theme" type="button">切换主题</button>
<script>
(()=>{
  const param=new URLSearchParams(location.search).get('theme');
  if(param==='light'||param==='dark')document.documentElement.dataset.theme=param;
  // ASCII ids (s-N) are resolved natively by the browser; no custom scroll is
  // needed and native behaviour keeps the sticky sidebar in place.
})();
const themeButton=document.querySelector('.theme');
themeButton.addEventListener('click',()=>{
  const root=document.documentElement;
  root.dataset.theme=root.dataset.theme==='dark'?'light':'dark';
});
const search=document.querySelector('.search');
search.addEventListener('input',()=>{
  const value=search.value.trim().toLowerCase();
  document.querySelectorAll('.toc a').forEach(link=>{
    link.hidden=value && !link.textContent.toLowerCase().includes(value);
  });
});
const links=[...document.querySelectorAll('.toc a')];
const targets=links.map(link=>document.getElementById(link.hash.slice(1))).filter(Boolean);
const observer=new IntersectionObserver(entries=>{
  entries.forEach(entry=>{
    if(!entry.isIntersecting)return;
    links.forEach(link=>link.classList.toggle('active',link.hash==='#'+entry.target.id));
  });
},{rootMargin:'0px 0px -70% 0px'});
targets.forEach(target=>observer.observe(target));
</script>
</body>
</html>
`;
}

async function main() {
  const markdown = await readFile(sourcePath, 'utf8');
  const title = markdown.split(/\r?\n/)[0].replace(/^#\s+/, '').trim();
  const { html, toc } = renderMarkdown(markdown);
  const page = renderPage(title, html, renderToc(toc));
  await mkdir(outputDir, { recursive: true });
  const temp = `${outputPath}.tmp`;
  await writeFile(temp, page);
  await rename(temp, outputPath);
  await rm(temp, { force: true });
  process.stdout.write(
    `${JSON.stringify({ output: outputPath, toc: toc.length, bytes: Buffer.byteLength(page) })}\n`,
  );
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exitCode = 1;
});
