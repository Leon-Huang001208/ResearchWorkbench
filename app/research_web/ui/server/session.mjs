/** Server-only account entry; never stores a session token in JavaScript storage. */
const originalFetch = window.fetch.bind(window);
const identity = await originalFetch('/api/server/me', { credentials: 'same-origin' });
if (!identity.ok) { location.replace('/auth'); throw Error('login_required'); }
const user = (await identity.json()).user;
globalThis.__RWB_USER_ID__ = user.id;
globalThis.__RWB_USER_ROLE__ = user.role;
const profileStyle = document.createElement('link');
profileStyle.rel = 'stylesheet'; profileStyle.href = '/server-static/profile.css'; document.head.append(profileStyle);
const restrictModelOptions = () => {
  const option = document.querySelector('#settings-form [name="provider"] option[value="openai-compatible"]');
  if (option) option.disabled = true;
};
new MutationObserver(restrictModelOptions).observe(document.body, { childList: true, subtree: true });
const link = document.createElement('a');
link.href = '/account'; link.textContent = '我的账号'; link.setAttribute('aria-label', '打开账号管理与退出登录');
Object.assign(link.style, { position: 'fixed', right: '16px', bottom: '16px', zIndex: '1000', padding: '8px 14px', borderRadius: '18px', background: 'var(--surface, #edf4f1)', color: 'var(--text, #234f45)', border: '1px solid #9eb5aa', font: '14px system-ui', textDecoration: 'none' });
document.body.append(link);
window.fetch = async (...args) => {
  const target = new URL(args[0] instanceof Request ? args[0].url : String(args[0]), location.href);
  let response;
  if (target.origin === location.origin && target.pathname.startsWith('/api/research/')) {
    const input = args[0] instanceof Request ? args[0] : target;
    const request = new Request(input, args[1]);
    request.headers.set('X-RWB-Page-User', user.id);
    response = await originalFetch(request);
  } else response = await originalFetch(...args);
  if (response.status === 401 && target.origin === location.origin && target.pathname.startsWith('/api/research/')) location.replace('/auth');
  return response;
};
const NativeEventSource = window.EventSource;
window.EventSource = class extends NativeEventSource {
  constructor(url, options) {
    const target = new URL(url, location.href);
    if (target.origin === location.origin && target.pathname.startsWith('/api/research/')) target.searchParams.set('rwb_user', user.id);
    super(target.href, options);
  }
};
await import('/static/app.mjs');
