import {finite} from './asset-indicators.mjs';

// Closed mathematical parameters. No formulas, field names or supplier requests are accepted.
export const INDICATOR_RULES = Object.freeze({
  volume: {short:[5,1,250,true],long:[10,1,250,true]},
  macd: {fast:[12,1,250,true],slow:[26,2,250,true],signal:[9,1,250,true]},
  kdj: {period:[9,1,250,true],k:[3,1,250,true],d:[3,1,250,true]},
  rsi: {period:[14,1,250,true]},
  boll: {period:[20,2,250,true],deviation:[2,.1,10,false]},
  wr: {long:[10,2,250,true],short:[6,1,249,true]},
  sar: {step:[.02,.001,1,false],maximum:[.2,.001,1,false]},
  dmi: {period:[14,2,250,true],adx:[6,1,250,true]},
  cci: {period:[14,2,250,true]},
  bias: {short:[6,1,248,true],middle:[12,2,249,true],long:[24,3,250,true]},
  roc: {period:[12,1,250,true],average:[6,1,250,true]},
  obv: {average:[30,1,250,true]},
  vr: {period:[26,1,250,true],average:[6,1,250,true]},
  emv: {period:[14,1,250,true],average:[9,1,250,true]},
  atr: {period:[14,1,250,true]},
});
for (const rules of Object.values(INDICATOR_RULES)) { for (const rule of Object.values(rules)) Object.freeze(rule); Object.freeze(rules); }
export const INDICATOR_IDS = Object.freeze(Object.keys(INDICATOR_RULES));
export const DEFAULT_FAVORITES = Object.freeze(['volume','macd','kdj','rsi','boll','wr','sar']);
export const INDICATOR_CATALOG = Object.freeze([
  ['volume','成交量','成交量指标'],['macd','MACD','趋势指标'],['kdj','KDJ','反趋势指标'],['rsi','RSI','反趋势指标'],
  ['boll','BOLL','波动指标'],['wr','W&R','反趋势指标'],['sar','SAR','趋势指标'],['dmi','DMI','趋势指标'],
  ['cci','CCI','反趋势指标'],['bias','BIAS','反趋势指标'],['roc','ROC','趋势指标'],['obv','OBV','能量指标'],
  ['vr','VR','能量指标'],['emv','EMV','量价指标'],['atr','ATR','波动指标'],
].map(([id,name,group])=>Object.freeze({id,name,group})));
export const UNAVAILABLE_INDICATORS = Object.freeze([
  {id:'pe',name:'市盈率',group:'估值与持仓',reason:'尚未取得同口径市盈率历史序列'},
  {id:'pb',name:'市净率',group:'估值与持仓',reason:'尚未取得同口径市净率历史序列'},
  {id:'holding',name:'陆股通持股占比',group:'估值与持仓',reason:'尚未取得逐日持股占比历史序列'},
].map(Object.freeze));
export const validIndicatorIds = value => Array.isArray(value) && value.length<=INDICATOR_IDS.length && new Set(value).size===value.length && value.every(id=>typeof id==='string' && INDICATOR_IDS.includes(id));
export function normalizeFavorites(value=DEFAULT_FAVORITES) {
  if (!validIndicatorIds(value)) throw new Error('invalid indicator favorites');
  return [...value];
}
const dictionary = value => value && typeof value==='object' && !Array.isArray(value) && [Object.prototype,null].includes(Object.getPrototypeOf(value));
export function normalizeIndicatorSettings(value={}) {
  if (!dictionary(value) || Object.keys(value).some(key=>!Object.hasOwn(INDICATOR_RULES,key))) throw new Error('unknown indicator settings');
  const result={};
  for (const [id,rules] of Object.entries(INDICATOR_RULES)) {
    const supplied=Object.hasOwn(value,id)?value[id]:{};
    if (!dictionary(supplied) || Object.keys(supplied).some(key=>!Object.hasOwn(rules,key))) throw new Error('unknown indicator parameter');
    const settings={};
    for (const [key,[fallback,min,max,integer]] of Object.entries(rules)) {
      const n=Object.hasOwn(supplied,key)?supplied[key]:fallback;
      if (typeof n!=='number' || !Number.isFinite(n) || n<min || n>max || integer&&!Number.isInteger(n)) throw new Error('indicator parameter outside its declared range');
      settings[key]=n;
    }
    if (['volume','wr'].includes(id) && settings.short>=settings.long || id==='macd'&&settings.fast>=settings.slow || id==='bias'&&!(settings.short<settings.middle&&settings.middle<settings.long) || id==='sar'&&settings.step>settings.maximum) throw new Error('invalid indicator parameter ordering');
    result[id]=settings;
  }
  return result;
}

