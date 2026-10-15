/** Public non-secret validator; no credentials, DB, network or model startup. */
import {validatePricing} from '../src/pricing.ts';
import {assertNodeRuntime} from '../src/config.ts';
try{
  assertNodeRuntime();const parts:Buffer[]=[];let size=0;
  for await(const chunk of process.stdin){size+=chunk.length;if(size>65536)throw Error('hot_pricing_invalid');parts.push(Buffer.from(chunk));}
  const input=JSON.parse(Buffer.concat(parts).toString('utf8'));
  const today=new Intl.DateTimeFormat('en-CA',{timeZone:input.timezone,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  console.log(JSON.stringify({state:'valid',pricing:validatePricing(input.pricing,today)}));
}catch{console.log(JSON.stringify({state:'invalid',code:'hot_pricing_invalid'}));process.exitCode=1;}
