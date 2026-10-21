import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import {createAccountAPI, legacyAccountTarget} from '../../app/research_web/ui/server/account-api.mjs';

const source = readFileSync(new URL('../../app/research_web/ui/server/accounts.mjs', import.meta.url), 'utf8').replace(/^import .*;$/gm, '');
const settle = () => new Promise(resolve => setImmediate(resolve));
function fixture(fetcher, pathname = '/auth') {
  const logs = [], redirects = [], requests = [];
  const button = {disabled:false, textContent:'登录'};
  const password = {value:'fixture-secret'};
  const message = {textContent:''};
  let submit;
  const form = {hidden:true, attributes:{}, elements:{username:{value:'fixture-user'}, password}, querySelector:()=>button, setAttribute(name,value){this.attributes[name]=value;}, addEventListener(name,handler){assert.equal(name,'submit');submit=handler;}};
  const nodes = {'login-form':form, message, heading:{textContent:''}, description:{textContent:''}};
  vm.runInNewContext(source, {createAccountAPI:options=>createAccountAPI({...options,fetcher:async(...args)=>{requests.push(args);return fetcher(...args);}}),legacyAccountTarget,safeLog:(...args)=>logs.push(args),document:{getElementById:id=>nodes[id]},location:{pathname,assign:url=>redirects.push(url),replace:url=>redirects.push(url)}});
  return {form,button,password,message,requests,logs,redirects,submit:()=>submit({preventDefault(){}})};
}

test('login communicates pending state and prevents repeated submissions, then clears password on success', async()=>{
  let finish;
  const f=fixture(()=>new Promise(resolve=>{finish=resolve;}));
  f.submit();f.submit();
  assert.equal(f.requests.length,1);
  assert.equal(f.button.disabled,true);
  assert.equal(f.button.textContent,'正在登录…');
  assert.equal(f.form.attributes['aria-busy'],'true');
  assert.equal(f.message.textContent,'正在登录…');
  assert.deepEqual(JSON.parse(f.requests[0][1].body),{username:'fixture-user',password:'fixture-secret'});
  finish({ok:true,status:200,json:async()=>({ok:true})});await settle();
  assert.deepEqual(f.redirects,['/']);assert.equal(f.password.value,'');
  assert.equal(f.form.attributes['aria-busy'],'false');assert.equal(f.button.textContent,'登录');
});
test('failed login is visible and retryable without exposing credentials in logs',async()=>{
  let attempt=0;
  const f=fixture(async()=>++attempt===1?{ok:false,status:401,json:async()=>({error:{code:'invalid_credentials'}})}:{ok:true,status:200,json:async()=>({ok:true})});
  f.submit();await settle();
  assert.equal(f.message.textContent,'账号或密码不正确。');assert.equal(f.button.disabled,false);assert.equal(f.password.value,'');
  assert.equal(f.button.textContent,'登录');assert.equal(f.form.elements.username.value,'fixture-user');
  assert.ok(!JSON.stringify(f.logs).includes('fixture-secret'));
  f.password.value='fixture-retry';f.submit();await settle();assert.deepEqual(f.redirects,['/']);
});
test('network failure clears password and leaves login available',async()=>{
  const f=fixture(async()=>{throw Error('fixture transport failure');});f.submit();await settle();
  assert.match(f.message.textContent,/网络请求未完成/);assert.equal(f.password.value,'');assert.equal(f.button.disabled,false);assert.equal(f.form.attributes['aria-busy'],'false');
});
test('old account document still redirects without creating a login handler',()=>{
  const f=fixture(()=>{throw Error('unexpected request');},'/account');assert.deepEqual(f.redirects,['/#/account']);assert.equal(f.requests.length,0);assert.equal(f.form.hidden,true);
});
