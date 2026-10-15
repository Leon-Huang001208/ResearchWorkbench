import{test}from'node:test';import assert from'node:assert/strict';import{eventDate}from'../src/events.ts';
const ref={id:'22222222-2222-4222-8222-222222222222',revision:1,quote:'The policy takes effect on 17 March 2026.'};
test('event dates preserve day precision and source timezone; malformed dates or evidence are rejected',()=>{
 const day={value:'2026-03-17',precision:'day',timezone:'Europe/London',evidence:ref};assert.deepEqual(eventDate(day),day);assert.equal(eventDate(null),null);
 const instant={...day,value:'2026-03-17T11:30:00.000Z',precision:'instant'};assert.deepEqual(eventDate(instant),instant);
 for(const bad of [{...day,value:'2026-02-30'},{...day,timezone:'bad_zone'},{...instant,value:'2026-03-17T11:30:00'},{...day,evidence:{...ref,revision:0}},{...day,evidence:{...ref,quote:''}},{...day,extra:true}])assert.throws(()=>eventDate(bad),/hot_event_time_invalid/);
});
