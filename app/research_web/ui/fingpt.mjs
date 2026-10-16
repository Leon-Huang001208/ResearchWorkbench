// Native Research Workbench UI. Host owns execution; changing pages never resubmits.
import { escapeHTML as e, renderMarkdown } from './markdown.mjs';
import { safeLog } from './core.mjs';
import { newAiMsg, reduceAi, readSSE } from './fingpt-stream.mjs';
import { FEATURED_CASES } from './fingpt-cases.mjs';
import { icon } from './icons.mjs';

export const FINGPT_ENGINE = 'fingpt-qa-v1';
export const TASK_PRESETS = [
  {title:'盘前早报',prompt:'请建立盘前早报任务：拉取自选股隔夜行情、核查舆情公告并形成有来源的早报；需要定时时先确认时间。'},
  {title:'持仓技术扫描',prompt:'请建立持仓技术扫描任务：遍历指定持仓，按真实行情计算MA/MACD/RSI并记录信号及失效条件。'},
  {title:'行业一页纸批量',prompt:'请建立行业一页纸批量任务：确认行业清单，逐个检索并生成可核验的一页纸报告和汇总表。'},
];
const MODES = {quick:'快速问答',deep:'深度研究',agent:'Agent'};
const TIERS = {lite:'Lite · MiMo',ultra:'Ultra · MiniMax',frontier:'Frontier · Qwen',kimi:'Kimi（可选）'};
const md = text => renderMarkdown(String(text || '').replace(/\[S(\d+)\]/g,'[doc$1]'));
export function renderMigratedTasks() {
  return `<section class="fq-task-presets"><h3>任务与自动化</h3><p class="small muted">定时、批量与预设任务由 Claw 执行。</p>${TASK_PRESETS.map((t,i)=>`<button class="button" data-fq-task="${i}">${e(t.title)} →</button>`).join('')}</section>`;
}
export function answerFromRound(round) {
  const value=(round.events||[]).reduce((m,ev)=>reduceAi(m,ev),newAiMsg(round.mode,round.tier));
  return {...value,generating:round.status==='running'};
}
function steps(m,sub) {
  return m.tools.filter(t=>sub==null||t.subId===sub).map(t=>`<div class="fq-step ${t.state}"><span>${t.state==='processing'?'◌':t.state==='failed'?'!':'✓'}</span>${t.state==='processing'?'正在检索':t.state==='failed'?'检索失败':'完成检索'}「${e(t.group)}」<span class="muted">${e(t.display)}</span></div>`).join('');
}
export function thinkPanel(m,rid,thinking){
  const done=m.thinkingDone||!m.generating;
  const subs=m.mode==='agent'?[]:m.subs;
  return `<section class="fq-think"><button class="text-button" data-fq-think="${rid}">${m.generating?'<span class="fq-spin" aria-hidden="true"></span>':''}${done?'已完成思考':'思考分析'} ${thinking?'▴':'▾'}</button>${thinking?`${steps(m)}${subs.map(s=>`<h4>${e(s.question)}</h4>${steps(m,s.id)}<p class="fq-reasoning">${e(s.cot)}</p>`).join('')}${m.outline?.sections?.length?`<p class="small muted">写作计划：${e(m.outline.sections.map(x=>x.title).join(' / '))}</p>`:''}<div class="fq-reasoning">${e(m.cot)}</div>${!m.cot&&!m.tools.length?`<div class="fq-reasoning">正在收集资料…</div>`:''}`:''}</section>`;
}
export function renderQAAnswer(m,rid,{thinking=false,full=false}={}) {
  const agent=m.mode==='agent';
  const body=agent?`${m.intro?`<p>${e(m.intro)}</p>`:''}${thinkPanel(m,rid,thinking)}<ol class="fq-plan">${m.plans.map(p=>`<li class="${p.state}"><strong>${p.state==='finished'?'✓':p.state==='processing'?'◌':'○'} ${e(p.question)}</strong>${steps(m,p.id)}${m.files.filter(f=>f.subId===p.id).map(f=>`<div class="fq-step muted">▤ 完成${f.op==='create'?'创建':'修改'}文件 ${e(f.name)}</div>`).join('')}${m.notes.filter(n=>n.subId===p.id).map(n=>`<p class="muted small">${e(n.body.slice(0,100))}…</p>`).join('')}${(m.subs.find(s=>s.id===p.id)?.cot||'')?(p.state==='processing'?`<p class="fq-reasoning">${e(m.subs.find(s=>s.id===p.id).cot)}</p>`:`<details class="fq-subcot"><summary>子任务思考过程</summary><div class="fq-reasoning">${e(m.subs.find(s=>s.id===p.id).cot)}</div></details>`):''}</li>`).join('')}</ol>${m.reflection?'<p class="small muted">✓ 已进行反思复核</p>':''}${m.reportWriting&&m.generating?'<p role="status">正在撰写报告…</p>':''}${m.summary?`<p>${e(m.summary)}</p>`:''}${m.message?`<section class="fq-report"><header><strong>最终报告</strong><button class="text-button" data-fq-full="${rid}">全屏</button><button class="text-button" data-fq-download="${rid}">下载</button></header><div class="markdown">${md(m.message)}</div></section>`:''}${m.generating?`<div class="fq-runbar" role="status">◌ 任务运行中 ${m.progress?.pct||0}%<progress max="100" value="${m.progress?.pct||0}"></progress><span>${e(m.progress?.text||m.status)}</span><button data-fq-stop>停止</button></div>`:''}`
  :`${thinkPanel(m,rid,thinking)}<div class="markdown">${md(m.message)}</div>${m.generating&&m.message?'<span class="fq-caret" aria-hidden="true">▍</span>':''}${m.generating?'<button class="button" data-fq-stop>停止回答</button>':''}`;
  return `<article class="fq-answer" data-fq-round="${rid}">${body}${m.error?`<div class="notice warning">${e(m.error)}</div>`:''}${!m.generating?`<footer class="fq-footer"><button class="text-button" data-fq-refs="${rid}">${agent?`参考${m.sources.length}篇文档 · 生成${m.notes.length}篇笔记`:`${m.sources.length}篇文档`}</button><button data-fq-retry="${rid}">重试</button><button data-fq-copy="${rid}">复制</button></footer>`:''}${!agent&&!m.generating?`<div class="fq-suggestions">${m.suggestions.map(q=>`<button class="button small" data-fq-suggest="${e(q)}">${e(q)}</button>`).join('')}</div>`:''}${full?`<div class="fq-modal" role="dialog" aria-modal="true" aria-label="最终报告"><button class="button" data-fq-close-full>关闭</button><div class="markdown">${md(m.message)}</div></div>`:''}</article>`;
}
export function createFinGPT({getState,onChange,onSession,onTask,onRefresh}) {
  const local={draft:'',mode:'quick',tier:'lite',tiers:null,error:'',notice:'',busy:false,sid:null,detail:null,panel:null,tab:'refs',source:null,full:null,thinking:new Map(),rounds:new Map(),attachments:[],stream:null,votes:new Map()};
  const api=async(path,{method='GET',body,key}={})=>{
    const res=await fetch(`/api/research/${path}`,{method,headers:{...(body instanceof FormData?{}:{'Content-Type':'application/json'}),'X-Research-User-Action':'?1',...(key?{'Idempotency-Key':key}:{})},body:body instanceof FormData?body:body===undefined?undefined:JSON.stringify(body)});
    const j=await res.json();if(!res.ok)throw new Error(j.error?.message||j.detail||'请求未完成，请重试');return j;
  };
  const keepLive=()=>requestAnimationFrame(()=>{for(const el of document.querySelectorAll('.fq-think .fq-reasoning'))if(el.scrollHeight>el.clientHeight+4)el.scrollTop=el.scrollHeight;});
  const current=()=>local.detail&&local.sid===getState().route.sessionId?local.detail:getState().detail;
  const view=round=>{const cached=local.rounds.get(round.id);return cached&&cached.count>=(round.events?.length||0)?cached.m:answerFromRound(round);};
  const refresh=async()=>{if(!local.sid)return;local.detail=await api(`sessions/${local.sid}`);onRefresh?.();onChange();};
  async function follow(sid,round) {
    local.stream?.abort();const ac=new AbortController();local.stream=ac;
    let m=view(round),count=round.events?.length||0;
    local.rounds.set(round.id,{m,count});local.panel=round.id;
    try {
      let ended=false;
      for(let attempt=0;attempt<5&&!ended&&!ac.signal.aborted;attempt++){
        const res=await fetch(`/api/research/fingpt/sessions/${sid}/rounds/${round.id}/events?after=${count}`,{signal:ac.signal});
        if(!res.ok)throw Error('回答流不可用');
        await readSSE(res,(event,data,id)=>{
          if(event==='round_end'){ended=true;m={...m,generating:false};return;}
          if(id&&id<=count)return;
          if(id)count=id;m=reduceAi(m,{event,data});local.rounds.set(round.id,{m,count});onChange();keepLive();
        });
      }
      if(!ended&&!ac.signal.aborted)throw Error('连接中断，刷新可继续读取同一回答');
    }catch(error){if(!ac.signal.aborted){local.error=error.message;safeLog('fingpt_stream_failed');}}
    finally{if(local.stream===ac){local.busy=false;await refresh();}}
  }
  async function activate(detail) {
    if(!local.tiers){try{local.tiers=(await api('fingpt/tiers')).tiers;onChange();}catch{local.error='问答配置暂不可用';onChange();}}
    if(detail?.engine!==FINGPT_ENGINE)return;
    if(local.sid!==detail.id){local.stream?.abort();local.sid=detail.id;local.detail=detail;local.panel=detail.qa_rounds?.at(-1)?.id||null;local.attachments=[];}
    const active=detail.qa_rounds?.find(r=>r.status==='running');
    if(active&&!local.busy){local.busy=true;follow(detail.id,active);}
  }
  async function send(question,forceMode) {
    const msg=String(question??local.draft).trim();if(!msg||local.busy)return;
    local.busy=true;local.error='';local.draft='';onChange();
    try{
      let detail=current();
      if(detail?.engine!==FINGPT_ENGINE){
        const made=await api('fingpt/sessions',{method:'POST',body:{title:msg.slice(0,80),project_id:detail?.project_id||'default',source_session_id:detail?.id||null,source_attachment_ids:detail?.id?(getState().attachments||[]).map(a=>a.id):[]}});
        local.sid=made.id;local.detail={...made,qa_rounds:[]};
        await onSession(made.id);detail=local.detail;
      }
      const res=await api(`fingpt/sessions/${detail.id}/ask`,{method:'POST',body:{msg,mode:forceMode||local.mode,tier:local.tier,attachment_ids:local.attachments.map(a=>a.id)},key:crypto.randomUUID()});
      local.attachments=[];local.detail=await api(`sessions/${detail.id}`);
      const round=local.detail.qa_rounds.find(r=>r.id===res.round_id);local.panel=res.round_id;onChange();
      await follow(detail.id,round);
    }catch(error){local.error=error.message;local.busy=false;safeLog('fingpt_submit_failed');onChange();}
  }
  function workspace(round,m){
    if(!round)return `<aside class="fq-workspace"><h3>精选案例</h3><p class="small muted">点击案例使用 Agent 模式研究</p><div class="fq-cases">${FEATURED_CASES.map((c,i)=>`<button data-fq-case="${i}"><strong>${e(c.title)}</strong><span>${e(c.prompt)}</span></button>`).join('')}</div></aside>`;
    return `<aside class="fq-workspace"><header><strong>${m.mode==='agent'?'Agent工作空间':'参考文件'}</strong><button data-fq-hide-panel>×</button></header><nav><button data-fq-tab="refs" aria-pressed="${local.tab==='refs'}">参考文件</button><button data-fq-tab="notes" aria-pressed="${local.tab==='notes'}">工作笔记</button></nav>${local.tab==='refs'?m.sources.map(s=>`<section class="fq-source ${local.source===s.id?'active':''}" id="fq-${round.id}-${e(s.id)}" tabindex="-1"><small>${e(s.id)} · ${e(s.provider)} · ${e(s.asof)}</small><strong>${e(s.title)}</strong>${s.url?`<a href="${e(s.url)}" target="_blank" rel="noopener noreferrer">查看原文 ↗</a>`:''}</section>`).join('')||'<p class="muted">资料搜集中…</p>':m.notes.map(n=>`<details><summary>▤ ${e(n.title)}</summary><div class="markdown">${md(n.body)}</div></details>`).join('')||'<p class="muted">工作笔记会随子任务完成生成。</p>'}</aside>`;
  }
  function render(detail){
    if(detail?.engine!==FINGPT_ENGINE&&detail)return null;
    detail=current()?.engine===FINGPT_ENGINE?current():detail;
    const rounds=detail?.qa_rounds||[];const selected=rounds.find(r=>r.id===local.panel)||rounds.at(-1);const selectedM=selected?view(selected):null;
    const empty=!rounds.length;
    const chevron='<svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m7 10 5 5 5-5"/></svg>';
    const tierMenu=`<details class="composer-model-menu fq-tier-menu"><summary aria-label="模型档位" title="模型档位">${e(TIERS[local.tier])}${chevron}</summary><div class="composer-model-options"><div class="composer-model-heading">模型档位</div>${Object.entries(TIERS).filter(([id])=>id!=='kimi').map(([id,name])=>`<button type="button" class="composer-model-option" data-fq-tier-pick="${id}" aria-pressed="${local.tier===id}" ${local.tiers&&!local.tiers[id]?.configured?'disabled':''}><span>${e(name)}${local.tiers&&!local.tiers[id]?.configured?' · 未配置':''}</span></button>`).join('')}</div></details>`;
    const sendIcon='<svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 19V5m-6 6 6-6 6 6"/></svg>';
    const stopIcon='<svg class="ui-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="7" y="7" width="10" height="10" rx="2"/></svg>';
    const plusIcon='<svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>';
    const composer=`<form id="fingpt-composer" class="fq-composer"><label class="sr-only" for="fingpt-prompt">向 FinGPT 提问</label><textarea id="fingpt-prompt" placeholder="向 FinGPT 提问；需要数字时会先调用工具取数" maxlength="4000">${e(local.draft)}</textarea>${local.attachments.length?`<div class="attachment-chips">${local.attachments.map(a=>`<span class="badge">${e(a.name)}</span>`).join('')}</div>`:''}<div class="composer-tools"><label class="fq-upload" title="添加资料" aria-label="添加资料">${plusIcon}<input type="file" data-fq-upload multiple hidden accept=".md,.csv,.pdf,.docx,.xlsx,.pptx,.json"></label><span class="spacer"></span>${tierMenu}${local.busy?`<button type="button" class="button primary composer-send" data-fq-stop aria-label="停止回答" title="停止回答">${stopIcon}</button>`:`<button type="submit" class="button primary composer-send" aria-label="发送" title="发送">${sendIcon}</button>`}</div></form>`;
    const casesHome=empty?`<div class="fq-cases-home"><h2>精选案例</h2><p class="muted small">点击案例使用 Agent 模式研究</p><div class="claw-case-grid">${FEATURED_CASES.map((c,i)=>`<button class="claw-case-card" data-fq-case="${i}"><strong>${e(c.title)}</strong><span>${e(c.prompt)}</span></button>`).join('')}</div></div>`:'';
    const hero=empty?`<div class="greeting"><span class="mode-label">${icon('layers')}FinGPT</span><h1>从一个问题，开始研究。</h1><p class="landing-subtitle">快速取数、深度研究与 Agent 报告；任务与自动化在 Claw。</p></div>`:`<header><span class="eyebrow">FINGPT · RESEARCH</span><h1>${e(detail?.title||'从一个问题，开始研究。')}</h1><p class="muted">快速取数、深度研究与 Agent 报告；任务与自动化在 Claw。</p></header>`;
    return `<section class="fq-root${empty?' fq-empty':''}" aria-label="FinGPT 投研问答"><div class="fq-main">${hero}<nav class="fq-modes" aria-label="问答模式">${Object.entries(MODES).map(([id,name])=>`<button data-fq-mode="${id}" aria-pressed="${local.mode===id}" ${local.busy?'disabled':''}>${name}</button>`).join('')}</nav>${local.error?`<div class="notice error" role="alert">${e(local.error)}</div>`:''}${local.notice?`<p role="status">${e(local.notice)}</p>`:''}<div class="fq-messages">${rounds.map(r=>`<article class="message user"><div class="markdown">${md(r.question)}</div></article>${renderQAAnswer(view(r),r.id,{thinking:local.thinking.get(r.id)??(r.status==='running'),full:local.full===r.id})}`).join('')}</div>${composer}${casesHome}</div>${empty?'':workspace(selected,selectedM)}</section>`;
  }
  async function handle(event){
    const state=getState();const target=event.target;
    const hit=target.closest?.('[data-fq-task],[data-fq-case],[data-fq-suggest],[data-fq-mode],[data-fq-tier],[data-fq-tier-pick],[data-fq-think],[data-fq-copy],[data-fq-share],[data-fq-retry],[data-fq-stop],[data-fq-tab],[data-fq-refs],[data-doc-ref],[data-fq-hide-panel],[data-fq-full],[data-fq-close-full],[data-fq-download],[data-fq-vote],[data-fq-upload]');
    const form=target.closest?.('#fingpt-composer');
    if(event.type==='submit'&&form){event.preventDefault();event.stopImmediatePropagation();await send();return true;}
    if(event.type==='submit'&&target.id==='composer'&&state.route.page==='fingpt'){
      event.preventDefault();event.stopImmediatePropagation();await send(state.draft);return true;
    }
    if(target.id==='fingpt-prompt'){
      if(event.type==='input'){local.draft=target.value;return true;}
      if(event.type==='keydown'&&event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();event.stopImmediatePropagation();form.requestSubmit();return true;}
    }
    if(!hit)return false;
    if(hit.hasAttribute('data-doc-ref')&&!hit.closest('.fq-answer,.fq-workspace'))return false;
    if(event.type==='change'&&hit.hasAttribute('data-fq-tier')){local.tier=hit.value;return true;}
    if(event.type==='click'&&'fqTierPick' in hit.dataset){local.tier=hit.dataset.fqTierPick;hit.closest('details')?.removeAttribute('open');onChange();return true;}
    if(event.type==='change'&&hit.hasAttribute('data-fq-upload')){
      event.stopImmediatePropagation();
      try{
        if(!local.sid||current()?.engine!==FINGPT_ENGINE){const made=await api('fingpt/sessions',{method:'POST',body:{title:'资料研究',project_id:state.detail?.project_id||'default'}});local.sid=made.id;local.detail={...made,qa_rounds:[]};await onSession(made.id);}
        const data=new FormData();for(const file of hit.files)data.append('files',file);
        const res=await api(`sessions/${local.sid}/uploads`,{method:'POST',body:data});local.attachments.push(...res.items);onChange();
      }catch(error){local.error=error.message;onChange();}return true;
    }
    if(event.type!=='click')return false;
    if(hit.hasAttribute('data-fq-upload'))return false;
    event.preventDefault();event.stopImmediatePropagation();
    try{
      const d=hit.dataset;let rid=Object.entries(d).find(([k])=>['fqCopy','fqShare','fqRetry','fqRefs','fqFull','fqDownload','fqThink'].includes(k))?.[1];
      const round=current()?.qa_rounds.find(r=>r.id===rid);const m=round&&view(round);
      if('fqTask'in d)await onTask(TASK_PRESETS[+d.fqTask].prompt);
      else if('fqCase'in d){local.mode='agent';await send(FEATURED_CASES[+d.fqCase].prompt,'agent');}
      else if('fqSuggest'in d)await send(d.fqSuggest);
      else if('fqMode'in d)local.mode=d.fqMode;
      else if('fqStop'in d)await api(`sessions/${local.sid}/cancel`,{method:'POST',body:{}});
      else if('fqThink'in d)local.thinking.set(rid,!(local.thinking.get(rid)??round.status==='running'));
      else if('fqRetry'in d)await send(round.question,round.mode);
      else if('fqCopy'in d||'fqShare'in d){await navigator.clipboard.writeText(m.message);local.notice='已复制完整回答';}
      else if('fqVote'in d){local.votes.set(d.fqVote,true);local.notice='已记录本次反馈（仅本页）';}
      else if('fqFull'in d)local.full=rid;
      else if('fqCloseFull'in d)local.full=null;
      else if('fqDownload'in d){const url=URL.createObjectURL(new Blob([m.message],{type:'text/markdown;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='FinGPT研究报告.md';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
      else if('fqTab'in d)local.tab=d.fqTab;
      else if('fqRefs'in d){local.panel=rid;local.tab='refs';}
      else if('docRef'in d){local.panel=hit.closest('[data-fq-round]')?.dataset.fqRound||local.panel;local.source='S'+d.docRef;local.tab='refs';local.full=null;}
      onChange();
      if('docRef'in d)requestAnimationFrame(()=>{document.getElementById(`fq-${local.panel}-${local.source}`)?.focus();});
      return true;
    }catch(error){local.error=error.message;safeLog('fingpt_action_failed');onChange();return true;}
  }
  return {render,activate,handle,send,local};
}
