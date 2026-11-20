import assert from 'node:assert/strict';
import test from 'node:test';
import {readFileSync} from 'node:fs';
import {createKnowledgeSettings, knowledgePanelHTML, mountKnowledgeSettings, safeKnowledgeManagementURL} from '../../app/research_web/ui/knowledge-settings.mjs';
import {createAPI} from '../../app/research_web/ui/core.mjs';

const settle = () => new Promise(resolve => setImmediate(resolve));
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return {promise, resolve, reject}; };
const configured = {enabled: true, configured: true, user_id: 'user-1', workspace_id: '7', connectivity: 'not_verified', live_acceptance: false, management_url: 'https://knowledge.example.test/'};

function fixture(request = async () => configured) {
  const requests = [], logs = [], handlers = new Map();
  const element = {
    html: '', renders: 0, removed: false,
    set innerHTML(value) {
      this.html = value; this.renders++;
      this.token = {value: ''};
      this.email = {value: ''}; this.password = {value: ''};
      this.workspace = {value: value.match(/name="workspace_id"[^>]*value="([^"]*)"/)?.[1] || ''};
    },
    get innerHTML() { return this.html; },
    addEventListener(name, handler) { handlers.set(name, handler); },
    removeEventListener(name, handler) { if (handlers.get(name) === handler) handlers.delete(name); },
    querySelector(selector) { return ({'[name="token"]':this.token,'[name="password"]':this.password,'[name="email"]':this.email})[selector] || null; },
    remove() { this.removed = true; },
  };
  const api = {request(path, options = {}) { requests.push({path, ...options, body: options.body ? {...options.body} : undefined}); return request(path, options); }};
  const document = {createElement: () => element};
  const controller = createKnowledgeSettings({api, document, logger: event => logs.push(event)});
  function submit(token = 'synthetic-jwt-secret', workspace = '7') {
    const input = element.token; input.value = token; element.workspace.value = workspace;
    const form = {matches: selector => selector === '[data-knowledge-binding]', elements: {namedItem: name => name === 'token' ? input : element.workspace}};
    handlers.get('submit')?.({target: form, preventDefault() {}, stopPropagation() {}});
    return input;
  }
  function click(action, data = {}) {
    const target = {disabled: false, dataset: {knowledgeAction: action,...data}};
    handlers.get('click')?.({target: {closest: () => target}, preventDefault() {}, stopPropagation() {}});
  }
  function form(kind, fields) {
    const form = {matches: selector => selector === `[data-knowledge-${kind}]`, elements: {namedItem:name=>({value:fields[name] ?? ''})}};
    handlers.get('submit')?.({target:form,preventDefault(){},stopPropagation(){}});
  }
  function change(dataset,value,checked) {
    handlers.get('change')?.({target:{dataset,value,checked},stopPropagation(){}});
  }
  function login(email='person@example.test',password='private-password') {
    const inputs={email:element.email,password:element.password}; inputs.email.value=email; inputs.password.value=password;
    const form={matches:selector=>selector==='[data-knowledge-login]',elements:{namedItem:name=>inputs[name]}};
    handlers.get('submit')?.({target:form,preventDefault(){},stopPropagation(){}});
    return inputs;
  }
  return {controller, element, api, document, requests, logs, handlers, submit, click, form, change, login};
}

test('email login is the primary binding flow and clears password before the user-action request settles',async()=>{
  const operation=deferred();
  const f=fixture(path=>path.endsWith('/login')?operation.promise:path.endsWith('/bases')?Promise.resolve({items:[{id:'own-kb',name:'My personal materials'}]}):Promise.resolve(configured));
  await settle();
  assert.match(f.element.html,/登录并绑定已有 WeKnora 账号/);
  assert.ok(f.element.html.indexOf('data-knowledge-login')<f.element.html.indexOf('高级绑定'));
  assert.match(f.element.html,/<details[^>]*><summary>高级绑定/);
  const input=f.login(); assert.equal(input.password.value,'');
  const request=f.requests.find(row=>row.path.endsWith('/login'));
  assert.deepEqual(request.body,{email:'person@example.test',password:'private-password'}); assert.equal(request.userAction,true);
  f.login('other@example.test','second-private-password');
  assert.equal(f.requests.filter(row=>row.path.endsWith('/login')).length,1);
  operation.resolve({...configured,user_id:'real-person',sync:{reconfiguration_required:true,configured:false}}); await settle();
  assert.deepEqual(f.requests.map(row=>row.path),['/knowledge','/knowledge/login','/knowledge/bases']);
  assert.match(f.element.html,/My personal materials/); assert.match(f.element.html,/请先完成本机资料目录的账号切换/);assert.match(f.element.html,/历史资料继续保留/);
  assert.doesNotMatch(f.element.html,/person@example.test|private-password|second-private-password/);
  assert.doesNotMatch(JSON.stringify(f.logs),/person@example.test|private-password/); f.controller.dispose();
});

