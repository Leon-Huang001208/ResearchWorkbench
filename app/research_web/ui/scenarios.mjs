import { escapeHTML as e } from './markdown.mjs';
import { safeLog } from './core.mjs';
import { cleanAsset } from './asset-navigation.mjs';
const stateLabel = value => ({ incomplete:'证据不完整', ready_for_draft:'可准备草稿', unverified:'待核验', unavailable:'暂不可用', ready:'具备准入条件', prepared:'已准备草稿', creation_outcome_unknown:'创建结果尚未确认' })[value] || '待核验';
const artifactLabel = value => ({ 'source-linked-research-draft':'带来源的研究草稿', 'coverage-and-missing-evidence-ledger':'覆盖与缺口台账' })[value] || value;

export function scenarioLaunchContext({ assetPage, route, observation, detail, draft, researchAsOf }, data) {
  if ('workbenchHandoff' in data && !assetPage) return null;
  if (assetPage && (!observation || route.asset && (cleanAsset(route.asset) !== cleanAsset(observation.asset) || (route.assetType || 'stock') !== observation.asset_type))) return { error: '当前证券观察尚未就绪，请等待切换完成；没有带入上一证券资料。' };
  const current = assetPage ? observation : null;
  return { context: { session_id: current?.session_id || detail?.id, observation_id: current?.id,
    subject: current ? {kind:current.asset_type,identity:current.asset} : undefined,
    as_of: current?.request_parameters?.end_date || researchAsOf || '',
    datasets: current ? Object.values(current.blocks || {}).map(x=>x.dataset).filter(Boolean) : detail?.datasets || [],
    question: draft || '', mode: data.workbenchHandoff || (route.page === 'claw' ? 'claw' : 'fingpt') } };
}

