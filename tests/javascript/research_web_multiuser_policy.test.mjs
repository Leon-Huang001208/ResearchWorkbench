import test from 'node:test';
import assert from 'node:assert/strict';
import { apply } from '../../app/research_web/runtime/guard.mjs';

test('tenant guard denies host, native document, automation, skill and MCP despite settings', () => {
  let guard;
  const ctx = { tools: { guard(fn) { guard = fn; } }, logger: { warn() {} } };
  const mcp = 'mcp__mcp-installation-0123456789abcdef0123456789abcdef__read';
  apply(ctx, {enabled: true, tenantMode: true, tabbitBrowserEnabled: true, tabbitWebFetchEnabled: true, mcpTools: [mcp]});
  const agent = {session: {snapshotEvents: () => [{type:'turn/start',data:{turn:1}}]}};
  for (const name of ['bash', 'read_file', 'tabbit_browser', 'web_fetch', 'skill', mcp, 'rwb_prepare_automation', 'rwb_run_automation']) {
    assert.ok(guard({name, agent}), name);
  }
  assert.ok(guard({name:'research_document_operation', agent, arguments:{mode:'native'}}));
  assert.equal(guard({name:'research_document_operation', agent, arguments:{mode:'file'}}), undefined);
  for (const name of ['research_run_script', 'research_check_quality', 'todo_write', 'web_search', 'subagent']) {
    assert.equal(guard({name, agent}), undefined, name);
  }
});

test('tenant guard permits only launcher-reviewed builtin skill identities', () => {
  let guard;
  apply({tools:{guard(fn){guard=fn;}},logger:{warn(){}}}, {enabled:true,tenantMode:true,tenantSkillNames:['reviewed-builtin']});
  const agent={session:{snapshotEvents:()=>[{type:'turn/start',data:{turn:1}}]}};
  assert.equal(guard({name:'skill',agent,arguments:{name:'reviewed-builtin'}}),undefined);
  assert.ok(guard({name:'skill',agent,arguments:{name:'rwb-user-package-v1'}}));
});
