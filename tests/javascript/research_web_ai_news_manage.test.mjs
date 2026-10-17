import test from 'node:test';
import assert from 'node:assert/strict';
import {createNewsManagement,renderNewsManagement} from '../../app/research_web/ui/ai-news-manage.mjs';
import {createAihotController,renderAihot} from '../../app/research_web/ui/aihot.mjs';
import {parseRoute} from '../../app/research_web/ui/core.mjs';

test('management route uses only same-origin control and explicit free preview',async()=>{
 const calls=[];
 const fetcher=async(url,options)=>{calls.push([url,options]);return {ok:true,json:async()=>url.endsWith('status')?{state:'running'}:{rows:[{id:'official',name:'<b>安全</b>',kind:'rss',health:'paused'}]}};};
 const controller=createAihotController({fetcher});
 await controller.activate(parseRoute('#/aihot/manage?section=sources'));
 assert.equal(controller.state.tab,'manage');assert.equal(calls.length,2);
 assert.ok(calls.every(([url])=>url.startsWith('/api/research/ai-news/')));
 const html=renderAihot(controller.state);assert.match(html,/&lt;b&gt;安全/);assert.match(html,/data-news-source="official"/);assert.match(html,/免费试抓/);assert.doesNotMatch(html,/https:\/\/aihot.news/);
 await controller.management.action('source.preview',{kind:'rss',config:{feedUrl:'https://example.org/rss'}});
 assert.equal(JSON.parse(calls.at(-1)[1].body).action,'source.preview');
});
test('unconfigured service never requests content or falls back externally',async()=>{
 const calls=[];const manager=createNewsManagement({fetcher:async url=>{calls.push(url);return {ok:true,json:async()=>({state:'not_configured'})};}});
 await manager.activate('sources');assert.equal(calls.length,1);assert.match(renderNewsManagement(manager.state),/not_configured/);
 await manager.activate('evaluation');assert.match(renderNewsManagement(manager.state),/NOT_RUN/);assert.equal(calls.length,2);
});
test('late management response cannot replace another section',async()=>{
 let finish;let count=0;
 const manager=createNewsManagement({fetcher:async()=>{count++;if(count===1)return new Promise(resolve=>{finish=()=>resolve({ok:true,json:async()=>({state:'stale'})});});return {ok:true,json:async()=>({state:'not_configured'})};}});
 const first=manager.activate('sources');await manager.activate('evaluation');finish();await first;
 assert.equal(manager.state.section,'evaluation');assert.equal(manager.state.status.state,'not_configured');
});
test('control failure remains visible without fabricating records',async()=>{
 const manager=createNewsManagement({fetcher:async()=>({ok:false,status:409,json:async()=>({})})});
 await manager.action('source.update',{id:'a',version:'old'});assert.match(manager.state.error,/409/);assert.equal(manager.state.data,null);
});
test('source update refreshes edit version and retains original history',async()=>{
 const manager=createNewsManagement({fetcher:async(_url,options)=>{
   const body=JSON.parse(options.body);return {ok:true,json:async()=>body.action==='source.detail'?{source:{id:'abc',updated_at:'new'},history:[{action:'source.update'}]}:{rows:[]}};
 }});
 manager.state.selection={id:'abc',updated_at:'old'};
 await manager.action('source.update',{id:'abc',version:'old',patch:{name:'new'}});
 assert.equal(manager.state.selection.updated_at,'new');assert.equal(manager.state.sourceDetail.history.length,1);
 assert.match(renderNewsManagement(manager.state),/采集运行、内容、统计与审计历史/);
});
test('duplicate address is not reported as successfully saved',async()=>{
 const manager=createNewsManagement({fetcher:async()=>({ok:true,json:async()=>({created:false,duplicate:{name:'existing'}})})});
 await manager.action('source.create',{id:'new'});assert.equal(manager.state.notice,'');assert.match(manager.state.error,/未创建/);
});
test('save refresh cannot overwrite a newly selected section',async()=>{
 let finish;const manager=createNewsManagement({fetcher:async(url,options)=>{
   if(url.endsWith('status'))return {ok:true,json:async()=>({state:'running'})};
   const body=JSON.parse(options.body);
   if(body.action==='source.list')return new Promise(resolve=>{finish=()=>resolve({ok:true,json:async()=>({rows:[{id:'old'}]})});});
   return {ok:true,json:async()=>body.action==='audit'?{audit:['current']}:{created:true}};
 }});
 const saving=manager.action('source.create',{id:'abc'});while(!finish)await new Promise(resolve=>setImmediate(resolve));
 await manager.activate('audit');finish();await saving;assert.deepEqual(manager.state.data,{audit:['current']});
});
test('preview preserves entered source configuration after rerender',async()=>{
 const original=globalThis.FormData;
 globalThis.FormData=class{constructor(){return new Map(Object.entries({id:'my-feed',name:'my draft',kind:'rss',config:'{"feedUrl":"https://example.org/rss"}',tier:'T1',interval:'30',mode:'editorial',operation:'preview'}));}};
 try{
   const manager=createNewsManagement({fetcher:async()=>({ok:true,json:async()=>({items:[]})})});
   await manager.submit({dataset:{newsForm:'source'}});const html=renderNewsManagement(manager.state);
   assert.match(html,/value="my draft"/);assert.match(html,/https:\/\/example.org\/rss/);assert.equal(manager.state.selection,null);
 }finally{globalThis.FormData=original;}
});
test('navigation cannot relabel an edited source draft as a new source',async()=>{
 const manager=createNewsManagement({fetcher:async()=>({ok:true,json:async()=>({state:'not_configured'})})});
 manager.state.selection={id:'existing'};manager.state.draft={id:'existing'};manager.state.preview={items:[]};
 await manager.activate('sources');assert.equal(manager.state.draft,null);assert.equal(manager.state.preview,null);assert.equal(manager.state.selection,null);
});
test('server members retain reading but never load or see global administration',async()=>{
 const calls=[];const controller=createAihotController({canManage:()=>false,fetcher:async url=>{calls.push(url);return {ok:true,json:async()=>({report:null,index:[]})};}});
 await controller.activate(parseRoute('#/aihot/manage?section=models'));
 assert.equal(calls.length,0);const html=renderAihot(controller.state);assert.match(html,/仅管理员/);assert.doesNotMatch(html,/data-news-form/);
 await controller.activate(parseRoute('#/aihot/daily'));assert.equal(calls.length,1);assert.doesNotMatch(renderAihot(controller.state),/>采编管理<\/a>/);
});