test('login rejects invalid credentials locally and shows a safe failure without retrying rejected passwords',async()=>{
  const f=fixture(path=>path.endsWith('/login')?Promise.reject(Object.assign(Error('private-password person@example.test upstream trace'),{code:'knowledge_login_failed',status:401})):Promise.resolve(configured));
  await settle();
  for (const email of ['', 'missing-domain', 'name@', 'person@example.test\ncanary']) assert.equal(f.login(email).password.value,'');
  assert.equal(f.requests.filter(row=>row.method==='POST').length,0);
  f.login(); await settle();
  assert.match(f.element.html,/登录失败，请检查邮箱和密码/);
  assert.doesNotMatch(f.element.html,/private-password|person@example.test|upstream trace/);
  assert.equal(f.requests.filter(row=>row.path.endsWith('/login')).length,1);
  assert.equal(f.requests.filter(row=>row.path.endsWith('/bases')).length,0); f.controller.dispose();
});

test('actual email login serializes credentials once and keeps uncertain or library-only failures distinct',async()=>{
  const requests=[];
  const api=createAPI({fetcher:async(url,options)=>{
    requests.push({url,...options});
    return {ok:!url.endsWith('/bases'),status:url.endsWith('/bases')?503:200,json:async()=>url.endsWith('/bases')?{error:{code:'weknora_unavailable',message:'private upstream response'}}:configured};
  },logger:()=>{}});
  const f=fixture((path,options)=>api.request(path,options));await settle();f.login();await settle();
  const post=requests.find(row=>row.method==='POST');
  assert.equal(post.url,'/api/research/knowledge/login');assert.equal(post.headers['X-Research-User-Action'],'?1');
  assert.deepEqual(JSON.parse(post.body),{email:'person@example.test',password:'private-password'});
  assert.match(f.element.html,/账号已绑定，但知识库读取未完成/);assert.doesNotMatch(f.element.html,/private upstream response|person@example.test|private-password/);
  assert.equal(requests.filter(row=>row.method==='POST').length,1);f.controller.dispose();
  const uncertain=fixture(path=>path.endsWith('/login')?Promise.reject(Object.assign(Error('private payload'),{code:'request_timeout'})):Promise.resolve(configured));
  await settle();uncertain.login();await settle();
  assert.match(uncertain.element.html,/登录绑定结果尚未确认/);assert.doesNotMatch(uncertain.element.html,/private payload/);uncertain.controller.dispose();
});

test('successful identity switch removes prior account DOM before the new library request settles',async()=>{
  const pendingBases=deferred();let baseReads=0;
  const sid='01234567-89ab-4cde-8fab-0123456789ab',hit='d'.repeat(64);
  const f=fixture(async path=>path.endsWith('/login')?{...configured,user_id:'new-person',sync:{reconfiguration_required:true,configured:false}}:path.endsWith('/bases')?++baseReads===1?{items:[{id:'kb-1',name:'Prior private library'}]}:pendingBases.promise:path==='/sessions'?{items:[{id:sid,title:'Study'}]}:path.endsWith('/search')?{session_id:sid,items:[{hit_id:hit,title:'Prior private report',snippet:'prior-private-excerpt',document_version:1}],generated_answer:false}:path.endsWith('/read')?{session_id:sid,hit_id:hit,content:'prior-private-original'}:{...configured,sync});
  await settle();f.click('bases');await settle();f.click('sessions');await settle();f.form('search',{session_id:sid,query:'ETF'});await settle();f.click('read',{hitId:hit});await settle();
  assert.match(f.element.html,/user-1/);assert.match(f.element.html,/Prior private library/);assert.match(f.element.html,/prior-private-original/);
  f.login();await settle();
  assert.equal(baseReads,2);
  assert.match(f.element.html,/new-person/);
  assert.doesNotMatch(f.element.html,/user-1|Prior private library|Prior private report|prior-private-excerpt|prior-private-original/);
  assert.match(f.element.html,/请先完成本机资料目录的账号切换/);assert.match(f.element.html,/历史资料继续保留/);
  pendingBases.reject(Object.assign(Error('private timeout body'),{code:'request_timeout'}));await settle();
  assert.match(f.element.html,/账号已绑定，但知识库读取未完成/);
  assert.doesNotMatch(f.element.html,/user-1|Prior private library|prior-private-excerpt|prior-private-original|private timeout body/);f.controller.dispose();
});

