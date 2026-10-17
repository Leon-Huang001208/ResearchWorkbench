import { e, list } from './aihot-common.mjs';
import { safeLog } from './core.mjs';

export const sections = {sources:'信源',content:'采编内容',runs:'阶段与出刊',settings:'标准与预算',models:'模型配置',audit:'审计',evaluation:'模型评测'};
const readAction = {sources:'source.list',content:'content.list',runs:'runs',settings:'settings',models:'models',audit:'audit'};
const json = value => JSON.stringify(value, null, 2);
export function createNewsManagement({fetcher = (...args) => fetch(...args), onChange = () => {}} = {}) {
  const state = {section:'sources',loading:false,status:null,data:null,error:'',notice:'',selection:null};
  let revision=0, pending;
  async function request(path, body, signal) {
    const response = await fetcher(`/api/research/ai-news/${path}`, {method:body ? 'POST' : 'GET',credentials:'same-origin',headers:{Accept:'application/json',...(body ? {'Content-Type':'application/json'} : {})},...(body ? {body:JSON.stringify(body)} : {}),signal});
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail?.message || `操作未完成（${response.status}），请检查服务状态、配置或版本冲突。`);
    return result;
  }
  function cancel() { revision++; pending?.abort(); state.loading=false; }
  async function activate(section='sources') {
    cancel(); const ticket=revision; const current=new AbortController();pending=current;
    Object.assign(state,{section:Object.hasOwn(sections,section) ? section : 'sources',loading:true,error:'',notice:'',data:null,selection:null,draft:null,preview:null,sourceDetail:null});onChange();
    const timer=setTimeout(()=>current.abort(),25000);
    try {
      const status=await request('status',null,current.signal);
      if (ticket!==revision) return;
      state.status=status;
      if (readAction[state.section] && state.status.state==='running') {
        const data=await request('control',{action:readAction[state.section],input:{}},pending.signal);
        if (ticket!==revision) return;state.data=data;
      }
      safeLog('ai_news_management_loaded',{status:'completed'});
    } catch (error) { if(ticket===revision)state.error=error.name==='AbortError' ? '管理服务读取超时，请重试。' : error.message;safeLog('ai_news_management_failed',{status:'failed'}); }
    finally {clearTimeout(timer);if(ticket===revision){state.loading=false;onChange();}}
  }
  async function action(action,input) {
    if(state.loading)return;
    const ticket=revision; state.loading=true;state.error='';state.notice='';onChange();
    try {
      const result=await request('control',{action,input});
      if(ticket!==revision)return;
      if(action==='source.create' && result.created===false)throw new Error(`未创建：已存在相同信源 ${result.duplicate?.name || result.duplicate?.id || ''}。`);
      if(action==='source.detail'){state.selection=result.source || result;state.sourceDetail=result;state.draft=null;state.preview=null;}
      else if(action==='source.preview')state.preview=result;
      else {
        state.notice='已保存，配置变更不代表采集或模型已获授权。';
        if(action==='source.update') {const detail=await request('control',{action:'source.detail',input:{id:input.id}});if(ticket!==revision)return;state.selection=detail.source || detail;state.sourceDetail=detail;state.draft=null;}
        const data=await request('control',{action:readAction[state.section],input:{}});if(ticket!==revision)return;state.data=data;
      }
      safeLog('ai_news_management_action',{status:'completed'});
    } catch(error){if(ticket===revision)state.error=error.message;safeLog('ai_news_management_action_failed',{status:'failed'});}
    finally{if(ticket===revision){state.loading=false;onChange();}}
  }
  async function submit(form, submitter) {
    try {
      const values=Object.fromEntries(new FormData(form,submitter));
      if(form.dataset.newsForm==='source') {
        state.draft={id:values.id,name:values.name,kind:values.kind,configText:values.config,tier:values.tier,interval_minutes:values.interval,participation_mode:values.mode,site_fulltext:values.fulltext==='on',enabled:values.enabled==='on',reason:values.reason};
        const input={id:values.id,name:values.name,kind:values.kind,config:JSON.parse(values.config),tier:values.tier,interval_minutes:Number(values.interval),participation_mode:values.mode,site_fulltext:values.fulltext==='on',syndicate_fulltext:false};
        if(values.operation==='preview')return await action('source.preview',input);
        if(state.selection)return await action('source.update',{id:state.selection.id,version:state.selection.updated_at,reason:values.reason,patch:{name:input.name,config:input.config,tier:input.tier,interval_minutes:input.interval_minutes,participation_mode:input.participation_mode,site_fulltext:input.site_fulltext,enabled:values.enabled==='on'}});
        return await action('source.create',input);
      }
      if(form.dataset.newsForm==='budget')return await action('budget.update',{service:values.service,perMinute:Number(values.minute),perHour:Number(values.hour),perDay:Number(values.day),reason:values.reason});
      if(form.dataset.newsForm==='model')return await action('model.update',{capability:values.capability,model:values.model || null,reason:values.reason});
      if(form.dataset.newsForm==='receipt')return await action('receipt.release',{id:Number(values.id),billed:values.billed==='true',note:values.note});
      if(form.dataset.newsForm==='requeue')return await action('processing.requeue',{group:values.group || null,reason:values.reason});
    } catch {state.error='配置格式有误，请检查 JSON、数值和必填字段。';safeLog('ai_news_form_invalid',{status:'failed'});onChange();}
  }
  return {state,activate,cancel,action,submit};
}
function sourceForm(source={}, editing=Boolean(source.id)) {
  return `<form data-news-form="source" class="aihot-panel"><h2>${editing ? '编辑信源' : '添加信源'}</h2><div class="ai-news-fields"><label>标识<input name="id" required pattern="[a-z0-9][a-z0-9-]{2,79}" value="${e(source.id || '')}" ${editing ? 'readonly' : ''}></label><label>名称<input name="name" required maxlength="200" value="${e(source.name || '')}"></label><label>类型<select name="kind" ${editing ? 'disabled' : ''}>${Object.entries({rss:'RSS',web_list:'网页',json_list:'JSON',x_search:'X（待凭据与预算）',mp_account:'微信公众号（待凭据与预算）',external:'外部推送（待接入密钥）'}).map(([key,label])=>`<option value="${key}" ${key===source.kind ? 'selected' : ''}>${label}</option>`).join('')}</select>${editing ? `<input type="hidden" name="kind" value="${e(source.kind)}">` : ''}</label><label>等级<select name="tier">${['T1','T1_5','T2','EXCLUDE_MP'].map(key=>`<option ${key===(source.tier || 'T2') ? 'selected' : ''}>${key}</option>`).join('')}</select></label><label>间隔（分钟）<input name="interval" type="number" min="1" max="1440" value="${e(source.interval_minutes || 30)}" required></label><label>参与方式<select name="mode">${['editorial','hot_signal','isolated'].map(key=>`<option ${key===source.participation_mode ? 'selected' : ''}>${key}</option>`).join('')}</select></label></div><label>采集规则（原引擎 JSON；请勿填写秘密）<textarea name="config" rows="8" required>${e(source.configText ?? json(source.config || {feedUrl:''}))}</textarea></label><label><input type="checkbox" name="fulltext" ${source.site_fulltext ? 'checked' : ''}>允许站内全文（须有来源许可）</label>${editing ? `<label><input type="checkbox" name="enabled" ${source.enabled ? 'checked' : ''}>启用信源（仍受全局采集授权门控制）</label><label>修改原因<input name="reason" value="${e(source.reason || '')}" required></label>` : ''}<div class="aihot-reading-actions"><button type="submit" name="operation" value="save">保存配置</button><button type="submit" name="operation" value="preview">免费试抓</button>${editing ? '<button type="button" data-news-new>新建另一个信源</button>' : ''}</div><p>RSS 使用 feedUrl；网页使用 url、itemSelector、titleSelector、linkSelector；JSON 使用 url、itemsPath 和字段映射。X 使用 query；公众号使用真实 wxid/ghid。凭据仅由本机凭据库接收，付费试抓在此阶段拒绝。</p></form>`;
}
export function renderNewsManagement(state) {
  const sources=list(state.data?.rows);
  const table=sources.length ? `<div class="ai-news-table"><table><thead><tr><th>信源</th><th>类型</th><th>状态</th><th>近7日</th><th></th></tr></thead><tbody>${sources.map(row=>`<tr><td>${e(row.name)}</td><td>${e(row.kind)}</td><td>${e(row.health)} · ${row.enabled ? '启用' : '暂停'}</td><td>${e(row.items_7d ?? '—')}</td><td><button data-news-source="${e(row.id)}">编辑与记录</button></td></tr>`).join('')}</tbody></table></div>` : '<p>暂无信源记录；服务就绪后可添加自己的信源。</p>';
  let body=state.section==='sources' ? `${table}${sourceForm(state.draft || state.selection || {},Boolean(state.selection))}${state.selection ? `<details class="aihot-panel" open><summary>采集运行、内容、统计与审计历史</summary><pre>${e(json(state.sourceDetail))}</pre></details>` : ''}${state.preview ? `<details class="aihot-panel" open><summary>本次免费试抓结果</summary><pre>${e(json(state.preview))}</pre></details>` : ''}` : `<pre class="ai-news-json">${e(json(state.data || {}))}</pre>`;
  if(state.section==='runs')body=`<section class="aihot-panel"><h2>采编阶段与失败恢复</h2>${body}<form data-news-form="receipt"><h3>人工核账后释放未知回执</h3><p>先在供应商账单核对本次请求，再填写结论与证据。结果仍不明时保持等待；此操作可能恢复原任务，仍受当前授权与预算门限制。</p><label>回执编号<input name="id" type="number" min="1" required></label><label>账单结论<select name="billed"><option value="true">已确认计费</option><option value="false">已确认未计费</option></select></label><label>核账依据<textarea name="note" required></textarea></label><button>记录核账并释放</button></form><form data-news-form="requeue"><h3>重排失败处理</h3><label>失败分组（空白为近30天全部失败）<input name="group"></label><label>恢复原因<input name="reason" required></label><button>按当前授权重排</button></form></section>`;
  if(state.section==='settings')body=`<section class="aihot-panel"><h2>精选标准与出刊</h2><p>保留原版预筛、两次独立评分、中文写作、翻译、归组与综述。固定原版入选门槛：T1 60、T1_5 65、T2 76，两次独立评分之和须达到两倍门槛；EXCLUDE_MP不参与精选，理解加工门槛50。这些是规则配置，不是实测质量分数。当前供应商预算、通知状态如下。</p><p>北京时间：日报08:00，周一周报10:00，每月1日月报10:30。未知付费结果必须人工核账，不自动重发。</p>${body}<form data-news-form="budget"><h3>调整持久预算</h3><label>服务标识<input name="service" required></label>${[['minute','每分钟'],['hour','每小时'],['day','每天']].map(([key,label])=>`<label>${label}<input name="${key}" type="number" min="0" required value="0"></label>`).join('')}<label>原因<input name="reason" required></label><button>保存预算</button></form></section>`;
  if(state.section==='models')body=`<section class="aihot-panel"><h2>任务模型</h2><p>模型与本地量化候选尚未实测，评测状态 NOT_RUN。保存已注册模型的任务映射不会授予推理权限；秘密通过本机凭据库配置。</p>${body}<form data-news-form="model"><label>任务 capability<input name="capability" required></label><label>已注册模型标识（留空使用原默认）<input name="model"></label><label>原因<input name="reason" required></label><button>保存映射</button></form></section>`;
  if(state.section==='evaluation')body='<section class="aihot-panel"><h2>云端与本地对照实验</h2><p>50篇真实原始素材、20组有原文证据的关系提案，参考标注待人工核对。覆盖中文、英文、长文与低信息样本；调参与留出集隔离。</p><p>逐任务检查精选、事实与数字、翻译、归组和综述，再比较完整流水线。耗时、失败率、内存与费用均为 NOT_RUN，质量分数为空。</p><p>可执行脚本 scripts/ai_news_eval.py；冻结清单 evals/ai_news/corpus-reference-20261017；标注与运行说明见 docs/ai-news-model-evaluation.md。24 GiB 本地模型共存条件尚待验证，不安装模型。</p></section>';
  return `<section class="aihot-page ai-news-manage" aria-busy="${Boolean(state.loading)}"><nav class="aihot-module-bar"><a href="#/aihot/daily">← 阅读资讯</a><strong>自主采编管理</strong><button data-aihot-refresh ${state.loading ? 'disabled' : ''}>刷新</button></nav><nav class="aihot-reading-actions" aria-label="采编管理栏目">${Object.entries(sections).map(([key,label])=>`<a href="#/aihot/manage?section=${key}" ${key===state.section ? 'aria-current="page"' : ''}>${label}</a>`).join('')}</nav><section class="aihot-panel"><h1>${sections[state.section]}</h1><p>本机原版引擎 · ${e(state.status?.state || '正在检查')} · 模型验收 NOT_RUN</p><p>从自主库重新起刊；不读取 AIHOT 线上接口、图片或历史刊物。采集、推理、付费源与生产切换分别受授权门控制。</p></section>${state.error ? `<p role="alert" class="notice danger">${e(state.error)}</p>` : ''}${state.notice ? `<p role="status">${e(state.notice)}</p>` : ''}${state.loading ? '<p role="status">正在读取管理状态…</p>' : body}</section>`;
}
