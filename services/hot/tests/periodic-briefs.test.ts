import {test} from 'node:test';
import assert from 'node:assert/strict';
import {parsePeriodicConfig,nextPeriodicDue,periodicIdentity} from '../src/periodic-briefs.ts';
const config={name:'宏观日简报',channelId:'macro',enabled:false,firstRunAt:'2026-10-14T08:00:00Z',intervalSeconds:86400,windowSeconds:86400,maxEvents:10,timezone:'Asia/Shanghai',sort:'importance'};
test('periodic config is bounded, strict, non-paid and uses an explicit timezone',()=>{
  assert.equal(parsePeriodicConfig(config).firstRunAt,'2026-10-14T08:00:00.000Z');
  for(const value of [{...config,enabled:1},{...config,intervalSeconds:0},{...config,maxEvents:21},{...config,timezone:'Missing/Zone'},{...config,firstRunAt:'2026-02-30T08:00:00Z'},{...config,model:true},{...config,sort:'model'}])assert.throws(()=>parsePeriodicConfig(value),/hot_periodic_config_invalid/);
});
test('late scheduler publishes one persisted due window and records skipped periods, not a catch-up burst',()=>{
  const due=new Date('2026-10-10T08:00:00Z'),now=new Date('2026-10-14T09:00:00Z');
  const result=nextPeriodicDue(due,86400,now);assert.equal(result.next.toISOString(),'2026-10-15T08:00:00.000Z');assert.equal(result.missedPeriods,4);
  assert.deepEqual(nextPeriodicDue(due,86400,due),{next:new Date('2026-10-11T08:00:00Z'),missedPeriods:0});
});
test('one plan version and due instant have stable independent run/brief/request identities',()=>{
  const id='11111111-1111-4111-8111-111111111111',due='2026-10-14T08:00:00.000Z';
  const first=periodicIdentity(id,1,due);assert.deepEqual(first,periodicIdentity(id,1,due));
  assert.equal(new Set(Object.values(first)).size,3);assert.notDeepEqual(first,periodicIdentity(id,2,due));
});
