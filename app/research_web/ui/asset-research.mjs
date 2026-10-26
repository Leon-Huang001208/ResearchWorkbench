import { escapeHTML as e } from './markdown.mjs';
import { safeLog } from './core.mjs';
import { cleanAsset } from './asset-navigation.mjs';

const quality = value => ({passed:'当前报告质量通过',incomplete:'当前报告证据不完整',invalid:'当前报告无效',not_assessed:'未形成质量结论'})[value] || '尚未核验';
const scopes = {datahub:'数据快照',uploads:'已有文件／上传资料',web:'联网与网页资料'};
const valueText = value => value === null || value === undefined ? '未提供' : typeof value === 'object' ? JSON.stringify(value) : String(value);
const keyFor = (observation, route) => observation && (!route.asset || cleanAsset(route.asset) === cleanAsset(observation.asset)) && (!route.assetType || route.assetType === observation.asset_type) ? `${observation.id}:${observation.asset}` : '';

export function createAssetResearchController({api,changed=()=>{},onResearch,logger=safeLog,account=()=>String(globalThis.__RWB_USER_ID__ || 'local')}={}) {
  const state={active:false,key:'',tab:'summaries',catalog:null,preview:null,material:null,comparisons:[],recordIndices:{},scope:['datahub'],asOf:'',question:'',loading:false,error:''};
  const owner=account();let generation=0;
  function deactivate(){generation++;state.active=false;state.key='';state.preview=null;state.catalog=null;state.error='';}
  async function activate(observation,route={}) {
    const key=keyFor(observation,route);
    if(!key || account()!==owner){if(state.key)deactivate();return;}
    if(state.active && state.key===key)return;
    generation++;Object.assign(state,{active:true,key,observation,comparisons:[],material:null,preview:null,catalog:null,scope:['datahub'],recordIndices:{},asOf:observation.request_parameters?.end_date || '',question:`基于已选原件研究 ${observation.asset}，区分事实、观点与资料声明。`,error:''});
    await refresh(true);
  }
  async function refresh(catalog=false) {
    if(!state.active || account()!==owner)return;
    const ticket=++generation, oid=state.observation.id;
    state.loading=true;state.error='';changed();
    try {
      if(catalog){const result=await api.assetResearchCatalog(oid);if(ticket!==generation || account()!==owner)return;state.catalog=result;}
      const result=await api.assetResearchPreview({observation_id:oid,comparison_observation_ids:[...state.comparisons],material:state.material});
      if(ticket!==generation || !state.active || account()!==owner)return;
      if(result.asset!==state.observation.asset || result.observation_id!==oid)throw new Error('返回的证券资料不属于当前工作区。');
      state.preview=result;state.material=result.material;
    } catch(error){if(ticket===generation){state.error=error.message || '原件无法核验，请保留原版本并检查来源权限。';state.preview=null;}logger('asset_research_read_failed',{code:error.code || 'request_failed'});}
    finally{if(ticket===generation){state.loading=false;changed();}}
  }
  async function importFile(file) {
    if(!file || state.loading || !state.catalog?.can_import || account()!==owner)return;
    const ticket=++generation, oid=state.observation.id;state.loading=true;state.error='';changed();
    try {
      const result=await api.assetResearchImport(oid,file);
      if(ticket!==generation || !state.active || account()!==owner)return;
      state.material=result.material;state.loading=false;await refresh(true);
    }catch(error){if(ticket===generation)state.error=error.message || '研究资料导入失败，未开始研究。';logger('asset_research_import_failed',{code:error.code || 'request_failed'});}
    finally{if(ticket===generation){state.loading=false;changed();}}
  }
  async function research() {
    if(state.loading || !state.preview || account()!==owner)return;
    if(!state.asOf || !state.question.trim()){state.error='请明确填写研究截止日和问题。';changed();return;}
    if(state.preview.required_source_scope.some(scope=>!state.scope.includes(scope))){state.error='所选文件或网页需要额外来源范围，请明确勾选后再准备。';changed();return;}
    const datasets=state.preview.comparisons.flatMap(item=>item.datasets.map(dataset=>({...dataset,name:`${item.role==='subject'?'主体':'比较'} ${item.asset}`,as_of:item.records[0]?.as_of})));
    await onResearch({session_id:state.observation.session_id,observation_id:state.observation.id,subject:{kind:'stock',identity:state.observation.asset},as_of:state.asOf,question:state.question,datasets,comparison_observation_ids:[...state.comparisons],workspace_material:state.preview.material,source_scope:[...state.scope],mode:'fingpt'});
  }
  async function handle(event) {
    const target=event.target;
    if(!target.closest?.('[data-asset-research]'))return false;
    if(event.type==='input' && target.dataset?.assetResearchField){state[target.dataset.assetResearchField]=target.value;return true;}
    if(event.type==='change') {
      if(target.dataset?.assetResearchPeer!==undefined){const oid=target.value;if(target.checked && !state.comparisons.includes(oid) && state.comparisons.length<4)state.comparisons.push(oid);if(!target.checked)state.comparisons=state.comparisons.filter(x=>x!==oid);await refresh();return true;}
      if(target.dataset?.assetResearchMaterial!==undefined){const selected=state.catalog.materials.find(x=>`${x.source_session_id}:${x.file_id}`===target.value);state.material=selected?{source_session_id:selected.source_session_id,file_id:selected.file_id,sha256:selected.sha256}:null;await refresh();return true;}
      if(target.dataset?.assetResearchUpload!==undefined){await importFile(target.files?.[0]);return true;}
      if(target.dataset?.assetResearchScope){const scope=target.dataset.assetResearchScope;state.scope=target.checked?[...new Set([...state.scope,scope])]:state.scope.filter(x=>x!==scope);changed();return true;}
      if(target.dataset?.assetResearchRecord){state.recordIndices[target.dataset.assetResearchRecord]=Number(target.value);changed();return true;}
    }
    const action=target.closest?.('[data-asset-research-action]')?.dataset.assetResearchAction;
    if(event.type!=='click' || !action)return false;
    event.preventDefault();
    if(action==='refresh')await refresh(true);
    else if(action==='research')await research();
    else if(['summaries','comparisons','relations'].includes(action)){state.tab=action;changed();}
    return true;
  }
  return {state,activate,deactivate,refresh,handle,importFile,research};
}