test('sync reconfiguration clears old knowledge selection and citation preview even for the same user',async()=>{
  const sid='01234567-89ab-4cde-8fab-0123456789ab',hit='d'.repeat(64);
  const f=fixture(async path=>path==='/sessions'?{items:[{id:sid,title:'Study'}]}:path.endsWith('/search')?{session_id:sid,items:[{hit_id:hit,title:'Old account report',snippet:'old-private-excerpt',document_version:1}],generated_answer:false}:path.endsWith('/sync')?{...sync,reconfiguration_required:true}:path.endsWith('/bases')?{items:[{id:'kb-1',name:'Old library'}]}:{...configured,sync});
  await settle();f.click('bases');await settle();f.click('sessions');await settle();f.form('search',{session_id:sid,query:'ETF'});await settle();
  assert.match(f.element.html,/old-private-excerpt/);
  f.click('sync');await settle();
  assert.doesNotMatch(f.element.html,/old-private-excerpt|value="kb-1" selected/); assert.match(f.element.html,/请先完成本机资料目录的账号切换/);assert.match(f.element.html,/历史资料继续保留/); f.controller.dispose();
});

const sync = {configured:true,enabled:false,source_root:'/Volumes/WorkDisk/Data/RWB/knowledge-inbox',knowledge_base_id:'kb-1',running:false,last_scan_result:'completed',last_scan_at:'2026-11-20T08:00:00Z',current_count:1,pending_count:1,error_count:1,last_error:null,items:[{path:'<report>.pdf',state:'current',version:1},{path:'pending.md',state:'pending',version:1},{path:'bad.docx',state:'error',error:'knowledge_parse_failed'}]};

test('directory sync exposes visible target selection and explicit enable, pause and scan actions only',async()=>{
  const f=fixture(async(path,options)=>path.endsWith('/bases')?{items:[{id:'kb-1',name:'Private notes'}]}:path.includes('/sync')?{...sync,enabled:options.body?.enabled ?? false}:{...configured,sync});
  await settle();
  assert.deepEqual(f.requests.map(row=>row.path),['/knowledge']);
  assert.match(f.element.html,/knowledge-inbox/); assert.match(f.element.html,/&lt;report&gt;\.pdf/); assert.doesNotMatch(f.element.html,/<report>/);
  f.form('sync',{knowledge_base_id:'guessed'}); await settle();
  assert.equal(f.requests.filter(row=>row.method==='POST').length,0);
  f.click('bases'); await settle();
  f.form('sync',{knowledge_base_id:'kb-1'}); await settle();
  assert.deepEqual(f.requests.at(-1).body,{knowledge_base_id:'kb-1',enabled:true}); assert.equal(f.requests.at(-1).userAction,true);
  f.click('pause'); await settle();
  assert.deepEqual(f.requests.at(-1).body,{knowledge_base_id:'kb-1',enabled:false});
  f.click('scan'); await settle();
  assert.equal(f.requests.at(-1).path,'/knowledge/sync/scan'); assert.equal(f.requests.at(-1).userAction,true);
  f.controller.dispose();
});

