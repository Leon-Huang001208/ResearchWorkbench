/** Server-only account entry; never stores a session token in JavaScript storage. */
import { mountLegacyAccountMenu } from './account-menu.mjs';
import { mountLegacyAccountWorkspace } from './account-workspace.mjs';
import { safeLog } from '/static/core.mjs';
const originalFetch = window.fetch.bind(window);
const identity = await originalFetch('/api/server/me', { credentials: 'same-origin' });
if (!identity.ok) { location.replace('/auth'); throw Error('login_required'); }
const identityData = await identity.json();
const user = { ...identityData.user, primary: identityData.primary === true };
globalThis.__RWB_USER_ID__ = user.id;
globalThis.__RWB_USER_ROLE__ = user.role;
globalThis.__RWB_ACCOUNT__ = Object.freeze({ username: user.username, role: user.role, primary: user.primary === true });
const profileStyle = document.createElement('link');
profileStyle.rel = 'stylesheet'; profileStyle.href = '/server-static/profile.css'; document.head.append(profileStyle);
const accountStyle = document.createElement('link');
accountStyle.rel = 'stylesheet'; accountStyle.href = '/server-static/account-menu.css'; document.head.append(accountStyle);
const workspaceStyle = document.createElement('link');
workspaceStyle.rel = 'stylesheet'; workspaceStyle.href = '/server-static/account-workspace.css'; document.head.append(workspaceStyle);
const restrictModelOptions = () => {
  const option = document.querySelector('#settings-form [name="provider"] option[value="openai-compatible"]');
  if (option) option.disabled = true;
};
new MutationObserver(restrictModelOptions).observe(document.body, { childList: true, subtree: true });
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
mountLegacyAccountMenu({ root: document.querySelector('#app'), user, logger: safeLog });
mountLegacyAccountWorkspace({root:document.querySelector('#app'),user,logger:safeLog});
