import{test}from'node:test';import assert from'node:assert/strict';import{hotTime}from'../../app/research_web/ui/hot-workspace.mjs';
test('day precision does not gain a time or shift across display zones',()=>{
 assert.equal(hotTime('2026-03-17','America/Los_Angeles'),'2026-03-17（日精度）');
 assert.equal(hotTime('2026-02-30'),'未知');assert.equal(hotTime(null),'未知');
});
