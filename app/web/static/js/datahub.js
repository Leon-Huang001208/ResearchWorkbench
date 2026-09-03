/* Live DataHub controls. Source values are always rendered as text, never HTML. */
const $ = id => document.getElementById(id);
let catalog = [], offset = 0, snapshot = null, generation = 0, timer;
const labels = {codes:'证券代码（逗号分隔）',start_date:'开始日期',end_date:'结束日期',date:'截面日期',dates:'截面日期列表（逗号分隔）',factors:'因子名称（逗号分隔）',table_name:'表名',universe:'板块',indicator:'指标名称@表名',fields:'查询字段（逗号分隔）',cycle:'周期',rate:'复权方式'};
const extras = {daily_quotes:['cycle','rate','fields'],factor_data:['date','dates'],table_data:['start_date','end_date','fields'],macro_data:['start_date','end_date'],stock_list:['date'],fund_list:['date'],codes:['date'],trading_days:['cycle']};
function message(text, error=false){ $('message').textContent=text; $('message').classList.toggle('error',error); }
async function api(path, body){
  const controller = new AbortController(), timeout = setTimeout(()=>controller.abort(),20000);
  try {
    const headers = {'Content-Type':'application/json'};
    if(body !== undefined){const token=await fetch('/api/config/token',{signal:controller.signal}); if(!token.ok)throw new Error('无法取得本机操作权限'); headers['X-AlphaFoundry-Config-Token']=(await token.json()).token;}
    const response=await fetch('/api/datahub'+path,{method:body===undefined?'GET':'POST',headers,body:body===undefined?undefined:JSON.stringify(body),signal:controller.signal});
    if(!response.ok){throw new Error(`请求失败（HTTP ${response.status}）`);}
    return await response.json();
  } finally {clearTimeout(timeout);}
}
function node(tag,text,className){const el=document.createElement(tag);el.textContent=text;if(className)el.className=className;return el;}
function fields(){
  snapshot=null;offset=0;const item=catalog.find(x=>x.dataset===$('dataset').value);if(!item)return;
  $('fields').replaceChildren();$('result-head').replaceChildren();$('result-body').replaceChildren();$('result-meta').textContent='选择数据集后浏览。';$('page-label').textContent='';$('previous').disabled=true;$('next').disabled=true;
  for(const key of [...new Set([...item.required,...(extras[item.dataset]||[])])]){
    const label=node('label',labels[key]||key);let input;
    if(key==='rate'||key==='cycle'){
      input=document.createElement('select');
      const options=key==='rate'?['前复权','不复权','后复权']:item.dataset==='trading_days'?['D','W','M','Q','H','Y']:['day','1m','5m','15m','30m','60m','120m'];
      options.forEach(x=>{const option=node('option',x);option.value=x;input.append(option);});
    }else{input=document.createElement('input');input.type=['start_date','end_date','date'].includes(key)?'date':'text';}
    input.addEventListener('change',()=>{offset=0;snapshot=null;generation++;});input.dataset.param=key;input.required=item.required.includes(key);label.append(input);$('fields').append(label);
  }
  $('coverage').textContent=item.last_sync?`最近批次 ${item.last_sync} · ${item.row_count} 行 · 隔离 ${item.quarantined_count} 行`:'尚未同步。目录数据也需同步后查看。';
}
function dictionary(value){const result={};for(const line of value.split('\n').map(x=>x.trim()).filter(Boolean)){const at=line.indexOf('=');if(at<1||!line.slice(at+1).trim())throw new Error('请使用“名称=值”格式');result[line.slice(0,at).trim()]=line.slice(at+1).trim();}return result;}
async function browse(){
  const ticket=++generation;
  const q=new URLSearchParams({dataset:$('dataset').value,offset:String(offset),limit:'50',include_quarantined:String($('show-quarantine').checked)});if(snapshot)q.set('snapshot_id',snapshot);
  if(!snapshot){document.querySelectorAll('[data-param]').forEach(input=>{const key=input.dataset.param,value=input.value.trim();if(!value)return;if(['start_date','end_date','cycle','table_name','indicator'].includes(key))q.set(key,value);if(key==='date'){q.set('start_date',value);q.set('end_date',value);}if(key==='codes'&&!/[,，]/.test(value))q.set('symbol',value);if(key==='rate')q.set('adjustment',{'前复权':'forward','后复权':'backward','不复权':'none'}[value]);if(key==='fields')value.split(/[,，]/).map(x=>x.trim()).filter(Boolean).forEach(x=>q.append('fields',x));});}
  const result=await api('/records?'+q);if(ticket!==generation)return;
  const columns=result.columns||[];
  $('result-head').replaceChildren();$('result-body').replaceChildren();const head=document.createElement('tr');['状态／质量','研究引用',...columns,'来源／事实 ID'].forEach(x=>head.append(node('th',x)));$('result-head').append(head);
  for(const record of result.records){const row=document.createElement('tr');row.classList.toggle('quarantined',record.freshness_status==='quarantined');const status=node('td',record.freshness_status);status.title=record.quality_flags.join(', ')+' · '+record.as_of+' · '+JSON.stringify(record.units);row.append(status);const action=document.createElement('td');const cite=node('button','引用到研究');cite.disabled=record.freshness_status==='quarantined';cite.addEventListener('click',()=>safe(async()=>{if(!$('cite-project').value.trim()||!$('cite-workspace').value.trim()||!$('cite-run').value.trim())throw new Error('请先填写研究引用区域的项目、Workspace 和 Run ID');const cited=await api('/research-evidence',{dataset:result.dataset,fact_id:record.fact_id,project_id:$('cite-project').value.trim(),workspace_id:$('cite-workspace').value.trim(),run_id:$('cite-run').value.trim()});message('已加入研究证据：'+cited.evidence_ref);}));action.append(cite);row.append(action);for(const key of columns){const value=record.payload.source_fields[key];const cell=node('td',value===null?'缺失':typeof value==='object'?JSON.stringify(value):String(value??''));cell.title=cell.textContent;row.append(cell);}const identity=node('td','CJPY · '+record.fact_id.slice(0,12)+'…');identity.title=record.fact_id;row.append(identity);$('result-body').append(row);}
  $('result-meta').textContent=`${result.freshness_status} · ${result.total} 行 · 隔离 ${result.quarantined_count||0} 行 · ${result.coverage_start||'—'} 至 ${result.coverage_end||'—'}`;
  $('page-label').textContent=`${result.records.length?offset+1:0}–${offset+result.records.length} / ${result.total}`;$('previous').disabled=offset===0;$('next').disabled=offset+50>=result.total;
}
async function loadRuns(){
  const result=await api('/runs');$('runs').replaceChildren();
  for(const run of result.runs){const row=node('div','', 'run');row.append(node('strong',run.dataset),node('span',run.status,'status'),node('span',`已存 ${run.saved} 行 · 失败批次 ${run.failed_batches} · 尝试 ${run.attempt}`));for(const batch of run.batches){if(!batch.snapshot_id)continue;const button=node('button','查看批次');button.addEventListener('click',()=>safe(async()=>{$('dataset').value=run.dataset;fields();snapshot=batch.snapshot_id;await browse();}));row.append(button);}$('runs').append(row);}
  clearTimeout(timer);if(result.runs.some(x=>['idle','leased','running'].includes(x.status)))timer=setTimeout(()=>safe(loadRuns),3000);
}
async function refresh(){
  const [sources,found]=await Promise.all([api('/sources'),api('/catalog')]);catalog=found.datasets;$('sources').replaceChildren();sources.sources.forEach(x=>{const card=node('div',x.name,'source');card.append(node('small',`${x.enabled?'已注册':'已禁用'} · ${x.version||x.health}`));$('sources').append(card);});
  const selected=$('dataset').value;$('dataset').replaceChildren();catalog.forEach(x=>{const option=node('option',x.name);option.value=x.dataset;$('dataset').append(option);});if(selected)$('dataset').value=selected;fields();await loadRuns();message(`已连接共享事实库 · ${sources.count} 个注册来源`);
}
async function safe(fn){try{await fn();}catch(error){console.error('[DataHub]',error);message(error.message,true);}}
$('dataset').addEventListener('change',()=>{generation++;fields();});$('refresh').addEventListener('click',()=>safe(refresh));$('browse').addEventListener('click',()=>{offset=0;safe(browse);});$('show-quarantine').addEventListener('change',()=>{offset=0;safe(browse);});
$('previous').addEventListener('click',()=>{offset=Math.max(0,offset-50);safe(browse);});$('next').addEventListener('click',()=>{offset+=50;safe(browse);});
$('health-check').addEventListener('click',()=>safe(async()=>{const status=await api('/sources/cjpy/health',{});$('health').textContent=`${status.status} · CJPY ${status.version||'未安装'} · ${status.reason||'连接正常'}`;}));
$('sync-form').addEventListener('submit',event=>{event.preventDefault();safe(async()=>{
  const button=event.submitter;button.disabled=true;
  try{const params={};document.querySelectorAll('[data-param]').forEach(input=>{if(input.value.trim())params[input.dataset.param]=['codes','factors','fields','dates'].includes(input.dataset.param)?input.value.split(/[,，]/).map(x=>x.trim()).filter(Boolean):input.value.trim();});if($('units').value.trim())params.column_units=dictionary($('units').value);if($('factor-repo').value.trim())params.repo=dictionary($('factor-repo').value);if($('date-field').value.trim())params.date_field=$('date-field').value.trim();
    const job=await api('/runs',{dataset:$('dataset').value,params,idempotency_key:crypto.randomUUID()});message(`同步任务已创建：${job.job_id}`);await loadRuns();
  }finally{button.disabled=false;}
});});
window.addEventListener('pagehide',()=>{clearTimeout(timer);generation++;});safe(refresh);
