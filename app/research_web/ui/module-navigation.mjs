import { PRIMARY_NAVIGATION, settingsSections, intelTabs, assetTabs, marketTabs } from './navigation-catalog.mjs';
import { escapeHTML as e } from './markdown.mjs';
import { icon, hasIcon } from './icons.mjs';
import { safeLog } from './core.mjs';
import { progressHref } from './progress.mjs';

export { PRIMARY_NAVIGATION } from './navigation-catalog.mjs';
// Reject bad primary glyphs rather than silently falling back to a document.
const primaryGlyphs = [...PRIMARY_NAVIGATION.map(item => item.glyph), 'milestones', 'settings'];
if (new Set(primaryGlyphs).size !== primaryGlyphs.length || primaryGlyphs.some(name => !hasIcon(name))) {
  safeLog('primary_navigation_icons_invalid');
  throw new Error('primary_navigation_icons_invalid');
}

export function moduleKey(route = {}) {
  if (route.page === 'skills' && route.capabilityView === 'plans') return 'automations';
  if (route.page === 'workbench') return ['market', 'industry', 'documents', 'hot'].includes(route.section) ? 'intel' : route.section === 'etf-paper' ? 'simulation' : 'assets';
  return route.page || 'fingpt';
}
export function moduleTitle(route) {
  const key = moduleKey(route);
  return PRIMARY_NAVIGATION.find(item => item.page === key)?.title || ({progress:'研发进展',settings:'设置',account:'账号',history:'研究历史'})[key] || '导航';
}

export function secondaryEntries(route = {}, { account = null, canManageNews = true, settingsSection = '' } = {}) {
  const key = moduleKey(route);
  let rows = [], selected = '';
  if (key === 'progress') {
    selected = route.progressTab || 'overview';
    rows = [['overview','进展概览',progressHref(route,{tab:'overview',item:'',month:''})],['changelog','更新日志',progressHref(route,{tab:'changelog',item:'',month:''})]];
  } else if (key === 'settings') {
    rows = settingsSections.filter(s => !s.adminOnly || account?.role === 'admin').map(s => [s.id,s.label,`#/settings/${s.id}`]);
    selected = settingsSection || route.settingsSection || 'general';
  } else if (key === 'assets') {
    rows = assetTabs.map(row => [...row]);
    selected = route.assetView === 'dossiers' ? 'dossiers' : route.section === 'funds' ? 'funds' : 'assets';
  } else if (key === 'intel') {
    rows = [['discovery','今日发现'],['hot','本地热点与事件'],['signals','机会与风险'],['search','主题检索'],...intelTabs.map(([id,label])=>[id,id==='overview'?'外部事件总览':id==='research-reports'?'外部研报':label])].map(([id,label])=>[id,label,`#/intel/${id}`]);
    selected = route.intelTab || (route.section === 'hot' ? 'hot' : 'search');
  } else if (key === 'market') {
    rows = marketTabs; selected = route.marketView || 'dashboard';
  } else if (key === 'simulation') {
    rows = [['etf','ETF 模拟','#/simulation/etf'],['events','事件与日历研究','#/simulation/events'],['scores','六维评分','#/simulation/scores']]; selected = route.simulationView || 'etf';
  } else if (key === 'skills') {
    const kind = route.capabilityKind || 'skill', view = route.capabilityView || 'library';
    rows = [['skill','技能'],['connector','连接器'],['plugin','插件']].map(([id,label])=>[id,label,`#/skills?kind=${id}`]);
    selected = kind;
    const subviews = kind === 'skill' ? [['mine','我的技能']] : kind === 'connector' ? [['market','添加 MCP'],['connections','连接状态']] : [];
    rows.push(...subviews.map(([id,label])=>[id,label,`#/skills?kind=${kind}&view=${id}`]));
    if (subviews.some(([id])=>id===view)) selected=view;
  } else if (key === 'aihot') {
    rows = [['daily','日报'],['hot','热点榜'],['weekly','周报'],['monthly','月报'],['archive','更早']];
    if (canManageNews) rows.push(['manage','采编管理']);
    rows = rows.map(([id,label])=>[id,label,`#/aihot/${id}`]);
    selected = ['item','story','topic'].includes(route.aihotTab) ? 'hot' : route.aihotTab || 'daily';
  } else if (key === 'history') {
    const mode = ['claw','fingpt'].includes(route.historyMode) ? `mode=${route.historyMode}&` : '';
    rows = [['active','研究',`#/history${mode?'?'+mode.slice(0,-1):''}`],['deleted','已删除',`#/history?${mode}view=deleted`]]; selected=route.historyView || 'active';
  } else {
    const definition = PRIMARY_NAVIGATION.find(item=>item.page===key);
    rows = [[key,definition?.title || moduleTitle(route),definition?.href || '#/account']]; selected=key;
  }
  if (!rows.some(([id])=>id===selected)) selected=rows[0]?.[0];
  return rows.map(([id,label,href])=>({id,label,href,active:id===selected}));
}

