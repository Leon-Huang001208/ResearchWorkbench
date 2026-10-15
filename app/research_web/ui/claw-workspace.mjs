/** Claw projections: one project index, one Automation directory, explicit references. */
import { escapeHTML as e, renderMarkdown } from './markdown.mjs';
import { sessionHash, safeLog } from './core.mjs';
import { fileURL, renderActivityCard, activitySummary } from './views.mjs';

export function renderClawNavigation(current = 'sessions', sessionId = null, projectId = 'default') {
  return `<nav class="claw-navigation" aria-label="Claw 工作入口">${[['sessions','会话'],['projects','项目工作区'],['plans','Agent 日程'],['skills','选择能力']].map(([view,label]) => `<a href="#/claw?view=${view}${view === 'projects' ? `&project=${encodeURIComponent(projectId)}` : ''}${sessionId ? `&session=${encodeURIComponent(sessionId)}` : ''}" ${view === current ? 'aria-current="page"' : ''}>${label}</a>`).join('')}</nav>`;
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
    if (kind === 'weekly') {
      const raw = typeof values.getAll === 'function' ? values.getAll('weekdays') : [values.get('weekdays')].filter(v => v != null);
      const days = raw.flatMap(v => String(v).split(',')).filter(v => v.trim() !== '').map(Number);
      if (!days.length && values.get('weekdays_present')) throw new Error('请至少选择一个执行日。');
      if (days.length) {
        if (days.some(v => !Number.isInteger(v) || v < 0 || v > 6)) throw new Error('请选择有效执行日。');
        body.schedule.weekdays = [...new Set(days)].sort((a,b) => a-b);
      } else if (values.get('weekday') != null) body.schedule.weekday = Number(values.get('weekday'));
      else if (locked.schedule?.weekdays?.length) body.schedule.weekdays = [...locked.schedule.weekdays];
      else if (locked.schedule?.weekday != null) body.schedule.weekday = locked.schedule.weekday;
      else throw new Error('请至少选择一个执行日。');
    }
    if (kind === 'monthly') body.schedule.day = Number(values.get('day'));
  }
  if (body.research_task) body.research_task.description = body.input_template;
  return body;
}

export function captureAutomationDraftEdits(values, previous = {}) {
  const next = { ...previous, ...Object.fromEntries(values) };
  if (values.get('weekdays_present')) next.weekdays = values.getAll('weekdays');
  return next;
}

