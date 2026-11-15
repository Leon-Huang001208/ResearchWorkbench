import test from 'node:test';
import assert from 'node:assert/strict';
import { renderResearchBots, createResearchBots, botFormBody } from '../../app/research_web/ui/research-bots.mjs';

test('Research Bot renders escaped content and separates unavailable from empty', () => {
  const html = renderResearchBots({items:[{id:'one',name:'<img src=x>',research_task:{bot:{objective:'<script>',keywords:[],watchlist:[],skills:[]}},enabled:false}], runs:[], models:[], skills:[]});
  assert.ok(html.includes('&lt;img src=x&gt;'));
  assert.ok(!html.includes('<script>'));
  assert.ok(renderResearchBots({items:[],error:'来源未连接'}).includes('来源未连接'));
  assert.ok(renderResearchBots({items:[],loading:true}).includes('读取中'));
});

test('Form uses viewed skill versions, caps bindings and retains a creation request identity', () => {
  const data = new FormData();
  for(const [key,value] of Object.entries({name:'观察',objective:'核实',model:'deepseek-official|deepseek-flash',interval_minutes:'30',avatar:'cow',color:'#0786ff',keywords:'AI，光模块',watchlist:'300308'})) data.set(key,value);
  data.append('skills','test|2');
  const body=botFormBody(data,'same-request');
  assert.equal(body.request_id,'same-request');
  assert.deepEqual(body.keywords,['AI','光模块']);
  assert.deepEqual(body.skills,[{id:'test',version:2,arguments:{}}]);
});

test('Late reads do not overwrite the newly activated page', async () => {
  let old;let calls=0;
  const api={researchBots:()=>++calls===1?new Promise(resolve=>old=resolve):Promise.resolve({items:[{id:'new'}]}),capabilities:async()=>({items:[]}),models:async()=>({groups:[]})};
  const workspace=createResearchBots({api,notify:()=>{},route:()=>({page:'research-bots'})});
  const first=workspace.activate();await workspace.activate();old({items:[{id:'old'}]});await first;
  assert.equal(workspace.state.items[0].id,'new');
});

test('An old binding is retained once and never silently upgraded in the form', () => {
  const html=renderResearchBots({items:[],draft:{existing:{},config:{skills:[{id:'one',version:1}]}},skills:[{id:'one',version:2,kind:'skill',enabled:true,name:'测试'}],models:[{id:'deepseek-official',models:[{id:'deepseek-flash'}]}]});
  assert.ok(html.includes('<option value="one|1" selected>'));
  assert.ok(!html.includes('<option value="one|2" selected>'));
  assert.ok(html.includes('新建和编辑保存后均停用'));
  assert.ok(html.includes('批准的研究工具'));
});

const botFixture = {
  id: 'bot-one',
  name: '产业观察',
  definition_version: 3,
  research_task: { bot: {}, model_provider: 'deepseek-official', model_id: 'deepseek-flash' },
};

function fixtureAPI(overrides = {}) {
  return {
    researchBots: async () => ({ items: [botFixture], latest_runs: [] }),
    capabilities: async () => ({ items: [] }),
    models: async () => ({ groups: [{ id: 'deepseek-official', models: [{ id: 'deepseek-flash' }] }] }),
    ...overrides,
  };
}

function click(attributes = [], dataset = {}) {
  const button = { type: 'button', dataset, hasAttribute: name => attributes.includes(name) };
  return {
    type: 'click',
    target: { closest: selector => selector === 'button' ? button : {} },
  };
}