test('user selects session hits and confirms frozen citations without supplying document identifiers',async()=>{
  const sid='01234567-89ab-4cde-8fab-0123456789ab',hit='d'.repeat(64);
  const f=fixture(async path=>path==='/sessions'?{items:[{id:sid,title:'ETF study',mode:'fingpt'}]}:path.endsWith('/search')?{session_id:sid,items:[{hit_id:hit,title:'Report',snippet:'Actual excerpt',source_status:'current',locator:{chunk_index:0},document_version:1,limitations:['source_time_unknown']}],generated_answer:false}:path.endsWith('/freeze')?{id:'e'.repeat(64),session_id:sid}:configured);
  await settle(); f.click('sessions'); await settle();
  f.form('search',{session_id:sid,query:'ETF'}); await settle();
  assert.deepEqual(f.requests.at(-1).body,{session_id:sid,query:'ETF'});
  assert.match(f.element.html,/Actual excerpt/);
  f.change({knowledgeHit:hit},hit,true);
  f.click('freeze'); await settle();
  assert.equal(f.requests.at(-1).path,'/knowledge/freeze'); assert.equal(f.requests.at(-1).userAction,true);
  assert.deepEqual(f.requests.at(-1).body,{session_id:sid,hit_ids:[hit]});
  assert.match(f.element.html,/已保存/);
  assert.match(f.element.html,new RegExp(`/api/research/knowledge/evidence/${'e'.repeat(64)}`));
  f.controller.dispose();
});

test('sync and freeze failures remain unconfirmed and do not leak remote errors or retry',async()=>{
  const f=fixture(async path=>path.endsWith('/scan')?Promise.reject(Error('private canary jwt')):{...configured,sync});
  await settle(); f.click('scan'); await settle();
  assert.match(f.element.html,/扫描结果尚未确认/); assert.doesNotMatch(f.element.html,/private canary jwt/);
  assert.equal(f.requests.filter(row=>row.path.endsWith('/scan')).length,1); f.controller.dispose();
});

test('knowledge links only allow absolute HTTP(S) without credential URLs', () => {
  for (const url of ['javascript:alert(1)', 'data:text/html,canary', '//evil.test/', '/relative', 'https://user:secret@example.test/', 'https://example.test/\ncanary']) assert.equal(safeKnowledgeManagementURL(url), '');
  assert.equal(safeKnowledgeManagementURL('http://127.0.0.1:8095/'), 'http://127.0.0.1:8095/');
  assert.equal(safeKnowledgeManagementURL('https://knowledge.example.test/'), 'https://knowledge.example.test/');
});

