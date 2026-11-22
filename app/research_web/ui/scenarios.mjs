import { escapeHTML as e } from './markdown.mjs';
import { safeLog } from './core.mjs';
import { selectAssetObservation } from './asset-navigation.mjs';
import { packScope, packQualification, packInputEdit, sourcePicker, sourcePack, sourceKey, ownedMethodScene } from './pack-ui.mjs';
const stateLabel = value => ({ incomplete:'证据不完整', ready_for_draft:'可准备草稿', unverified:'待核验', unavailable:'暂不可用', ready:'具备准入条件', prepared:'已准备草稿', context_unavailable:'来源暂不可读取，请恢复授权后查询', creation_outcome_unknown:'创建结果尚未确认' })[value] || '待核验';
const artifactLabel = value => ({ 'source-linked-research-draft':'带来源的研究草稿', 'coverage-and-missing-evidence-ledger':'覆盖与缺口台账' })[value] || value;
function ownedPresetQuestion(inputs, scenarioId) {
  const presets = scenarioId === 'owned-company-evidence' ? ['company_one_pager','fundamental_analysis'] : scenarioId === 'owned-research-prep' ? ['research_outline'] : [];
  const query = inputs.preset_query;
  return presets.includes(inputs.question_preset) && typeof query === 'string' && query.trim().length > 0 && query.length <= 2000 && !/[\x00-\x1f]|:\/\//.test(query) && !query.trim().toLowerCase().startsWith('www.');
}

// Only closed, public reason categories are displayed; server text may contain
// private details. Reasons never authorize a retry or change request ownership.
function failureReason(error) {
  const codes = {source_selection_scope_revoked:403,source_scope_denied:403,research_source_capture_changed:409,source_selection_preview_changed:409,source_selection_source_changed:409,session_deleted:410,scenario_inputs_invalid:422,source_selection_request_invalid:422};
  return ({
    403:['原会话的来源授权当前不可用。','请恢复原会话的来源授权后重新预览。'],
    409:['所选资料或方法版本已变化。','请重新选择可用的已保存来源并重新预览。'],
    410:['来源已删除或过期。','请重新选择仍可用的已保存来源并重新预览。'],
    422:['研究参数不符合要求。','请修改参数后重新预览。'],
    404:['来源或请求记录当前不可读取。','请核对并重新选择可用的已保存来源。'],
  })[Object.hasOwn(codes,error.code) ? codes[error.code] : error.status] || ['资料校验或服务响应未确认。','请核对来源与参数后重新预览。'];
}