const COLORS=['#d1d5db','#ed8936','#22d3ee','#a78bfa'];
export const PANEL_SERIES = Object.freeze({
  volume:[['volume','VOL','bar'],['volShort','MA1'],['volLong','MA2']],
  macd:[['dif','DIF'],['dea','DEA'],['hist','MACD','bar']],
  kdj:[['k','K'],['d','D'],['j','J']], rsi:[['rsi','RSI']],
  boll:[['upper','UPPER'],['middle','MID'],['lower','LOWER']], wr:[['wr1','WR1'],['wr2','WR2']],
  sar:[['sar','SAR','scatter']], dmi:[['pdi','PDI'],['mdi','MDI'],['adx','ADX'],['adxr','ADXR']],
  cci:[['cci','CCI']], bias:[['b1','BIAS1'],['b2','BIAS2'],['b3','BIAS3']],
  roc:[['roc','ROC'],['average','MAROC']], obv:[['obv','OBV'],['average','MAOBV']],
  vr:[['vr','VR'],['average','MAVR']], emv:[['emv','EMV'],['average','MAEMV']], atr:[['atr','ATR']],
});
export const panelField = (id,key) => `panel_${id}_${key}`;
export function indicatorSeries(id) {
  return (PANEL_SERIES[id]||[]).map(([key,name,type='line'],index)=>({key:panelField(id,key),name,type,color:COLORS[index%COLORS.length]}));
}
export function indicatorTitle(id,settings) {
  const params=settings?.[id]||Object.fromEntries(Object.entries(INDICATOR_RULES[id]||{}).map(([key,rule])=>[key,rule[0]]));
  return `${INDICATOR_CATALOG.find(item=>item.id===id)?.name||id}(${Object.values(params).join(',')})`;
}

const average = values => values[0]+values.reduce((sum,n)=>sum+(n-values[0])/values.length,0);
function rolling(values,n,fn=average) {
  return values.map((_,index)=>{
    if (index+1<n) return null;
    const window=values.slice(index-n+1,index+1);
    return window.every(value=>finite(value)!==null)?fn(window):null;
  });
}
const wilder = (values,n) => {
  let previous=null; const seed=[];
  return values.map(value=>{
    if (finite(value)===null) {previous=null;seed.length=0;return null;}
    if (previous===null) {seed.push(value);if(seed.length<n)return null;previous=average(seed);}
    else previous+=(value-previous)/n;
    return previous;
  });
};
function parabolic(rows,{step,maximum}) {
  const output=rows.map(()=>null); if(rows.length<2)return output;
  const up=rows[1].high-rows[0].high; const down=rows[0].low-rows[1].low;
  let rising=!(down>0&&down>up); let extreme=rising?rows[1].high:rows[1].low;
  let stop=rising?rows[0].low:rows[0].high; let acceleration=step;
  for(let i=1;i<rows.length;i++) {
    const current=rows[i]; const previous=rows[i===1?1:i-1];
    if(rising) {
      if(current.low<=stop) {rising=false;stop=Math.max(extreme,previous.high,current.high);output[i]=stop;acceleration=step;extreme=current.low;stop=Math.max(stop+acceleration*(extreme-stop),previous.high,current.high);}
      else {output[i]=stop;if(current.high>extreme){extreme=current.high;acceleration=Math.min(maximum,acceleration+step);}stop=Math.min(stop+acceleration*(extreme-stop),previous.low,current.low);}
    } else if(current.high>=stop) {rising=true;stop=Math.min(extreme,previous.low,current.low);output[i]=stop;acceleration=step;extreme=current.high;stop=Math.min(stop+acceleration*(extreme-stop),previous.low,current.low);}
    else {output[i]=stop;if(current.low<extreme){extreme=current.low;acceleration=Math.min(maximum,acceleration+step);}stop=Math.max(stop+acceleration*(extreme-stop),previous.high,current.high);}
  }
  return output;
}

/** Fully warmed, prefix-causal OHLCV calculations. Invalid price segments never join.
 * Existing AF defaults are copied exactly; all added fields are derived display data.
 */
