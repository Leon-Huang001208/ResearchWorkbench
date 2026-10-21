import { escapeHTML as e } from './markdown.mjs';
import { icon } from './icons.mjs';
import { modelOptions } from './views.mjs';
import { modelConfigurationPayload, syncModelForm } from './settings.mjs';

const providers = Object.freeze([
  { id: 'deepseek-official', name: 'DeepSeek 官方', domain: 'platform.deepseek.com', category: 'official', search: 'deepseek 官方 深度求索 platform.deepseek.com' },
  { id: 'openai-compatible', name: '自定义兼容服务', domain: '手动填写请求地址和模型', category: 'custom', search: '自定义 openai compatible 兼容 本机 custom' },
]);
export const matchingModelProviders = (query = '', category = 'all') => providers.filter(item => (category === 'all' || item.category === category) && item.search.includes(query.trim().toLowerCase()));
const logo = item => `<span class="mp-logo">${item.provider === 'deepseek-official' ? '<img src="/static/assets/providers/deepseek.svg" alt="DeepSeek">' : icon(item.credential_mode === 'none' ? 'terminal' : 'share')}</span>`;
const credentialLabel = item => item.uncertain ? '提交结果未知' : item.credential_required === false || item.credential_mode === 'none' ? '无需 Key' : item.credential_configured === true ? '凭据已配置' : item.credential_configured === false ? '未配置凭据' : '凭据状态未知';
const notice = text => text ? `<div class="notice warning" role="status">${e(text)}</div>` : '';
const button = (action, label, disabled = false, extra = '') => `<button class="button" type="button" data-mp-action="${action}" ${disabled ? 'disabled' : ''} ${extra}>${label}</button>`;
const labelFor = id => providers.find(item => item.id === id)?.name || '未知服务商';

export function renderModelProfileList({ items = [], runtime = {}, busy = false, loading = false, error = '' } = {}) {
  const disabled = busy || !runtime.owned_runtime;
  const test = runtime.last_model_test;
  const testLabel = test?.status === 'passed' ? '已收到最终文本' : test ? `失败：${test.code || 'model_generation_failed'}` : '未测试';
  return `<div class="mp-header"><h1>模型服务</h1><div class="button-row">${button('add','＋ 添加服务商',disabled,'data-primary')}</div></div>
    <div class="mp-status"><span>运行时 · ${runtime.connected ? '已连接' : '未连接或待确认'}</span><span>生成验证 · ${e(testLabel)}</span></div>${notice(error)}${runtime.configuration_uncertain ? notice('凭据提交结果未知；请重新录入或明确清除后再继续。') : ''}${!runtime.owned_runtime ? notice('当前运行时不可管理，暂时不能修改连接。') : ''}
    <h2 class="mp-section-label">已添加的服务商</h2><div class="mp-list">${items.map(item => `<section class="mp-card ${item.active ? 'is-active' : ''}">${logo(item)}<div class="mp-identity"><h3>${e(item.name)} <span class="badge">${item.provider === 'deepseek-official' ? '官方' : item.credential_mode === 'none' ? '本机' : '兼容服务'}</span></h3><p>${e(item.provider === 'deepseek-official' ? 'https://platform.deepseek.com' : item.base_url)}</p><p class="mp-mobile-facts">${e(item.model)} · ${e(credentialLabel(item))}</p></div><div class="mp-facts"><span>${e(item.model)}</span><span>${e(credentialLabel(item))}</span></div><div class="mp-actions">${item.active ? '<span class="mp-current">使用中</span>' : button('activate',icon('arrowRight'),disabled || item.uncertain,`data-profile="${e(item.id)}" aria-label="将${e(item.name)}设为当前" title="设为当前"`)}${button('edit',icon('pencil'),busy,`data-profile="${e(item.id)}" aria-label="编辑${e(item.name)}" title="编辑连接"`)}<details class="mp-more"><summary data-mp-action="more" data-profile="${e(item.id)}" aria-label="${e(item.name)}的更多操作">${icon('more')}</summary><div class="mp-menu">${button('diagnostics','连接与测试',busy,`data-profile="${e(item.id)}"`)}${button('archive','移除连接',disabled,`data-profile="${e(item.id)}"`)}</div></details></div></section>`).join('')}</div>${loading ? '<p class="muted" role="status">正在读取连接…</p>' : !items.length ? '<p class="muted">尚未添加服务商。</p>' : ''}
    <p class="muted small">当前连接用于新研究。已有会话保留原连接；研究运行中或状态未确认时不能切换。</p><details class="mp-diagnostics" data-mp-runtime-info><summary>运行时信息</summary><dl class="runtime-details"><div><dt>版本</dt><dd>${e(runtime.version || '未知')}</dd></div><div><dt>配置保存</dt><dd>${runtime.configuration_saved === true ? '已保存' : runtime.configuration_saved === false ? '尚未保存' : '未知'}</dd></div><div><dt>运行时应用</dt><dd>${runtime.runtime_applied === true ? '已应用于新会话' : '待新会话应用或连接确认'}</dd></div><div><dt>凭据存储</dt><dd>${e(({system_keychain:'系统 Keychain',docker_encrypted:'本实例加密存储',docker_encrypted_file:'加密文件存储',not_required:'无需凭据'})[runtime.credential_storage] || '未知')}</dd></div></dl>${button('refresh','刷新状态',busy,'data-refresh')}</details>`;
}

