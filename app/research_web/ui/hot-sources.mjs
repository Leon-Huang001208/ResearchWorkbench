import {escapeHTML as e} from './markdown.mjs';
const labels={scheduled:'已接入计划采集',paused:'已暂停',awaiting_catalog:'尚未接入持续采集',catalog_mismatch:'目录或运营主体不匹配'};
export function renderHotSources(state,disabled,time){
 return `<div class="hot-source-grid">${state.sources.map(source=>`<article class="hot-card"><h2>${e(source.operator)}</h2><p>${e(labels[source.collection_state]||'采集能力未核验')} · ${e(source.latest_snapshot?.coverage==='latest_snapshot'?'最新快照':source.latest_snapshot?.coverage||'尚无取得记录')}</p><dl><dt>最近成功</dt><dd>${e(time(source.last_success_at))}</dd><dt>待解析条目</dt><dd>${e(source.pending_items??'未知')}</dd><dt>已知缺口／错误</dt><dd>${e(source.last_error_code||source.latest_snapshot?.gap?.code||'未记录；不等于完整覆盖')}</dd></dl><p class="small muted">覆盖发布区间 ${e(time(source.latest_snapshot?.oldestPublishedAt))} — ${e(time(source.latest_snapshot?.newestPublishedAt))}</p>${source.catalog_activation_code?'<p class="notice">目录激活权限未就绪：停止 Hot 后运行 rwb hot setup 更新最小权限，再启动。</p>':''}<form data-hot-form="source" data-hot-form-key="source:${e(source.id)}:${e(source.config_revision)}"><input type="hidden" name="sourceId" value="${e(source.id)}"><label>运行选择<select name="enabled"><option value="true" ${source.enabled?'selected':''}>启用</option><option value="false" ${!source.enabled?'selected':''}>暂停</option></select></label><label>采集间隔（秒，0 使用默认值）<input name="frequencySeconds" type="number" min="0" max="86400" step="1" required value="${e(source.frequency_seconds??0)}"></label><label><input type="checkbox" name="useCatalog" ${!source.catalog_activation_allowed?'disabled':''}> 明确按已验证公开目录接入</label><label>目录激活理由<textarea name="reason" maxlength="1000"></textarea></label><p class="small muted">60–86400 秒或 0；目录由服务端固定，不接受网址或凭据。保存不会授权模型。</p><button class="button primary" ${disabled}>保存来源配置</button></form></article>`).join('')||'<p class="muted">暂无来源状态。</p>'}</div>`;
}
export function hotSourceSubmission(values,state,uuid){
 const source=state.sources.find(row=>row.id===String(values.get('sourceId'))),enabled=String(values.get('enabled')),rawFrequency=String(values.get('frequencySeconds'));
 if(!source||!['true','false'].includes(enabled)||!/^\d+$/.test(rawFrequency))throw Error('请核对来源与采集间隔。');
 const frequency=Number(rawFrequency);
 if(!Number.isSafeInteger(frequency)||frequency!==0&&(frequency<60||frequency>86400))throw Error('采集间隔须为60–86400秒或0。');
 const body={sourceId:source.id,expectedRevision:source.config_revision,enabled:enabled==='true',frequencySeconds:frequency,requestId:uuid()};
 if(values.get('useCatalog')==='on'){
  const reason=String(values.get('reason')||'').trim();
  if(!source.catalog_activation_allowed||!reason||reason.length>1000)throw Error('目录激活需权限就绪并填写理由。');
  Object.assign(body,{useCatalog:true,reason});
 }
 return {method:'hotSourceConfigure',body};
}