export function scenarioLaunchContext({ assetPage, route, observation, observations = [], detail, draft, researchAsOf }, data) {
  if ('workbenchHandoff' in data && !assetPage) return null;
  const matched = assetPage && selectAssetObservation(observations.length ? observations : observation ? [observation] : [], route);
  if (assetPage && (!observation || !matched || matched.id !== observation.id || matched.asset !== observation.asset || matched.asset_type !== observation.asset_type)) return { error: '当前证券观察尚未就绪，请等待切换完成；没有带入上一证券资料。' };
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
  const state = { open: false, loading: false, busy: false, previewing: false, preview: null, stale: false, error: '', items: [], query: '', selected: '', inputs: {}, datasets: [], request: null, result: null, material_mode:'datasets', source_ids:[], sourceItems:[], sourceSession:'', sourceScopes:{}, sourceError:'', sourceLoaded:false };
  const sourceMode = () => state.material_mode === 'sources' && sourcePack(state.items.find(item=>item.id === state.selected));
  let inputRevision = 0, materialGeneration = 0;
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
      if (!/^[A-Za-z0-9_.:-]{8,128}$/.test(saved.request?.key || '') || !(saved.request?.body?.scenario_id || saved.request?.body?.handoff?.scenario_id)) throw new Error('receipt_invalid');
      state.request = saved.request; state.result = saved.result;
      const handoff = saved.request.body.handoff || saved.request.body;
      state.inputs = handoff.scenario_inputs; state.selected = handoff.scenario_id;
      state.material_mode = saved.request.body.handoff ? 'sources' : 'datasets';
      state.context = { session_id: handoff.source_session_id, mode: handoff.target_mode };
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
    Object.assign(state, { open: true, loading: true, error: '', preview: null, stale: false, previewing: false, materialLoading: false, material_mode:'datasets', source_ids:[], sourceItems:[], sourceScopes:{}, sourceSession:'', sourceLoaded:false, sourceError:'', context, selected: context.scenario || '', inputs: { subject: context.subject || { kind: 'stock', identity: '' }, as_of: context.as_of || '', question: context.question || '', material_ids: [...(context.datasets || []).map(x => x.dataset_id), ...(context.workspace_material ? ['file:'+context.workspace_material.file_id] : [])] }, datasets: context.datasets || [], result: null }); changed();
    try {
      const [catalog, sessions] = await Promise.allSettled([
        api.scenarioCatalog(),
        !context.observation_id && !context.workspace_material && !context.material_sessions?.length && api.sessions ? api.sessions() : Promise.resolve(null),
      ]);
      if (catalog.status === 'rejected') throw catalog.reason;
      if (current(ticket)) {
        state.items = catalog.value.items; state.selected ||= catalog.value.items[0]?.id || '';
        if (sessions.status === 'fulfilled' && sessions.value) state.context.material_sessions = sessions.value.items || [];
        else if (sessions.status === 'rejected') { state.error = '本人原会话目录暂不可读取；当前材料输入仍保留。'; logger('scenario_material_catalog_failed'); }
      }
    }
    catch (error) { if (current(ticket)) state.error = error.message || '场景目录不可读取'; logger('scenario_catalog_failed', { code: error.code || 'request_failed' }); }
    finally { if (current(ticket)) { state.loading = false; changed(); } }
  }
  function close() { state.open = false; generation++; changed(); }
  function edit(name, value) {
    if (state.busy || state.request || state.result || account() !== owner) return;
    inputRevision++; state.stale = !!state.preview || state.stale; state.preview = null;
    const row = state.items.find(item=>item.id === state.selected);
    if (name === 'material_mode') {
      if (!['datasets','sources'].includes(value) || value === 'sources' && (!sourcePack(row) || state.context.observation_id || state.context.workspace_material)) return;
      state.material_mode = value;
    }
    else if (name === 'source_ids') {
      const known = new Set(state.sourceItems.filter(item=>item.selectable).map(sourceKey));
      state.source_ids = [...new Set(value)].filter(key=>known.has(key) || state.source_ids.includes(key));
    }
    else if (name === 'query') { state.query = value; state.selected = ''; }
    else if (name === 'scenario') { state.selected = value; delete state.inputs.window_start; delete state.inputs.research_scope; delete state.inputs.cutoff_at; delete state.inputs.question_preset; delete state.inputs.preset_query; }
    else if (name === 'cutoff_at' && ['owned-news-evidence','owned-research-prep'].includes(state.selected)) state.inputs.cutoff_at = value;
    else if (['question_preset','preset_query'].includes(name) && ['owned-company-evidence','owned-research-prep'].includes(state.selected)) {
      if (name === 'question_preset' && !value) { delete state.inputs.question_preset; delete state.inputs.preset_query; }
      else state.inputs[name] = value;
    }
    else if (name === 'identity' || name === 'kind') state.inputs.subject = { ...state.inputs.subject, [name]: value };
    else if (!packInputEdit(state.inputs, row, name, value) && ['as_of','question','material_ids','window_start'].includes(name)) state.inputs[name] = value;
    state.error = ''; changed();
  }
  async function selectSourceSession(id) {
    if (!sourceMode() || state.busy || state.request || state.result || account() !== owner || !id || !(state.context.material_sessions || []).some(item=>item.id === id)) return;
    const ticket = generation, materialTicket = ++materialGeneration; ++inputRevision;
    state.preview = null; state.stale = true; state.sourceSession = id; state.sourceLoaded = false;
    state.sourceError = ''; state.materialLoading = true; changed();
    try {
      const [detail, result] = await Promise.all([api.detail(id), api.sourceSelectionList(id)]);
      if (detail.id !== id || !Array.isArray(result.items) || result.items.some(item=>item.source_session_id !== id)) throw new Error('source_session_identity_mismatch');
      if (current(ticket) && materialTicket === materialGeneration) {
        const returned = new Set(result.items.map(sourceKey));
        const missing = state.sourceItems.filter(item=>item.source_session_id === id && state.source_ids.includes(sourceKey(item)) && !returned.has(sourceKey(item))).map(item=>({...item,selectable:false,state:'unavailable',reason_code:'source_missing'}));
        state.sourceItems = [...state.sourceItems.filter(item=>item.source_session_id !== id), ...result.items, ...missing];
        state.sourceScopes[id] = detail.source_scope || []; state.sourceLoaded = true;
      }
    } catch (error) {
      if (current(ticket) && materialTicket === materialGeneration) {
        state.sourceError = ({403:'此原会话来源权限已撤回或未批准网页范围。',404:'此原会话或来源记录不存在。',410:'此原会话或来源已删除或永久清理。',409:'原文已变化或完整性不可核验，请重新读取。'})[error.status] || '原文来源读取失败，请恢复原来源后重试。';
      }
      logger('scenario_source_list_failed',{code:error.code || 'request_failed'});
    } finally { if (current(ticket) && materialTicket === materialGeneration) { state.materialLoading = false; changed(); } }
  }
  function sourceBody(inputs) {
    if (!state.source_ids.length || state.source_ids.length > 20) throw Object.assign(new Error('请明确选择 1–20 份已保存原文。'),{sourceInput:true});
    const sources = state.source_ids.map(key=>state.sourceItems.find(item=>sourceKey(item) === key));
    if (state.sourceError || sources.some(item=>!item?.selectable)) throw Object.assign(new Error('所选来源当前不可读取；选择与输入已保留，请重新读取原会话。'),{sourceInput:true});
    const sid = sources[0].source_session_id;
    if (!['datahub','uploads','web'].every(scope=>(state.sourceScopes[sid] || []).includes(scope))) throw Object.assign(new Error('首份所选原文的会话须已有金融数据、附件与网页资料三项权限；请在原会话确认，界面不会自动开启。'),{sourceInput:true});
    inputs.material_ids = [];
    const handoff = {...requestBody(inputs), source_session_id:sid, source_scope:state.sourceScopes[sid]};
    return {handoff,sources:sources.map(({source_session_id,id,sha256})=>({source_session_id,id,sha256}))};
  }
  async function selectMaterialSession(id) {
    if (state.busy || state.request || state.result || state.context.observation_id || state.context.workspace_material || account() !== owner) return;
    if (id && !(state.context.material_sessions || []).some(item=>item.id === id)) return;
    const ticket = generation, materialTicket = ++materialGeneration; ++inputRevision;
    state.preview = null; state.stale = true; state.datasets = []; state.inputs.material_ids = [];
    state.context.session_id = id || undefined; delete state.context.source_scope; state.materialLoading = !!id; state.error = ''; changed();
    if (!id) return;
    try {
      const detail = await api.detail(id);
      if (detail.id !== id) throw new Error('material_session_identity_mismatch');
      if (current(ticket) && materialTicket === materialGeneration) {
        state.datasets = detail.datasets || [];
        state.context.source_scope = detail.source_scope;
      }
    } catch (error) {
      if (current(ticket) && materialTicket === materialGeneration) state.error = '此会话材料当前不可读取；请选择本人仍有权限的原会话。';
      logger('scenario_material_session_failed',{code:error.code || 'request_failed'});
    } finally { if (current(ticket) && materialTicket === materialGeneration) {state.materialLoading = false; changed();} }
  }
  function requestBody(inputs) {
    const row = state.items.find(item=>item.id === state.selected);
    if (row?.pack_id) for (const method of row.ui_methods || []) for (const field of method.fields) {
      const value = inputs.research_scope?.methods?.[method.id]?.[field.name];
      if (field.type === 'securities' && Array.isArray(value)) inputs.research_scope.methods[method.id][field.name] = value.filter(item=>Object.values(item).some(Boolean));
    }
    return { source_session_id: state.context.session_id || null, target_mode: state.context.mode || 'fingpt', section: state.context.section || 'assets', dataset_ids: inputs.material_ids.filter(id=>!id.startsWith('file:')), scenario_id: state.selected, scenario_inputs: inputs, ...(state.context.observation_id ? { observation_id: state.context.observation_id } : {}), ...(state.context.comparison_observation_ids?.length ? {comparison_observation_ids:state.context.comparison_observation_ids} : {}), ...(state.context.workspace_material ? {workspace_material:state.context.workspace_material} : {}), ...(state.context.source_scope ? {source_scope:state.context.source_scope} : {}) };
  }
  function validInputs(inputs, pack) {
    if (inputs.question_preset && !ownedPresetQuestion(inputs, state.selected)) return '请填写与当前自有方法匹配的有效预置研究问题。';
    if (!inputs.as_of || !(inputs.question_preset ? inputs.preset_query || '' : inputs.question).trim() || !inputs.subject.identity.trim()) return '请填写规范标的、明确截止日和研究问题。';
    if (inputs.question_preset && inputs.question && inputs.question !== inputs.preset_query) return '已有研究问题与问题预置冲突；请明确清空原研究问题，或填写相同内容。';
    if (['owned-news-evidence','owned-research-prep'].includes(state.selected) && inputs.cutoff_at) {
      const cutoff = inputs.cutoff_at;
      if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(cutoff) || !Number.isFinite(Date.parse(cutoff))) return '资料截止时刻须包含明确时间与时区。';
      if (new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(cutoff)) !== inputs.as_of) return '资料截止时刻换算为北京时间后须与研究截止日相同。';
    }
    if (pack) {
      const cutoff = inputs.research_scope?.cutoff_at || '';
      if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(cutoff) || !Number.isFinite(Date.parse(cutoff))) return '请填写明确的截止时点与时区，例如 YYYY-MM-DDTHH:mm:ss+08:00。';
      if (new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(cutoff)) !== inputs.as_of) return '截止时点换算为北京时间后须与研究截止日相同。';
      const row = state.items.find(item=>item.id === state.selected);
      for (const method of row.ui_methods || []) for (const field of method.fields) {
        const value = inputs.research_scope?.methods?.[method.id]?.[field.name];
        if (value === undefined || value === '') continue;
        if (field.type === 'securities' && value.some(item=>Object.values(item).some(Boolean) && !['security_id','market','asset_class','currency'].every(key=>item[key]?.trim()))) return `${field.label}须明确填写证券代码、市场、类别与币种。`;
        if (['integer','number'].includes(field.type) && (!Number.isFinite(value) || field.type === 'integer' && !Number.isInteger(value) || field.min !== undefined && value < field.min || field.max !== undefined && value > field.max)) return `${field.label}超出允许范围。`;
        if (field.type === 'instant' && (!/(?:Z|[+-]\d{2}:\d{2})$/.test(value) || !Number.isFinite(Date.parse(value)))) return `${field.label}须包含明确时间与时区。`;
      }
    }
    return '';
  }
  async function preview() {
    if (state.restoreBlocked || state.busy || state.previewing || state.materialLoading || state.request || account() !== owner) return;
    const row = state.items.find(item=>item.id === state.selected);
    if (!row?.pack_id && !ownedMethodScene(row)) return;
    const inputs = structuredClone(state.inputs);
    if (!['owned-news-evidence','owned-research-prep'].includes(state.selected) || !inputs.cutoff_at) delete inputs.cutoff_at;
    if (!['owned-company-evidence','owned-research-prep'].includes(state.selected) || !inputs.question_preset) { delete inputs.question_preset; delete inputs.preset_query; }
    state.error = validInputs(inputs, !!row?.pack_id);
    if (state.error) { changed(); return; }
    const ticket = generation, revision = inputRevision;
    state.previewing = true; state.preview = null; changed();
    try {
      const result = sourceMode() ? await api.sourceSelectionPreview(sourceBody(inputs)) : await api.scenarioPrepare(row.id, requestBody(inputs));
      if (current(ticket) && revision === inputRevision) { state.preview = sourceMode() ? {...result,...(ownedMethodScene(row) ? {method_qualification:result.qualification} : {pack_qualification:result.qualification})} : result; state.stale = false; }
    } catch (error) {
      if (current(ticket) && revision === inputRevision) state.error = error.sourceInput ? error.message : `${failureReason(error).join('')} 输入与选择已保留；只读预览未创建研究草稿。`;
      logger('scenario_pack_preview_failed', {code:error.code || 'request_failed'});
    } finally { if (current(ticket)) { state.previewing = false; changed(); } }
  }
  async function prepare() {
    if (state.restoreBlocked || state.busy || state.materialLoading || state.request || account() !== owner) return;
    const selected = state.items.find(row => row.id === state.selected);
    if (!selected || selected.capabilities.some(x => !x.available)) { state.error = '此场景所需能力当前不可执行；输入已保留。'; changed(); return; }
    if (selected.subject_kinds && !selected.subject_kinds.includes(state.inputs.subject.kind)) { state.error = '当前观察类型与场景不符；请明确选择独立研究身份，不推断证券与行业关系。'; changed(); return; }
    const inputs = structuredClone(state.inputs);
    if (!['owned-news-evidence','owned-research-prep'].includes(state.selected) || !inputs.cutoff_at) delete inputs.cutoff_at;
    if (!['owned-company-evidence','owned-research-prep'].includes(state.selected) || !inputs.question_preset) { delete inputs.question_preset; delete inputs.preset_query; }
    state.error = validInputs(inputs, selected.pack_id);
    if (state.error) { changed(); return; }
    if (selected.pack_id && (!state.preview?.pack_qualification?.executable_methods?.length || state.preview.pack_qualification.status === 'blocked')) { state.error = '请先完成只读资格预览；缺少来源或完整方法参数时不能准备可发送草稿。'; changed(); return; }
    if (sourceMode() && !state.preview?.preview_sha256) { state.error = '请先核验已保存原文的只读预览。'; changed(); return; }
    let body;
    try { body = sourceMode() ? {...sourceBody(inputs),preview_sha256:state.preview.preview_sha256} : requestBody(inputs); }
    catch (error) { state.error = error.message; changed(); return; }
    state.request = { key: makeID(), body }; persist(); state.busy = true; changed();
    try { const result = sourceMode() ? await api.sourceSelectionFreeze(body, state.request.key) : await api.handoff(body, state.request.key); if (account() === owner) state.result = result; }
    catch (error) {
      // Only a server proof made under the creation lock permits correction.
      // Error codes (including 404) alone say nothing about a prior intent.
      const notCreated = error.handoffOutcome === 'not_created' && error.status >= 400 && error.status < 500;
      const [reason, correction] = failureReason(error);
      state.error = notCreated ? `${reason}未创建研究草稿，输入与选择已保留。${correction}` : `${reason}创建结果尚未确认，输入与原请求已保留；请仅查询原请求，不会自动重新提交。`;
      if (notCreated) { state.request = null; state.preview = null; state.stale = true; }
      logger('scenario_prepare_failed', { code: error.code || 'request_failed' });
    } finally { state.busy = false; persist(); changed(); }
  }
  async function lookup() {
    if (!state.request || state.busy || account() !== owner) return;
    state.busy = true; changed();
    try { const result = await api.handoffRequest(state.request.key); if (account() === owner) state.result = result; state.error = ''; }
    catch (error) { state.error = `${failureReason(error)[0]}创建结果尚未确认，原请求已保留；请仅查询原请求，不会自动重新提交。`; logger('scenario_receipt_failed', { code: error.code || 'request_failed' }); }
    finally { state.busy = false; persist(); changed(); }
  }
  async function handle(event) {
    const target = event.target;
    if (['input', 'change'].includes(event.type) && target.dataset?.scenarioField) {
      const name = target.dataset.scenarioField;
      if (name === 'source_session') { if (event.type === 'change') await selectMaterialSession(target.value); return true; }
      if (name === 'source_browse') { if (event.type === 'change') await selectSourceSession(target.value); return true; }
      if (name === 'source_ids') {
        const ids = new Set(state.source_ids); if (target.checked) ids.add(target.value); else ids.delete(target.value);
        edit(name,[...ids]); return true;
      }
      edit(name, name === 'material_ids' ? [...[...target.closest('form').querySelectorAll('[name="scenario-material"]:checked')].map(x => x.value), ...(state.context.workspace_material ? ['file:'+state.context.workspace_material.file_id] : [])] : target.value); return true;
    }
    if (event.type === 'submit' && target.matches?.('[data-scenario-form]')) { event.preventDefault(); if (event.submitter?.dataset?.scenarioFreeze !== undefined) await prepare(); return true; }
    const action = target.closest?.('[data-scenario-action]')?.dataset.scenarioAction;
    if (event.type !== 'click' || !action) return false;
    event.preventDefault();
    if (action === 'close') close();
    else if (action === 'preview') await preview();
    else if (action === 'add-security' && !state.request && !state.busy) {
      const control = target.closest('[data-scenario-action]');
      const row = state.items.find(item=>item.id === state.selected);
      const method = row?.ui_methods?.find(item=>item.id === control.dataset.packMethod);
      const field = method?.fields.find(item=>item.name === control.dataset.packField && item.type === 'securities');
      if (field) {
        const existing = state.inputs.research_scope?.methods?.[method.id]?.[field.name] || [];
        if (existing.length < 100) {
          if (!existing.length) edit(`method:${method.id}:${field.name}:0:security_id`, '');
          edit(`method:${method.id}:${field.name}:${Math.max(1,existing.length)}:security_id`, '');
        }
      }
    }
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
    if (event.isComposing || event.keyCode === 229) return false;
    if (event.key === 'Enter' && (event.target.dataset?.scenarioField === 'query' || ['INPUT', 'SELECT'].includes(event.target.tagName))) { event.preventDefault(); return true; }
    if (event.key === 'Escape') { event.preventDefault(); close(); return true; }
    if (event.key !== 'Tab') return false;
    const panel = event.target.closest?.('.scenario-panel');
    const controls = [...(panel?.querySelectorAll('button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled])') || [])];
    const index = controls.indexOf(event.target);
    if (controls.length && (event.shiftKey && index === 0 || !event.shiftKey && index === controls.length - 1)) { event.preventDefault(); controls[event.shiftKey ? controls.length - 1 : 0].focus(); return true; }
    return false;
  }
  return { state, open, close, edit, preview, selectMaterialSession, selectSourceSession, prepare, lookup, handle, key };
}