const dayNames = ['周一','周二','周三','周四','周五','周六','周日'];
export function clawScheduleLabel(schedule = {}) {
  const clock = `${String(schedule.hour ?? 0).padStart(2,'0')}:${String(schedule.minute ?? 0).padStart(2,'0')}`;
  if (schedule.kind === 'once') return schedule.once_at || '时间未知';
  const days = schedule.weekdays?.length ? schedule.weekdays : [schedule.weekday ?? 0];
  return `${schedule.kind === 'weekly' ? days.map(d => dayNames[d] || '未知执行日').join('、') : schedule.kind === 'monthly' ? `每月 ${schedule.day} 日` : '每日'} ${clock} · ${schedule.timezone || '时区未知'}`;
}
const runState = value => ({completed:'研究完成',running:'研究中',queued:'待执行',pending:'待执行',failed:'研究失败',interrupted:'已中断',blocked_version:'版本受限'})[value] || value || '未执行';
const dateLabel = (value, timezone = 'UTC') => {
  if (!value) return '尚未安排';
  const date = new Date(typeof value === 'number' && value < 1e12 ? value * 1000 : value);
  if (Number.isNaN(date.getTime())) return '时间未知';
  try { return `${date.toLocaleString('zh-CN', { timeZone: timezone, hour12: false })} · ${timezone}`; }
  catch { safeLog('claw_schedule_timezone_invalid'); return '时间与时区无法验证'; }
};
export function renderClawSchedules(automations = [], runs = [], busy = false, error = '') {
  return `<section class="claw-schedules"><header class="page-header"><div><h1>Agent 日程</h1><p class="muted">在对话中提出任务、澄清参数并确认创建。每周执行日不是交易日历，节假日仍按所选星期运行。</p></div><div class="button-row"><button class="button" data-claw-schedule-refresh${busy ? ' disabled' : ''}>刷新日程与运行</button><button class="button primary" data-claw-case="schedule">新建任务</button></div></header>${error ? `<p class="notice danger" role="alert">${e(error)}</p>` : ''}<div class="claw-table-scroll"><table><thead><tr><th>任务名称</th><th>模型与版本</th><th>执行时间</th><th>下次执行</th><th>状态</th><th>操作</th></tr></thead><tbody>${automations.map(a=>`<tr><td><strong>${e(a.name)}</strong><details><summary>研究内容</summary><p>${e(a.research_task?.description || a.input_template || '')}</p></details></td><td>${e(a.research_task?.model_id || a.target?.id || '既有能力')}<small>v${e(a.definition_version || a.target?.version || '—')}</small></td><td>${e(clawScheduleLabel(a.schedule))}</td><td>${e(dateLabel(a.next_run_at,a.schedule?.timezone || 'UTC'))}</td><td>${a.enabled ? '已启用' : '已停用'}</td><td><div class="button-row"><button class="button small" data-run-automation="${e(a.id)}" ${busy?'disabled':''}>试跑</button><button class="button small" data-claw-edit-task="${e(a.id)}" ${busy?'disabled':''}>在对话中修改</button><button class="button small" data-${a.enabled?'disable':'enable'}-automation="${e(a.id)}" ${busy?'disabled':''}>${a.enabled?'停用':'启用'}</button><button class="button small" data-delete-automation="${e(a.id)}" ${busy?'disabled':''}>删除</button></div></td></tr>`).join('') || '<tr><td colspan="6">暂无任务。先在会话中说明研究内容和时间。</td></tr>'}</tbody></table></div><h2>执行记录</h2>${renderClawRunCards(runs)}</section>`;
}
export function positionClawAutomationCards(detail, edits = new Map(), busy = false) {
  const entries = []; const unpositionedDrafts = []; const unpositionedRuns = [];
  const activities = (detail.activities || []).filter(activity=>Number.isFinite(activity.seq) && activity.status === 'completed' && activity.result && typeof activity.result === 'object' && !Array.isArray(activity.result));
  const anchor = (row,tools,requireTask) => {
    const matches=activities.filter(activity=>tools.includes(activity.tool || activity.title) && activity.result.id === row.id && (!requireTask || activity.arguments?.automation_id === row.automation_id));
    return matches.length === 1 ? matches[0].seq : null;
  };
  for (const draft of detail.automation_drafts || []) {
    const update=draft.operation === 'update' || draft.action === 'update';
    const seq=anchor(draft,[update ? 'rwb_prepare_automation_update' : 'rwb_prepare_automation'],update);
    const html=renderAutomationDrafts([draft],edits,busy);
    if (!html) continue;
    if (seq === null) unpositionedDrafts.push(draft); else entries.push({seq,html});
  }
  for (const run of detail.automation_runs || []) {
    const seq=anchor(run,['rwb_run_automation'],true);
    if (seq === null) unpositionedRuns.push(run); else entries.push({seq,html:renderClawRunCards([run])});
  }
  return {entries,unpositionedDrafts,unpositionedRuns};
}