// A separate form preserves the original composer text and attachments. Opening
// and selection are reads; only the explicit freeze action creates a session.
export function createScenarioController({ api, changed = () => {}, onOpen, makeID = () => crypto.randomUUID(), account = () => String(globalThis.__RWB_USER_ID__ || 'local'), logger = safeLog, storage } = {}) {
  const state = { open: false, loading: false, busy: false, error: '', items: [], query: '', selected: '', inputs: {}, datasets: [], request: null, result: null };
  let generation = 0; const owner = account();
  const storageKey = `research-web:${owner}:scenario-pending:v1`;
  if (storage === undefined) { try { storage = globalThis.sessionStorage; } catch { logger('scenario_storage_unavailable'); } }
  function persist() {
    if (!storage) return;
    try {
      if (!state.request) storage.removeItem(storageKey);
      else storage.setItem(storageKey, JSON.stringify({ request: state.request, result: state.result }));
    } catch { state.error = '本页仍保留原请求，但刷新恢复副本保存失败，请保留本页查询。'; logger('scenario_receipt_storage_failed'); }
  }
  try {
    const raw = storage?.getItem(storageKey);
    if (raw) {
      if (raw.length > 300000) throw new Error('receipt_too_large');
      const saved = JSON.parse(raw);
      if (!/^[A-Za-z0-9_.:-]{8,128}$/.test(saved.request?.key || '') || !saved.request?.body?.scenario_id) throw new Error('receipt_invalid');
      state.request = saved.request; state.result = saved.result;
      state.inputs = saved.request.body.scenario_inputs; state.selected = saved.request.body.scenario_id;
      state.context = { session_id: saved.request.body.source_session_id, mode: saved.request.body.target_mode };
    }
  } catch { state.restoreBlocked = true; state.error = '原场景请求恢复副本不可核验；请查询原交接记录。'; logger('scenario_receipt_restore_failed'); }
  function current(ticket) { return ticket === generation && state.open && account() === owner; }
  async function open(context = {}) {
    if (account() !== owner) return;
    if (state.restoreBlocked) { state.open = true; changed(); return; }
    // Keep an unresolved request bound to the same ID; reopening cannot mask it.
    if (state.request) { state.open = true; changed(); return; }
    const ticket = ++generation;
    context = {...context,datasets:[...new Map((context.datasets || []).map(item=>[item.dataset_id,item])).values()]};
    Object.assign(state, { open: true, loading: true, error: '', context, selected: context.scenario || '', inputs: { subject: context.subject || { kind: 'stock', identity: '' }, as_of: context.as_of || '', question: context.question || '', material_ids: [...(context.datasets || []).map(x => x.dataset_id), ...(context.workspace_material ? ['file:'+context.workspace_material.file_id] : [])] }, datasets: context.datasets || [], result: null }); changed();
    try { const value = await api.scenarioCatalog(); if (current(ticket)) { state.items = value.items; state.selected ||= value.items[0]?.id || ''; } }
    catch (error) { if (current(ticket)) state.error = error.message || '场景目录不可读取'; logger('scenario_catalog_failed', { code: error.code || 'request_failed' }); }
    finally { if (current(ticket)) { state.loading = false; changed(); } }
  }
  function close() { state.open = false; generation++; changed(); }
  function edit(name, value) {
    if (state.busy || state.request || state.result) return;
    if (name === 'query') { state.query = value; state.selected = ''; }
    else if (name === 'scenario') { state.selected = value; delete state.inputs.window_start; }
    else if (name === 'identity' || name === 'kind') state.inputs.subject = { ...state.inputs.subject, [name]: value };
    else state.inputs[name] = value;
    state.error = ''; changed();
  }
  async function prepare() {
    if (state.restoreBlocked || state.busy || state.request || account() !== owner) return;
    const selected = state.items.find(row => row.id === state.selected);
    if (!selected || selected.capabilities.some(x => !x.available)) { state.error = '此场景所需能力当前不可执行；输入已保留。'; changed(); return; }
    if (selected.subject_kinds && !selected.subject_kinds.includes(state.inputs.subject.kind)) { state.error = '当前观察类型与场景不符；请明确选择独立研究身份，不推断证券与行业关系。'; changed(); return; }
    const inputs = structuredClone(state.inputs);
    if (!inputs.as_of || !inputs.question.trim() || !inputs.subject.identity.trim()) { state.error = '请填写规范标的、明确截止日和研究问题。'; changed(); return; }
    const body = { source_session_id: state.context.session_id || null, target_mode: state.context.mode || 'fingpt', section: state.context.section || 'assets', dataset_ids: inputs.material_ids.filter(id=>!id.startsWith('file:')), scenario_id: state.selected, scenario_inputs: inputs, ...(state.context.observation_id ? { observation_id: state.context.observation_id } : {}), ...(state.context.comparison_observation_ids?.length ? {comparison_observation_ids:state.context.comparison_observation_ids} : {}), ...(state.context.workspace_material ? {workspace_material:state.context.workspace_material} : {}), ...(state.context.source_scope ? {source_scope:state.context.source_scope} : {}) };
    state.request = { key: makeID(), body }; persist(); state.busy = true; changed();
    try { const result = await api.handoff(body, state.request.key); if (account() === owner) state.result = result; }
    catch (error) {
      state.error = error.message || '冻结结果未知，请查询原请求';
      // Only these deterministic pre-create rejections permit editing. An
      // unknown transport/server outcome always retains the original key.
      if (['scenario_inputs_invalid','scenario_material_selection_mismatch','scenario_capability_unavailable','scenario_subject_mismatch','scenario_cutoff_mismatch','scenario_observation_foreign','scenario_observation_material_mismatch','scenario_source_missing'].includes(error.code)) state.request = null;
      logger('scenario_prepare_failed', { code: error.code || 'request_failed' });
    } finally { state.busy = false; persist(); changed(); }
  }
  async function lookup() {
    if (!state.request || state.busy || account() !== owner) return;
    state.busy = true; changed();
    try { const result = await api.handoffRequest(state.request.key); if (account() === owner) state.result = result; state.error = ''; }
    catch (error) { state.error = error.message || '原请求回执暂不可用'; logger('scenario_receipt_failed', { code: error.code || 'request_failed' }); }
    finally { state.busy = false; persist(); changed(); }
  }
  async function handle(event) {
    const target = event.target;
    if (['input', 'change'].includes(event.type) && target.dataset?.scenarioField) {
      const name = target.dataset.scenarioField;
      edit(name, name === 'material_ids' ? [...[...target.closest('form').querySelectorAll('[name="scenario-material"]:checked')].map(x => x.value), ...(state.context.workspace_material ? ['file:'+state.context.workspace_material.file_id] : [])] : target.value); return true;
    }
    if (event.type === 'submit' && target.matches?.('[data-scenario-form]')) { event.preventDefault(); if (event.submitter?.dataset?.scenarioFreeze !== undefined) await prepare(); return true; }
    const action = target.closest?.('[data-scenario-action]')?.dataset.scenarioAction;
    if (event.type !== 'click' || !action) return false;
    event.preventDefault();
    if (action === 'close') close();
    else if (action === 'independent' && !state.request && !state.busy) {
      const selected = state.items.find(row => row.id === state.selected);
      state.context = { mode: state.context.mode, section: 'industry' };
      state.inputs.subject = { kind: selected.subject_kinds[0], identity: '' };
      state.inputs.material_ids = []; state.datasets = []; state.error = ''; changed();
    }
    else if (action === 'lookup') await lookup();
    else if (action === 'open' && state.result?.state === 'prepared' && account() === owner) { await onOpen(state.result); state.request = null; state.result = null; persist(); close(); }
    return true;
  }
  function key(event) {
    if (event.key === 'Enter' && (event.target.dataset?.scenarioField === 'query' || ['INPUT', 'SELECT'].includes(event.target.tagName))) { event.preventDefault(); return true; }
    if (event.key === 'Escape') { event.preventDefault(); close(); return true; }
    if (event.key !== 'Tab') return false;
    const panel = event.target.closest?.('.scenario-panel');
    const controls = [...(panel?.querySelectorAll('button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled])') || [])];
    const index = controls.indexOf(event.target);
    if (controls.length && (event.shiftKey && index === 0 || !event.shiftKey && index === controls.length - 1)) { event.preventDefault(); controls[event.shiftKey ? controls.length - 1 : 0].focus(); return true; }
    return false;
  }
  return { state, open, close, edit, prepare, lookup, handle, key };
}

