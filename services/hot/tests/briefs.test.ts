import {test} from 'node:test';
import assert from 'node:assert/strict';
import {sealBrief,briefMarkdown} from '../src/briefs.ts';
const payload=()=>({schemaVersion:1 as const,cutoff:'2026-10-08T00:00:00.000Z',timezone:'Asia/Shanghai',
  window:{from:null,to:null},channel:{channel_id:'macro',version:2,config:{name:'Macro'}},
  events:[{canonicalId:'event-id',revision:1,title:'<script>publisher</script>',occurredAt:null,effectiveAt:null,
    materialCount:1,reports:[{materialId:'material-id',revision:1,contentHash:'a'.repeat(64),title:'Official [release]',url:'javascript:bad',
      excerpt:'Source says <img src=x>\n# instruction',excerptIsPartial:true,state:'active',publishedAt:null,acquiredAt:'2026-10-07T00:00:00Z',sources:[]}],
    judgments:[{channelId:'macro',authority:'human',id:'judgment-id',event_revision:1,channel_version:1,inherited:true,
      applied_event_revision:2,applied_channel_version:2,judgment:{relevance:90,importance:80,heat:0,informationIncrement:0,reason:'Policy evidence'},ruleEvidence:null}]}],
  limitations:['Snapshot coverage does not imply complete coverage']});
test('brief seal is canonical, validates content and separates source text from derived titles',()=>{
  const brief=sealBrief(payload()),md=briefMarkdown(brief);
  assert.ok(md.includes('事件摘要（归组结果）'));assert.ok(md.includes('来源摘录'));assert.ok(md.includes('人工判断'));
  assert.ok(md.includes('原事件版本 1 · 原频道版本 1'));assert.ok(md.includes('应用版本：事件 2 · 频道 2 · 继承判断'));
  assert.ok(md.includes('Asia/Shanghai'));assert.ok(md.includes('未知'));assert.ok(md.includes('版本 1'));
  assert.ok(md.includes('摘录截断'));assert.ok(!md.includes('<script>'));assert.ok(!md.includes('<img'));assert.ok(!md.includes('javascript:'));
  assert.equal(sealBrief({...payload(),events:payload().events,cutoff:payload().cutoff}).contentHash,brief.contentHash);
  const changed=structuredClone(brief);changed.payload.events=[];
  assert.throws(()=>briefMarkdown(changed),/hot_brief_integrity_invalid/);
});
test('brief rejects invalid timezones and oversized input before sealing',()=>{
  assert.throws(()=>sealBrief({...payload(),timezone:'Unknown/Invalid'}),/hot_brief_timezone_invalid/);
  assert.throws(()=>sealBrief({...payload(),cutoff:'2026-02-30T00:00:00Z'}),/hot_brief_window_invalid/);
  assert.throws(()=>sealBrief({...payload(),events:Array(21).fill(payload().events[0])}),/hot_brief_limit/);
});
test('publisher titles cannot open tilde code fences, horizontal rules or indented blocks',()=>{
  const p=payload();p.events[0].title='~~~html';p.events[0].reports[0].title='    ---';
  const markdown=briefMarkdown(sealBrief(p));
  assert.ok(markdown.includes('\\~\\~\\~html'));assert.ok(markdown.includes('\\-\\-\\-'));
  assert.ok(!markdown.includes('\n~~~'));assert.ok(!markdown.includes('\n    '));
  assert.ok(markdown.includes('### 人工判断'));assert.ok(markdown.includes('### 来源摘录'));
});
