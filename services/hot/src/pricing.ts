/** Non-secret, operator-verified tariffs; configuration never grants budget. */
import {openSync,closeSync,fstatSync,readFileSync,lstatSync,constants} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {sha256} from './material.ts';
export const PRICE_KEYS=['version','verifiedOn','source','provider','requestedModel','documentedAlias','documentedBackend','currency','basis',
  'inputMicrosPerMillion','cacheReadMicrosPerMillion','cacheWriteMicrosPerMillion','outputMicrosPerMillion','cacheWriteBasis','automaticallyActive'];
export function priceExists(path:string){try{lstatSync(path);return true;}catch(error){if((error as NodeJS.ErrnoException).code==='ENOENT')return false;throw Error('hot_pricing_private_invalid');}}
export function validatePricing(value:unknown,today:string):Record<string,any>{
  if(!value||typeof value!=='object'||Array.isArray(value))throw Error('hot_pricing_invalid');
  const p=value as Record<string,any>;
  if(Object.keys(p).length!==PRICE_KEYS.length||Object.keys(p).some(k=>!PRICE_KEYS.includes(k))||p.version!==1||p.verifiedOn!==today||
    p.source!=='https://api-docs.deepseek.com/quick_start/pricing/'||p.provider!=='deepseek-official'||p.requestedModel!=='deepseek-v4-flash'||
    p.documentedAlias!=='deepseek-flash'||typeof p.documentedBackend!=='string'||p.documentedBackend.length>100||
    p.currency!=='USD'||p.basis!=='conservative_peak_tariff_ceiling_not_invoice'||p.cacheWriteBasis!=='conservative_uncached_input_ceiling'||p.automaticallyActive!==false)
    throw Error('hot_pricing_invalid');
  for(const [key,floor] of [['inputMicrosPerMillion',300000],['cacheReadMicrosPerMillion',6000],['cacheWriteMicrosPerMillion',300000],['outputMicrosPerMillion',1200000]] as const)
    if(!Number.isSafeInteger(p[key])||p[key]<floor||p[key]>10000000000)throw Error('hot_pricing_invalid');
  if(p.cacheWriteMicrosPerMillion<p.inputMicrosPerMillion)throw Error('hot_pricing_invalid');
  return p;
}
export function readPrivatePrice(path:string,instanceId:string,today:string){
  const absolute=resolve(path);let parent=absolute;
  while(true){if(lstatSync(parent).isSymbolicLink())throw Error('hot_pricing_private_invalid');const next=dirname(parent);if(next===parent)break;parent=next;}
  const fd=openSync(absolute,constants.O_RDONLY|constants.O_NOFOLLOW|constants.O_NONBLOCK);
  try{
    const info=fstatSync(fd);
    if(!info.isFile()||info.nlink!==1||info.uid!==process.getuid?.()||(info.mode&0o777)!==0o600||info.size>65536)throw Error('hot_pricing_private_invalid');
    const bytes=readFileSync(fd),envelope=JSON.parse(bytes.toString('utf8'));
    if(envelope.version!==1||envelope.instanceId!==instanceId||envelope.projectRoot!==resolve(import.meta.dirname,'../../..')||
      typeof envelope.reason!=='string'||!envelope.reason.trim()||envelope.reason.length>2000||envelope.verifiedBy!==`os-uid:${process.getuid?.()}`)
      throw Error('hot_pricing_private_invalid');
    return {pricing:validatePricing(envelope.pricing,today),fingerprint:sha256(bytes)};
  }finally{closeSync(fd);}
}