function proofs(items) {
  return `<ul class="ar-proofs">${items.map(item=>`<li><a href="${e(item.url)}" target="_blank" rel="noopener noreferrer">核对原件：${e(item.title || item.reference.id)}</a><blockquote>${e(item.locator.quote)}</blockquote><small>${e(item.source || '来源未命名')} · ${item.locator.kind==='json-cell'?`原始行 ${item.locator.row+1}／字段 ${e(item.locator.field)}`:`文本字符 ${item.locator.start}–${item.locator.end}`} · SHA-256 ${e(item.sha256)}</small></li>`).join('')}</ul>`;
}
function summaries(s){return s.preview.summaries.map(item=>`<article class="ar-card"><h3>${e(item.title)}</h3><p class="ar-state">分析观点／引用摘录 · ${quality(item.quality)}</p><p class="ar-summary">${e(item.text)}</p>${proofs(item.evidence)}${item.quality_contract?`<small>当前质量合同 ${e(item.quality_contract)}</small>`:''}</article>`).join('') || '<p>尚未选择带来源的研究摘要。可选择已保存资料，或下载模板后导入；不自动生成观点。</p>'}
function comparisons(s) {
  const items=s.preview.comparisons;
  const selected=items.map(item=>({...item,selected:item.records[s.recordIndices[item.observation_id] || 0]}));
  const fields=[...new Set(selected.flatMap(item=>Object.keys(item.selected?.values || {})))].filter(key=>!['asset','report_period','period','date'].includes(key)).slice(0,40);
  return `<p class="ar-state">明确选择的比较对象，不自动认定同业。原值并列；不同报告期、单位或口径不排名、不换算、不混算。</p><div class="ar-table-wrap"><table><thead><tr><th>原字段</th>${selected.map(item=>`<th>${item.role==='subject'?'主体':'比较'} ${e(item.asset)}<label>报告记录<select id="ar-record-${e(item.observation_id)}" data-asset-research-record="${e(item.observation_id)}">${item.records.map((row,index)=>`<option value="${index}" ${(s.recordIndices[item.observation_id] || 0)===index?'selected':''}>${e(row.period || '报告期未提供')} · ${e(row.source || '来源未提供')} · 原始行 ${row.row+1}</option>`).join('')}</select></label></th>`).join('')}</tr></thead><tbody>${fields.map(field=>`<tr><th>${e(field)}</th>${selected.map(item=>{const row=item.selected,unit=row?.units?.[field];return `<td><strong>${e(valueText(row?.values?.[field]))}</strong><small>${e(unit?.unit || '单位未提供')} · ${e(unit?.currency || '币种未提供')} · ${e(unit?.basis || '口径未提供')}</small></td>`}).join('')}</tr>`).join('')}<tr><th>原件与版本</th>${selected.map(item=>`<td>${item.selected?`<a href="${e(item.selected.url)}" target="_blank" rel="noopener noreferrer">查看完整原件</a><small>数据截至 ${e(item.selected.as_of || '未提供')}<br>取得 ${e(item.selected.retrieved_at || '未提供')}<br>Manifest ${e(item.selected.manifest_sha256)}</small>${item.selected.truncated_rows?`<p>还存在 ${item.selected.truncated_rows} 条原始记录，本预览仅含前100条。</p>`:''}`:'该观察尚无可读财务或估值快照。'}</td>`).join('')}</tr></tbody></table></div>${items.length<2?'<p>请至少再选择一家公司形成并列对照；最多含主体在内5个对象。</p>':''}`;
}
function relations(s){return s.preview.relations.map(item=>`<article class="ar-card"><h3>${e(item.from_identity)} → ${e(item.to_identity)}</h3><p>${e(item.relation)}</p><p class="ar-state">资料声明 · 待核验</p>${proofs(item.evidence)}</article>`).join('') || '<p>尚无带原件定位的产业关系。未从名称、行业字段或相似标题推断关联；可导入带来源的关系声明。</p>'}

