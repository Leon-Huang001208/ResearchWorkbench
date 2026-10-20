import { escapeHTML as e } from './markdown.mjs';
import { icon } from './icons.mjs';

const avatar = user => `<span class="account-avatar" aria-hidden="true">${e(Array.from(String(user.username || '账号').trim())[0]?.toLocaleUpperCase() || '账')}</span>`;

export function renderAccountTrigger(user) {
  return `<button type="button" id="account-menu-trigger" class="account-trigger" data-account-trigger aria-label="${e(user.username || '我的账号')}的账号菜单" title="我的账号" aria-haspopup="menu" aria-expanded="false" aria-controls="account-menu">${avatar(user)}</button>`;
}

export function renderAccountMenu(user, { busy = false, error = '' } = {}) {
  return `<header class="account-identity" role="presentation">${avatar(user)}<span><strong>${e(user.username || '我的账号')}</strong><small>${user.role === 'admin' ? '管理员' : '用户'}</small></span></header><div class="account-actions" role="presentation"><a role="menuitem" tabindex="-1" href="/account">${icon('account')}<span>我的账号</span></a><a role="menuitem" tabindex="-1" href="#/settings/general">${icon('settings')}<span>设置</span></a><div class="account-divider" role="separator"></div><button type="button" role="menuitem" tabindex="-1" data-account-logout ${busy ? 'disabled aria-disabled="true"' : ''}>${icon('logout')}<span>${busy ? '正在退出…' : '退出登录'}</span></button></div>${error ? `<p class="account-error" role="alert">${e(error)}</p>` : ''}`;
}

/** One body-level overlay survives shell redraws and escapes the rail's clipping. */
export function createAccountMenu({ root, user, document = globalThis.document, window = globalThis.window, fetcher = globalThis.fetch?.bind(globalThis), logger = () => {} } = {}) {
  if (!user) return { sync() {} };
  const menu = document.createElement('section');
  menu.id = 'account-menu'; menu.className = 'account-menu'; menu.hidden = true;
  menu.setAttribute('role', 'menu'); menu.setAttribute('aria-label', '账号菜单');
  menu.setAttribute('tabindex', '-1');
  document.body.append(menu);
  let open = false;
  let busy = false;
  let error = '';
  const trigger = () => root.querySelector('[data-account-trigger]');
  const items = () => [...menu.querySelectorAll('[role="menuitem"]')].filter(item => !item.disabled);
  function sync() {
    const anchor = trigger();
    if (!anchor || !anchor.getClientRects().length) { close(); return; }
    anchor.setAttribute('aria-expanded', String(open));
    if (!open) return;
    const rect = anchor.getBoundingClientRect();
    if (rect.right <= 0 || rect.left >= window.innerWidth || rect.top >= window.innerHeight || rect.bottom <= 0) { close(); return; }
    menu.style.left = `${Math.max(8, Math.min(rect.left, window.innerWidth - menu.offsetWidth - 8))}px`;
    menu.style.bottom = `${Math.max(8, Math.min(window.innerHeight - rect.top + 8, window.innerHeight - menu.offsetHeight - 8))}px`;
  }
  function close(restoreFocus = false) {
    open = false; menu.hidden = true;
    trigger()?.setAttribute('aria-expanded', 'false');
    if (restoreFocus) trigger()?.focus({ preventScroll: true });
  }
  function paint() {
    menu.innerHTML = renderAccountMenu(user, { busy, error });
    menu.hidden = !open;
    sync();
  }
  function show(last = false) {
    open = true; paint();
    if (!open) return;
    const targets = items();
    (last ? targets.at(-1) : targets[0])?.focus({ preventScroll: true });
    logger('account_menu_opened');
  }
  async function logout() {
    if (busy) return;
    busy = true; error = ''; paint();
    if (open) menu.focus({ preventScroll: true });
    const abort = new AbortController();
    const timer = window.setTimeout(() => abort.abort(), 15000);
    try {
      const response = await fetcher('/api/server/logout', { method: 'POST', credentials: 'same-origin', signal: abort.signal });
      if (!response.ok && response.status !== 401) throw new Error('logout_failed');
      logger('account_logout_completed');
      window.location.assign('/auth');
    } catch {
      error = '退出未完成，请检查网络后重试。';
      logger('account_logout_failed', { status: 'request_failed' });
    } finally {
      window.clearTimeout(timer);
      busy = false; paint();
      if (open && error) menu.querySelector('[data-account-logout]')?.focus({ preventScroll: true });
    }
  }
  document.addEventListener('click', event => {
    if (event.target.closest('[data-account-trigger]')) { if (open) close(true); else show(); return; }
    if (menu.contains(event.target)) {
      if (event.target.closest('[data-account-logout]')) void logout();
      else if (event.target.closest('a')) close();
    } else if (open) close();
  });
  document.addEventListener('keydown', event => {
    const onTrigger = Boolean(event.target.closest('[data-account-trigger]'));
    if (onTrigger && ['ArrowDown', 'ArrowUp'].includes(event.key)) {
      event.preventDefault(); show(event.key === 'ArrowUp'); return;
    }
    if (!open || (!onTrigger && !menu.contains(event.target))) return;
    if (event.key === 'Escape') { event.preventDefault(); close(true); return; }
    if (event.key === 'Tab') { close(true); return; }
    if (event.key === ' ' && event.target.closest('a')) {
      event.preventDefault(); event.target.closest('a').click(); return;
    }
    if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const targets = items();
    const current = targets.indexOf(document.activeElement);
    const index = event.key === 'Home' ? 0 : event.key === 'End' ? targets.length - 1 : (current + (event.key === 'ArrowDown' ? 1 : -1) + targets.length) % targets.length;
    targets[index]?.focus({ preventScroll: true });
  });
  document.addEventListener('focusin', event => {
    if (open && !menu.contains(event.target) && !event.target.closest('[data-account-trigger]')) close();
  });
  window.addEventListener('hashchange', () => close());
  window.addEventListener('resize', () => sync());
  document.addEventListener('scroll', () => sync(), true);
  return { sync };
}
