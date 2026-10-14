import {test} from 'node:test';
import assert from 'node:assert/strict';
import {parseFollowRequest} from '../src/follows.ts';
const id='11111111-1111-4111-8111-111111111111';
const input={followId:id,expectedVersion:0,config:{kind:'channel',target:'macro',name:'宏观政策',enabled:true},reason:'关注政策变化'};
test('follow control validates kind, target, bounded text, strict revision and booleans',()=>{
  assert.deepEqual(parseFollowRequest(input),input);
  for(const value of [{...input,expectedVersion:true},{...input,unexpected:1},{...input,reason:' '},
    {...input,config:{...input.config,enabled:'true'}},{...input,config:{...input.config,kind:'sql'}},
    {...input,config:{...input.config,target:'macro;drop'}},{...input,config:{...input.config,name:'x'.repeat(121)}},
    {...input,config:{...input.config,kind:'event',target:'not-uuid'}}])assert.throws(()=>parseFollowRequest(value),/hot_follow_request_invalid/);
});
test('event and literal keyword follows preserve targets; unknown nested config is rejected',()=>{
  assert.equal(parseFollowRequest({...input,config:{...input.config,kind:'event',target:id.toUpperCase()}}).config.target,id);
  for(const kind of ['keyword','institution','asset'])assert.equal(parseFollowRequest({...input,config:{...input.config,kind,target:'100%_policy'}}).config.target,'100%_policy');
  assert.throws(()=>parseFollowRequest({...input,config:{...input.config,secret:'bad'}}),/hot_follow_request_invalid/);
});
