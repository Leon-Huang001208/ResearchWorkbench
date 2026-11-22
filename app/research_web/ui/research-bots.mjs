import { escapeHTML as e } from './markdown.mjs';

const avatars = {
  cow: '🐮', cat: '🐱', dog: '🐶', bear: '🐻', rabbit: '🐰', panda: '🐼', fox: '🦊', penguin: '🐧',
};
const statusLabels = {
  queued: '排队中',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
  interrupted: '受理或恢复未确认',
  blocked_version: '版本被阻断',
  skipped_overlap: '跳过重叠',
};
const actionLabels = {
  edit: '编辑', run: '立即运行', enable: '开启监控', disable: '停用', history: '历史与来源', delete: '移除',
};
const actionConfirmations = {
  run: '立即使用所选模型执行一次研究？',
  enable: '开启定时监控？有新匹配资讯时会调用所选模型，请确认用量。',
  delete: '移除此 Bot？已有运行和证据记录会保留。',
};
const terms = value => [...new Set(String(value || '').split(/[,，\n]/).map(term => term.trim()).filter(Boolean))];
const runStatus = value => statusLabels[value] || value || '尚未运行';

export function botFormBody(data, requestId, existing = null) {
  const [model_provider, model_id] = String(data.get('model') || '').split('|');
  let parameters;
  try {
    parameters = JSON.parse(String(data.get('arguments') || '{}'));
  } catch {
    throw new Error('技能参数格式有误，请填写 JSON 对象。');
  }
  if (!parameters || typeof parameters !== 'object' || Array.isArray(parameters)) {
    throw new Error('技能参数必须是 JSON 对象。');
  }
  const skills = data.getAll('skills').map(value => {
    const [id, version] = String(value).split('|');
    return { id, version: Number(version), arguments: Object.hasOwn(parameters, id) ? parameters[id] : {} };
  });
  if (skills.length > 12) throw new Error('每个 Bot 最多绑定 12 项技能。');
  if (Object.keys(parameters).some(id => !skills.some(skill => skill.id === id))) {
    throw new Error('参数中包含未选择的技能。');
  }
  return {
    name: String(data.get('name') || '').trim(),
    objective: String(data.get('objective') || '').trim(),
    avatar: String(data.get('avatar') || 'cow'),
    color: String(data.get('color') || '#0786ff'),
    keywords: terms(data.get('keywords')),
    watchlist: terms(data.get('watchlist')),
    interval_minutes: Number(data.get('interval_minutes')),
    model_provider,
    model_id,
    approved_tools: data.getAll('approved_tools').map(String),
    skills,
    ...(existing ? { expected_version: existing.definition_version } : { request_id: requestId }),
  };
}

