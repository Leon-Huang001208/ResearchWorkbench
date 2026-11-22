import test from 'node:test';
import assert from 'node:assert/strict';
import {matchingModelProviders,renderModelProfileList,renderModelProfileForm} from '../../app/research_web/ui/model-settings.mjs';
import {createAPI} from '../../app/research_web/ui/core.mjs';

test('provider directory searches names/domains and filters without making up providers',()=>{
 assert.equal(matchingModelProviders().length,2);
 assert.equal(matchingModelProviders('deepseek.com')[0].id,'deepseek-official');
 assert.equal(matchingModelProviders('本机','custom')[0].id,'openai-compatible');
 assert.deepEqual(matchingModelProviders('本机','official'),[]);
 assert.deepEqual(matchingModelProviders('unknown'),[]);
});
test('provider cards escape names, include brand icon and preserve uncertain truth',()=>{
 const html=renderModelProfileList({runtime:{owned_runtime:true,connected:true},items:[{id:'a'.repeat(32),name:'<script>canary</script>',provider:'deepseek-official',model:'deepseek-flash',active:true,uncertain:true}]});
 assert.match(html,/assets\/providers\/deepseek.svg/);assert.match(html,/&lt;script&gt;/);assert.doesNotMatch(html,/<script>/);assert.match(html,/提交结果未知/);assert.match(html,/使用中/);assert.match(html,/生成验证 · 未测试/);
});
test('editor keeps key out of markup and disables hidden protocol fields',()=>{
 const html=renderModelProfileForm({item:{provider:'deepseek-official',model:'deepseek-flash',name:'One',api_key:'synthetic-secret-canary'},runtime:{owned_runtime:true}});
 assert.doesNotMatch(html,/synthetic-secret-canary/);assert.match(html,/id="api-key"[^>]*type="password"/);assert.doesNotMatch(html,/id="api-key"[^>]*value=/);assert.match(html,/id="profile-base-url"[^>]*disabled/);
 const keyless=renderModelProfileForm({item:{provider:'openai-compatible',model:'local',credential_mode:'none',base_url:'http:\/\/127.0.0.1:8000/v1'},runtime:{owned_runtime:true}});
 assert.match(keyless,/id="api-key"[^>]*disabled/);assert.match(keyless,/data-mp-key hidden/);
});
test('model profile API is scoped and does not expose arbitrary credentials operations',async()=>{
 const calls=[];const api=createAPI({fetcher:async(url,options)=>{calls.push({url,method:options?.method});return{ok:true,json:async()=>({items:[]})};}});
 await api.modelProfiles();await api.saveModelProfile('a'.repeat(32),{name:'One'});await api.activateModelProfile('a'.repeat(32));await api.archiveModelProfile('a'.repeat(32));
 assert.deepEqual(calls.map(item=>item.method||'GET'),['GET','PUT','POST','DELETE']);
 assert.match(calls[2].url,/model-profiles\/a{32}\/activate$/);
});

test('critical unknown submission remains outside collapsed diagnostics',()=>{
 const html=renderModelProfileForm({item:{provider:'deepseek-official',model:'deepseek-flash',name:'One',uncertain:true},runtime:{owned_runtime:true}});
 assert.ok(html.indexOf('此连接的凭据提交结果未知')>=0);assert.ok(html.indexOf('此连接的凭据提交结果未知')<html.indexOf('<details'));
});