test('knowledge metadata and library titles cannot create markup or saved token fields', () => {
  const html = knowledgePanelHTML({...configured, user_id: '<img src=x onerror=canary>', token: 'saved-secret', management_url: 'javascript:canary'}, {basesLoaded: true, bases: [{name: '<script>canary</script>'}]});
  assert.doesNotMatch(html, /<img|<script|saved-secret|href="javascript:/);
  assert.match(html, /&lt;img/); assert.match(html, /&lt;script/);
  assert.match(html, /name="token"[^>]*type="password"/);
  assert.doesNotMatch(html, /name="token"[^>]*value=/);
  assert.match(html, /检索待核验/);
});

test('status is the only automatic request; listing libraries needs explicit action', async () => {
  const f = fixture(async path => path.endsWith('/bases') ? {items: [{id: 'kb-1', name: '<img src=x>'}]} : configured);
  await settle(); assert.deepEqual(f.requests.map(row => row.path), ['/knowledge']);
  f.click('bases'); await settle();
  assert.deepEqual(f.requests.map(row => row.path), ['/knowledge', '/knowledge/bases']);
  assert.match(f.element.html, /&lt;img src=x&gt;/); assert.doesNotMatch(f.element.html, /<img/);
  f.controller.dispose();
});

test('binding clears JWT immediately, sends userAction, rejects duplicate and hides remote failure', async () => {
  const operation = deferred();
  const f = fixture(path => path.endsWith('/binding') ? operation.promise : Promise.resolve(configured));
  await settle();
  const input = f.submit();
  assert.equal(input.value, '');
  const post = f.requests.find(row => row.path.endsWith('/binding'));
  assert.deepEqual(post.body, {token: 'synthetic-jwt-secret', workspace_id: '7'});
  assert.equal(post.method, 'POST'); assert.equal(post.userAction, true);
  const duplicate = f.submit('second-secret'); assert.equal(duplicate.value, '');
  assert.equal(f.requests.filter(row => row.method === 'POST').length, 1);
  operation.reject(Error('raw body includes synthetic-jwt-secret and private-user'));
  await settle();
  assert.match(f.element.html, /绑定结果尚未确认/);
  assert.doesNotMatch(f.element.html, /synthetic-jwt-secret|second-secret|private-user|raw body/);
  assert.deepEqual(f.logs, ['knowledge_settings_operation_completed', 'knowledge_settings_operation_failed']);
  f.controller.dispose();
});

test('invalid workspace and unavailable entry never submit and clear any typed secret', async () => {
  const f = fixture(); await settle();
  for (const value of ['0', '-1', '1.5', '01', '99999999999999999999']) assert.equal(f.submit('secret', value).value, '');
  assert.equal(f.requests.filter(row => row.method === 'POST').length, 0);
  const disabled = fixture(async () => ({enabled: false, configured: false})); await settle();
  assert.equal(disabled.submit().value, ''); disabled.click('bases'); await settle();
  assert.equal(disabled.requests.length, 1);
  assert.match(disabled.element.html, /入口未启用/);
  f.controller.dispose(); disabled.controller.dispose();
});

test('the actual API serializes JWT once with the explicit user-action header', async () => {
  const requests = [];
  const api = createAPI({fetcher: async (url, options) => {
    requests.push({url, ...options});
    return {ok: true, status: 200, json: async () => configured};
  }, logger: () => {}});
  const f = fixture((path, options) => api.request(path, options));
  await settle(); f.submit(); await settle();
  const post = requests.find(row => row.method === 'POST');
  assert.equal(post.url, '/api/research/knowledge/binding');
  assert.equal(post.credentials, 'same-origin');
  assert.equal(post.headers['X-Research-User-Action'], '?1');
  assert.deepEqual(JSON.parse(post.body), {token: 'synthetic-jwt-secret', workspace_id: '7'});
  assert.equal(f.element.token.value, '');
  f.controller.dispose();
});

test('credential editing stays inside the card instead of entering global draft handlers', async () => {
  const f = fixture(); await settle();
  for (const name of ['input', 'change', 'keydown', 'compositionstart', 'compositionend']) {
    let stopped = false;
    f.handlers.get(name)({stopPropagation() { stopped = true; }});
    assert.equal(stopped, true);
  }
  f.controller.dispose();
});

test('dispose aborts the request, clears secrets and ignores late responses', async () => {
  const operation = deferred(); const f = fixture(() => operation.promise);
  f.element.token.value = 'typed-secret'; const input = f.element.token;
  f.element.password.value = 'typed-password'; const password = f.element.password;
  f.element.email.value = 'private@example.test'; const email = f.element.email;
  const renders = f.element.renders;
  f.controller.dispose();
  assert.equal(input.value, ''); assert.equal(f.requests[0].signal.aborted, true);
  assert.equal(password.value,'');assert.equal(email.value,'');
  assert.equal(f.handlers.size, 0); assert.equal(f.element.removed, true);
  operation.resolve({...configured, user_id: 'late-user'}); await settle();
  assert.equal(f.element.renders, renders); assert.deepEqual(f.logs, []);
});

test('mount reuses the panel across redraw and disposes when leaving settings/data', async () => {
  const requests = []; const f = fixture(); await settle(); f.controller.dispose();
  let mounted = null, present = true;
  const root = {querySelector: () => present ? {replaceWith: element => { mounted = element; }} : null};
  const options = {api: {request: async path => { requests.push(path); return configured; }}, document: f.document};
  let panel = mountKnowledgeSettings(root, null, options); await settle();
  assert.equal(mounted, panel.element);
  assert.equal(mountKnowledgeSettings(root, panel, options), panel);
  assert.equal(requests.length, 1);
  present = false; panel = mountKnowledgeSettings(root, panel, options);
  assert.equal(panel, null); assert.equal(f.element.removed, true);
});

test('settings mount is adjacent to warehouse and app stays within existing byte budget', () => {
  const settings = readFileSync(new URL('../../app/research_web/ui/settings.mjs', import.meta.url), 'utf8');
  const app = readFileSync(new URL('../../app/research_web/ui/app.mjs', import.meta.url));
  assert.match(settings, /data-research-warehouse-root><\/div><div data-research-knowledge-root/);
  assert.match(app.toString(), /knowledgeSettingsPanel = mountKnowledgeSettings\(root,knowledgeSettingsPanel/);
  assert.ok(app.length <= 262144, `app.mjs ${app.length} exceeds fixed 256 KiB limit`);
});
