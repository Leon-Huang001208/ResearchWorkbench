import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { apply } from '../../app/research_web/runtime/guard.mjs';

test('tenant guard denies host access and permits only exact Host-verified MCP names', () => {
  const root = mkdtempSync(join(tmpdir(), 'rwb-plugin-guard-'));
  try {
  let guard;
  const ctx = { on() {}, tools: { guard(fn) { guard = fn; } }, logger: { warn() {}, info() {} } };
  const mcp = 'mcp__mcp-installation-0123456789abcdef0123456789abcdef__read';
  apply(ctx, {enabled: true, tenantMode: true, researchRoot: root, tabbitBrowserEnabled: true, tabbitWebFetchEnabled: true, mcpTools: [mcp]});
  const agent = {session: {snapshotEvents: () => [{type:'turn/start',data:{turn:1}}]}};
  for (const name of ['bash', 'read_file', 'tabbit_browser', 'web_fetch', 'skill', mcp + '_other', 'rwb_prepare_automation', 'rwb_run_automation']) {
    assert.ok(guard({name, agent}), name);
  }
  assert.equal(guard({name: mcp, agent}), undefined);
  assert.ok(guard({name:'research_document_operation', agent, arguments:{mode:'native'}}));
  assert.equal(guard({name:'research_document_operation', agent, arguments:{mode:'file'}}), undefined);
  for (const name of ['research_run_script', 'research_check_quality', 'todo_write', 'web_search', 'subagent']) {
    assert.equal(guard({name, agent}), undefined, name);
  }
  writeFileSync(join(root, 'plugins/runtime-freeze.json'), '{}', {mode: 0o600});
  assert.equal(guard({name: mcp, agent}), 'plugin_runtime_frozen');
  } finally { rmSync(root, {recursive: true}); }
});

test('tenant guard permits only launcher-reviewed builtin skill identities', () => {
  const root = mkdtempSync(join(tmpdir(), 'rwb-plugin-guard-'));
  try {
  let guard;
  apply({on(){},tools:{guard(fn){guard=fn;}},logger:{warn(){},info(){}}}, {enabled:true,tenantMode:true,researchRoot:root,tenantSkillNames:['reviewed-builtin']});
  const agent={session:{snapshotEvents:()=>[{type:'turn/start',data:{turn:1}}]}};
  assert.equal(guard({name:'skill',agent,arguments:{name:'reviewed-builtin'}}),undefined);
  assert.ok(guard({name:'skill',agent,arguments:{name:'rwb-user-package-v1'}}));
  } finally { rmSync(root, {recursive: true}); }
});