function editor(state) {
  const draft = state.draft;
  if (!draft) return '';
  const config = draft.config || {};
  const fields = draft.fields;
  const value = (name, fallback = '') => fields?.get(name) ?? fallback;
  const options = (state.models || []).flatMap(group =>
    (group.models || []).map(model => [`${group.id}|${model.id}`, `${group.name || group.id} / ${model.name || model.id}`]),
  );
  const model = value('model', draft.model || options[0]?.[0] || '');
  const modelOptions = options.map(([key, label]) =>
    `<option value="${e(key)}" ${model === key ? 'selected' : ''}>${e(label)}</option>`,
  );
  const missingModel = model && !options.some(([key]) => key === model)
    ? `<option value="${e(model)}" selected>当前不可用：${e(model)}</option>`
    : '';
  const toolChoices = (state.tools || []).filter(tool => tool.selectable);
  const chosenTools = fields?.getAll('approved_tools') ?? config.approved_tools ?? [];
  const toolOptions = toolChoices.map(tool =>
    `<option value="${e(tool.id)}" ${chosenTools.includes(tool.id) ? 'selected' : ''}>${e(tool.name || tool.id)}</option>`,
  );
  for (const id of chosenTools.filter(id => !toolChoices.some(tool => tool.id === id))) {
    toolOptions.push(`<option value="${e(id)}" selected>不可用：${e(id)}</option>`);
  }

  const skillChoices = (state.skills || []).filter(skill => ['skill', 'workflow'].includes(skill.kind) && skill.enabled);
  const chosenSkills = fields?.getAll('skills') ?? (config.skills || []).map(skill => `${skill.id}|${skill.version}`);
  const skillOptions = skillChoices.map(skill => {
    const key = `${skill.id}|${skill.version}`;
    return `<option value="${e(key)}" ${chosenSkills.includes(key) ? 'selected' : ''}>${e(skill.name)} · v${e(skill.version)}</option>`;
  });
  for (const key of chosenSkills.filter(key => !skillChoices.some(skill => `${skill.id}|${skill.version}` === key))) {
    const [id, version] = key.split('|');
    skillOptions.push(`<option value="${e(key)}" selected>不可用：${e(id)} v${e(version)}</option>`);
  }
  const defaultArguments = Object.fromEntries((config.skills || []).map(skill => [skill.id, skill.arguments || {}]));
  const disabled = state.busy || state.loading || state.uncertain;
  return `<form data-bot-form class="automation-form">
    <div class="section-heading"><h3>${draft.existing ? '编辑' : '新建'} Research Bot</h3><button type="button" class="button" data-bot-cancel ${state.busy ? 'disabled' : ''}>关闭</button></div>
    <p class="muted">新建和编辑保存后均停用。开启监控或立即运行会使用所选模型。运行状态未知时请先检查历史。</p>
    <div class="automation-form-grid" ${state.busy ? 'inert' : ''}>
      <label>名称<input name="name" required maxlength="80" value="${e(value('name', draft.name))}"></label>
      <label>头像<select name="avatar">${Object.entries(avatars).map(([id, label]) => `<option value="${id}" ${value('avatar', config.avatar) === id ? 'selected' : ''}>${label}</option>`).join('')}</select></label>
      <label>颜色<input type="color" name="color" value="${e(value('color', config.color || '#0786ff'))}"></label>
      <label>检查间隔（分钟）<input type="number" min="5" max="1440" name="interval_minutes" value="${e(value('interval_minutes', config.interval_minutes || 30))}" required></label>
      <label class="span-all">研究目标<textarea name="objective" maxlength="3000" rows="3" required>${e(value('objective', config.objective))}</textarea></label>
      <label>关键词（逗号分隔）<input name="keywords" value="${e(value('keywords', (config.keywords || []).join(', ')))}"></label>
      <label>观察标的代码（逗号分隔）<input name="watchlist" value="${e(value('watchlist', (config.watchlist || []).join(', ')))}"></label>
      <label class="span-all">分析模型<select name="model" required>${missingModel}${modelOptions.join('')}</select></label>
      <label class="span-all">批准的研究工具（不选择则不能取行情、检索网页或执行脚本）<select name="approved_tools" multiple size="5">${toolOptions.join('')}</select></label>
      <label class="span-all">绑定已发布技能（最多12项，可多选）<select name="skills" multiple size="6">${skillOptions.join('')}</select></label>
      <label class="span-all">技能参数（按技能标识填写 JSON 对象）<textarea name="arguments" rows="3">${e(value('arguments', JSON.stringify(defaultArguments, null, 2)))}</textarea></label>
    </div>
    <div class="button-row"><button class="button primary" type="submit" ${disabled || !options.length ? 'disabled' : ''}>${state.busy ? '保存中…' : '保存 Bot（不自动运行）'}</button></div>
  </form>`;
}

function renderResult(result) {
  return `<strong>${e(result.headline)}</strong><p>${e(result.judgment)}</p>
    <p>研判：${e(result.signal)} · 置信度：${e(result.confidence ?? '未提供')}（非收益概率）</p>
    <p>观察条件：${e(result.buyZone || '未提供')} · 失效条件：${e(result.sellZone || '未提供')}</p>
    <p>风险：${e(result.risks?.join('；'))}</p><p>下一验证点：${e(result.triggers?.join('；'))}</p>`;
}

function renderHistory(history) {
  if (!history) return '';
  const entries = history.items.map(run => {
    const evidence = {
      materials: run.bot_materials || [],
      skills: run.definition_snapshot?.research_task?.bot?.skills || [],
    };
    return `<article class="context-section"><strong>${e(runStatus(run.research_status))}</strong>
      <p>${e(run.scheduled_for || run.created_at || '时间未记录')} · ${e(run.trigger)} · 定义v${e(run.definition_version)}</p>
      ${run.session_id ? `<a href="#/claw?session=${encodeURIComponent(run.session_id)}">查看原研究会话</a>` : ''}
      <p>${e(run.summary || run.failure_code || '结果待确认')}</p>
      <details><summary>本次冻结资讯与技能</summary><pre>${e(JSON.stringify(evidence, null, 2))}</pre></details></article>`;
  }).join('');
  return `<section>
    <div class="section-heading"><h3>运行历史与来源 · ${e(history.name)}</h3><button type="button" class="button" data-bot-close-history>关闭</button></div>
    ${history.error ? `<p class="notice error" role="alert">${e(history.error)}</p>` : ''}
    ${entries || (!history.loading && !history.error ? '<p>暂无运行历史。</p>' : '')}
    ${history.loading ? '<p role="status">读取历史…</p>' : ''}
    ${history.nextBefore ? `<button type="button" class="button" data-bot-older-history ${history.loading ? 'disabled' : ''}>加载更早</button>` : ''}
  </section>`;
}

