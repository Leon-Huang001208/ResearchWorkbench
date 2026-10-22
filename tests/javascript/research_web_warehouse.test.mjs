import test from 'node:test';
import assert from 'node:assert/strict';
import {warehousePanelHTML,verifyWarehouseReads} from '../../app/research_web/ui/research-warehouse.mjs';

test('warehouse form escapes endpoint metadata and never renders saved secrets',()=>{
  const html=warehousePanelHTML({configured:true,enabled:false,configuration:{host:'"><img src=x>',password:'synthetic-secret'}});
  assert.doesNotMatch(html,/<img|synthetic-secret/);
  assert.match(html,/初始化并启用研究仓/);
  assert.doesNotMatch(html,/data-warehouse-validate/);
});

const parameters={asset:'000001.SZ',source:'akshare',start_date:'2025-01-02',end_date:'2025-01-03'};
function fixture(persisted=true,hit=true){
  let calls=0,reads=0;
  const api={
    async createAssetObservation(body){
      calls++; assert.deepEqual(body.sections,['history']); assert.equal(body.adjustment,'none');
      return {id:`observation-${calls}`,session_id:'owned-session',blocks:{history:{status:'complete',dataset:{dataset_id:'dataset',row_count:2}}}};
    },
    async datasetManifest(){reads++;return {source:'akshare',row_count:2,provider_metadata:reads===1?{warehouse_persisted:persisted}:{warehouse_hit:hit,warehouse_snapshot_sha256:'a'.repeat(64)}};},
  };
  return {api,get calls(){return calls;}};
}

test('bounded validation requires actual persistence and a second warehouse hit',async()=>{
  let refreshed=0;
  const f=fixture(); const result=await verifyWarehouseReads(f.api,parameters,{onVerified:async()=>{refreshed++;}});
  assert.equal(refreshed,1);
  assert.equal(f.calls,2);assert.equal(result.rows,2);assert.equal(result.snapshot,'a'.repeat(64));
  const failed=fixture(false);
  await assert.rejects(verifyWarehouseReads(failed.api,parameters,{onVerified:async()=>{refreshed++;}}),/没有持久化/);
  assert.equal(refreshed,1);
  assert.equal(failed.calls,1);
  await assert.rejects(verifyWarehouseReads(fixture(true,false).api,parameters),/第二次没有得到/);
});

test('warehouse validation rejects paid sources and oversized ranges before any request',async()=>{
  const f=fixture();
  await assert.rejects(verifyWarehouseReads(f.api,{...parameters,source:'wind'}));
  await assert.rejects(verifyWarehouseReads(f.api,{...parameters,end_date:'2025-02-03'}));
  assert.equal(f.calls,0);
});