export function renderScenarioPanel(s) {
  if (!s.open) return '';
  const row = s.items.find(x => x.id === s.selected); const locked = s.busy || !!s.request || !!s.result;
  const options = s.items.filter(x => `${x.name} ${x.description} ${x.coverage.join(' ')}`.toLowerCase().includes(s.query.toLowerCase()));
  const frozen = s.result?.scenario_context;
  return `<div class="d-drawer-backdrop scenario-panel"><aside class="d-drawer" role="dialog" aria-modal="true" aria-label="研究场景"><header><h2>研究场景</h2><button type="button" class="button" data-scenario-action="close">关闭</button></header><form data-scenario-form><div class="d-drawer-body">${s.error ? `<p role="alert" class="notice danger">${e(s.error)}</p>` : ''}${s.loading ? '<p role="status">正在读取当前场景与能力版本…</p>' : ''}<label>搜索场景<input type="search" form="scenario-browse-only" id="scenario-query" data-scenario-field="query" value="${e(s.query)}" ${locked ? 'disabled' : ''}></label><label>场景<select id="scenario-scenario" data-scenario-field="scenario" ${locked ? 'disabled' : ''}><option value="">选择一个场景</option>${options.map(x => `<option value="${e(x.id)}" ${x.id === s.selected ? 'selected' : ''}>${e(x.name)}${x.capabilities.some(c => !c.available) ? ' · 能力不可用' : ''}</option>`).join('')}</select></label>${!options.length ? '<p>没有匹配的场景。</p>' : ''}${row ? `<section><h3>${e(row.name)}</h3><p>${e(row.coverage.join('；'))}</p><ol>${row.steps.map(x => `<li>${e(x)}</li>`).join('')}</ol><p>当前能力：${row.capabilities.map(x => `${e(x.id)} ${x.available ? `v${e(x.version)} · 发送资格 ${e(stateLabel(x.execution_status))}` : e(x.code || '不可用')}`).join('；')}</p><p>示例：${e(row.examples[0].question)}</p><p>输出：${e(row.expected_artifacts.map(artifactLabel).join('；'))}</p></section>` : ''}${row?.subject_kinds && !row.subject_kinds.includes(s.inputs.subject?.kind) ? '<p class="notice warning">当前证券不是行业身份，尚无可核验的行业关联。<button type="button" class="button" data-scenario-action="independent">另行填写独立行业身份</button></p>' : ''}<fieldset ${locked ? 'disabled' : ''}><legend>冻结研究输入</legend><label>标的类型<select id="scenario-kind" data-scenario-field="kind" ${s.context?.observation_id ? 'disabled' : ''}>${['stock', 'industry', 'topic'].map(kind => `<option value="${kind}" ${s.inputs.subject?.kind === kind ? 'selected' : ''}>${({ stock:'证券', industry:'行业分类', topic:'独立主题' })[kind]}</option>`).join('')}</select></label><label>规范身份<input id="scenario-identity" data-scenario-field="identity" value="${e(s.inputs.subject?.identity || '')}" placeholder="600600.SH / SW:801080 / 主题" ${s.context?.observation_id ? 'readonly' : ''}></label><label>研究截止<input type="date" id="scenario-as_of" data-scenario-field="as_of" value="${e(s.inputs.as_of || '')}" required></label>${row?.required_inputs.includes('window_start') ? `<label>历史起点<input type="date" id="scenario-window_start" data-scenario-field="window_start" value="${e(s.inputs.window_start || '')}" required></label>` : ''}<label>研究问题<textarea rows="4" maxlength="6000" id="scenario-question" data-scenario-field="question" required>${e(s.inputs.question || '')}</textarea></label><legend>已取得资料（仅勾选项）</legend>${s.context?.workspace_material ? `<p>另含已确认资料合同 ${e(s.context.workspace_material.file_id)} 与其原件引用；明确来源范围：${e((s.context.source_scope || []).map(x=>({datahub:'数据快照',uploads:'已有文件／上传资料',web:'联网与网页资料'})[x]).join('、'))}。</p>` : ''}${s.datasets.map(x => `<label><input type="checkbox" name="scenario-material" data-scenario-field="material_ids" value="${e(x.dataset_id)}" ${s.inputs.material_ids.includes(x.dataset_id) ? 'checked' : ''}>${e(x.name || x.capability || x.dataset_id)} · ${e(x.as_of || '日期未提供')}</label>`).join('') || '<p>当前没有已选快照，将保留资料缺口。原输入附件仍保留在原草稿。</p>'}</fieldset>${frozen ? `<section><h3>已冻结 · ${e(stateLabel(frozen.scenario.status))}</h3><p>截止 ${e(frozen.scenario.inputs.as_of)} · ${e(frozen.scenario.inputs.subject.identity)}</p><ul>${frozen.requirements.map(x => `<li>${e(x)}</li>`).join('')}</ul><p>准备成功不表示证据齐全或质量通过。进入问答后，明确发送才启动模型。</p></section>` : ''}</div><footer>${s.result?.state === 'prepared' ? '<button class="button primary" type="button" data-scenario-action="open">确认冻结资料，进入研究草稿</button>' : s.request ? `<p>${e(stateLabel(s.result?.state))}；不自动重复创建</p><button class="button" type="button" data-scenario-action="lookup" ${s.busy ? 'disabled' : ''}>查询原请求</button>` : `<button class="button primary" type="submit" data-scenario-freeze ${s.loading || s.busy || !row || row.capabilities.some(x=>!x.available) ? 'disabled' : ''}>冻结资料并准备草稿</button>`}</footer></form></aside></div>`;
}
