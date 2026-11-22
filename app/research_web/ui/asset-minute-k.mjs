import {safeLog} from './core.mjs';
import {createAssetChartController} from './asset-chart.mjs';

export const MINUTE_K_CYCLES = ['1m','5m','15m','30m','60m','120m'];

/** Direct Wind-style cycle keys; no disclosure or select is rendered. */
export function createMinuteButtons(doc) {
  const group=doc.createElement('div');group.className='asset-minute-periods';
  group.setAttribute('role','group');group.setAttribute('aria-label','分钟K周期');
  for(const cycle of MINUTE_K_CYCLES){
    const button=doc.createElement('button');button.type='button';button.className='kline-btn';
    button.textContent=`${cycle.slice(0,-1)}分`;button.dataset.minuteCycle=cycle;
    button.setAttribute('aria-label',`${cycle.slice(0,-1)}分钟K`);button.setAttribute('aria-pressed','false');
    group.append(button);
  }
  return group;
}

/** A separate canvas/controller keeps the daily instance, range and selection intact. */
export function createAssetMinuteK({api, intraday, chartOptions = {}}) {
  const controller=createAssetChartController(chartOptions);
  let page, dailySlot, slot, menu, originalGroup, observation, account, preferences;
  let active=false, cycle='5m', adjustment='none', data=null, ticket=0, abort;
  let status, identity='', bound=false, lastRequest=null, requestState={kind:'idle',text:''};
  function show(value) {
    active=value;
    if(!page)return;
    page.classList.toggle('asset-minute-k-on',active);
    if(slot)slot.hidden=!active;
    if(menu){
      const group=active?slot?.querySelector('.kline-period-group'):originalGroup;
      group?.insertBefore(menu,group.querySelector('[data-asset-chart-action="period-day"],[data-minute-exit="day"]'));
      for(const button of menu.querySelectorAll('[data-minute-cycle]')){
        const selected=active&&data?.cycle===button.dataset.minuteCycle;
        button.classList.toggle('active',selected);button.setAttribute('aria-pressed',String(selected));
      }
    }
    if(active)intraday.setActive(false);
    window.dispatchEvent(new Event('resize'));
  }
  function draw() {
    if(!slot)return;
    const snapshot=data || {rows:[],cycle,adjustment,version:'pending',fields:{},requested_range:{start_date:'',end_date:''}};
    const metadata={chartIdentity:`minute:${snapshot.cycle}`,frequency:'minute',minute_k:true,daily_reference:snapshot.daily_reference,
      fields:snapshot.fields,adjustment:snapshot.adjustment,accountIdentity:account,
      assetIdentity:`stock:${observation.asset}`,asset:observation.asset,canLoadHistory:false,
      asset_history:{canonical_version:snapshot.version,adjustment:snapshot.adjustment}};
    controller.configure(snapshot.rows,`${observation.asset}:minute:${snapshot.cycle}:${snapshot.adjustment}:${snapshot.version}`,metadata,preferences);
    controller.mount(slot);
    slot.querySelector('.kline-terminal-layout').hidden=!snapshot.rows.length;
    slot.querySelector('.asset-history-readout').hidden=!snapshot.rows.length;
    // This controller never sends daily history or adjustment jobs.
    const group=slot.querySelector('.kline-period-group');
    group.replaceChildren();
    for(const [label,mode] of [['分时','intraday'],['日K','day'],['周K','week'],['月K','month']]){
      const b=document.createElement('button');b.type='button';b.className='kline-btn';b.textContent=label;b.dataset.minuteExit=mode;b.setAttribute('aria-pressed','false');group.append(b);
    }
    group.append(menu);
    const select=slot.querySelector('[data-asset-chart-adjustment]');
    select.removeAttribute('data-asset-chart-adjustment');select.dataset.minuteAdjustment='';select.disabled=false;
    select.value=snapshot.adjustment;
    status=document.createElement('div');status.className='asset-minute-status';status.setAttribute('role','status');status.hidden=!data;
    status.textContent=`${snapshot.cycle.slice(0,-1)}分钟K · ${snapshot.requested_range.start_date}—${snapshot.requested_range.end_date} · ${snapshot.rows.length}根 · 快照，非持续实时行情${snapshot.rows.length?'':' · 暂无记录'}`;
    const detail=document.createElement('details'),summary=document.createElement('summary');summary.textContent='数据说明';detail.append(summary);
    const note=document.createElement('p');note.textContent=['按交易时段分段；集合竞价09:25单独成柱；末根可能尚未结束。价格复权，成交量额保留原口径。',...(snapshot.limitations||[])].join(' ');detail.append(note);status.append(detail);slot.append(status);
    renderProgress();show(active);
  }
  function progress() {
    let node=slot?.querySelector('[data-minute-progress]');
    if(!node&&slot){node=document.createElement('p');node.dataset.minuteProgress='';node.setAttribute('role','status');slot.prepend(node);}
    return node;
  }
  function renderProgress(){
    if(!slot)return;
    if(requestState.kind==='idle'){slot.querySelector('[data-minute-progress]')?.remove();return;}
    const node=progress();node.textContent=requestState.text;
    if(requestState.kind==='failed'){const retry=document.createElement('button');retry.type='button';retry.textContent='重试';retry.dataset.minuteRetry='';node.append(retry);}
  }
  async function load(nextCycle, nextAdjustment=data?.adjustment||adjustment, refresh=false) {
    if(!MINUTE_K_CYCLES.includes(nextCycle)||!observation?.id)return;
    const current=++ticket;abort?.abort();abort=new AbortController();cycle=nextCycle;adjustment=nextAdjustment;lastRequest={cycle,adjustment};
    // Retain the previous complete version until replacement is validated.
    if(!slot.querySelector('[data-asset-echarts]'))draw();
    requestState={kind:'loading',text:`正在读取${cycle.slice(0,-1)}分钟K…`};renderProgress();
    show(true);
    try{
      const result=await api.assetMinuteBars(observation.id,{cycle,adjustment,refresh},{signal:abort.signal});
      if(current!==ticket)return;
      if(result.asset!==observation.asset||result.cycle!==cycle||result.adjustment!==adjustment||!Array.isArray(result.rows)||result.rows.length>5000||!['complete','empty'].includes(result.status)||!/^[a-f0-9]{64}$/.test(result.version||'')||!/^\d{4}-\d{2}-\d{2}$/.test(result.requested_range?.start_date||'')||!/^\d{4}-\d{2}-\d{2}$/.test(result.requested_range?.end_date||'')||!result.fields)throw new Error('minute_response_invalid');
      data=result;requestState={kind:'idle',text:''};draw();
    }catch(error){
      if(current!==ticket||error.name==='AbortError')return;
      safeLog('asset_minute_k_load_failed',{status:error.code||'request_failed'});
      requestState={kind:'failed',text:`${cycle.slice(0,-1)}分钟K未取得${data?'，保留原版本':''}：${error.message}`};renderProgress();
      const select=slot.querySelector('[data-minute-adjustment]');if(select)select.value=data?.adjustment||'none';
      show(active);
    }
  }
  function click(event){
    const target=event.target.closest('[data-minute-cycle],[data-minute-exit],[data-minute-retry]');
    if(!target)return;
    event.preventDefault();event.stopImmediatePropagation();
    if(target.dataset.minuteCycle)void load(target.dataset.minuteCycle);
    else if(Object.hasOwn(target.dataset,'minuteRetry'))void load(lastRequest?.cycle||cycle,lastRequest?.adjustment||adjustment,true);
    else{
      // Abort only this consumer; backend/SDK drains through the existing task witness.
      ticket++;abort?.abort();show(false);
      const mode=target.dataset.minuteExit;
      const button=mode==='intraday'?dailySlot.querySelector('[data-intraday-mode]'):dailySlot.querySelector(`[data-asset-chart-action="period-${mode}"]`);
      button?.click();
    }
  }
  function change(event){if(event.target.matches('[data-minute-adjustment]')){event.stopImmediatePropagation();void load(data?.cycle||cycle,event.target.value);}}
  function release(){
    if(bound){page?.removeEventListener('click',click,true);page?.removeEventListener('change',change,true);}bound=false;
    controller.dispose();menu?.remove();slot?.remove();page?.classList.remove('asset-minute-k-on');slot=menu=page=null;
  }
  return {
    mount(nextPage,nextObservation,nextAccount='single-user',nextPreferences={}){
      if(!nextPage||nextObservation?.asset_type!=='stock'||!nextObservation.id){this.dispose();return;}
      const key=`${nextAccount}:${nextObservation.id}:${nextObservation.asset}`;
      if(key!==identity){ticket++;abort?.abort();active=false;data=null;requestState={kind:'idle',text:''};lastRequest=null;identity=key;controller.dispose();}
      observation=nextObservation;account=nextAccount;preferences=nextPreferences;
      const nextSlot=nextPage.querySelector('[data-asset-chart-slot]');
      if(page!==nextPage||dailySlot!==nextSlot||originalGroup!==nextSlot?.querySelector('.kline-period-group')||!menu?.isConnected){
        release();page=nextPage;dailySlot=nextSlot;originalGroup=dailySlot?.querySelector('.kline-period-group');if(!originalGroup)return;
        menu=createMinuteButtons(document);
        originalGroup.append(menu);slot=document.createElement('div');slot.dataset.assetMinuteSlot='';slot.hidden=true;
        dailySlot.after(slot);page.addEventListener('click',click,true);page.addEventListener('change',change,true);bound=true;
        draw();
      }
      show(active);
    },
    dispose(){ticket++;abort?.abort();release();data=null;identity='';active=false;requestState={kind:'idle',text:''};lastRequest=null;},
  };
}
