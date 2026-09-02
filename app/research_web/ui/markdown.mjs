// Deliberately small Markdown subset. User/runtime content never becomes raw HTML.
export function escapeHTML(value = '') {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
}

export function safeURL(value) {
  if (typeof value !== 'string' || /[\s\\\u0000-\u001f\u007f]/.test(value)) return null;
  if (value.startsWith('/') && !value.startsWith('//')) return value;
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}

function inline(value) {
  const pattern = /(`+)([^`]+)\1|\[([^\]\n]+)\]\(([^)\s]+)\)|\*\*([^*\n]+)\*\*|\*([^*\n]+)\*/g;
  let result = ''; let start = 0;
  for (const match of value.matchAll(pattern)) {
    result += escapeHTML(value.slice(start, match.index));
    if (match[2]) result += `<code>${escapeHTML(match[2])}</code>`;
    else if (match[3]) {
      const url = safeURL(match[4]);
      result += url ? `<a href="${escapeHTML(url)}" target="_blank" rel="noopener noreferrer">${escapeHTML(match[3])}</a>` : escapeHTML(match[0]);
    } else if (match[5]) result += `<strong>${escapeHTML(match[5])}</strong>`;
    else result += `<em>${escapeHTML(match[6])}</em>`;
    start = match.index + match[0].length;
  }
  return result + escapeHTML(value.slice(start));
}

export function renderMarkdown(value = '') {
  const lines = String(value ?? '').replace(/\r\n?/g, '\n').split('\n');
  const output = []; let i = 0;
  const cells = (line) => line.trim().replace(/^\||\|$/g, '').split('|').map((cell) => inline(cell.trim()));
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    const fence = line.match(/^\s*(`{3,}|~{3,})([\w+-]*)\s*$/);
    if (fence) {
      const content = []; i++;
      while (i < lines.length && !lines[i].trim().startsWith(fence[1])) content.push(lines[i++]);
      if (i < lines.length) i++;
      output.push(`<pre><code${fence[2] ? ` class="language-${escapeHTML(fence[2])}"` : ''}>${escapeHTML(content.join('\n'))}</code></pre>`); continue;
    }
    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) { output.push(`<h${heading[1].length}>${inline(heading[2])}</h${heading[1].length}>`); i++; continue; }
    if (/^\s*([-*_])(?:\s*\1){2,}\s*$/.test(line)) { output.push('<hr>'); i++; continue; }
    if (line.includes('|') && /^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(lines[i + 1] ?? '')) {
      const header = cells(line); i += 2; const rows = [];
      while (i < lines.length && lines[i].includes('|') && lines[i].trim()) rows.push(`<tr>${cells(lines[i++]).map((cell) => `<td>${cell}</td>`).join('')}</tr>`);
      output.push(`<div class="table-scroll"><table><thead><tr>${header.map((cell) => `<th>${cell}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`); continue;
    }
    if (/^\s*([-+*]|\d+\.)\s+/.test(line)) {
      const ordered = /^\s*\d+\./.test(line); const rows = [];
      const listPattern = ordered ? /^\s*\d+\.\s+(.*)$/ : /^\s*[-+*]\s+(.*)$/;
      while (i < lines.length && listPattern.test(lines[i])) rows.push(`<li>${inline(lines[i++].replace(listPattern, '$1'))}</li>`);
      output.push(`<${ordered ? 'ol' : 'ul'}>${rows.join('')}</${ordered ? 'ol' : 'ul'}>`); continue;
    }
    if (/^>\s?/.test(line)) {
      const quotes = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) quotes.push(inline(lines[i++].replace(/^>\s?/, '')));
      output.push(`<blockquote>${quotes.join('<br>')}</blockquote>`); continue;
    }
    const paragraph = [inline(line)]; i++;
    while (i < lines.length && lines[i].trim() && !/^(?:#{1,6}\s|\s*(?:`{3,}|~{3,}|[-+*]\s|\d+\.\s)|>)/.test(lines[i]) && !(lines[i].includes('|') && /---/.test(lines[i + 1] ?? ''))) paragraph.push(inline(lines[i++]));
    output.push(`<p>${paragraph.join('<br>')}</p>`);
  }
  return output.join('\n');
}
