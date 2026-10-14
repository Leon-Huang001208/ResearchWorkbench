import {test} from 'node:test';
import assert from 'node:assert/strict';
import {hotReaderDays,renderHotReaderFeed,renderHotReaderRank} from '../../app/research_web/ui/hot-reader.mjs';
import {createHotController} from '../../app/research_web/ui/hot-workspace.mjs';

test('reader groups observation dates without inventing publication freshness',()=>{
  const events=[{id:'old',observedAt:'2026-10-12T23:00:00Z',publishedAt:'2020-01-01'}, {id:'unknown',observedAt:null}];
  const days=hotReaderDays(events,'Asia/Shanghai');
  assert.equal(days[0].key,'2026-10-13');assert.equal(days[1].key,'unknown');
  const html=renderHotReaderFeed(events,'Asia/Shanghai');
  assert.match(html,/观察记录/);assert.match(html,/观察时间未知/);assert.doesNotMatch(html,/今天热点|今日发布/);
});
test('feed and page-scoped ranking escape source content and preserve independent metrics',()=>{
  const events=[{id:'a',title:'<img src=x>',observedAt:null,materialCount:1,judgment:{heat:3,importance:2,reason:'<script>bad</script>'}},
    {id:'b',title:'Official policy',observedAt:null,materialCount:1,judgment:{heat:0,importance:3,reason:'Important with one source'}}];
  const before=JSON.stringify(events),feed=renderHotReaderFeed(events,'Asia/Shanghai'),ranking=renderHotReaderRank(events);
  assert.match(feed,/研究重要性/);assert.match(feed,/传播热度/);assert.match(feed,/Official policy/);
  assert.match(ranking,/本页/);assert.match(feed,/&lt;img/);assert.doesNotMatch(feed+ranking,/<script>|<img src=x>/);
  assert.equal(JSON.stringify(events),before);assert.doesNotMatch(ranking,/热度上升|准确率|全市场/);
});
test('reader channel and sort actions only reload owned read projections',async()=>{
  const calls=[],controller=createHotController({api:{hotEvents:async query=>{calls.push(query);return {items:[],cutoff:'2026-10-13T00:00:00Z',offset:0,hasMore:false};}}});
  controller.state.channels=[{channel_id:'macro',config:{name:'宏观政策'}}];
  await controller.action({dataset:{hotAction:'feed-channel',channel:'macro'}});
  await controller.action({dataset:{hotAction:'feed-sort',sort:'importance'}});
  assert.equal(calls.length,2);assert.equal(calls[1].channelId,'macro');assert.equal(calls[1].sort,'importance');
  await controller.action({dataset:{hotAction:'feed-sort',sort:'invented'}});assert.equal(calls.length,2);
});
test('failed new channel cannot retain or paginate an old channel snapshot',async()=>{
  let calls=0;
  const c=createHotController({api:{hotEvents:async()=>{calls++;throw Error('offline');}}});
  c.state.channels=[{channel_id:'macro',config:{name:'宏观'}}];
  c.state.events=[{id:'old-ai'}];c.state.cutoff='old-cutoff';c.state.hasMore=true;
  await c.action({dataset:{hotAction:'feed-channel',channel:'macro'}});
  assert.deepEqual(c.state.events,[]);assert.equal(c.state.hasMore,false);assert.equal(c.state.cutoff,'');
  await c.action({dataset:{hotAction:'more'}});assert.equal(calls,1);
});
test('late rejected reader request cannot overwrite a newer view error',async()=>{
  let reject;
  const c=createHotController({api:{hotEvents:()=>new Promise((_,no)=>{reject=no;})}});
  c.state.channels=[{channel_id:'macro',config:{name:'宏观'}}];
  const pending=c.action({dataset:{hotAction:'feed-channel',channel:'macro'}});
  c.deactivate();c.state.error='new-view-error';reject(Error('stale reader failure'));await pending;
  assert.equal(c.state.error,'new-view-error');
});
test('late rejected page load keeps a newer view error intact',async()=>{
  let reject;
  const c=createHotController({api:{hotEvents:()=>new Promise((_,no)=>{reject=no;})}});
  c.state.hasMore=true;c.state.cutoff='frozen';
  const pending=c.action({dataset:{hotAction:'more'}});
  c.deactivate();c.state.error='new-view-error';reject(Error('old-page-error'));await pending;
  assert.equal(c.state.error,'new-view-error');
});
