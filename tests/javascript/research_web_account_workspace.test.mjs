import assert from 'node:assert/strict';
import test from 'node:test';
import { parseRoute, legacyRouteTarget } from '../../app/research_web/ui/core.mjs';
import { renderSettingsPage, resolveSettingsSection } from '../../app/research_web/ui/settings.mjs';
import { renderAccountMenu } from '../../app/research_web/ui/server/account-menu.mjs';
import { createAccountAPI, legacyAccountTarget } from '../../app/research_web/ui/server/account-api.mjs';
import { createAccountWorkspace, renderAccountProfile, userActions } from '../../app/research_web/ui/server/account-workspace.mjs';

test('identity header opens account workspace and settings has only admin user management', () => {
  const admin = { username:'admin', role:'admin' };
  const menu = renderAccountMenu(admin);
  assert.match(menu, /class="account-identity[^\"]*"[^>]*href="#\/account"/);
  assert.doesNotMatch(menu, /<span>我的账号<\/span>|href="\/account"/);
  assert.equal(parseRoute('#/account').page, 'account');
  assert.equal(legacyRouteTarget('#/settings/account'), '#/account');
  assert.equal(parseRoute('#/settings/users').settingsSection, 'users');
  assert.match(renderSettingsPage({account:admin}), /href="#\/settings\/users"/);
  for (const account of [null, {username:'reader',role:'user'}]) {
    const html = renderSettingsPage({account,route:{settingsSection:'users'}});
    assert.doesNotMatch(html, /data-account-management-slot|href="#\/settings\/users"/);
    assert.equal(resolveSettingsSection({settingsSection:'users'}, [], account), 'general');
  }
});

test('profile escapes identity and does not invent usage; compatibility enters the app', () => {
  const html=renderAccountProfile({username:'<img src=x>',role:'user'});
  assert.ok(html.includes('&lt;img src=x&gt;'));
  assert.ok(!html.includes('settings-navigation'));
  assert.ok(!html.includes('Token'));
  assert.equal(legacyAccountTarget('/account'),'/#/account');
  assert.equal(legacyAccountTarget('/auth'),null);
  assert.equal(legacyAccountTarget('/','#/settings/account'),'/#/account');
  assert.deepEqual(userActions({id:'primary'},{id:'me'},'primary'),{reset:true,toggle:false,stop:false});
  assert.deepEqual(userActions({id:'me'},{id:'me'},'primary'),{reset:true,toggle:false,stop:true});
});

test('API preserves cookie/body binding; expired/non-JSON errors never leak responses', async () => {
  const sent=[],redirects=[],logs=[];
  const request=createAccountAPI({fetcher:async(...args)=>{sent.push(args);return {ok:true,status:201,json:async()=>({ok:true})};},logger:(...args)=>logs.push(args)});
  await request('users','POST',{username:'sample',password:'fake-test-only'});
  assert.equal(sent[0][1].credentials,'same-origin');
  assert.deepEqual(JSON.parse(sent[0][1].body),{username:'sample',password:'fake-test-only'});
  const expired=createAccountAPI({fetcher:async()=>({ok:false,status:401,json:async()=>{throw Error('secret-response');}}),redirect:url=>redirects.push(url),logger:(...args)=>logs.push(args)});
  await assert.rejects(expired('users'),error=>error.code==='login_required');
  assert.deepEqual(redirects,['/auth']);
  const forbidden=createAccountAPI({fetcher:async()=>({ok:false,status:403,json:async()=>({error:{code:'private-response'}})}),logger:(...args)=>logs.push(args)});
  await assert.rejects(forbidden('users'),error=>error.code==='forbidden');
  assert.ok(!JSON.stringify(logs).includes('secret-response')&&!JSON.stringify(logs).includes('fake-test-only'));
});

test('login rejection remains on login; network timeout is bounded and not automatically retried', async () => {
  const redirects=[];let calls=0;
  const request=createAccountAPI({fetcher:async()=>({ok:false,status:401,json:async()=>({error:{code:'invalid_credentials'}})}),redirect:url=>redirects.push(url)});
  await assert.rejects(request('login','POST',{}),error=>error.code==='invalid_credentials');
  assert.deepEqual(redirects,[]);
  const timeout=createAccountAPI({timeout:5,fetcher:async(url,options)=>{calls++;return new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(Error('aborted'))));}});
  await assert.rejects(timeout('users'),error=>error.code==='account_network_failed');
  assert.equal(calls,1);
});

function deferredWorkspace(role='admin') {
  const pending=[],events={},panels=[];
  const slot={contains:panel=>slot.panel===panel,replaceChildren:panel=>{slot.panel=panel;}};
  const root={querySelector:()=>slot,addEventListener(){}};
  const document={createElement(){const status={textContent:'',setAttribute(){}};const list={innerHTML:''};const panel={status,list,querySelector:s=>s==='[data-user-message]'?status:s==='[data-user-list]'?list:null,querySelectorAll:()=>[],replaceChildren(){},contains:()=>false};panels.push(panel);return panel;},addEventListener(){},activeElement:null,body:{}};
  const window={location:{hash:'#/settings/users'},addEventListener:(name,fn)=>{events[name]=fn;}};
  const controller=createAccountWorkspace({root,user:{id:'admin',role},document,window,fetcher:()=>new Promise(resolve=>pending.push(resolve))});
  return {controller,pending,events,panels,window};
}
const flush=()=>new Promise(resolve=>setImmediate(resolve));
const response=()=>({ok:true,status:200,json:async()=>({items:[{id:'admin',username:'admin',role:'admin',enabled:true}],primary_user_id:'admin'})});
test('leaving and returning during initial load reloads the new panel and ignores stale response', async () => {
  const f=deferredWorkspace();f.controller.sync();assert.equal(f.pending.length,1);
  f.window.location.hash='#/account';f.events.hashchange();f.window.location.hash='#/settings/users';f.controller.sync();
  assert.equal(f.panels.length,2);f.pending.shift()(response());await flush();assert.equal(f.pending.length,1);
  assert.equal(f.panels[1].list.innerHTML,'');f.pending.shift()(response());await flush();
  assert.ok(f.panels[1].list.innerHTML.includes('admin'));assert.equal(f.panels[1].status.textContent,'');
});
test('ordinary users never mount management DOM or fetch user data', () => {
  const f=deferredWorkspace('user');f.controller.sync();assert.equal(f.panels.length,0);assert.equal(f.pending.length,0);
});
test('missing primary identity fails closed rather than exposing unknown stop controls', async () => {
  const f=deferredWorkspace();f.controller.sync();f.pending.shift()({ok:true,status:200,json:async()=>({items:[{id:'primary',username:'admin',role:'admin',enabled:true}]})});await flush();
  assert.equal(f.panels[0].list.innerHTML,'');assert.match(f.panels[0].status.textContent,/返回异常/);
});
