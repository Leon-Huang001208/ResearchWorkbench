import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createBudget, createTiers, replaceTiers, wrapTools} from '../../research_workbench_entrypoint/fingpt_compare_node.mjs';

test('tool cap includes concurrent admission and preserves partial results',()=>{
  const rows=[],budget=createBudget(x=>rows.push(x));
  for(let i=0;i<48;i++)budget.before('get_economic_data');
  assert.throws(()=>budget.before('get_economic_data'),/budget_exhausted/);
  assert.equal(rows.filter(x=>x.event==='tool_admitted').length,48);
});
test('six searches maximum and no subagent',()=>{
  const budget=createBudget(()=>{});
  for(let i=0;i<6;i++)budget.before('search_news_notices');
  assert.throws(()=>budget.before('get_news_flash'),/budget_exhausted/);
  assert.throws(()=>createBudget(()=>{}).before('subagent'),/subagent_denied/);
});
test('all native DataHub search aliases share the same six-search allowance',()=>{
  const rows=[],budget=createBudget(x=>rows.push(x));
  for(const name of ['web_search','datahub_search_web','datahub_search_news','datahub_search_announcements','datahub_search_research','get_news_flash'])budget.before(name);
  assert.throws(()=>budget.before('datahub_search_assets'),/budget_exhausted/);
  assert.equal(rows.filter(x=>x.event==='tool_admitted').at(-1).searches,6);
});
test('model seam leaves chat client and original tool body intact',()=>{
  const source='prefix\nexport function getTiers() { return 1; }\n\nexport function publicTiers(){return getTiers();}\nclient';
  const result=replaceTiers(source);
  assert.ok(result.endsWith('client'));assert.ok(result.includes('publicTiers(){return getTiers();}'));
  const tool='export async function runTool(name, args, { signal } = {}) { return {original:true}; }';
  assert.ok(wrapTools(tool).includes('return {original:true}'));
  assert.throws(()=>wrapTools('unknown'),/seam_unknown/);
  assert.throws(()=>replaceTiers('unknown'),/seam_unknown/);
});
test('model configuration is private client memory, not a child process environment',()=>{
  const beforeMimo=process.env.MIMO_API_KEY,beforeQwen=process.env.DASHSCOPE_API_KEY;
  const tiers=createTiers('B',{},'fixture-secret');
  assert.equal(tiers.frontier.model,'deepseek-flash');
  assert.equal(tiers.lite.key,'');
  assert.equal(process.env.MIMO_API_KEY===beforeMimo,true);
  assert.equal(process.env.DASHSCOPE_API_KEY===beforeQwen,true);
  assert.throws(()=>createTiers('A',{},'fixture-secret'),/binding_invalid/);
  assert.throws(()=>createTiers('C',{},'bad\r\nheader'),/binding_invalid/);
});
