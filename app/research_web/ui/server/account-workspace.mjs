/** Account workspace and persistent DOM-owned management forms; no secret storage. */
import {createAccountAPI, legacyAccountTarget} from './account-api.mjs';
const e=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const avatar=user=>`<span class="account-avatar" aria-hidden="true">${e(Array.from(String(user.username||'账号'))[0]?.toLocaleUpperCase()||'账')}</span>`;
export const managementSlot=()=>'<div data-account-management-slot></div>';
export function renderAccountProfile(user) {
  if(!user)return '<p class="muted">账号资料仅在已登录的服务器模式中提供。</p>';
  return `<section class="account-profile" aria-label="账号资料" data-account-profile><header class="account-profile-heading">${avatar(user)}<h1>${e(user.username)}</h1><p>${user.role==='admin'?'管理员':'用户'}</p></header><section class="settings-card"><h2>个人空间</h2><p>会话、附件和报告保存在服务器的个人空间中。</p><p class="muted">退出登录不会停止正在运行的研究。</p></section><p class="account-help">账号由管理员创建。如需修改账号或重置密码，请联系管理员。</p></section>`;
}
export function userActions(user, me, primaryId) {
  return {reset:true,toggle:user.id!==me.id&&user.id!==primaryId,stop:user.id!==primaryId};
}
const input=(name,label,extra='')=>`<label>${label}<input name="${name}" ${extra}></label>`;
const secret=label=>input('password',label,'type="password" autocomplete="new-password" required minlength="12" maxlength="1024"');
const managementHTML=()=>`<section class="account-management settings-card" aria-label="用户管理"><div class="users-heading"><h2>用户</h2><button class="button primary" type="button" data-user-invite>邀请用户</button></div><p class="users-note">停用账号会撤销登录并停止该用户的研究。停止实例会结束任务并释放容量，数据保留。</p><p class="account-feedback" data-user-message role="status" aria-live="polite"></p><form class="account-admin-form" data-user-create hidden><h3>邀请用户</h3><div class="account-fields">${input('username','账号','autocomplete="off" required pattern="[a-zA-Z][a-zA-Z0-9_.\\-]{2,63}" maxlength="64"')}${secret('初始密码（至少12个字符）')}</div><p>请通过你们既有的安全渠道交付初始密码。</p><div class="button-row"><button class="button primary" type="submit">创建账号</button><button class="button" type="button" data-user-cancel>取消</button></div></form><form class="account-admin-form" data-user-reset hidden><h3 data-user-reset-title>重置密码</h3>${secret('新密码（至少12个字符）')}<p>保存后会撤销该用户的所有登录。</p><div class="button-row"><button class="button primary" type="submit">保存密码</button><button class="button" type="button" data-user-cancel>取消</button></div></form><div data-user-list></div><button class="button" type="button" data-user-reload>刷新用户列表</button></section><p class="account-help">原常驻实例的停止与停用由原监督器管理。</p>`;
const key=Symbol.for('rwb.account-workspace');

