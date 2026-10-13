/** Claw projections: one project index, one Automation directory, explicit references. */
import { escapeHTML as e } from './markdown.mjs';
import { sessionHash } from './core.mjs';

export function renderClawNavigation(current = 'sessions', sessionId = null, projectId = 'default') {
  return `<nav class="claw-navigation" aria-label="Claw 工作入口">${[['sessions','会话'],['projects','项目工作区'],['plans','Agent 日程'],['skills','技能与连接']].map(([view,label]) => `<a href="#/claw?view=${view}${view === 'projects' ? `&project=${encodeURIComponent(projectId)}` : ''}${sessionId ? `&session=${encodeURIComponent(sessionId)}` : ''}" ${view === current ? 'aria-current="page"' : ''}>${label}</a>`).join('')}</nav>`;
}

export const clawNavigationCurrent = (expected, current) => expected === current;

export function renderClawProject({ projects = [], detail = null, busy = false, error = '', newName = '', targetSession = '', renameEdits = new Map() } = {}) {
  const options = projects.map(p => `<option value="${e(p.id)}" ${p.id === detail?.id ? 'selected' : ''}>${e(p.name)}${p.archived ? ' · 已归档' : ''}</option>`).join('');
  const sessions = detail?.sessions || [];
  const projectOptions = projects.filter(p => !p.archived).map(p => `<option value="${e(p.id)}" ${p.id === detail?.id ? 'selected' : ''}>${e(p.name)}</option>`).join('');
  const disabled = busy ? 'disabled' : '';
  return `<section class="claw-project-page"><header class="page-header"><div><h1>项目工作区</h1><p class="muted">按研究项目组织会话、资料与产物。引用文件必须显式选择接收会话。</p></div></header>${error ? `<p class="notice danger" role="alert">${e(error)}</p>` : ''}<div class="claw-project-toolbar"><label>项目<select data-claw-project-select ${disabled}>${options}</select></label><button class="button" type="button" data-claw-project-refresh ${disabled}>刷新</button><form data-claw-project-create><label>新项目名称<input name="name" value="${e(newName)}" maxlength="120" required ${disabled}></label><button class="button" ${disabled}>创建项目</button></form></div>${!detail ? '<p role="status">正在读取项目…</p>' : `<h2>${e(detail.name)}${detail.archived ? ' · 已归档' : ''}</h2>${detail.id !== 'default' ? `<form data-claw-project-update="${e(detail.id)}"><label>项目名称<input name="name" id="claw-project-name" value="${e(renameEdits.get(detail.id) ?? detail.name)}" maxlength="120" required ${disabled}></label><button class="button" ${disabled}>改名</button><button type="button" class="button" data-claw-project-archive="${e(detail.id)}" data-archived="${detail.archived ? 'false' : 'true'}" ${disabled}>${detail.archived ? '恢复项目' : '归档项目'}</button></form>` : ''}${!detail.archived ? `<button type="button" class="button primary" data-claw-new-session="${e(detail.id)}" ${disabled}>在项目中新建研究</button>` : ''}<h3>研究会话</h3><div class="claw-project-sessions">${sessions.length ? sessions.map(s => `<article><a href="${sessionHash(s)}">${e(s.title)}</a><label>移入项目<select data-claw-session-project="${e(s.id)}" ${disabled}><option value="">选择项目</option>${projectOptions}</select></label></article>`).join('') : '<p class="muted">项目内尚无会话。</p>'}</div><h3>资料与产物</h3><label>显式引用到<select data-claw-reference-target ${disabled}><option value="">选择接收会话</option>${sessions.map(s => `<option value="${e(s.id)}" ${s.id === targetSession ? 'selected' : ''}>${e(s.title)}</option>`).join('')}</select></label><div class="claw-project-files">${(detail.files || []).map(f => `<article><div><strong>${e(f.name)}</strong><small>来源：${e(f.session_title)} · ${f.kind === 'outputs' ? '产物' : '资料'}</small></div><div class="button-row"><a class="button small" href="${e(f.preview_url)}" target="_blank" rel="noopener">预览</a><a class="button small" href="${e(f.url)}">下载</a>${!detail.archived ? `<button type="button" class="button small" data-claw-reference="${e(f.id)}" data-source-session="${e(f.session_id)}" data-sha256="${e(f.sha256)}" ${disabled}>引用到草稿</button>` : ''}</div></article>`).join('') || '<p class="muted">尚无可用文件。</p>'}</div><h3>数据资料快照</h3>${(detail.datasets || []).map(d => `<p><a href="#/claw?session=${encodeURIComponent(d.session_id)}">${e(d.name || d.dataset_id)} · ${e(d.session_title)}</a></p>`).join('') || '<p class="muted">尚无数据资料；查看来源会话不会自动载入其他会话。</p>'}`}</section>`;
}

