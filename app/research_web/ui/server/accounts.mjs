/** Invite-only account controls. Passwords exist only in the submitted form/request. */
const select = id => document.getElementById(id);
const messages = {
  invalid_credentials: '账号或密码不正确。', login_rate_limited: '登录尝试过多，请稍后再试。',
  username_exists: '这个账号已存在。', invalid_username: '账号需为3—64位字母、数字、下划线、点或短横线，并以字母开头。',
  invalid_password: '密码至少需要12个字符。', last_active_admin: '不能停用最后一个管理员。',
  runtime_capacity: '服务器正在处理其他研究，请稍后再试。', login_required: '登录已过期，请重新登录。',
};
let me;
let resetUser;

async function api(path, method = 'GET', body) {
  const response = await fetch(`/api/server/${path}`, {
    method, credentials: 'same-origin', headers: body ? { 'Content-Type': 'application/json' } : {},
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  const value = await response.json();
  if (!response.ok) throw Error(messages[value?.error?.code] || '操作未完成，请检查输入或稍后重试。');
  return value;
}

async function action(form, callback) {
  const buttons = [...form.querySelectorAll('button')];
  buttons.forEach(button => { button.disabled = true; });
  select('message').textContent = '';
  try { await callback(); }
  catch (error) { select('message').textContent = error.message; }
  finally { buttons.forEach(button => { button.disabled = false; }); }
}

async function loadUsers() {
  const { items } = await api('users');
  const list = select('user-list');
  list.replaceChildren();
  for (const user of items) {
    const row = document.createElement('div'); row.className = 'user-row';
    const name = document.createElement('span'); name.className = 'user-name';
    name.textContent = `${user.username} · ${user.role === 'admin' ? '管理员' : '用户'} · ${user.enabled ? '启用' : '停用'}`;
    row.append(name);
    const button = (text, callback) => {
      const element = document.createElement('button'); element.type = 'button'; element.textContent = text;
      element.addEventListener('click', () => action(row, callback)); row.append(element);
    };
    if (user.id !== me.id) button(user.enabled ? '停用' : '启用', async () => {
      if (user.enabled && !confirm(`停用 ${user.username} 并停止其研究？`)) return;
      await api(`users/${user.id}`, 'PATCH', { enabled: !user.enabled }); await loadUsers();
    });
    button('重置密码', async () => {
      resetUser = user.id; select('reset-title').textContent = `重置 ${user.username} 的密码`;
      select('reset-form').hidden = false; select('reset-form').elements.password.focus();
    });
    button('停止实例', async () => {
      if (!confirm(`停止 ${user.username} 的实例和运行中的任务？会话文件保留。`)) return;
      await api(`users/${user.id}/stop`, 'POST'); select('message').textContent = '实例已停止，数据已保留。';
    });
    list.append(row);
  }
}

select('login-form').addEventListener('submit', event => {
  event.preventDefault(); const form = event.currentTarget;
  void action(form, async () => {
    try { await api('login', 'POST', { username: form.elements.username.value, password: form.elements.password.value }); location.assign('/'); }
    finally { form.elements.password.value = ''; }
  });
});
select('create-form').addEventListener('submit', event => {
  event.preventDefault(); const form = event.currentTarget;
  void action(form, async () => {
    try { await api('users', 'POST', { username: form.elements.username.value, password: form.elements.password.value }); form.reset(); await loadUsers(); select('message').textContent = '账号已创建，请通过你们既有的安全渠道交付初始密码。'; }
    finally { form.elements.password.value = ''; }
  });
});
select('reset-form').addEventListener('submit', event => {
  event.preventDefault(); const form = event.currentTarget;
  void action(form, async () => {
    try { await api(`users/${resetUser}/password`, 'POST', { password: form.elements.password.value }); form.hidden = true; select('message').textContent = '密码已重置，旧登录已撤销。'; }
    finally { form.elements.password.value = ''; }
  });
});
select('cancel-reset').addEventListener('click', () => { select('reset-form').reset(); select('reset-form').hidden = true; });
select('logout').addEventListener('click', () => { void action(select('signed-in'), async () => { await api('logout', 'POST'); location.assign('/auth'); }); });

if (location.pathname !== '/auth') try {
  me = (await api('me')).user;
  select('login-form').hidden = true; select('signed-in').hidden = false;
  select('heading').textContent = `你好，${me.username}`;
  select('description').textContent = '你的会话、附件和报告保存在服务器的独立个人空间。退出登录不会停止正在运行的研究。';
  if (me.role === 'admin') { select('administration').hidden = false; await loadUsers(); }
} catch (error) {
  if (location.pathname !== '/auth') location.replace('/auth');
}
