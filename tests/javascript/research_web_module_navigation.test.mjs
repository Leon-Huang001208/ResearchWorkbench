import test from 'node:test';
import assert from 'node:assert/strict';
import { parseRoute } from '../../app/research_web/ui/core.mjs';
import { PRIMARY_NAVIGATION, moduleKey, secondaryEntries, createModulePreferences, renderModuleSidebar, closesSecondaryDrawer, focusModuleSelection, trapSecondaryFocus } from '../../app/research_web/ui/module-navigation.mjs';
import { icon, hasIcon } from '../../app/research_web/ui/icons.mjs';

test('primary navigation uses valid, independently recognizable glyphs', () => {
  const all = [...PRIMARY_NAVIGATION, { glyph: 'milestones' }, { glyph: 'settings' }];
  assert.equal(new Set(all.map(item => item.glyph)).size, all.length);
  assert.equal(new Set(all.map(item => icon(item.glyph))).size, all.length);
  for (const item of all) assert.equal(hasIcon(item.glyph), true);
  assert.equal(hasIcon('not-a-real-icon'), false);
});
test('every canonical business module has secondary navigation and a current destination', () => {
  for (const href of [...PRIMARY_NAVIGATION.map(x => x.href), '#/progress', '#/progress/changelog', '#/settings/model', '#/account', '#/history?mode=claw&view=deleted']) {
    const route = parseRoute(href), items = secondaryEntries(route);
    assert(items.length, href); assert.equal(items.filter(x => x.active).length, 1, href);
    assert.match(renderModuleSidebar({ route }), /module-secondary-navigation/);
  }
});
test('legacy routes map to canonical module and active section', () => {
  for (const [href, key] of [['#/automations','automations'],['#/skills?view=plans','automations'],['#/workbench/funds','assets'],['#/workbench/industry','intel'],['#/simulation/scores','simulation']]) {
    const r = parseRoute(href); assert.equal(moduleKey(r), key); assert.equal(secondaryEntries(r).filter(x => x.active).length, 1, href);
  }
});
test('market sidebar preserves five discoverable destinations when duplicate inner tabs are hidden', () => {
  const destinations = [
    ['dashboard', '综合总览', '#/market'],
    ['overview', '行情分析', '#/market?view=overview'],
    ['quotes', '沪深北行情', '#/market?view=quotes'],
    ['sectors', '板块与资金', '#/market?view=sectors'],
    ['workbench', '研究工作台', '#/market?view=workbench'],
  ];
  for (const [id, label, href] of destinations) {
    const route = parseRoute(href), items = secondaryEntries(route);
    assert.deepEqual(items.map(item => [item.id, item.label, item.href]), destinations);
    assert.deepEqual(items.filter(item => item.active).map(item => item.id), [id], href);
    const html = renderModuleSidebar({ route, account: { role: 'user' } });
    assert.match(html, new RegExp(`href="${href.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}" aria-current="page">${label}</a>`));
    assert.equal((html.match(/<a href=/g) || []).length, 5);
  }
});
test('progress navigation preserves compatible filters and clears incompatible detail/month', () => {
  const items = secondaryEntries(parseRoute('#/progress?status=developing&module=产品体验&item=feature-id&month=2026-11'));
  const target = parseRoute(items[1].href);
  assert.equal(target.progressTab, 'changelog'); assert.equal(target.progressModule, '产品体验');
  assert.equal(target.progressItem, ''); assert.equal(target.progressMonth, '');
});
test('permissions and plain text do not expose admin destinations', () => {
  assert(!secondaryEntries(parseRoute('#/settings/general'), { account: {role:'user'} }).some(x => x.href === '#/settings/users'));
  assert(secondaryEntries(parseRoute('#/settings/general'), { account: {role:'admin'} }).some(x => x.href === '#/settings/users'));
  assert(!secondaryEntries(parseRoute('#/aihot/daily'), { canManageNews:false }).some(x => x.href === '#/aihot/manage'));
});
test('per-module preferences persist and remain isolated by account', () => {
  const saved = new Map(); const storage={getItem:k=>saved.get(k),setItem:(k,v)=>saved.set(k,v)};let owner='account-a';
  const p=createModulePreferences({ storage, owner:()=>owner });assert.equal(p.get('assets'),false);
  p.set('assets',true);assert.equal(p.get('assets'),true);assert.equal(p.get('progress'),false);
  assert.equal(createModulePreferences({storage,owner:()=>owner}).get('assets'),true);
  owner='account-b';assert.equal(p.get('assets'),false);p.set('progress',true);owner='account-a';assert.equal(p.get('progress'),false);
});
test('blocked or malformed storage retains in-memory preference and logs a stable code', () => {
  const events=[];const p=createModulePreferences({storage:{getItem(){throw Error('private')},setItem(){throw Error('private')}},logger:code=>events.push(code)});
  assert.equal(p.get('assets'),false);p.set('assets',true);assert.equal(p.get('assets'),true);assert(events.includes('module_navigation_write_failed'));
  const invalid=createModulePreferences({storage:{getItem:()=>'{"collapsed":"yes"}'}});assert.equal(invalid.get('assets'),false);
});
test('drawer selection closes for same and different hashes but preserves modified clicks', () => {
  const target={closest:()=>({getAttribute:()=>'#/assets'})};
  assert.equal(closesSecondaryDrawer({target,button:0}),true);
  assert.equal(closesSecondaryDrawer({target,button:0,ctrlKey:true}),false);
  assert.equal(closesSecondaryDrawer({target,button:1}),false);
  assert.equal(closesSecondaryDrawer({target:{closest:()=>null}}),false);
});
test('detail Escape fallback focuses a visible opener when secondary navigation is hidden', () => {
  const focused=[];const nodes=[{getClientRects:()=>[],closest:()=>null,focus:()=>focused.push('hidden')},{getClientRects:()=>[{}],closest:()=>null,focus:()=>focused.push('opener')}];
  focusModuleSelection({querySelectorAll:()=>nodes});assert.deepEqual(focused,['opener']);
});
test('secondary focus wraps without making the persistent primary part of the trap', () => {
  let focused='';const first={getClientRects:()=>[{}],closest:()=>null,focus:()=>focused='first'},last={getClientRects:()=>[{}],closest:()=>null,focus:()=>focused='last'};
  const pane={ownerDocument:{activeElement:last},contains:()=>true,querySelectorAll:()=>[first,last]};let prevented=false;
  trapSecondaryFocus({key:'Tab',preventDefault:()=>prevented=true},{querySelector:()=>pane});assert(prevented);assert.equal(focused,'first');
  pane.ownerDocument.activeElement=first;trapSecondaryFocus({key:'Tab',shiftKey:true,preventDefault(){}},{querySelector:()=>pane});assert.equal(focused,'last');
});
