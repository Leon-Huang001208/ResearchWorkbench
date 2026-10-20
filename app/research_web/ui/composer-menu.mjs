import { escapeHTML as e } from './markdown.mjs';
import { icon } from './icons.mjs';
import { modelGroups } from './views.mjs';
import { reportWorkflowEligibility } from './capabilities.mjs';

const commands = [
  ['upload', '添加附件', 'PDF、图片、Markdown、Office 文件', 'folder'],
  ['capabilities', '能力', '选择 Skill 或 Workflow', 'grid'],
  ['methods', '思考方法', '最多选择三个', 'sliders'],
  ['formats', '输出格式', '自动、文件格式或仅聊天', 'document'],
  ['models', '模型', '选择新研究使用的模型', 'layers'],
];
const titles = { root: '命令', capabilities: '能力', methods: '思考方法', formats: '输出格式', models: '模型' };
export const closedComposerMenu = () => ({ entry: '', view: 'root', query: '', index: 0 });
export function openComposerMenu(entry = 'add', view = 'root', query = '') {
  return { entry, view, query, index: 0 };
}
// Only the first line is a command query. Subsequent lines remain ordinary draft text.
export function composerSlashQuery(draft) {
  const match = String(draft ?? '').match(/^[\t ]*\/([^\r\n]*)/u);
  return match ? match[1] : null;
}
export function consumeComposerSlash(draft) {
  return String(draft ?? '').replace(/^[\t ]*\/[^\r\n]*(?:\r?\n)?/u, '');
}
const matches = (row, query) => `${row.label} ${row.description || ''} ${row.search || ''}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase());
export function composerMenuRows(menu, context = {}) {
  const { skills = [], methods = [], methodIds = [], expectedFormats = null, models = [], model = '', modelProvider = '', modelEndpoint = '', disabled = false, busy = false, uploadsAllowed = true } = context;
  const commandRows = commands.filter(([key]) => menu.entry === 'slash' || key !== 'models').map(([key, label, description, glyph]) => ({ key, label, description, glyph, action: key === 'upload' ? 'upload' : 'view', value: key, search: key, group: menu.query.trim() ? '操作' : '', disabled: disabled || (key === 'upload' && (!uploadsAllowed || busy)) }));
  const capabilityRows = (Array.isArray(skills) ? skills : []).filter(item => {
    if (!item || item.kind && !['skill', 'workflow'].includes(item.kind)) return false;
    const report = reportWorkflowEligibility(item);
    return report.report ? report.eligible : item.enabled !== false;
  }).map(item => ({ key: `cap:${item.id}`, action: 'capability', value: item.id, label: item.name || item.id, description: item.description || '', search: item.id, glyph: 'grid', group: item.kind === 'workflow' ? 'Workflow' : 'Skill', disabled: disabled || busy || !item.version && !reportWorkflowEligibility(item).report })).sort((a, b) => a.group.localeCompare(b.group));
  let rows;
  if (menu.view === 'root') rows = [...commandRows, ...(menu.entry === 'slash' && menu.query.trim() ? capabilityRows : [])];
  else if (menu.view === 'capabilities') rows = capabilityRows;
  else if (menu.view === 'methods') rows = (Array.isArray(methods) ? methods : []).filter(item => item?.enabled && item.version).map(item => ({ key: `method:${item.id}`, action: 'method', value: item.id, label: item.name || item.id, description: item.description || `v${item.version}`, glyph: 'sliders', checked: methodIds.includes(item.id), disabled: disabled || busy || !methodIds.includes(item.id) && methodIds.length >= 3 }));
  else if (menu.view === 'formats') rows = [
    { key: 'auto', action: 'format', value: 'auto', label: '按 Skill 默认格式', description: '自动', checked: expectedFormats === null },
    ...['md', 'html', 'docx', 'pdf', 'xlsx', 'png'].map(format => ({ key: format, action: 'format', value: format, label: format.toUpperCase(), checked: Array.isArray(expectedFormats) && expectedFormats.includes(format) })),
    { key: 'none', action: 'format', value: 'none', label: '仅聊天，无需文件', checked: Array.isArray(expectedFormats) && !expectedFormats.length },
  ].map(row => ({ ...row, glyph: 'document', disabled: disabled || busy }));
  else if (menu.view === 'models') rows = modelGroups(models, modelEndpoint).flatMap(group => (group.models || []).map(item => ({ key: `model:${group.provider}:${item.id}`, action: 'model', value: JSON.stringify({ provider: group.provider, model: item.id }), label: item.name || item.id, description: '仅影响新研究，当前会话保持原模型', glyph: 'layers', group: group.provider, checked: item.id === model && (!modelProvider || modelProvider === group.provider), disabled: disabled || busy })));
  else rows = [];
  return rows.filter(row => matches(row, menu.query));
}
export function composerMenuKey(key, index, rows) {
  if (key === 'Escape') return { handled: true, back: true };
  const enabled = rows.map((row, i) => row.disabled ? -1 : i).filter(i => i >= 0);
  if (key === 'Enter') return { handled: true, select: rows[index] && !rows[index].disabled ? rows[index] : null };
  if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(key)) return { handled: false };
  if (!enabled.length) return { handled: true, index: 0 };
  if (key === 'Home') return { handled: true, index: enabled[0] };
  if (key === 'End') return { handled: true, index: enabled.at(-1) };
  const position = enabled.indexOf(index);
  if (position < 0) return { handled: true, index: key === 'ArrowUp' ? enabled.at(-1) : enabled[0] };
  return { handled: true, index: enabled[(position + (key === 'ArrowDown' ? 1 : -1) + enabled.length) % enabled.length] };
}
export function nextComposerFormats(current, value) {
  if (value === 'auto') return null;
  if (value === 'none') return [];
  const selected = Array.isArray(current) ? current : [];
  return selected.includes(value) ? selected.filter(item => item !== value) : [...selected, value];
}
export function renderComposerMenu(menu, context = {}) {
  if (!menu?.entry) return '';
  const rows = composerMenuRows(menu, context);
  const multi = ['methods', 'formats'].includes(menu.view);
  let group;
  const items = rows.map((row, index) => {
    const heading = row.group && row.group !== group ? `<div class="composer-command-group" role="presentation">${e(row.group)}</div>` : '';
    group = row.group;
    const role = multi ? 'menuitemcheckbox' : row.action === 'model' ? 'menuitemradio' : 'menuitem';
    return `${heading}<button id="composer-command-${index}" type="button" role="${role}" ${'checked' in row ? `aria-checked="${row.checked}"` : ''} class="composer-command-row${index === menu.index ? ' is-active' : ''}" data-cm-row="${index}" ${row.disabled ? 'disabled' : ''}>${icon(row.glyph)}<span class="composer-command-label">${e(row.label)}</span>${row.description ? `<span class="composer-command-description">${e(row.description)}</span>` : ''}${row.action === 'view' ? icon('chevronRight') : row.checked ? icon('check') : ''}</button>`;
  }).join('');
  return `<section id="claw-composer-menu" class="composer-command-panel" tabindex="-1" aria-label="${e(titles[menu.view] || '添加')}"><div class="composer-command-heading">${menu.view !== 'root' ? `<button id="composer-command-back" type="button" data-cm-back aria-label="返回上一级">${icon('chevronLeft')}返回</button>` : ''}<span>${menu.view === 'root' && menu.entry === 'add' ? '添加' : titles[menu.view]}${menu.view === 'methods' ? ` ${context.methodIds?.length || 0}/3` : ''}</span>${multi ? '<button id="composer-command-done" type="button" data-cm-done>完成</button>' : ''}</div>${menu.view !== 'root' ? `<input id="composer-command-search" type="search" autocomplete="off" aria-label="搜索${e(titles[menu.view])}" placeholder="搜索${e(titles[menu.view])}…" value="${e(menu.query)}" role="combobox" aria-expanded="true" aria-autocomplete="list" aria-controls="composer-command-options"${rows[menu.index] ? ` aria-activedescendant="composer-command-${menu.index}"` : ''}>` : ''}<div id="composer-command-options" class="composer-command-options" role="menu" aria-label="${e(titles[menu.view])}">${items || '<p class="composer-command-empty" role="status">没有匹配的可用选项</p>'}</div></section>`;
}