function renderPicker(query, category) {
  return `<header class="mp-editor-heading">${button('back',icon('chevronLeft'),false,'aria-label="返回服务商列表"')}<h1>添加服务商</h1></header><label class="mp-search">${icon('search')}<input type="search" data-mp-search placeholder="搜索服务商名称或网址" value="${e(query)}" aria-label="搜索服务商"></label><div class="mp-catalog"><nav aria-label="服务商分类">${[['all','全部','2'],['official','模型厂商','1'],['custom','自定义连接','1']].map(([id,label,count]) => `<button type="button" data-mp-category="${id}" aria-pressed="${category === id}">${label}<span>${count}</span></button>`).join('')}</nav><div><p class="muted small">选择服务商，下一步配置连接。</p><div class="mp-choices" data-mp-choices>${renderChoices(query,category)}</div><p class="muted small">同一家服务商可以添加多个独立连接。</p></div></div>`;
}
function renderChoices(query, category) {
  const matches = matchingModelProviders(query,category);
  return matches.length ? matches.map(item => `<button class="mp-choice" type="button" data-mp-provider="${item.id}">${logo({provider:item.id})}<span><strong>${item.name}</strong><small>${item.domain}</small></span></button>`).join('') : '<p class="muted" role="status">没有匹配的服务商。</p>';
}

