import {test} from 'node:test';
import assert from 'node:assert/strict';
import {acquireFeed,publicSources} from '../src/collection.ts';

test('same URL and content with contradictory publication times stays unknown without blocking the feed',async()=>{
  const source=(await publicSources())[0];
  const xml='<rss><channel><item><title>Same article</title><link>https://openai.com/index/article</link><description>Same content</description><pubDate>Tue, 29 Sep 2026 17:00:00 GMT</pubDate></item><item><title>Same article</title><link>https://openai.com/index/article</link><description>Same content</description><pubDate>Tue, 29 Sep 2026 10:00:00 GMT</pubDate></item></channel></rss>';
  const result=await acquireFeed(source,new AbortController().signal,async()=>new Response(xml));
  assert.equal(result.code,null);assert.equal(result.items.length,1);
  assert.equal(result.items[0].publishedAt,null);
  assert.deepEqual(JSON.parse(result.items[0].publishedRaw),['Tue, 29 Sep 2026 10:00:00 GMT','Tue, 29 Sep 2026 17:00:00 GMT']);
  assert.equal(result.raw?.toString('utf8'),xml);
  const reversed=xml.replace(/(<item>[\s\S]*?<\/item>)(<item>[\s\S]*?<\/item>)/,'$2$1');
  const other=await acquireFeed(source,new AbortController().signal,async()=>new Response(reversed));
  assert.deepEqual(other.items,result.items); // Listing order is not a source revision.
  const conflicting=xml.replace('<title>Same article</title>','<title>Different article</title>');
  const unsafe=await acquireFeed(source,new AbortController().signal,async()=>new Response(conflicting));
  assert.equal(unsafe.code,'hot_source_identity_conflict');assert.equal(unsafe.raw?.toString('utf8'),conflicting);
});
