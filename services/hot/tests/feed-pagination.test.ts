import {test} from 'node:test';
import assert from 'node:assert/strict';
import {acquireFeedPages} from '../src/collection.ts';
const source={id:'example',operator:'Example',channelHint:'ai',official:true,url:'https://example.org/feed'};
const feed=(next='',date='')=>`<feed><link rel="next" href="${next}"/><entry><title>Article</title><link href="https://example.org/article"/>${date?`<published>${date}</published>`:''}</entry></feed>`;
test('actual next requests are same-origin, bounded and retain earlier pages on HTTP failure',async()=>{
 const calls:string[]=[];
 const result=await acquireFeedPages(source,new AbortController().signal,30,async url=>{
  calls.push(String(url));return calls.length===1?new Response(feed('/page2')):new Response('',{status:503});
 });
 assert.deepEqual(calls,['https://example.org/feed','https://example.org/page2']);
 assert.equal(result.pages.length,2);assert.equal(result.pages[0].acquired.items.length,1);
 assert.equal(result.gap,'hot_source_http_failed');
});
test('cross-origin, cycles, page ceiling and disabled backfill never send an unsafe extra request',async()=>{
 for(const [next,days,expected,callsExpected] of [
  ['https://other.org/next',30,'hot_source_pagination_unsafe',1],
  ['/feed',30,'hot_source_pagination_cycle',1],
  ['/page2',0,'hot_source_backfill_disabled',1],
 ] as const){let calls=0;const result=await acquireFeedPages(source,new AbortController().signal,days,async()=>{calls++;return new Response(feed(next));});assert.equal(result.gap,expected);assert.equal(calls,callsExpected);}
 let calls=0;const bounded=await acquireFeedPages(source,new AbortController().signal,30,async()=>new Response(feed(`/page${++calls+1}`)));
 assert.equal(calls,3);assert.equal(bounded.gap,'hot_source_page_limit');
});
test('range boundary and unpaginated snapshots retain accurate gaps and raw items',async()=>{
 let calls=0;const old=await acquireFeedPages(source,new AbortController().signal,1,async()=>{calls++;return new Response(feed('/page2','2020-01-01T00:00:00Z'));});
 assert.equal(calls,1);assert.equal(old.gap,'hot_source_backfill_boundary');assert.equal(old.pages[0].acquired.items.length,1);
 const single=await acquireFeedPages(source,new AbortController().signal,30,async()=>new Response(feed()));
 assert.equal(single.gap,null);assert.equal(single.stop,'no_next_link');assert.equal(single.pages.length,1);
});
