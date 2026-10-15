import {test} from 'node:test';
import assert from 'node:assert/strict';
import {scoreChannel} from '../src/channel-rules.ts';
import type {ChannelConfig} from '../src/events.ts';

test('official low-heat policy keeps importance separate from relevance and old-import heat',()=>{
  const config:ChannelConfig={name:'Macro',topics:['interest rate'],sourceIds:['fed'],importanceRules:['Official rate decisions are material'],
    rules:[{id:'rates',keywords:['interest rate'],requireOfficial:true,relevance:95,importance:90}]};
  const report={id:'report',revision:1,contentHash:'hash',title:'Interest rate decision',excerpt:'Official policy',url:'https://www.federalreserve.gov/newsevents/pressreleases/test.htm',
    publishedAt:new Date('2026-10-08T00:00:00Z'),acquiredAt:new Date('2026-10-08T01:00:00Z'),state:'active',official:true,sources:[{id:'fed',operator:'Federal Reserve'}]};
  const result=scoreChannel(config,[report],[],new Date('2026-10-08T10:00:00Z'));
  assert.equal(result.judgment.importance,90);assert.equal(result.judgment.relevance,95);
  assert.ok(result.judgment.heat<result.judgment.importance);assert.equal(result.judgment.evidence,'single_official');
  assert.equal(result.metrics.reportCount,1);assert.equal(result.metrics.independentOperators,1);
  const old=scoreChannel(config,[{...report,publishedAt:new Date('2026-08-01T00:00:00Z')}],[],new Date('2026-10-08T10:00:00Z'));
  assert.equal(old.judgment.heat,0);assert.equal(old.judgment.importance,90);
  assert.equal(scoreChannel(config,[{...report,publishedAt:null}],[],new Date('2026-10-08T10:00:00Z')).judgment.heat,0);
  const unrelated=scoreChannel({...config,topics:['gold'],rules:[{id:'gold',keywords:['gold'],relevance:95,importance:85}]},[report],[],new Date('2026-10-08T10:00:00Z'));
  assert.equal(unrelated.judgment.relevance,0);assert.equal(unrelated.judgment.importance,0);
  assert.equal(scoreChannel(config,[report],[report.contentHash],new Date('2026-10-08T10:00:00Z')).judgment.informationIncrement,0);
  const repost={...report,id:'repost',sources:[{id:'fed-alias',operator:'Federal Reserve'}]};
  const syndicated=scoreChannel(config,[report,repost],[],new Date('2026-10-08T10:00:00Z'));
  assert.equal(syndicated.metrics.reportCount,2);assert.equal(syndicated.metrics.sourceCount,2);
  assert.equal(syndicated.metrics.independentOperators,1);assert.equal(syndicated.judgment.informationIncrement,25);
});
