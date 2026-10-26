/** Login stays standalone; old /account links enter the authenticated workspace. */
import { createAccountAPI, legacyAccountTarget } from './account-api.mjs';
import { safeLog } from '/static/core.mjs';
const target = legacyAccountTarget(location.pathname);
if (target) {
  document.getElementById('heading').textContent = '正在打开账号资料…';
  document.getElementById('description').textContent = '';
  location.replace(target);
} else {
  const form = document.getElementById('login-form');
  const message = document.getElementById('message');
  const api = createAccountAPI({logger:safeLog});
  let busy = false;
  form.hidden = false;
  form.addEventListener('submit', event => {
    event.preventDefault(); if(busy)return;
    busy=true; const button=form.querySelector('button');button.disabled=true;button.textContent='正在登录…';form.setAttribute('aria-busy','true');message.textContent='正在登录…';
    void (async()=>{
      try {await api('login','POST',{username:form.elements.username.value,password:form.elements.password.value});location.assign('/');}
      catch(error){message.textContent=error.message;safeLog('account_login_failed',{status:error.status||0});}
      finally {form.elements.password.value='';busy=false;button.disabled=false;button.textContent='登录';form.setAttribute('aria-busy','false');}
    })();
  });
}