test('refresh uses latest run projections and fetches only the selected Bot history page', async () => {
  const reads = [];
  const workspace = createResearchBots({
    route: () => ({ page: 'research-bots' }),
    api: fixtureAPI({
      researchBots: async () => ({
        items: [botFixture],
        latest_runs: [{ id: 'new', automation_id: botFixture.id, research_status: 'completed', summary: '最新运行' }],
      }),
      researchBotRuns: async (id, before) => {
        reads.push([id, before]);
        return before
          ? { items: [{ id: 'older', summary: '更早运行' }], next_before: null }
          : { items: [{ id: 'new', summary: '最新运行' }], next_before: 'page-2' };
      },
    }),
  });
  await workspace.activate();
  assert.deepEqual(reads, []);
  assert.match(workspace.render(), /最新运行/);

  await workspace.handle(click([], { botAction: 'history', botId: botFixture.id }));
  assert.match(workspace.render(), /加载更早/);
  await workspace.handle(click(['data-bot-older-history']));
  assert.deepEqual(reads, [[botFixture.id, undefined], [botFixture.id, 'page-2']]);
  assert.match(workspace.render(), /更早运行/);
  assert.doesNotMatch(workspace.render(), /加载更早/);
});

test('a read error for one history keeps Bot mutations available', async () => {
  const workspace = createResearchBots({
    route: () => ({ page: 'research-bots' }),
    api: fixtureAPI({ researchBotRuns: async () => { throw new Error('历史读取失败'); } }),
  });
  await workspace.activate();
  await workspace.handle(click([], { botAction: 'history', botId: botFixture.id }));
  assert.match(workspace.render(), /历史读取失败/);
  assert.equal(workspace.state.uncertain, false);
});

test('a skipped or blocked run is not reported as accepted', async () => {
  const cases = [
    ['queued', /已受理/],
    ['skipped_overlap', /已有运行，已跳过/],
    ['blocked_version', /版本校验未通过/],
  ];
  for (const [research_status, message] of cases) {
    const workspace = createResearchBots({
      route: () => ({ page: 'research-bots' }),
      confirm: () => true,
      api: fixtureAPI({
        researchBotAction: async (_id, _action, body) => {
          assert.equal(body.expected_version, 3);
          assert.match(body.request_id, /^[a-f0-9-]{36}$/);
          return { research_status };
        },
      }),
    });
    await workspace.activate();
    await workspace.handle(click([], { botAction: 'run', botId: botFixture.id }));
    assert.match(workspace.render(), message);
    if (research_status !== 'queued') assert.doesNotMatch(workspace.render(), /已受理/);
  }
});

test('invalid JSON leaves the entered fields intact through refresh and submit', async () => {
  const originalFormData = globalThis.FormData;
  const fields = new originalFormData();
  fields.set('name', '未保存名称');
  fields.set('keywords', '待核实， 仍在输入');
  fields.set('arguments', '{\"draft\": <broken>');
  const workspace = createResearchBots({ api: fixtureAPI(), route: () => ({ page: 'research-bots' }) });
  await workspace.activate();
  await workspace.handle(click(['data-bot-new']));

  const form = {
    matches: selector => selector === '[data-bot-form]',
    closest: selector => selector === '[data-research-bots]' ? {} : null,
  };
  globalThis.FormData = class { constructor() { return fields; } };
  try {
    await workspace.handle({
      type: 'input',
      target: { closest: selector => selector === '[data-bot-form]' ? form : {} },
    });
    await workspace.activate();
    assert.match(workspace.render(), /待核实， 仍在输入/);
    await workspace.handle({ type: 'submit', target: form, preventDefault() {} });
  } finally {
    globalThis.FormData = originalFormData;
  }
  assert.match(workspace.render(), /未保存名称/);
  assert.match(workspace.render(), /&lt;broken&gt;/);
  assert.match(workspace.render(), /技能参数/);
});

test('history requests encode the cursor and use a read-only HTTP method', async () => {
  const { createAPI } = await import('../../app/research_web/ui/core.mjs');
  const requests = [];
  const api = createAPI({
    fetcher: async (path, options) => {
      requests.push({ path, method: options.method });
      return { ok: true, status: 200, json: async () => ({ items: [], next_before: null }) };
    },
  });
  await api.researchBotRuns('bot/one', 'run+2?');
  assert.deepEqual(requests, [{ path: '/api/research/research-bots/bot%2Fone/runs?before=run%2B2%3F', method: 'GET' }]);
});