export function automationDraftBody(locked, values) {
  const body = structuredClone(locked);
  body.name = String(values.get('name') || '');
  body.input_template = String(values.get('input_template') || '');
  const kind = String(values.get('kind') || '');
  body.schedule = { kind, timezone: String(values.get('timezone') || '') };
  if (kind === 'once') body.schedule.once_at = String(values.get('once_at') || '');
  else {
    const time = String(values.get('time') || '').split(':');
    if (time.length !== 2 || time.some(v => !/^\d{2}$/.test(v))) throw new Error('请填写有效执行时间。');
    body.schedule.hour = Number(time[0]); body.schedule.minute = Number(time[1]);
    if (kind === 'weekly') body.schedule.weekday = Number(values.get('weekday'));
    if (kind === 'monthly') body.schedule.day = Number(values.get('day'));
  }
  return body;
}

export function renderAutomationDrafts(drafts = [], edits = new Map(), busy = false) {
  const proposed = drafts.filter(d => d.status === 'proposed');
  if (!proposed.length) return '';
  return `<section class="claw-automation-drafts" aria-label="待确认日程"><h2>待确认日程</h2><p class="muted">保存后默认停用；在 Agent 日程中另行启用才会自动执行。</p>${proposed.map(d => {
    const b = d.body; const s = b.schedule; const values = edits.get(d.id) || {};
    const value = (name, fallback) => e(values[name] ?? fallback ?? '');
    return `<form data-claw-draft-form="${e(d.id)}"><p>锁定能力：${e(b.target_id)} · v${e(b.target_version)}</p><div class="automation-form-grid"><label>任务名称<input id="claw-draft-${e(d.id)}-name" name="name" value="${value('name',b.name)}" required maxlength="160"></label><label>日程<select id="claw-draft-${e(d.id)}-kind" name="kind">${[['once','一次'],['daily','每日'],['weekly','每周'],['monthly','每月']].map(([k,l])=>`<option value="${k}" ${(values.kind || s.kind) === k ? 'selected' : ''}>${l}</option>`).join('')}</select></label><label>时区<input id="claw-draft-${e(d.id)}-timezone" name="timezone" value="${value('timezone',s.timezone)}" required></label><label>执行时间<input id="claw-draft-${e(d.id)}-time" name="time" type="time" value="${value('time',`${String(s.hour ?? 9).padStart(2,'0')}:${String(s.minute ?? 0).padStart(2,'0')}`)}"></label><label>周几（0=周一）<input id="claw-draft-${e(d.id)}-weekday" name="weekday" type="number" min="0" max="6" value="${value('weekday',s.weekday ?? 0)}"></label><label>每月日期<input id="claw-draft-${e(d.id)}-day" name="day" type="number" min="1" max="31" value="${value('day',s.day ?? 1)}"></label><label>一次执行时间<input id="claw-draft-${e(d.id)}-once_at" name="once_at" value="${value('once_at',s.once_at)}" placeholder="带时区的 ISO 时间"></label><label class="span-all">研究目标<textarea id="claw-draft-${e(d.id)}-input_template" name="input_template" required maxlength="100000">${value('input_template',b.input_template)}</textarea></label></div><div class="button-row"><button class="button primary" ${busy ? 'disabled' : ''}>确认保存</button><button type="button" class="button" data-claw-draft-dismiss="${e(d.id)}" ${busy ? 'disabled' : ''}>取消草稿</button></div></form>`;
  }).join('')}</section>`;
}

export function renderClawConnections(capabilities = [], tools = []) {
  return `<section><h1>技能与连接</h1><p class="muted">使用既有能力与连接目录；启用、配置和会话授权分别管理。</p><div class="button-row"><a class="button" href="#/skills?kind=skill">Skill 能力库</a><a class="button" href="#/skills?kind=workflow">Workflow</a><a class="button" href="#/skills?kind=tool&view=market">MCP 市场与安装</a><a class="button" href="#/skills?kind=tool&view=connections">连接状态</a><a class="button" href="#/settings/data">数据源配置</a></div><h2>研究能力</h2><div class="claw-project-files">${capabilities.filter(c => ['skill','workflow'].includes(c.kind)).map(c=>`<article><div><strong>${e(c.name)}</strong><small>${e(c.description || '')}</small></div><span class="badge">${c.enabled ? '已启用' : '不可执行'}</span><a class="button small" href="#/skills?kind=${c.kind}">查看与选择</a></article>`).join('') || '<p class="muted">当前能力目录为空，请刷新。</p>'}</div><p class="muted">当前目录包含 ${tools.length} 个工具声明；声明不代表可调用。</p></section>`;
}