export function renderModuleSidebar({ route = {}, collapsed = false, mobileOpen = false, account = globalThis.__RWB_ACCOUNT__, ...options } = {}) {
  options.account = account;
  return `<aside id="module-secondary-navigation" class="sidebar secondary-sidebar module-sidebar ${collapsed?'collapsed':''} ${mobileOpen?'mobile-open':''}" aria-label="${e(moduleTitle(route))}子页面" ${collapsed&&!mobileOpen?'inert aria-hidden="true"':''}><header class="sidebar-top"><h2>${e(moduleTitle(route))}</h2><button type="button" class="icon-button sidebar-collapse" data-collapse-sidebar aria-label="收起二级导航" aria-controls="module-secondary-navigation" aria-expanded="true">${icon('sidebar')}</button></header><nav class="module-links" aria-label="${e(moduleTitle(route))}视图">${secondaryEntries(route, options).map(item=>`<a href="${e(item.href)}" ${item.active?'aria-current="page"':''}>${e(item.label)}</a>`).join('')}</nav></aside>`;
}

export function createModulePreferences({ storage, owner = () => globalThis.__RWB_USER_ID__ || 'single-user', logger = safeLog } = {}) {
  const memory = new Map();
  const key = module => `research-web.secondary-navigation.v1.${encodeURIComponent(String(owner()))}.${module}`;
  return {
    get(module) {
      const id = key(module);
      if (memory.has(id)) return memory.get(id);
      let value = false;
      try { value = JSON.parse((storage || globalThis.localStorage)?.getItem(id) || '{}')?.collapsed === true; }
      catch { logger('module_navigation_read_failed'); }
      memory.set(id,value); return value;
    },
    set(module, collapsed) {
      const id = key(module), value = collapsed === true; memory.set(id,value);
      try { (storage || globalThis.localStorage)?.setItem(id,JSON.stringify({collapsed:value})); }
      catch { logger('module_navigation_write_failed'); }
      logger('module_navigation_view_changed', { status: value?'collapsed':'expanded' });
    },
  };
}

// The secondary drawer is modal on narrow screens; the primary rail stays visible.
export function trapSecondaryFocus(event, root) {
  if (event.key !== 'Tab') return;
  const pane = root.querySelector('.secondary-sidebar.mobile-open');
  const nodes = [...(pane?.querySelectorAll('a[href],button:not(:disabled),input,select,summary,[tabindex="0"]') || [])].filter(node=>node.getClientRects().length && !node.closest('[inert]'));
  if (!nodes.length) return;
  const first=nodes[0],last=nodes.at(-1),active=pane.ownerDocument.activeElement;
  if (!pane.contains(active) || event.shiftKey&&active===first || !event.shiftKey&&active===last) { event.preventDefault(); (event.shiftKey?last:first).focus({preventScroll:true}); }
}

export function closesSecondaryDrawer(event) {
  const link = event.target.closest?.('.secondary-sidebar a[href]');
  return Boolean(link && link.getAttribute?.('href')?.startsWith('#/') && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey && (event.button === undefined || event.button === 0));
}

export function focusModuleSelection(document) {
  const candidates = document.querySelectorAll('.secondary-sidebar [aria-current="page"], .topbar .sidebar-reopen, .topbar .menu-toggle');
  [...candidates].find(node=>node.getClientRects().length && !node.closest('[inert]'))?.focus({preventScroll:true});
}
