import {test} from 'node:test';import assert from 'node:assert/strict';
import {renderHotSources,hotSourceSubmission} from '../../app/research_web/ui/hot-sources.mjs';
const row={id:'fed',operator:'Federal Reserve',enabled:true,config_revision:'4',adapter:'frozen_acceptance_subset',collection_state:'awaiting_catalog',catalog_activation_allowed:true};
test('frozen source is not rendered as collecting and explicit activation binds current version and reason',()=>{
 const html=renderHotSources({sources:[row]},'',value=>String(value||'未知'));
 assert.match(html,/尚未接入持续采集/);assert.doesNotMatch(html,/采集中/);
 const fields=new Map([['sourceId','fed'],['enabled','true'],['frequencySeconds','60'],['useCatalog','on'],['reason','resume official']]);
 assert.deepEqual(hotSourceSubmission(fields,{sources:[row]},()=> 'request'),{method:'hotSourceConfigure',body:{sourceId:'fed',expectedRevision:'4',enabled:true,frequencySeconds:60,useCatalog:true,reason:'resume official',requestId:'request'}});
 fields.set('reason','');assert.throws(()=>hotSourceSubmission(fields,{sources:[row]},()=> 'request'));
 assert.throws(()=>hotSourceSubmission(fields,{sources:[{...row,catalog_activation_allowed:false}]},()=> 'request'));
});
test('ordinary source frequency change does not implicitly activate or include reason; invalid limits reject',()=>{
 const fields=new Map([['sourceId','fed'],['enabled','false'],['frequencySeconds','0']]);
 const result=hotSourceSubmission(fields,{sources:[row]},()=> 'request');assert.equal(result.body.enabled,false);assert.equal(result.body.frequencySeconds,0);assert.ok(!('useCatalog'in result.body));
 for(const value of ['true','1.5','5','86401','NaN']){fields.set('frequencySeconds',value);assert.throws(()=>hotSourceSubmission(fields,{sources:[row]},()=> 'request'));}
});