export function renderResearchBots(state = {}) {
  const disabled = state.busy || state.loading || state.uncertain ? 'disabled' : '';
  const cards = (state.items || []).map(item => {
    const config = item.research_task?.bot || {};
    const run = (state.runs || []).find(itemRun => itemRun.automation_id === item.id);
    const color = /^#[a-fA-F0-9]{6}$/.test(config.color || '') ? config.color : '#0786ff';
    const avatar = Object.hasOwn(avatars, config.avatar) ? avatars[config.avatar] : avatars.cow;
    const actions = ['edit', 'run', item.enabled ? 'disable' : 'enable', 'history', 'delete'];
    return `<article><header><div><span aria-hidden="true" style="color:${color}">${avatar}</span><h3>${e(item.name)}</h3></div><span class="badge">${item.enabled ? '监控已启用' : '已停用'}</span></header>
      <p>${e(config.objective)}</p><p class="muted small">关键词：${e((config.keywords || []).join('、') || '全部')} · 标的：${e((config.watchlist || []).join('、') || '无')} · 技能 ${(config.skills || []).length} 项</p>
      <dl><div><dt>间隔</dt><dd>${e(config.interval_minutes)} 分钟</dd></div><div><dt>下次检查</dt><dd>${e(item.next_run_at || '未启用')}</dd></div><div><dt>运行</dt><dd>${e(runStatus(run?.research_status))}</dd></div><div><dt>模型</dt><dd>${e(item.research_task?.model_id)}</dd></div></dl>
      ${run?.bot_result ? renderResult(run.bot_result) : run?.summary ? `<p>${e(run.summary)}</p>` : ''}
      ${run?.failure_code ? `<p class="notice error">${e(run.failure_code)}；请检查原运行记录。</p>` : ''}
      <div class="button-row">${actions.map(action => `<button type="button" class="button small" data-bot-action="${action}" data-bot-id="${e(item.id)}" ${disabled}>${actionLabels[action]}</button>`).join('')}</div>
    </article>`;
  }).join('');
  return `<section data-research-bots>
    <header class="page-header"><div><h1>Research Bot</h1></div>
    <div class="button-row"><button type="button" class="button" data-bot-refresh ${state.busy || state.loading ? 'disabled' : ''}>刷新</button><button type="button" class="button primary" data-bot-new ${disabled}>新建 Bot</button></div></header>
    ${state.loading ? '<p role="status">读取中…</p>' : ''}
    ${state.error ? `<p class="notice error" role="alert">${e(state.error)}</p>` : ''}
    ${state.message ? `<p class="notice" role="status">${e(state.message)}</p>` : ''}
    ${state.uncertain ? '<p class="notice">状态尚未核实，请刷新后再操作。写入不会自动重发。</p>' : ''}
    ${editor(state)}
    <div class="capability-plan-list">${cards || (!state.loading && !state.error ? '<p>创建第一个 Research Bot。保存设置后可开启监控。</p>' : '')}</div>
    ${renderHistory(state.history)}
  </section>`;
}

function runMessage(result) {
  switch (result?.research_status) {
    case 'queued':
    case 'running':
      return '已受理，结果请刷新查看。';
    case 'skipped_overlap':
      return '已有运行，已跳过本次请求。';
    case 'blocked_version':
      return '版本校验未通过，本次未启动。';
    default:
      return '运行状态请查看历史。';
  }
}

