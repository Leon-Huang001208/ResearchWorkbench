import {test} from 'node:test';
import assert from 'node:assert/strict';
import {sourceChange} from '../src/source-control.ts';

test('catalog activation requires explicit bounded reason and never accepts arbitrary source endpoints',()=>{
  const change={sourceId:'fed',expectedRevision:'4',useCatalog:true,reason:'Resume verified public source'};
  assert.deepEqual(sourceChange(change),change);
  for(const value of [{...change,useCatalog:1},{...change,reason:''},{...change,reason:'x'.repeat(1001)},
    {...change,url:'https://elsewhere.invalid/'},{...change,useCatalog:false},{sourceId:'fed',expectedRevision:'4',reason:'no activation'}]){
    assert.throws(()=>sourceChange(value as any),/hot_source_config_invalid/);
  }
  assert.deepEqual(sourceChange({sourceId:'fed',expectedRevision:'4',enabled:true}),{sourceId:'fed',expectedRevision:'4',enabled:true});
});