export function createAccountWorkspace({root,user,document=globalThis.document,window=globalThis.window,fetcher=globalThis.fetch?.bind(globalThis),logger=()=>{},confirm=message=>window.confirm(message)}={}) {
  if(!root||!user)return {captureFocus(){},sync(){}};
  if(root[key])return root[key];
  const request=createAccountAPI({fetcher,redirect:url=>window.location.assign(url),logger});
  let panel=null,rows=[],primaryId=null,resetId=null,busy=false,epoch=0,focused=null,loading=false,reloadPending=false;
  const active=()=>user.role==='admin'&&/^#\/settings\/users(?:\?|$)/.test(window.location.hash);
  const message=(text,error=false)=>{const el=panel?.querySelector('[data-user-message]');if(el){el.textContent=text;el.setAttribute('role',error?'alert':'status');}};
  function clearSecrets(){panel?.querySelectorAll('input[type="password"]').forEach(el=>{el.value='';});}
  function deactivate(){epoch++;clearSecrets();panel?.replaceChildren();panel=null;rows=[];primaryId=null;resetId=null;focused=null;loading=false;reloadPending=false;}
  function setBusy(){panel?.querySelectorAll('button').forEach(button=>{button.disabled=busy;});panel?.querySelectorAll('input').forEach(el=>{el.readOnly=busy;});}
  function list(){
    const el=panel?.querySelector('[data-user-list]');if(!el)return;
    el.innerHTML=rows.length?rows.map(item=>{const actions=userActions(item,user,primaryId);return `<div class="account-user-row"><div class="account-user-identity">${avatar(item)}<div><strong>${e(item.username)}</strong><small>${item.role==='admin'?'管理员':'用户'} · ${item.enabled?'启用':'停用'}${item.id===user.id?' · 当前账号':''}${item.id===primaryId?' · 原常驻实例':''}</small></div></div><div class="account-user-actions"><button class="button" type="button" data-user-action="reset" data-user-id="${e(item.id)}">重置密码</button>${actions.toggle?`<button class="button ${item.enabled?'account-danger':''}" type="button" data-user-action="toggle" data-user-id="${e(item.id)}">${item.enabled?'停用':'启用'}</button>`:''}${actions.stop?`<button class="button account-danger" type="button" data-user-action="stop" data-user-id="${e(item.id)}">停止实例</button>`:''}</div></div>`;}).join(''):'<p class="muted">暂无用户。</p>';
    setBusy();
  }
  async function load(ticket=epoch){
    loading=true;
    try {
      const value=await request('users');
      if(ticket!==epoch||!active())return;
      if(!Array.isArray(value.items)||!Object.hasOwn(value,'primary_user_id')||!(value.primary_user_id===null||typeof value.primary_user_id==='string')||value.items.some(item=>!item||typeof item.id!=='string'||typeof item.username!=='string'||!['admin','user'].includes(item.role)||typeof item.enabled!=='boolean'))throw Error('用户列表返回异常，请重试。');
      rows=value.items;primaryId=value.primary_user_id;list();
    } finally {if(ticket===epoch)loading=false;}
  }
  async function perform(callback){
    if(busy||!active())return;
    const control=document.activeElement;
    const restore=panel?.contains(control)&&control?.dataset?.userId?{id:control.dataset.userId,action:control.dataset.userAction}:null;
    busy=true;const ticket=epoch;message('');setBusy();
    try {await callback(ticket);}
    catch(error){if(ticket===epoch&&active()){if(['forbidden','login_required'].includes(error.code)){clearSecrets();rows=[];list();panel.querySelectorAll('form').forEach(form=>{form.hidden=true;});}message(error.message,true);}logger('account_management_failed',{status:error.status||0});}
    finally {
      busy=false;
      if(active()){
        setBusy();
        if(restore&&ticket===epoch&&document.activeElement===document.body){const next=[...panel.querySelectorAll('[data-user-action]')].find(button=>button.dataset.userId===restore.id&&button.dataset.userAction===restore.action);(next||panel.querySelector('[data-user-reload]'))?.focus({preventScroll:true});}
        if(reloadPending&&panel){reloadPending=false;initialLoad();}
      }
    }
  }
  function initialLoad(){void perform(async ticket=>{await load(ticket);if(ticket===epoch)message('');});}
  function cancelForms(){clearSecrets();resetId=null;panel?.querySelectorAll('form').forEach(form=>{form.reset();form.hidden=true;});}
  function captureFocus(){if(panel?.contains(document.activeElement))focused=document.activeElement;}
  function sync(){
    if(!active()){if(panel)deactivate();return;}
    const slot=root.querySelector('[data-account-management-slot]');if(!slot)return;
    if(!panel){panel=document.createElement('div');panel.innerHTML=managementHTML();message('正在读取用户列表…');if(busy)reloadPending=true;else initialLoad();}
    if(!slot.contains(panel))slot.replaceChildren(panel);
    setBusy();
    if(focused?.isConnected&&document.activeElement===document.body){focused.focus({preventScroll:true});}focused=null;
  }
  root.addEventListener('click',event=>{
    if(!active()||busy||!panel?.contains(event.target))return;
    if(event.target.closest('[data-user-cancel]')){cancelForms();panel.querySelector('[data-user-invite]')?.focus();return;}
    if(event.target.closest('[data-user-invite]')){cancelForms();const form=panel.querySelector('[data-user-create]');form.hidden=false;form.elements.username.focus();return;}
    if(event.target.closest('[data-user-reload]')){void perform(async ticket=>{await load(ticket);if(ticket===epoch)message('用户列表已更新。');});return;}
    const control=event.target.closest('[data-user-action]');if(!control)return;
    const item=rows.find(row=>row.id===control.dataset.userId);if(!item)return;
    const action=control.dataset.userAction;const allowed=userActions(item,user,primaryId);
    if(action==='reset'){cancelForms();resetId=item.id;const form=panel.querySelector('[data-user-reset]');form.querySelector('[data-user-reset-title]')?.replaceChildren(document.createTextNode(`重置 ${item.username} 的密码`));form.hidden=false;form.elements.password.focus();return;}
    if(action==='toggle'&&allowed.toggle){if(item.enabled&&!confirm(`停用 ${item.username} 并停止其研究？`))return;void perform(async ticket=>{await request(`users/${encodeURIComponent(item.id)}`,'PATCH',{enabled:!item.enabled});if(ticket!==epoch)return;await load(ticket);if(ticket===epoch)message('账号状态已更新。');});}
    if(action==='stop'&&allowed.stop){if(!confirm(`停止 ${item.username} 的实例和运行中的任务？会话文件保留。`))return;void perform(async ticket=>{await request(`users/${encodeURIComponent(item.id)}/stop`,'POST');if(ticket===epoch)message('实例已停止，数据已保留。');});}
  });
  root.addEventListener('submit',event=>{
    const form=event.target;if(!form.matches?.('[data-user-create],[data-user-reset]'))return;
    event.preventDefault();if(!active()||busy)return;
    const targetId=resetId;const create=form.hasAttribute('data-user-create');
    if(!create&&!rows.some(item=>item.id===targetId))return;
    if(!create&&!confirm(`重置密码并撤销${targetId===user.id?'你':'该用户'}的所有登录？`))return;
    void perform(async ticket=>{
      try {
        await request(create?'users':`users/${encodeURIComponent(targetId)}/password`,'POST',create?{username:form.elements.username.value,password:form.elements.password.value}:{password:form.elements.password.value});
        if(!create&&targetId===user.id){window.location.assign('/auth');return;}
        if(ticket!==epoch)return;
        form.reset();form.hidden=true;resetId=null;
        if(create)await load(ticket);
        if(ticket===epoch){message(create?'账号已创建，请通过既有安全渠道交付初始密码。':'密码已重置，旧登录已撤销。');panel.querySelector('[data-user-invite]')?.focus();}
      } finally {form.elements.password.value='';}
    });
  });
  document.addEventListener('focusin',event=>{focused=panel?.contains(event.target)?event.target:null;});
  document.addEventListener('pointerdown',event=>{if(!panel?.contains(event.target))focused=null;});
  window.addEventListener('hashchange',()=>{if(!active())deactivate();});
  const controller={captureFocus,sync};root[key]=controller;return controller;
}