export function createResearchBots({ api, notify = () => {}, route = () => ({}), logger = () => {}, confirm = message => globalThis.confirm(message) } = {}) {
  const state = {
    items: [], runs: [], models: [], skills: [], tools: [], loading: false, busy: false,
    error: '', message: '', uncertain: true, draft: null, history: null,
  };
  let generation = 0;
  const active = () => route().page === 'research-bots';

  async function activate() {
    const ticket = ++generation;
    state.loading = true;
    state.error = '';
    notify();
    try {
      const items = await api.researchBots();
      if (ticket !== generation || !active()) return;
      const [skills, models, tools] = await Promise.all([
        api.capabilities(), api.models(), api.tools ? api.tools() : { items: [] },
      ]);
      if (ticket !== generation || !active()) return;
      state.items = items.items || [];
      state.runs = items.latest_runs || [];
      state.skills = skills.items || [];
      state.models = models.groups || [];
      state.tools = tools.items || [];
      state.uncertain = false;
    } catch (error) {
      if (ticket === generation && active()) {
        state.error = error.message || '读取 Bot 失败';
        state.uncertain = true;
      }
      logger('research_bot_read_failed', { status: error.code || 'request_failed' });
    } finally {
      if (ticket === generation) {
        state.loading = false;
        if (active()) notify();
      }
    }
  }

  async function loadHistory(history, before) {
    history.loading = true;
    history.error = '';
    notify();
    try {
      const page = await api.researchBotRuns(history.id, before);
      if (state.history !== history) return;
      const incoming = page.items || [];
      history.items.push(...incoming.filter(item => !history.items.some(known => known.id === item.id)));
      history.nextBefore = page.next_before || null;
    } catch (error) {
      if (state.history === history) history.error = error.message || '读取 Bot 历史失败';
      logger('research_bot_history_failed', { status: error.code || 'request_failed' });
    } finally {
      history.loading = false;
      if (state.history === history && active()) notify();
    }
  }

  function captureForm(target) {
    const form = target.closest?.('[data-bot-form]');
    if (!form || !state.draft) return false;
    if (!state.busy) state.draft.fields = new FormData(form);
    return true;
  }

  async function saveDraft(body, draft) {
    body.skills = await Promise.all(body.skills.map(async binding => {
      const locked = await api.researchBotSkill(binding.id, binding.version);
      const previous = draft.config.skills?.find(skill => skill.id === binding.id && skill.version === binding.version);
      if (previous && previous.sha256 !== locked.sha256) {
        throw new Error('原技能内容已变化，请重新选择并确认技能版本。');
      }
      return { ...locked, arguments: binding.arguments };
    }));
    if (draft.existing) await api.updateResearchBot(draft.existing.id, body);
    else await api.createResearchBot(body);
    state.draft = null;
    state.message = 'Bot 已保存。可单独开启监控。';
  }

  async function handle(event) {
    if (!active() || !event.target.closest?.('[data-research-bots]')) return false;
    if (event.type === 'input' || event.type === 'change') return captureForm(event.target);
    const button = event.target.closest?.('button');
    if (event.type === 'click' && button?.type === 'submit') return false;
    const submitting = event.type === 'submit';
    if (submitting && !event.target.matches?.('[data-bot-form]')) return false;
    if (submitting) event.preventDefault();
    if (state.busy) return true;
    if (button?.hasAttribute('data-bot-refresh')) {
      if (!state.loading) await activate();
      return true;
    }
    if (button?.hasAttribute('data-bot-cancel')) {
      state.draft = null;
      state.error = '';
      notify();
      return true;
    }
    if (button?.hasAttribute('data-bot-close-history')) {
      state.history = null;
      notify();
      return true;
    }
    if (button?.hasAttribute('data-bot-older-history')) {
      const history = state.history;
      if (history?.nextBefore && !history.loading) await loadHistory(history, history.nextBefore);
      return true;
    }
    if (state.uncertain || state.loading) return true;
    if (button?.hasAttribute('data-bot-new')) {
      state.draft = { requestId: globalThis.crypto.randomUUID(), config: {} };
      state.error = '';
      notify();
      return true;
    }

    const action = button?.dataset.botAction;
    if (!submitting && !action) return false;
    const item = state.items.find(candidate => candidate.id === button?.dataset.botId);
    if (action && !item) return true;
    if (action === 'history') {
      state.history = { id: item.id, name: item.name, items: [], nextBefore: null, loading: false, error: '' };
      await loadHistory(state.history);
      return true;
    }
    if (action === 'edit') {
      state.draft = {
        existing: item,
        name: item.name,
        model: `${item.research_task.model_provider}|${item.research_task.model_id}`,
        config: structuredClone(item.research_task.bot),
      };
      state.error = '';
      notify();
      return true;
    }
    if (actionConfirmations[action] && !confirm(actionConfirmations[action])) return true;

    const draft = state.draft;
    let body;
    if (submitting) {
      if (!draft) return true;
      draft.fields = new FormData(event.target);
      try {
        body = botFormBody(draft.fields, draft.requestId, draft.existing);
      } catch (error) {
        state.error = error.message;
        notify();
        return true;
      }
    }
    state.busy = true;
    state.error = '';
    state.message = '';
    notify();
    try {
      if (body) {
        await saveDraft(body, draft);
      } else {
        const request = { expected_version: item.definition_version };
        if (action === 'run') request.request_id = globalThis.crypto.randomUUID();
        const result = await api.researchBotAction(item.id, action, request);
        if (action === 'delete' && state.history?.id === item.id) state.history = null;
        state.message = action === 'run' ? runMessage(result) : '操作已保存。';
      }
      if (active()) await activate();
    } catch (error) {
      state.error = error.message || '操作未确认，请刷新检查原任务。';
      state.uncertain = true;
      logger('research_bot_write_unconfirmed', { status: error.code || 'request_failed' });
    } finally {
      state.busy = false;
      if (active()) notify();
    }
    return true;
  }

  return { state, activate, handle, render: () => renderResearchBots(state) };
}