export function renderClawRunCards(runs = []) {
  if (!runs.length) return '<p class="muted">尚无执行记录。</p>';
  return `<section class="claw-run-cards" aria-label="日程运行记录">${runs.map(r=>`<article class="claw-run-card"><header><strong>${e(r.automation_name || r.name || r.definition_snapshot?.name || '研究任务')}</strong><span class="badge">${({schedule:'定时运行',scheduled:'定时运行',manual:'手动试跑',retry:'手动重试'})[r.trigger] || '运行来源未知'}</span><span>${e(runState(r.research_status))}</span></header><p class="muted small">来源：Automation ${e(r.automation_id)} · 定义 v${e(r.definition_version || '—')} · ${e(dateLabel(r.created_at,r.definition_snapshot?.schedule?.timezone || 'UTC'))}</p>${r.failure_code ? `<p class="notice danger">${e(r.failure_code)}</p>` : ''}${r.result_error ? `<p class="notice warning" role="status">结果受限：${e(r.result_error)}</p>` : ''}${r.result_text ? `<details><summary>运行结果</summary><div class="markdown claw-run-result">${renderMarkdown(r.result_text)}</div></details>` : ''}${r.activities?.length ? `<details><summary>${e(activitySummary(r.activities))}</summary><ol class="activity-list">${r.activities.map(a=>`<li>${renderActivityCard(a,[],{compact:true})}</li>`).join('')}</ol></details>` : ''}${r.files?.length ? `<details><summary>文件（${r.files.length}）</summary><p class="muted small">来源：执行会话 ${e(r.session_id || '尚未关联')} · 定义 v${e(r.definition_version || '—')}</p>${r.files.map(f=>fileURL(f.url) ? `<p><a href="${e(fileURL(f.url))}">${e(f.name || f.id)}</a></p>` : `<p>${e(f.name || f.id)}</p>`).join('')}</details>` : ''}${(r.files || []).map(f=>{ const preview=fileURL(f.preview_url); return /\.md$/i.test(f.name || '') && r.session_id && preview?.startsWith(`/api/research/sessions/${encodeURIComponent(r.session_id)}/files/`) && preview.split('?')[0].endsWith('/preview') ? `<details class="claw-inline-report"><summary>完整报告 · ${e(f.name)}</summary><p class="muted small">来源：执行会话 ${e(r.session_id)} · 定义 v${e(r.definition_version || '—')}</p><iframe title="${e(f.name)} 完整报告" src="${e(preview)}" sandbox="" referrerpolicy="no-referrer" loading="lazy"></iframe></details>` : ''; }).join('')}${r.session_id ? `<a class="button small" href="#/claw?session=${encodeURIComponent(r.session_id)}">查看执行会话与文件</a>` : '<p class="muted small">执行会话尚未关联。</p>'}</article>`).join('')}</section>`;
}
function renderDraftSchedule(schedule, values, id) {
  const kind = values.kind || schedule.kind;
  const value = (name, fallback) => e(values[name] ?? fallback ?? '');
  if (kind === 'once') return `<label>执行日期与时间<input id="claw-draft-${e(id)}-once_at" name="once_at" value="${value('once_at',schedule.once_at)}" placeholder="例如：2026-10-15T15:30:00+08:00" required></label>`;
  const time = `<label>执行时间<input id="claw-draft-${e(id)}-time" name="time" type="time" value="${value('time',`${String(schedule.hour ?? 9).padStart(2,'0')}:${String(schedule.minute ?? 0).padStart(2,'0')}`)}" required></label>`;
  if (kind === 'monthly') return time + `<label>每月日期<input id="claw-draft-${e(id)}-day" name="day" type="number" min="1" max="31" value="${value('day',schedule.day ?? 1)}" required></label>`;
  if (kind !== 'weekly') return time;
  const selected = Array.isArray(values.weekdays) ? values.weekdays.map(Number) : values.weekdays != null ? String(values.weekdays).split(',').filter(Boolean).map(Number) : schedule.weekdays?.length ? schedule.weekdays : schedule.weekday != null ? [schedule.weekday] : [];
  return time + `<fieldset class="claw-weekdays"><legend>执行日</legend><input type="hidden" name="weekdays_present" value="1">${dayNames.map((name,index)=>`<label><input type="checkbox" name="weekdays" value="${index}" ${selected.includes(index)?'checked':''}>${name}</label>`).join('')}</fieldset>`;
}
export function renderAutomationDrafts(drafts = [], edits = new Map(), busy = false) {
  const receipts=drafts.filter(d=>d.status === 'confirmed' && !d.enable_error).map(d=>{
    const definition=d.confirmed_definition || {};const task=definition.research_task || {};
    const version=Number.isInteger(definition.definition_version) && definition.definition_version > 0 ? `定义 v${definition.definition_version}` : '版本未知';
    const enabled=d.confirmed_enabled === true ? '已保存 · 已启用' : d.confirmed_enabled === false ? '已保存 · 已停用' : '状态未记录';
    return `<article class="claw-confirm-receipt" aria-label="日程确认回执"><header><h3>日程确认回执</h3><strong>${e(definition.name || '已确认日程')} · ${e(version)}</strong></header><p class="muted small">来源：产品日程保存记录 · 任务 ${e(d.automation_id || definition.id || '标识未提供')}</p><p>当时保存/启用状态：${enabled}。当前状态请查看 Agent 日程。</p><p class="muted small">确认时间：${e(d.confirmed_at ? dateLabel(d.confirmed_at,definition.schedule?.timezone || 'UTC') : '未记录')}</p>${task.description || definition.input_template ? `<p>${e(task.description || definition.input_template)}</p>` : '<p class="muted small">旧记录未保存确认定义快照。</p>'}${definition.schedule ? `<p>${e(clawScheduleLabel(definition.schedule))}</p>` : ''}<dl class="claw-confirm-scope"><div><dt>模型</dt><dd>${e(task.model_id ? `${task.model_provider || ''} / ${task.model_id}` : '未记录')}</dd></div><div><dt>输出</dt><dd>${e(task.output_requirements || (definition.output_formats || []).join('、') || '未记录')}</dd></div></dl><p class="small">创建或更新不会立即运行。${definition.name ? `如需试跑，请明确发送“先跑一次${e(definition.name)}”。` : '如需试跑，请在 Agent 日程选择已确认的任务。'}</p><a class="button small" href="#/claw?view=plans">查看 Agent 日程</a></article>`;
  }).join('');
  const proposed = drafts.filter(d => d.status === 'proposed' || (d.status === 'confirmed' && d.enable_error));
  if (!proposed.length) return receipts;
  return `${receipts}<section class="claw-automation-drafts" aria-label="待确认日程"><h2>待确认日程</h2>${proposed.map(d => {
    const b = d.body || {}; const s = b.schedule || d.previous_definition?.schedule || {}; const values = edits.get(d.id) || {};
    const research = b.target_kind === 'research_task' || Boolean(b.research_task) || Boolean(d.previous_definition?.research_task);
    const update = d.operation === 'update' || d.action === 'update';
    const retry = d.status === 'confirmed' && Boolean(d.enable_error);
    const value = (name, fallback) => e(values[name] ?? fallback ?? '');
    const task = b.research_task || d.previous_definition?.research_task || {};
    return `<form data-claw-draft-form="${e(d.id)}"><header><h3>${update ? '确认变更' : '确认创建'}</h3>${update ? `<p>同一任务 ${e(d.automation_id)} · 预期版本 v${e(b.expected_version ?? d.expected_version)}；确认后保存新定义版本，历史运行保留原快照。</p>` : ''}</header><p class="muted">${update ? '确认后更新同一任务，保留启用状态，不立即运行。' : research ? '确认创建并启用后按日程执行；创建成功不会立即运行。' : '既有能力任务保存后默认停用；请在日程页显式启用。'}</p>${d.enable_error ? `<p class="notice warning">任务已创建但启用失败：${e(d.enable_error)}。重试只启用同一任务。</p>` : ''}<dl class="claw-confirm-scope"><div><dt>模型</dt><dd>${e(task.model_id ? `${task.model_provider ? task.model_provider + ' / ' : ''}${task.model_id}` : task.model || '沿用既有模型')}</dd></div><div><dt>权限</dt><dd>数据：${e((task.approved_data_sources || task.approved_scope?.data || []).join('、') || '未选择')}；工具：${e((task.approved_tools || task.approved_scope?.tools || []).join('、') || '无额外工具')}</dd></div><div><dt>输出</dt><dd>${e(task.output_requirements || (b.output_formats || task.expected_formats || []).join('、') || '文本')}</dd></div></dl>${!research ? `<p>锁定能力：${e(b.target_id)} · v${e(b.target_version)}</p>` : ''}${retry ? `<section class="claw-enable-retry-definition" aria-label="已保存定义，只重试启用"><h4>${e(b.name)}</h4><p>${e(task.description || b.input_template || '')}</p><p>${e(clawScheduleLabel(s))}</p><p class="muted small">任务 ${e(d.automation_id)} 已保存。本次只重试启用，不修改内容、模型、权限或日程。</p></section>` : update ? `<section class="claw-update-diff" aria-label="定义变更确认"><h4>变更前</h4><p>${e(d.previous_definition?.name || '')}</p><p>${e(d.previous_definition?.research_task?.description || d.previous_definition?.input_template || '')}</p><h4>变更后</h4><p>${e(b.name || d.previous_definition?.name || '')}</p><p>${e(b.research_task?.description || b.input_template || d.previous_definition?.research_task?.description || '')}</p><p>执行时间：${e(clawScheduleLabel(s))}${b.schedule ? '（请求变更）' : '（保持原定义）'}</p><p>模型与权限：${b.research_task ? '以本卡展示的待确认定义为准' : '保持原定义'}</p></section>` : `<div class="automation-form-grid"><label>任务名称<input id="claw-draft-${e(d.id)}-name" name="name" value="${value('name',b.name)}" required maxlength="160"></label><label>日程<select name="kind">${[['once','一次'],['daily','每日'],['weekly','每周'],['monthly','每月']].map(([k,l])=>`<option value="${k}" ${(values.kind || s.kind) === k ? 'selected' : ''}>${l}</option>`).join('')}</select></label><label>时区<input name="timezone" value="${value('timezone',s.timezone)}" required></label>${renderDraftSchedule(s,values,d.id)}<label class="span-all">研究目标<textarea id="claw-draft-${e(d.id)}-input_template" name="input_template" required maxlength="100000">${value('input_template',task.description || b.input_template)}</textarea></label></div>`}<div class="button-row"><button class="button primary" ${busy?'disabled':''}>${d.enable_error ? '重试启用' : update ? '确认更新同一任务' : research ? '确认创建并启用' : '确认保存'}</button>${retry ? '<a class="button" href="#/claw?view=plans">查看已保存任务</a>' : `<button type="button" class="button" data-claw-draft-dismiss="${e(d.id)}" ${busy?'disabled':''}>取消草稿</button>`}</div></form>`;
  }).join('')}</section>`;
}
export function renderClawConnections(capabilities = []) {
  return `<section class="claw-capability-picker"><header class="page-header"><div><h1>选择能力</h1><p class="muted">选择只放入研究草稿。能力与连接由能力中心统一管理。</p></div><a class="button" href="#/skills">管理能力与连接 · 能力中心</a></header><div class="claw-project-files">${capabilities.filter(c => ['skill','workflow'].includes(c.kind)).map(c=>`<article><div><strong>${e(c.name)}</strong><small>${e(c.description || '')}</small></div><button class="button small" data-skill-shortcut="${e(c.id)}" ${!c.enabled?'disabled':''}>选择能力</button></article>`).join('') || '<p class="muted">当前没有可选能力。</p>'}</div></section>`;
}
export const clawCases = [
  {id:'schedule',category:'agent',name:'每日收盘点评',text:'帮我创建定时任务：每日收盘点评。请先澄清研究内容、模型、执行时间、时区与数据范围，提出待确认日程。'},
  {id:'watchlist',category:'research',name:'跟踪自选股动态',text:'请研究我提供的自选股近期公告与新闻，区分已核实来源与缺失数据，交付带来源的报告。'},
  {id:'industry',category:'research',name:'研究行业与公司',text:'请先确认研究对象、时间范围与资料来源，再分析行业变化和公司影响，交付可核查的研究报告。'},
  {id:'documents',category:'research',name:'从资料到报告',text:'请基于我显式上传的资料提炼关键事实、冲突与待核实项，形成有来源的研究报告。'},
  {id:'skill',category:'capability',name:'选择研究能力',text:'请帮助我选择适合研究目标的现有能力，并说明所需资料和输出。'},
  {id:'review',category:'agent',name:'定期复核研究结论',text:'帮我设计定期复核研究结论的日程。先澄清频次、数据和工具范围，确认后再创建。'},
];
export function renderClawCases(category = '') {
  const items=clawCases.filter(c=>!category || category==='all' || c.category===category);
  return `<section class="claw-cases" aria-label="研究案例草稿"><div class="claw-case-categories">${[['','全部'],['research','研究实战'],['agent','Agent 日程'],['capability','能力使用']].map(([id,name])=>`<button class="text-button ${category===id?'active':''}" data-claw-case-category="${id}" aria-pressed="${category===id}">${name}</button>`).join('')}</div><div class="claw-case-grid">${items.map(c=>`<button class="claw-case-card" data-claw-case="${c.id}"><strong>${c.name}</strong><span>${e(c.text)}</span></button>`).join('')}</div></section>`;
}