export function renderModelProfileForm({ item, models = [], busy = false, runtime = {} }) {
  const compatible = item.provider === 'openai-compatible';
  const keyless = compatible && item.credential_mode === 'none';
  const groups = models.filter(group => (group.id || group.provider) === 'deepseek-official');
  const available = groups.flatMap(group => group.models || []);
  const official = available.some(model => model.id === item.model) ? available : [{ id:item.model, name:item.model },...available];
  const locked = busy || !runtime.owned_runtime;
  const disabled = locked ? 'disabled' : '';
  return `<header class="mp-editor-heading">${button('back',icon('chevronLeft'),busy,'aria-label="返回"')}<h1>${item.id ? '编辑连接' : '添加服务商'}</h1></header>${item.uncertain ? notice('此连接的凭据提交结果未知，请重新录入或明确清除。') : ''}${!runtime.owned_runtime ? notice('当前运行时不可管理，暂时不能修改连接。') : ''}<div class="mp-form-heading">${logo(item)}<span>${labelFor(item.provider)}</span>${!item.id ? button('change','更换',busy) : ''}</div>
    <form id="settings-form" class="mp-form" autocomplete="off"><select id="provider" name="provider" hidden><option value="${item.provider}" selected>${labelFor(item.provider)}</option></select>
      <label for="connection-name">连接名称</label><input id="connection-name" name="name" maxlength="80" required value="${e(item.name || '')}" ${disabled}>
      ${compatible ? '' : `<label for="settings-model">默认模型</label><select id="settings-model" ${disabled}>${official.map(model => `<option value="${e(model.id)}" ${model.id === item.model ? 'selected' : ''}>${e(model.name || model.id)}</option>`).join('')}</select>`}
      ${!compatible ? `<input id="model-id" name="model" type="hidden" value="${e(item.model || '')}" ${disabled}>` : ''}
      <div data-compatible-settings ${compatible ? '' : 'hidden'}><label for="profile-base-url">服务地址</label><input id="profile-base-url" name="base_url" type="url" required value="${e(item.base_url || '')}" placeholder="https://api.example.com/v1" ${!compatible || locked ? 'disabled' : ''}>${compatible ? `<label for="model-id">模型 ID</label><input id="model-id" name="model" required value="${e(item.model || '')}" placeholder="填写服务商提供的模型 ID" ${disabled}>` : ''}<label for="profile-authentication">认证方式</label><select id="profile-authentication" name="credential_mode" ${!compatible || locked ? 'disabled' : ''}><option value="api_key" ${!keyless ? 'selected' : ''}>API Key</option><option value="none" ${keyless ? 'selected' : ''}>本机服务，无需 Key</option></select><p class="muted small">OpenAI Chat Completions；仅文本/流式已验证。工具能力未验证，localhost 指当前后端设备。新地址须重新录入专用 Key。</p></div>
      <div data-mp-key ${keyless ? 'hidden' : ''}><label for="api-key">API Key</label><input id="api-key" name="api_key" type="password" autocomplete="new-password" spellcheck="false" ${locked || keyless ? 'disabled' : ''} placeholder="${item.id ? '留空保留此连接的已有凭据' : '可先保存连接，使用前配置专用 Key'}"><p class="muted small">各连接独立存储。提交即清空，不回填。</p></div><p data-mp-keyless class="muted small" ${keyless ? '' : 'hidden'}>此连接无需 API Key，仅限本机回环地址。</p>
      <details class="mp-diagnostics"><summary>高级连接设置</summary>${compatible ? `<label for="settings-model">目录模型（可选）</label><select id="settings-model" ${disabled}>${modelOptions(models.filter(group=>(group.id||group.provider)===item.provider),item.model,item.base_url).replace('选择运行模型','手动填写模型 ID')}</select>` : ''}<p class="muted small">协议：${compatible ? 'OpenAI Chat Completions' : 'DeepSeek 官方'}。修改已激活连接的模型或地址时，请添加新连接并显式切换，保留原会话绑定。</p></details>
      <details class="mp-diagnostics" data-mp-diagnostics><summary>连接与测试</summary><p class="muted small">凭据：${e(credentialLabel(item))}</p><p class="muted small">真实测试会调用当前连接，消耗模型额度，最长等待 93 秒，并保留测试会话。连接成功或保存成功不代表生成成功。</p>${button('test','测试真实生成',locked || !item.active,'data-model-test')}${item.active ? '' : '<p class="muted small">请先将此连接设为当前再测试。</p>'}${button('clear','清除凭据',locked || !item.id || keyless,'data-model-clear')}${item.id ? button('archive','移除连接',locked,`data-profile="${e(item.id)}"`) : ''}</details>
      <div data-mp-feedback role="status"></div><footer class="mp-footer"><span class="muted small">仅影响新研究默认连接</span>${button('cancel','取消',busy)}<button class="button primary" type="submit" ${disabled}>保存连接</button></footer></form>`;
}

