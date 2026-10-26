import {safeLog} from './core.mjs';
import {escapeHTML as e} from './markdown.mjs';
import {formatAssetMagnitude, formatAssetVolume, assetPriceClass, assetChangeClass} from './asset-format.mjs';
import {intradayOption} from './asset-intraday-option.mjs';

const price = n => Number.isFinite(n) ? n.toFixed(2) : '—';

/** Own only the intraday canvas and requests; never configure or destroy K. */
export function createAssetIntraday({api, echarts = () => globalThis.echarts}) {
  let terminal, stage, readout, chart, resize, selectionObserver, abort, identity = '', observationId = '', data;
  let active = true, generation = 0, loading = false, attempted = false, lastFailed = false;
  let loadedAt = 0;
  const qty = value => formatAssetVolume(value, 'share', identity, {compact:true});
  const cash = value => formatAssetMagnitude(value, '元', '', {compact:true});
  function maskKSelection() {
    if(!active||!terminal)return;
    for(const button of terminal.querySelectorAll('.kline-period-group button:not([data-intraday-mode])')) {
      if(!Object.hasOwn(button.dataset,'kPressed'))button.dataset.kPressed=button.getAttribute('aria-pressed')||'false';
      if(button.getAttribute('aria-pressed')!=='false')button.setAttribute('aria-pressed','false');
    }
  }
  function updateReadout(index) {
    const row = data?.rows?.[index]; if (!readout || !row) return;
    const change = (row.price / data.previous_close - 1) * 100;
    readout.innerHTML = `<strong>${e(data.trading_date)} ${e(row.time)}</strong><span>收 <strong class="${assetPriceClass(row.price,data.previous_close)}">${price(row.price)}</strong></span><span>幅 <strong class="${assetChangeClass(change)}">${change>0?'+':''}${price(change)}%</strong></span><span>均 <strong class="${assetPriceClass(row.mean,data.previous_close)}">${price(row.mean)}</strong></span><span title="成交量（手）">量 <strong>${qty(row.cumulative_volume)}</strong></span><span>额 <strong>${cash(row.cumulative_amount)}</strong></span>`;
  }
  function draw() {
    if (!active || !stage || !data?.rows?.length || !echarts()) return;
    const canvas = stage.querySelector('.intraday-canvas');
    chart ||= echarts().init(canvas);
    chart.setOption(intradayOption(data, {dark:document.documentElement.dataset.theme==='dark', updateReadout}), true);
    chart.resize(); canvas.dataset.tradingDate=data.trading_date; canvas.dataset.points=data.rows.length;
    updateReadout(data.rows.length-1);
  }
  function mode(value) {
    active=value; if(!terminal)return;
    terminal.classList.toggle('intraday-on',active); stage.hidden=!active; readout.hidden=!active;
    const button=terminal.querySelector('[data-intraday-mode]');
    button.classList.toggle('active',active); button.setAttribute('aria-pressed',String(active));
    for(const b of terminal.querySelectorAll('.kline-period-group button:not([data-intraday-mode])')) {
      if(active) { if(!Object.hasOwn(b.dataset,'kPressed'))b.dataset.kPressed=b.getAttribute('aria-pressed')||'false'; b.setAttribute('aria-pressed','false'); }
      else if(Object.hasOwn(b.dataset,'kPressed')) { b.setAttribute('aria-pressed',b.dataset.kPressed); delete b.dataset.kPressed; }
    }
    if(active){draw();if((!attempted||(data&&!lastFailed&&Date.now()-loadedAt>=60000))&&!loading)void load();} else window.dispatchEvent(new Event('resize'));
  }
  async function load(refresh=false) {
    if(!observationId || !stage || loading)return;
    const ticket=++generation; abort?.abort(); abort=new AbortController(); loading=true;attempted=true;
    const status=stage.querySelector('[data-intraday-status]');status.textContent=data?'更新中，保留上次快照':'正在加载最近交易日分时';
    try {
      const result=await api.assetIntraday(observationId,{refresh},{signal:abort.signal});
      if(ticket!==generation)return;
      if(!Array.isArray(result.rows)||!['complete','empty'].includes(result.status))throw new Error('intraday_response_invalid');
      data=result; loadedAt=Date.now();lastFailed=false;
      if(!result.rows.length){chart?.clear();readout.textContent='';stage.querySelector('.intraday-canvas').hidden=true;}
      else stage.querySelector('.intraday-canvas').hidden=false;
      status.textContent=result.rows.length?'分时快照 · 非持续实时行情':'最近交易日暂无分钟记录';draw();
    }catch(error){if(ticket!==generation||error.name==='AbortError')return;lastFailed=true;if(!data?.rows?.length)stage.querySelector('.intraday-canvas').hidden=true;status.textContent=`${data?'更新失败，保留原快照；':''}分时未取得：${error.message}`;safeLog('asset_intraday_load_failed',{status:error.code||'request_failed'});}
    finally {if(ticket===generation)loading=false;}
  }
  function click(event) {
    if(event.target.closest('[data-intraday-mode]')){event.preventDefault();event.stopImmediatePropagation();mode(true);}
    else if(event.target.closest('[data-asset-chart-action^="period-"]'))mode(false);
    else if(event.target.closest('[data-intraday-refresh]'))void load(true);
  }
  function release() {
    terminal?.removeEventListener('click',click,true);resize?.disconnect();resize=null;selectionObserver?.disconnect();selectionObserver=null;chart?.dispose();chart=null;
    stage?.remove();readout?.remove();terminal?.querySelector('[data-intraday-mode]')?.remove();terminal?.classList.remove('intraday-on');
    terminal=null;stage=null;readout=null;
  }
  return {
    mount(page, observation, account='single-user') {
      const nextIdentity=`${observation?.asset_type||'stock'}:${observation?.asset||''}`,next=page?.querySelector('.asset-market-terminal');
      if(!next || !observation?.id || observation.asset_type!=='stock')return;
      if(identity!==nextIdentity || observationId!==`${observation.id}` || this.account!==account){generation++;abort?.abort();loading=false;attempted=false;lastFailed=false;data=null;loadedAt=0;chart?.clear();if(readout)readout.textContent='';active=true;identity=nextIdentity;observationId=observation.id;this.account=account;}
      if(terminal!==next || !stage?.isConnected){
        release();terminal=next;
        const group=terminal.querySelector('.kline-period-group');if(!group)return;
        const button=document.createElement('button');button.type='button';button.dataset.intradayMode='';button.textContent='分时';group.prepend(button);
        selectionObserver=new MutationObserver(maskKSelection);selectionObserver.observe(group,{attributes:true,subtree:true,attributeFilter:['aria-pressed']});
        readout=document.createElement('div');readout.className='intraday-readout';
        stage=document.createElement('section');stage.className='asset-intraday-stage';stage.innerHTML='<div class="intraday-canvas" role="img" aria-label="最近交易日价格、计算均价和分钟成交量"></div><div class="asset-intraday-status"><span data-intraday-status></span> <button type="button" data-intraday-refresh>刷新</button></div>';
        const anchor=terminal.querySelector('.kline-terminal-layout');terminal.insertBefore(readout,anchor);terminal.insertBefore(stage,anchor);
        terminal.addEventListener('click',click,true);resize=new ResizeObserver(()=>{if(active)chart?.resize();});resize.observe(stage);
        stage.addEventListener('mouseleave',()=>{if(data)updateReadout(data.rows.length-1);});
      }
      mode(active);
    },
    dispose(){generation++;abort?.abort();loading=false;attempted=false;lastFailed=false;release();data=null;identity='';observationId='';active=true;},
  };
}
