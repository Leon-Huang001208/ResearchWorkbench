import { test } from 'node:test';
import assert from 'node:assert/strict';
import type { ConnectionOptions, PeerCertificate } from 'node:tls';
import { parseConfig, schemaName, poolOptions, assertNodeRuntime } from '../src/config.ts';

test('non-secret configuration has bounded defaults and explicit TLS policy', () => {
  const settings = parseConfig({ enabled: false });
  assert.equal(settings.timezone, 'Asia/Shanghai');
  assert.equal(settings.database.mode, 'managed');
  assert.equal(settings.database.tls, 'disable');
  assert.equal(settings.budget.maxCallsPerDay, 0);
  assert.deepEqual(settings.model, {enabled:false,scopeId:'hot'});
  assert.deepEqual(parseConfig({model:{enabled:true,scopeId:'hot_events_goal_01a11684'}}).model,
    {enabled:true,scopeId:'hot_events_goal_01a11684'});
  assert.throws(()=>parseConfig({model:{enabled:'true'}}));
  assert.throws(()=>parseConfig({model:{scopeId:'../other'}}));
  assert.throws(()=>parseConfig({model:{provider:'arbitrary'}}));
  assert.throws(() => parseConfig({ password: 'secret' }), /hot_config_unknown_field/);
  assert.throws(() => parseConfig({ database: { mode: 'external', host: 'db.example', tls: 'disable' } }), /hot_external_tls_required/);
  const external = parseConfig({ database: { mode: 'external', host: 'db.example', tls: 'verify-full' } });
  assert.equal((poolOptions(external.database, 'only-injected-secret').ssl as ConnectionOptions).rejectUnauthorized, true);
});

test('verified database TLS binds certificate identity to configured DNS or IP host',()=>{
  const options=(host:string)=>poolOptions(parseConfig({database:{mode:'external',host,tls:'verify-full'}}).database,'injected-test-secret').ssl as ConnectionOptions;
  const dns={subject:{CN:'localhost'},subjectaltname:'DNS:localhost'} as PeerCertificate;
  const ip={subject:{CN:'localhost'},subjectaltname:'IP Address:127.0.0.1'} as PeerCertificate;
  assert.equal(typeof options('127.0.0.1').checkServerIdentity,'function');
  const mismatch=options('127.0.0.1').checkServerIdentity!('localhost',dns) as (Error & {code:string})|undefined;
  assert.equal(mismatch?.code,'ERR_TLS_CERT_ALTNAME_INVALID');
  assert.equal(options('127.0.0.1').checkServerIdentity!('localhost',ip),undefined);
  assert.equal(options('localhost').checkServerIdentity!('driver-fallback',dns),undefined);
});

test('Hot runtime requires its supported Node family without changing base Web requirements', () => {
  assertNodeRuntime('24.19.0');
  assert.throws(() => assertNodeRuntime('22.19.0'), /hot_node_version_unsupported/);
  assert.throws(() => assertNodeRuntime('25.9.0'), /hot_node_version_unsupported/);
});

test('explicit processing selection is bounded, normalized and does not alter budget authorization',()=>{
  const id='A1111111-1111-4111-8111-111111111111';
  const config=parseConfig({model:{materialIds:[id]}});
  assert.deepEqual(config.model.materialIds,[id.toLowerCase()]);assert.equal(config.model.enabled,false);assert.equal(config.budget.maxCallsPerDay,0);
  for(const ids of ['bad',[true],['bad'],[id,id.toLowerCase()],Array(21).fill(id)])assert.throws(()=>parseConfig({model:{materialIds:ids}}),/hot_config_invalid/);
});

test('schema and credentials references reject arbitrary SQL, URLs and paths', () => {
  assert.equal(schemaName('hot_custom_1'), 'hot_custom_1');
  assert.equal(schemaName('h'.repeat(48)).length, 48);
  assert.throws(() => schemaName('h'.repeat(49)));
  for (const value of ['public', 'pg_catalog', 'x;drop schema hot', 'Hot', '../hot', '']) assert.throws(() => schemaName(value));
  assert.throws(() => parseConfig({ database: { secretRef: '/tmp/password' } }));
  assert.throws(() => parseConfig({ database: { host: 'postgres://name:secret@server/db' } }));
  assert.throws(() => parseConfig({ worker: { concurrency: 999 } }));
  assert.throws(() => parseConfig({database:{user:'same',controllerUser:'same'}}),/hot_database_roles_overlap/);
  assert.throws(() => parseConfig({ timezone: 'not-a-timezone' }));
});