/** Gateway compatibility adapter for a preserved primary shell without these routes. */
export function mountLegacyAccountWorkspace(options={}) {
  const {root,user,document=globalThis.document,window=globalThis.window,Observer=globalThis.MutationObserver,logger=()=>{}}=options;
  if(!root||!user)return;
  const controller=createAccountWorkspace(options);
  if(root.dataset.accountWorkspaceNative==='1')return controller;
  function reconcile(){
    const target=legacyAccountTarget('',window.location.hash);if(target){window.location.replace(target);return;}
    const content=root.querySelector('.page-content');if(!content)return;
    if(/^#\/account(?:\?|$)/.test(window.location.hash)){
      if(!content.querySelector('[data-account-profile]'))content.innerHTML=renderAccountProfile(user);
    } else if(/^#\/settings(?:\/|$)/.test(window.location.hash)) {
      const nav=content.querySelector('.settings-navigation');
      if(user.role==='admin'&&nav&&!nav.querySelector('[data-legacy-user-settings]')){let link=nav.querySelector('a[href="#/settings/users"]');if(!link){link=document.createElement('a');link.href='#/settings/users';link.className='settings-navigation-link';link.textContent='用户管理';const general=nav.querySelector('a[href="#/settings/general"]');if(general)general.after(link);else nav.append(link);}link.dataset.legacyUserSettings='1';}
      if(/^#\/settings\/users(?:\?|$)/.test(window.location.hash)&&user.role==='admin'){
        nav?.querySelectorAll('a').forEach(link=>{link.classList.toggle('active',link.hasAttribute('data-legacy-user-settings'));if(link.hasAttribute('data-legacy-user-settings'))link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');});
        const page=content.querySelector('.settings-page');
        if(page&&!page.querySelector('[data-account-management-slot]'))page.innerHTML=`<header class="settings-page-header"><div><p class="eyebrow">USER MANAGEMENT</p><h1>用户管理</h1><p class="muted">邀请用户，并管理账号和研究实例。</p></div></header>${managementSlot()}`;
      }
    }
    controller.sync();
  }
  new Observer(reconcile).observe(root,{childList:true,subtree:true});window.addEventListener('hashchange',reconcile);reconcile();logger('account_workspace_legacy_mounted');return controller;
}