export function renderScenarioPanel(s) {
  if (!s.open) return '';
  const row = s.items.find(x => x.id === s.selected); const locked = s.busy || !!s.request || !!s.result;
  const options = s.items.filter(x => `${x.name} ${x.description} ${x.coverage.join(' ')}`.toLowerCase().includes(s.query.toLowerCase()));
  const frozen = s.result?.scenario_context;
  return `<div class="d-drawer-backdrop scenario-panel"><aside class="d-drawer" role="dialog" aria-modal="true" aria-label="研究场景"><header><h2>研究场景</h2><button type="button" class="button" data-scenario-action="close">关闭</button></header><form data-scenario-form><div class="d-drawer-body" data-scenario-view="${e(s.selected)}">${s.error ? `<p role="alert" class="notice danger">${e(s.error)}</p>` : ''}${s.loading ? '<p role="status">正在读取当前场景与能力版本…</p>' : ''}<label>搜索场景<input type="search" form="scenario-browse-only" id="scenario-query" data-scenario-field="query" value="${e(s.query)}" ${locked ? 'disabled' : ''}></label><label>场景<select id="scenario-scenario" data-scenario-field="scenario" ${locked ? 'disabled' : ''}><option value="">选择一个场景</option>${options.map(x => `<option value="${e(x.id)}" ${x.id === s.selected ? 'selected' : ''}>${e(x.name)}${x.capabilities.some(c => !c.available) ? ' · 能力不可用' : ''}</option>`).join('')}</select></label>${!options.length ? '<p>没有匹配的场景。</p>' : ''}${row ? `<section><h3>${e(row.name)}</h3><p>${e(row.coverage.join('；'))}</p><ol>${row.steps.map(x => `<li>${e(x)}</li>`).join('')}</ol><p>当前能力：${row.capabilities.map(x => `${e(x.id)} ${x.available ? `v${e(x.version)} · 发送资格 ${e(stateLabel(x.execution_status))}` : e(x.code || '不可用')}`).join('；')}</p><p>示例：${e(row.examples[0].question)}</p><p>输出：${e(row.expected_artifacts.map(artifactLabel).join('；'))}</p></section>` : ''}${row?.subject_kinds && !row.subject_kinds.includes(s.inputs.subject?.kind) ? '<p class="notice warning">当前证券不是行业身份，尚无可核验的行业关联。<button type="button" class="button" data-scenario-action="independent">另行填写独立行业身份</button></p>' : ''}<fieldset ${locked ? 'disabled' : ''}><legend>冻结研究输入</legend>${['owned-company-evidence','owned-research-prep'].includes(s.selected) ? `<label>固定问题预置<select data-scenario-field="question_preset"><option value="">使用原研究问题</option>${(s.selected === 'owned-company-evidence' ? [['company_one_pager','公司简报问题'],['fundamental_analysis','基本面核验问题']] : [['research_outline','调研提纲问题']]).map(([value,label])=>`<option value="${value}" ${s.inputs.question_preset === value ? 'selected' : ''}>${label}</option>`).join('')}</select></label>${s.inputs.question_preset ? `<label>预置研究问题<input type="text" data-scenario-field="preset_query" value="${e(s.inputs.preset_query || '')}"></label><p>只使用已选规范主体与原件；不从问题解析证券或自动取数。原研究问题须为空或与此处相同。</p>` : ''}` : ''}${['owned-news-evidence','owned-research-prep'].includes(s.selected) ? `<label>资料截止时刻（含时区）<input type="text" data-scenario-field="cutoff_at" value="${e(s.inputs.cutoff_at || '')}" placeholder="YYYY-MM-DDTHH:mm:ss+08:00"></label><p>可不填；缺失时不执行版本去重。不得自动补造截止时刻。</p>` : ''}<label>标的类型<select id="scenario-kind" data-scenario-field="kind" ${s.context?.observation_id ? 'disabled' : ''}>${['stock', 'industry', 'topic'].map(kind => `<option value="${kind}" ${s.inputs.subject?.kind === kind ? 'selected' : ''}>${({ stock:'证券', industry:'行业分类', topic:'独立主题' })[kind]}</option>`).join('')}</select></label><label>规范身份<input id="scenario-identity" data-scenario-field="identity" value="${e(s.inputs.subject?.identity || '')}" placeholder="600600.SH / SW:801080 / 主题" ${s.context?.observation_id ? 'readonly' : ''}></label><label>研究截止<input type="date" id="scenario-as_of" data-scenario-field="as_of" value="${e(s.inputs.as_of || '')}" required></label>${row?.required_inputs.includes('window_start') ? `<label>历史起点<input type="date" id="scenario-window_start" data-scenario-field="window_start" value="${e(s.inputs.window_start || '')}" required></label>` : ''}<label>研究问题<textarea rows="4" maxlength="6000" id="scenario-question" data-scenario-field="question" ${ownedPresetQuestion(s.inputs, s.selected) ? '' : 'required'}>${e(s.inputs.question || '')}</textarea></label>${packScope(row, s.inputs, locked)}${sourcePicker(s, row, locked)}${s.material_mode !== 'sources' || !sourcePack(row) ? `<legend>已取得资料（仅勾选项）</legend>${row?.pack_id && s.context?.material_sessions?.length && !s.context.observation_id && !s.context.workspace_material ? `<label>选择本人已有材料的原会话<select id="scenario-source-session" data-scenario-field="source_session" ${locked ? 'disabled' : ''}><option value="">选择一个原会话</option>${s.context.material_sessions.map(item=>`<option value="${e(item.id)}" ${item.id === s.context.session_id ? 'selected' : ''}>${e(item.title || item.id)}</option>`).join('')}</select></label><p>只读取该会话已取得材料，不自动查询来源；下方勾选后再预览。</p>` : ''}${s.materialLoading ? '<p role="status">正在读取本人原会话材料…</p>' : ''}${s.context?.workspace_material ? `<p>另含已确认资料合同 ${e(s.context.workspace_material.file_id)} 与其原件引用；明确来源范围：${e((s.context.source_scope || []).map(x=>({datahub:'数据快照',uploads:'已有文件／上传资料',web:'联网与网页资料'})[x]).join('、'))}。</p>` : ''}${s.datasets.map(x => `<label><input type="checkbox" name="scenario-material" data-scenario-field="material_ids" value="${e(x.dataset_id)}" ${s.inputs.material_ids.includes(x.dataset_id) ? 'checked' : ''}>${e(x.name || x.capability || x.dataset_id)} · ${e(x.as_of || '日期未提供')}</label>`).join('') || '<p>当前没有已选快照，将保留资料缺口。原输入附件仍保留在原草稿。</p>'}` : ''}</fieldset>${packQualification(s.preview, s.stale)}${frozen ? `<section><h3>${s.result?.state === 'prepared' ? '已准备草稿' : '准备状态待确认'} · ${e(stateLabel(frozen.scenario.status))}</h3><p>截止 ${e(frozen.scenario.inputs.as_of)} · ${e(frozen.scenario.inputs.subject.identity)}</p><ul>${frozen.requirements.map(x => `<li>${e(x)}</li>`).join('')}</ul><p>准备成功不表示证据齐全或质量通过。进入问答后，明确发送才启动模型。</p></section>` : ''}</div><footer>${s.result?.state === 'prepared' ? '<button class="button primary" type="button" data-scenario-action="open">确认冻结资料，进入研究草稿</button>' : s.request ? `<p>${e(stateLabel(s.result?.state))}；不自动重复创建</p><button class="button" type="button" data-scenario-action="lookup" ${s.busy ? 'disabled' : ''}>查询原请求</button>` : `${row?.pack_id || ownedMethodScene(row) ? `<button class="button" type="button" data-scenario-action="preview" ${s.loading || s.busy || s.previewing || s.materialLoading ? 'disabled' : ''}>${s.previewing ? '正在核验资格…' : '只读资格预览'}</button>` : ''}<button class="button primary" type="submit" data-scenario-freeze ${s.loading || s.busy || !row || row.capabilities.some(x=>!x.available) || (row?.pack_id && (!s.preview?.pack_qualification?.executable_methods?.length || s.preview.pack_qualification.status === 'blocked')) ? 'disabled' : ''}>${row?.pack_id ? '明确准备研究草稿' : '冻结资料并准备草稿'}</button>`}</footer></form></aside></div>`;
}