export function createModelSettings({ api, runtime = {}, models = [], busy = false, changed = async () => {}, logger = () => {} }) {
  const element = document.createElement('section'); element.className = 'model-profile-workspace'; element.dataset.modelProfilesRoot = '';
  let inputs = {runtime,models,busy}, items = [], view = 'list', selected = null, query = '', category = 'all', loading = false, pending = false, error = '', draftForm = null, disposed = false, requestGeneration = 0, returnId = null, runtimeInfoOpen = false;
  const locked = () => pending || inputs.busy || !inputs.runtime?.owned_runtime;
  const focus = selector => (element.querySelector(selector) || (view==='list' ? element.querySelector('[data-mp-action="add"]') : null))?.focus({preventScroll:true});
  const form = () => element.querySelector('#settings-form');
  function report(exception) { error = exception?.message || '模型连接操作未完成，请刷新后确认状态。'; logger('model_profile_action_failed',{code:exception?.code || 'model_profile_action_failed'}); const feedback=element.querySelector('[data-mp-feedback]'); if(feedback)feedback.innerHTML=notice(error); else render(); }
  function positionFooter() {
    const footer=element.querySelector('.mp-footer');if(!footer)return;
    const rect=element.getBoundingClientRect();footer.style.left=`${Math.max(0,rect.left)}px`;footer.style.width=`${Math.min(640,Math.max(0,Math.min(rect.right,window.innerWidth)-Math.max(0,rect.left)))}px`;
  }
  window.addEventListener('resize',positionFooter);
  function sync() {
    if(!form()){element.querySelectorAll('button').forEach(button=>{button.disabled=pending||inputs.busy||(!inputs.runtime?.owned_runtime&&button.dataset.mpAction!=='back');});return;}
    syncModelForm(form(), {busy:locked()});
    const keyless = selected?.provider === 'openai-compatible' && form().querySelector('[name="credential_mode"]').value === 'none';
    form().querySelector('[data-mp-key]').hidden=keyless; form().querySelector('[data-mp-keyless]').hidden=!keyless;
    element.querySelectorAll('button').forEach(button=>{ if(button.dataset.mpAction==='test')button.disabled=locked()||!selected?.active; else if(button.dataset.mpAction==='clear')button.disabled=locked()||!selected?.id||keyless; else button.disabled=pending || inputs.busy || (!inputs.runtime?.owned_runtime && !['cancel','back'].includes(button.dataset.mpAction)); });
  }
  function render() {
    if(disposed)return;
    const previousRuntimeInfo=element.querySelector('[data-mp-runtime-info]');if(previousRuntimeInfo)runtimeInfoOpen=previousRuntimeInfo.open;
    element.innerHTML=view==='list' ? renderModelProfileList({items,...inputs,busy:pending||inputs.busy,loading,error}) : view==='pick' ? renderPicker(query,category) : renderModelProfileForm({item:selected,...inputs,busy:pending||inputs.busy});
    if(view==='edit'&&draftForm){element.querySelector('#settings-form').replaceWith(draftForm);draftForm=null;}
    const nextRuntimeInfo=element.querySelector('[data-mp-runtime-info]');if(nextRuntimeInfo)nextRuntimeInfo.open=runtimeInfoOpen;
    if(view==='edit')sync(); positionFooter();
  }
  async function refresh() {
    const generation=++requestGeneration; loading=true;if(view==='list')render();
    try { const result=await api.modelProfiles();if(disposed||generation!==requestGeneration)return;if(!Array.isArray(result?.items))throw Error('模型连接列表不可读取，请刷新状态。');items=result.items;error=''; }
    catch(exception){if(generation===requestGeneration)report(exception);}
    finally { if(generation===requestGeneration){loading=false;if(view==='list')render();} }
  }
  function open(item) { returnId=item?.id||null;selected=item?{...item}:null;query='';category='all';draftForm=null;error='';view=item?'edit':'pick';render();focus(item?'#connection-name':'[data-mp-search]'); }
  function back() {
    if(pending)return;
    if(view==='edit'&&!selected.id){draftForm=form();view='pick';render();focus('[data-mp-search]');}
    else {view='list';draftForm=null;render();focus(returnId?`[data-mp-action="edit"][data-profile="${returnId}"]`:'[data-mp-action="add"]');}
  }
  async function operation(work, success) {
    if(pending)return;const activeControl=document.activeElement?.closest?.('[data-mp-action]');const previousFocus=activeControl&&element.contains(activeControl)?{action:activeControl.dataset.mpAction,profile:activeControl.dataset.profile}:null;pending=true;sync(); if(view==='list')render();
    try { const result=await work();if(disposed)return;await success?.(result);logger('model_profile_action_completed'); }
    catch(exception){if(!disposed)report(exception);}
    finally {pending=false;if(!disposed){if(view==='list'){render();const previous=previousFocus?[...element.querySelectorAll('[data-mp-action]')].find(node=>node.dataset.mpAction===previousFocus.action&&node.dataset.profile===previousFocus.profile):null;if(previous&&!previous.disabled)previous.focus({preventScroll:true});else focus(returnId?`[data-mp-action="edit"][data-profile="${returnId}"]`:'[data-mp-action="add"]');}else sync();}}
  }
  element.addEventListener('toggle',event=>{if(event.target.matches?.('.mp-more[open]'))element.querySelectorAll('.mp-more').forEach(menu=>{if(menu!==event.target)menu.open=false;});},true);
  const closeMenus=event=>element.querySelectorAll('.mp-more[open]').forEach(menu=>{if(!menu.contains(event.target))menu.open=false;});
  document.addEventListener('click',closeMenus);
  element.addEventListener('input', event=>{event.stopPropagation();if(event.target.matches('[data-mp-search]')){query=event.target.value;element.querySelector('[data-mp-choices]').innerHTML=renderChoices(query,category);} });
  element.addEventListener('change', event=>{event.stopPropagation();if(event.target.id==='settings-model'&&event.target.value){let model=event.target.value;try{model=JSON.parse(model).model;}catch{}form().querySelector('#model-id').value=model;}if(event.target.name==='credential_mode')sync();if(event.target.name==='base_url'){const choices=form().querySelector('#settings-model');if(choices)choices.innerHTML=modelOptions(inputs.models.filter(group=>(group.id||group.provider)===selected.provider),form().querySelector('#model-id').value,event.target.value).replace('选择运行模型','手动填写模型 ID');}});
  element.addEventListener('keydown',event=>{event.stopPropagation();if(event.isComposing)return;if(event.key==='Escape'){const more=element.querySelector('.mp-more[open]');if(more){more.open=false;more.querySelector('summary').focus();}else if(view!=='list')back();event.preventDefault();}if(event.key==='Enter'&&event.target.matches('[data-mp-search]')){event.preventDefault();element.querySelector('[data-mp-provider]')?.click();}});
  element.addEventListener('click',event=>{
    event.stopPropagation();closeMenus(event);
    const categoryButton=event.target.closest('[data-mp-category]');
    if(categoryButton){category=categoryButton.dataset.mpCategory;render();focus(`[data-mp-category="${category}"]`);return;}
    const providerButton=event.target.closest('[data-mp-provider]');
    if(providerButton){const provider=providerButton.dataset.mpProvider;selected={...(selected||{}),provider,name:selected?.name|| (provider==='deepseek-official'?'DeepSeek 官方':''),model:provider==='deepseek-official'?(inputs.models.find(group=>group.id===provider)?.models?.[0]?.id||'deepseek-flash'):'',credential_mode:'api_key',credential_configured:false};if(draftForm?.querySelector('#provider')?.value!==provider)draftForm=null;view='edit';render();focus('#connection-name');return;}
    const target=event.target.closest('[data-mp-action]');if(!target||target.disabled)return;
    const action=target.dataset.mpAction, item=items.find(row=>row.id===target.dataset.profile)||selected;
    if(action==='add'){open();return;}if(action==='edit'||action==='diagnostics'){open(item);if(action==='diagnostics'){element.querySelector('[data-mp-diagnostics]').open=true;focus('[data-mp-action="test"]');}return;}
    if(action==='back'||action==='change'){back();return;}if(action==='cancel'){view='list';draftForm=null;render();focus(returnId?`[data-mp-action="edit"][data-profile="${returnId}"]`:'[data-mp-action="add"]');return;}
    if(action==='refresh'){operation(async()=>{await changed();await refresh();});return;}
    if(action==='activate'){if(locked())return;operation(()=>api.activateModelProfile(item.id),async()=>{await changed();await refresh();returnId=item.id;});return;}
    if(action==='archive'){if(locked()||!window.confirm('从列表移除此连接？已有会话、日程绑定和凭据将保留。'))return;operation(()=>api.archiveModelProfile(item.id),async()=>{view='list';await refresh();});return;}
    if(action==='test'){if(locked()||!selected?.active)return;operation(()=>api.testModel(),async result=>{if(result.status!=='passed')throw Error(`真实生成测试失败：${result.code||'model_generation_failed'}`);await changed();element.querySelector('[data-mp-feedback]').textContent='已收到真实生成的最终文本；工具能力需单独验证。';});return;}
    if(action==='clear'){if(!selected?.id||locked()||!window.confirm('清除此连接的模型凭据？绑定此连接的研究将暂时不可用，已有会话仍保留。'))return;submit(true);}
  });
  async function submit(clear=false) {
    if(locked())return;
    const node=form(), values=new FormData(node);node.querySelector('#api-key').value='';
    let payload;
    try {payload={...modelConfigurationPayload(values,{clear}),name:String(values.get('name')||'').trim()};if(!payload.name)throw Error('请填写连接名称');}
    catch(exception){values.delete('api_key');report(exception);return;}
    values.delete('api_key');
    await operation(()=>{const promise=api.saveModelProfile(selected.id,payload);delete payload.api_key;return promise;},async()=>{view='list';draftForm=null;await changed();await refresh();focus('[data-mp-action="add"]');});
    delete payload.api_key;
  }
  element.addEventListener('submit',event=>{event.preventDefault();event.stopPropagation();submit();});
  render();refresh();
  return {element,update(next){inputs={...inputs,...next};if(view==='list')render();else {sync();positionFooter();}},dispose(){disposed=true;document.removeEventListener('click',closeMenus);window.removeEventListener('resize',positionFooter);requestGeneration++;const key=form()?.querySelector('#api-key');if(key)key.value='';const draftKey=draftForm?.querySelector('#api-key');if(draftKey)draftKey.value='';draftForm=null;}};
}
