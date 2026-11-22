import test from 'node:test';
import assert from 'node:assert/strict';
import {chroniclePart} from '../chronicle.mjs';
test('topic chronology uses rechecked local evidence and keeps all three dates distinct',()=>{
 const row={id:'abc',title:'Source claim',revision:2,factId:7,scope:'single',publishedAt:new Date('2026-01-03'),factOccurredAt:new Date('2026-01-01')};
 const result=chroniclePart([row,{...row,id:'withdrawn'}],new Map([['abc',row]]),new Map([['abc',new Date('2026-01-05')]]));
 assert.equal(result.chronicle.length,1);const point=result.chronicle[0];assert.equal(point.timeKind,'event');assert.equal(point.at,'2026-01-01T00:00:00.000Z');assert.equal(point.publishedAt,'2026-01-03T00:00:00.000Z');assert.equal(point.collectedAt,'2026-01-05T00:00:00.000Z');assert.equal(point.provenance.revision,2);
 const composite={...row,scope:'composite'};assert.equal(chroniclePart([composite],new Map([['abc',composite]])).chronicle[0].occurredAt,null);
 assert.equal(chroniclePart([{id:'unknown'}],new Map([['unknown',{id:'unknown'}]])).chronicle.length,0);
 const moved={...row,topics:['other']};assert.equal(chroniclePart([row],new Map([['abc',moved]]),new Map(),'openai').chronicle.length,0);
});