export function renderAssetResearch(s) {
  if(!s.active)return '<section class="asset-research-workspace"><h2>研究摘要、可比与产业交叉</h2><p>等待当前证券观察就绪后读取本人已有资料。</p></section>';
  const preview=s.preview,disabled=s.loading?'disabled':'';
  return `<section class="asset-research-workspace" data-asset-research><header><div><h2>研究摘要、可比与产业交叉</h2><p>${e(s.observation.asset)} · 仅本人已取得原件</p></div><button type="button" class="button" data-asset-research-action="refresh" ${disabled}>重新核对原件</button></header>${s.error?`<p class="notice danger" role="alert">${e(s.error)}</p>`:''}${s.loading?'<p role="status">正在核对资料身份、版本和来源权限…</p>':''}<div class="ar-selectors"><fieldset ${disabled}><legend>选择比较观察（最多4项）</legend>${(s.catalog?.observations || []).filter(item=>item.asset!==s.observation.asset).map(item=>`<label><input type="checkbox" id="ar-peer-${e(item.id)}" data-asset-research-peer value="${e(item.id)}" ${s.comparisons.includes(item.id)?'checked':''} ${!s.comparisons.includes(item.id)&&s.comparisons.length>=4?'disabled':''}>${e(item.asset)} · 截止 ${e(item.as_of || '未提供')}</label>`).join('') || '<p>还没有其他本人证券观察；先在资产页取得明确对象资料。</p>'}</fieldset><div><label>选择已保存资料<select id="asset-research-material" data-asset-research-material ${disabled}><option value="">仅查看已选财务快照</option>${(s.catalog?.materials || []).map(item=>`<option value="${e(item.source_session_id+':'+item.file_id)}" ${s.material?.file_id===item.file_id&&s.material?.source_session_id===item.source_session_id?'selected':''}>${e(item.title || item.name)} · ${e(item.subject || '')}${item.saved_at?` · 保存于 ${e(new Date(item.saved_at).toLocaleDateString('zh-CN',{timeZone:'Asia/Shanghai'}))}`:''}</option>`).join('')}</select></label><div class="button-row"><a class="button" href="/api/research/assets/research/template/${e(s.observation.id)}">下载研究资料模板</a><label class="button">导入研究资料<input type="file" id="asset-research-import" data-asset-research-upload accept="application/json,.json" ${s.catalog?.can_import&&!s.loading?'':'disabled'}></label></div><details><summary>资料格式与边界</summary><p>版本 asset-research-workspace/v1；subject为规范证券。summaries记录观点文字与evidence；relations记录from_identity、to_identity、relation及evidence。每条引用必须包含source_session_id、reference、真实sha256和json-cell或text精确定位。模板中只有现有原件摘录，关系需明确填写并引用原文。quality字段不可自报。</p><p>${e(s.catalog?.coverage || '')}</p></details></div></div><nav role="tablist" aria-label="研究资料工作区">${[['summaries','研究摘要'],['comparisons','可比对照'],['relations','产业交叉']].map(([id,label])=>`<button type="button" role="tab" aria-selected="${s.tab===id}" id="ar-tab-${id}" data-asset-research-action="${id}">${label}${preview?` · ${id==='comparisons'?preview.comparisons.length:preview[id].length}`:''}</button>`).join('')}</nav><div class="ar-panel" role="tabpanel">${preview?(s.tab==='summaries'?summaries(s):s.tab==='comparisons'?comparisons(s):relations(s)):'资料核验完成后展示内容；读取失败不会用旧内容替代。'}</div><footer><label>研究截止<input type="date" id="asset-research-cutoff" data-asset-research-field="asOf" value="${e(s.asOf)}"></label><label class="ar-question">继续研究的问题<input id="asset-research-question" data-asset-research-field="question" value="${e(s.question)}" maxlength="6000"></label>${(preview?.required_source_scope || []).filter(scope=>scope!=='datahub').map(scope=>`<label><input type="checkbox" data-asset-research-scope="${scope}" ${s.scope.includes(scope)?'checked':''}>明确使用${scopes[scope]}范围</label>`).join('')}<button type="button" class="button primary" data-asset-research-action="research" ${s.loading||!preview?'disabled':''}>用已确认资料准备研究</button></footer></section>`;
}