/** Internal contract: numerical bars from enrichMarketBars / aggregateMarketBars only. */
export function calculatePanelIndicators(input,provided={}) {
  const settings=normalizeIndicatorSettings(provided);
  const output=input.map(row=>({...row}));
  for(const row of output)for(const id of INDICATOR_IDS)for(const [key] of PANEL_SERIES[id])row[panelField(id,key)]=null;
  const put=(rows,id,key,values)=>rows.forEach((row,index)=>{row[panelField(id,key)]=finite(values[index]);});
  put(output,'volume','volume',output.map(row=>finite(row.volume)!==null&&finite(row.volume)>=0?finite(row.volume):null));
  for(const [name,period] of [['volShort',settings.volume.short],['volLong',settings.volume.long]])put(output,'volume',name,rolling(output.map(row=>row.gap||finite(row.volume)===null||finite(row.volume)<0?null:finite(row.volume)),period));
  const segments=[];let segment=[];
  for(const row of output){if(!row.validOHLC||row.gap){if(segment.length)segments.push(segment);segment=[];}else segment.push(row);}
  if(segment.length)segments.push(segment);
  for(const rows of segments) {
    const closes=rows.map(row=>row.close); const highs=rows.map(row=>row.high); const lows=rows.map(row=>row.low);
    const changes=closes.map((value,index)=>index?value-closes[index-1]:null);
    const volumes=rows.map(row=>finite(row.volume)!==null&&finite(row.volume)>=0?finite(row.volume):null);
    // MACD retains AF first-close EMA seeding and display-only warmup masks.
    const m=settings.macd;let fast=null,slow=null,signal=null;const dif=[],dea=[],hist=[];
    for(let i=0;i<rows.length;i++){fast=fast===null?closes[i]:fast+2/(m.fast+1)*(closes[i]-fast);slow=slow===null?closes[i]:slow+2/(m.slow+1)*(closes[i]-slow);const raw=fast-slow;signal=signal===null?raw:signal+2/(m.signal+1)*(raw-signal);dif.push(i+1>=m.slow?raw:null);dea.push(i+1>=m.slow+m.signal-1?signal:null);hist.push(dea[i]===null?null:2*(raw-signal));}
    put(rows,'macd','dif',dif);put(rows,'macd','dea',dea);put(rows,'macd','hist',hist);
    const kdj=settings.kdj;let k=null,d=null;const ks=[],ds=[],js=[];
    for(let i=0;i<rows.length;i++){const first=Math.max(0,i-kdj.period+1);const lo=Math.min(...lows.slice(first,i+1));const hi=Math.max(...highs.slice(first,i+1));const rsv=hi===lo?50:(closes[i]-lo)/(hi-lo)*100;k=k===null?rsv:k+(rsv-k)/kdj.k;d=d===null?k:d+(k-d)/kdj.d;const ready=i+1>=kdj.period;ks.push(ready?k:null);ds.push(ready?d:null);js.push(ready?3*k-2*d:null);}
    put(rows,'kdj','k',ks);put(rows,'kdj','d',ds);put(rows,'kdj','j',js);
    const gains=rolling(changes.map(n=>n===null?null:Math.max(n,0)),settings.rsi.period);const losses=rolling(changes.map(n=>n===null?null:Math.max(-n,0)),settings.rsi.period);
    put(rows,'rsi','rsi',gains.map((gain,i)=>gain===null?null:gain===0&&losses[i]===0?50:losses[i]===0?100:100-100/(1+gain/losses[i])));
    const b=settings.boll;const middle=rolling(closes,b.period);const sigma=rolling(closes,b.period,values=>{const mean=average(values);return Math.sqrt(values.reduce((sum,n)=>sum+(n-mean)**2,0)/(b.period-1));});
    put(rows,'boll','middle',middle);put(rows,'boll','upper',middle.map((value,i)=>value===null?null:value+b.deviation*sigma[i]));put(rows,'boll','lower',middle.map((value,i)=>value===null?null:value-b.deviation*sigma[i]));
    for(const [key,period] of [['wr1',settings.wr.long],['wr2',settings.wr.short]]) {const hi=rolling(highs,period,values=>Math.max(...values));const lo=rolling(lows,period,values=>Math.min(...values));put(rows,'wr',key,closes.map((close,i)=>hi[i]===null||hi[i]===lo[i]?null:100*(hi[i]-close)/(hi[i]-lo[i])));}
    put(rows,'sar','sar',parabolic(rows,settings.sar));
    const tr=rows.map((row,i)=>i?Math.max(row.high-row.low,Math.abs(row.high-closes[i-1]),Math.abs(row.low-closes[i-1])):null);
    put(rows,'atr','atr',wilder(tr,settings.atr.period));
    const plus=rows.map((row,i)=>{if(!i)return null;const up=row.high-highs[i-1],down=lows[i-1]-row.low;return up>0&&up>down?up:0;});
    const minus=rows.map((row,i)=>{if(!i)return null;const up=row.high-highs[i-1],down=lows[i-1]-row.low;return down>0&&down>up?down:0;});
    const trRma=wilder(tr,settings.dmi.period),plusRma=wilder(plus,settings.dmi.period),minusRma=wilder(minus,settings.dmi.period);
    const pdi=trRma.map((n,i)=>n===null?null:n===0?0:100*plusRma[i]/n),mdi=trRma.map((n,i)=>n===null?null:n===0?0:100*minusRma[i]/n);
    const dx=pdi.map((n,i)=>n===null?null:n+mdi[i]===0?0:100*Math.abs(n-mdi[i])/(n+mdi[i]));const adx=wilder(dx,settings.dmi.adx);
    put(rows,'dmi','pdi',pdi);put(rows,'dmi','mdi',mdi);put(rows,'dmi','adx',adx);put(rows,'dmi','adxr',adx.map((n,i)=>n===null||i<settings.dmi.adx||adx[i-settings.dmi.adx]===null?null:(n+adx[i-settings.dmi.adx])/2));
    const typical=rows.map(row=>(row.high+row.low+row.close)/3);
    put(rows,'cci','cci',rolling(typical,settings.cci.period,values=>{const mean=average(values);const deviation=average(values.map(n=>Math.abs(n-mean)));return deviation===0?0:(values.at(-1)-mean)/(.015*deviation);}));
    for(const [key,period] of [['b1',settings.bias.short],['b2',settings.bias.middle],['b3',settings.bias.long]]){const means=rolling(closes,period);put(rows,'bias',key,closes.map((n,i)=>means[i]===null||means[i]===0?null:100*(n-means[i])/means[i]));}
    const roc=closes.map((n,i)=>i<settings.roc.period||closes[i-settings.roc.period]===0?null:100*(n/closes[i-settings.roc.period]-1));put(rows,'roc','roc',roc);put(rows,'roc','average',rolling(roc,settings.roc.average));
    let obv=null;const obvs=volumes.map((volume,i)=>{if(volume===null||volume<0){obv=null;return null;}if(obv===null)obv=volume;else if(changes[i]>0)obv+=volume;else if(changes[i]<0)obv-=volume;return obv;});put(rows,'obv','obv',obvs);put(rows,'obv','average',rolling(obvs,settings.obv.average));
    const upVolume=changes.map((n,i)=>n===null||volumes[i]===null?null:n>0?volumes[i]:n===0?volumes[i]/2:0);const downVolume=changes.map((n,i)=>n===null||volumes[i]===null?null:n<0?volumes[i]:n===0?volumes[i]/2:0);
    const ups=rolling(upVolume,settings.vr.period,values=>values.reduce((a,n)=>a+n,0)),downs=rolling(downVolume,settings.vr.period,values=>values.reduce((a,n)=>a+n,0));const vr=ups.map((n,i)=>n===null||downs[i]===0?null:100*n/downs[i]);put(rows,'vr','vr',vr);put(rows,'vr','average',rolling(vr,settings.vr.average));
    const rawEmv=rows.map((row,i)=>!i||volumes[i]===null||volumes[i]<=0?null:((row.high+row.low-highs[i-1]-lows[i-1])/2)*(row.high-row.low)/(volumes[i]/1e8));const emv=rolling(rawEmv,settings.emv.period);put(rows,'emv','emv',emv);put(rows,'emv','average',rolling(emv,settings.emv.average));
  }
  // Default values remain byte-for-byte numerically aligned with the original AF fields.
  const defaults=normalizeIndicatorSettings();
  const aliases={volume:{volShort:'volumeMA5',volLong:'volumeMA10'},macd:{dif:'dif',dea:'dea',hist:'macd'},kdj:{k:'k',d:'d',j:'j'},rsi:{rsi:'rsi'},boll:{middle:'ma20',upper:'bollUpper',lower:'bollLower'}};
  for(const [id,keys] of Object.entries(aliases))if(JSON.stringify(settings[id])===JSON.stringify(defaults[id]))for(const row of output)for(const [key,original]of Object.entries(keys))if(Object.hasOwn(row,original))row[panelField(id,key)]=finite(row[original]);
  return output;
}
