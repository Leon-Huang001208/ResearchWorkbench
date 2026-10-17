#!/usr/bin/env node
// Private launcher for the pinned upstream engine. Never prints configuration or secrets.
import { readFileSync, lstatSync, realpathSync, mkdirSync, cpSync, writeFileSync, existsSync, readdirSync, openSync, closeSync, symlinkSync, constants, fstatSync } from 'node:fs';
import path from 'node:path';
import { createHash, timingSafeEqual } from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { spawn } from 'node:child_process';
import { loadActivation } from './activation.mjs';
const ROOT = path.dirname(fileURLToPath(import.meta.url));
export const supportedNode = version => { const [major, minor] = version.split('.').map(Number); return major > 24 || major === 24 && minor >= 11; };
const hash = value => createHash('sha256').update(value).digest('hex');
export function readPrivate(file) {
  if (typeof file !== 'string' || !path.isAbsolute(file)) throw new Error('secret_path_invalid');
  const fd = openSync(file, constants.O_RDONLY | constants.O_NOFOLLOW);
  let value;
  try {
    const stat = fstatSync(fd);
    if (!stat.isFile() || stat.size > 65536 || (stat.mode & 0o777) !== 0o600 || (process.getuid && stat.uid !== process.getuid()) || realpathSync(file) !== file) throw new Error('secret_file_not_private');
    value = readFileSync(fd, 'utf8').trim();
  } finally { closeSync(fd); }
  return value;
}
export function secret(file, minimum = 16) {
  const value=readPrivate(file);
  if (value.length < minimum || value.includes('\0') || /[\r\n]/.test(value)) throw new Error('secret_value_invalid');
  return value;
}
export function loadConfig(file) {
  if (!path.isAbsolute(file)) throw new Error('config_path_invalid');
  const c = JSON.parse(readFileSync(file, 'utf8'));
  if (!Number.isInteger(c.port) || c.port < 1024 || c.port > 65535 || !path.isAbsolute(c.dataDir ?? '')) throw new Error('config_invalid');
  if (!['127.0.0.1', 'localhost', '::1'].includes(c.database?.host) || !Number.isInteger(c.database.port) || c.database.port < 1 || c.database.port > 65535 || !/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(c.database.name) || !/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(c.database.user)) throw new Error('database_config_invalid');
  return c;
}
export function verifyOrigin(root = path.join(ROOT, 'vendor/aihot'), manifestFile = path.join(ROOT, 'upstream.json')) {
  const manifest = JSON.parse(readFileSync(manifestFile, 'utf8'));
  if (manifest.commit !== '26d436497d9ddba9e7dd88eed255cfe0105ce368' || manifest.license !== 'MIT' || manifest.upstream !== 'https://github.com/KKKKhazix/AIHOT') throw new Error('upstream_identity_invalid');
  const actual = [];
  function walk(dir, prefix = '') {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      if (entry.name === 'node_modules') continue;
      const relative = prefix + entry.name;
      if (entry.isDirectory()) walk(path.join(dir, entry.name), relative + '/');
      else if (entry.isFile()) actual.push(relative);
      else throw new Error('upstream_non_regular_file');
    }
  }
  walk(root);
  if (actual.length !== Object.keys(manifest.files).length) throw new Error('upstream_closure_invalid');
  for (const file of actual) if (hash(readFileSync(path.join(root, file))) !== manifest.files[file]) throw new Error('upstream_hash_invalid');
  return { commit: manifest.commit, files: actual.length };
}
export function patchFile(root, relative, transform, records) {
  const file = path.join(root, relative), before = readFileSync(file, 'utf8'), after = transform(before);
  if (before === after) throw new Error('patch_precondition_failed');
  writeFileSync(file, after);
  records.push({ file: relative, beforeSha256: hash(before), afterSha256: hash(after) });
}
export function linkDependencies(stage) {
  const source = path.join(ROOT, 'vendor/aihot/node_modules');
  if (!existsSync(source)) return;
  const target = path.join(stage, 'node_modules');
  mkdirSync(target, { recursive: true });
  for (const entry of readdirSync(source)) {
    if (entry === '@aihot' || existsSync(path.join(target, entry))) continue;
    symlinkSync(path.join(source, entry), path.join(target, entry), 'dir');
  }
  mkdirSync(path.join(target, '@aihot'), { recursive: true });
  for (const group of ['apps', 'packages', 'modules']) {
    for (const name of readdirSync(path.join(stage, group))) {
      const folder = path.join(stage, group, name), manifest = path.join(folder, 'package.json');
      if (!existsSync(manifest)) continue;
      const packageName = JSON.parse(readFileSync(manifest, 'utf8')).name;
      if (packageName?.startsWith('@aihot/') && !existsSync(path.join(target, packageName))) symlinkSync(folder, path.join(target, packageName), 'dir');
    }
  }
  for (const name of ['site', 'industry']) if (!existsSync(path.join(target, '@aihot', name))) symlinkSync(path.join(stage, name), path.join(target, '@aihot', name), 'dir');
}
export function stageEngine(dataDir) {
  const origin = verifyOrigin();
  const stage = path.join(dataDir, 'engine');
  const marker = path.join(stage, '.rwb-patches.json');
  if (existsSync(stage)) {
    if (!existsSync(marker)) throw new Error('stage_unverified');
    const records = JSON.parse(readFileSync(marker, 'utf8'));
    const upstream = JSON.parse(readFileSync(path.join(ROOT, 'upstream.json'), 'utf8'));
    if (records.commit !== origin.commit || records.adapterSha256 !== hash(readFileSync(import.meta.filename))) throw new Error('stage_adapter_changed_restage_required');
    const patched = new Map(records.patches.map(p => [p.file, p.afterSha256]));
    for (const [file, digest] of Object.entries(upstream.files)) if (hash(readFileSync(path.join(stage, file))) !== (patched.get(file) ?? digest)) throw new Error('stage_hash_invalid');
    linkDependencies(stage);
    return stage;
  }
  mkdirSync(dataDir, { recursive: true, mode: 0o700 });
  cpSync(path.join(ROOT, 'vendor/aihot'), stage, { recursive: true, filter: source => path.basename(source) !== 'node_modules' });
  const patches = [];
  patchFile(stage, 'packages/backend/src/operations/recover.ts', text => {
    const start = text.indexOf('export async function autoReleaseUnknownReceipts('), end = text.indexOf('\n/** ops.recover', start);
    if (start < 0 || end < 0) throw new Error('receipt_patch_precondition');
    return text.slice(0, start).replace(/\/\*\*\n \* Unknown receipts older[\s\S]*?\*\/\n$/, '// RWB: no automatic release of unknown paid outcomes.\n').replace(`An unknown receipt is released once automatically after\n// half an hour without checking the provider's bill, so a lost answer costs at most one repeat; one that\n// turns unknown again waits for the admin, who checks the bill and releases it with a note.`, 'Unknown receipts always wait for an operator to check the bill and explicitly release with a note.').replace('const AUTO_RELEASE_AFTER_MS = 30 * 60_000;\n', '') + 'export async function autoReleaseUnknownReceipts(_now = Date.now()) {\n  // RWB: unknown paid outcomes require explicit operator reconciliation. Never retry on elapsed time.\n  return { released: 0, requeued: 0 };\n}\n' + text.slice(end);
  }, patches);
  patchFile(stage, 'packages/backend/src/providers/receipts.ts', text => text.replace('  if (!budget) return; // default rows come with the migrations; a service an operator removed is unlimited', '  // RWB: permission and persisted positive limits are required before every actual paid attempt.\n  const { assertPaidAuthorization } = await import(process.env.RWB_AI_NEWS_POLICY_URL!);\n  assertPaidAuthorization(service, budget);\n  if (!budget) throw new Error("paid_persisted_budget_required");').replace('it is released once automatically, then from the admin', 'explicit operator reconciliation is required'), patches);
  patchFile(stage, 'packages/backend/src/operations/alerts.ts', text => text.replace('仍在等待自动恢复；付费结果未知的请求会在 30 分钟后自动放行一次', '付费结果未知，必须人工核对供应商账单后显式放行'), patches);
  patchFile(stage, 'packages/backend/src/lib/url.ts', text => text.replace('export async function assertPublicUrl(url: string, allowPrivate = false, resolve?: (host: string) => Promise<string[]>): Promise<URL> {', 'export async function assertPublicUrl(url: string, allowPrivate = false, resolve?: (host: string) => Promise<string[]>): Promise<URL> {\n  const rwbHost = new URL(url).hostname.toLowerCase().replace(/\\.$/, "");\n  if (rwbHost === "aihot.news" || rwbHost.endsWith(".aihot.news")) throw new Error("rwb_outbound_origin_forbidden");'), patches);
  patchFile(stage, 'apps/api/src/app.ts', text => text.replace('import Fastify,', 'import { timingSafeEqual } from "node:crypto";\nimport Fastify,').replace('  app.setChildLoggerFactory', '  app.addHook("onRequest", async (req, reply) => {\n    const given = Buffer.from(String(req.headers["x-rwb-ai-news-token"] ?? ""));\n    const expected = Buffer.from(process.env.RWB_AI_NEWS_TOKEN ?? "");\n    if (!expected.length || given.length !== expected.length || !timingSafeEqual(given, expected)) return reply.code(401).header("Cache-Control", "no-store").send({ error: "unauthorized" });\n  });\n\n  app.setChildLoggerFactory').replace('"req.headers.authorization", "req.headers.cookie"', '"req.headers.authorization", "req.headers.cookie", "req.headers.x-rwb-ai-news-token", "req.headers.x-csrf-token"').replace('trustProxy: true', 'trustProxy: false'), patches);
  patchFile(stage, 'site/site.ts', text => text.replace('name: "MyHOT"', 'name: "AI 资讯"').replace('homeTitle: "MyHOT —', 'homeTitle: "AI 资讯 —'), patches);
  patchFile(stage, 'industry/sources.json', text => {
    const data = JSON.parse(text);
    for (const source of data.sources) source.enabled = false;
    return JSON.stringify(data, null, 2) + '\n';
  }, patches);
  writeFileSync(marker, JSON.stringify({ commit: origin.commit, adapterSha256: hash(readFileSync(import.meta.filename)), patches }, null, 2) + '\n', { mode: 0o600 });
  linkDependencies(stage);
  return stage;
}
export function environment(c) {
  const db = c.database;
  const activation = loadActivation(c.activationFile);
  const url = new URL(`postgresql://${db.host === '::1' ? '[::1]' : db.host}:${db.port}/${db.name}`);
  url.username = db.user; url.password = secret(db.passwordFile, 1);
  // Allowlisted environment: ambient dotenv, development bypasses, proxies and credentials cannot leak in.
  return { PATH: process.env.PATH ?? '', HOME: process.env.HOME ?? '', NODE_ENV: 'production', API_HOST: '127.0.0.1', API_PORT: String(c.port), SITE_URL: `http://127.0.0.1:${c.port}`, DATABASE_URL: url.href,
    AIHOT_DATA_DIR: path.join(c.dataDir, 'data'), AIHOT_CREDENTIALS_DIR: path.join(c.dataDir, 'credentials-disabled'), AIHOT_ENVIRONMENT: 'rwb-local',
    RWB_AI_NEWS_TOKEN: secret(c.tokenFile, 24), ADMIN_PASSWORD: secret(c.adminPasswordFile, 12), SESSION_SECRET: secret(c.sessionSecretFile, 32), IMG_PROXY_SIGN_SECRET: secret(c.imageSecretFile, 32),
    ...activation.environment, RWB_AI_NEWS_ACTIVATION_FILE: c.activationFile ?? '', RWB_AI_NEWS_POLICY_URL: pathToFileURL(path.join(ROOT, 'activation.mjs')).href, COLLECT_ENABLED: String(activation.collectionEnabled), MODEL_CALLS_ENABLED: String(activation.modelCallsEnabled), FEISHU_CONTENT_PUSH_ENABLED: 'false', FEISHU_INTERNAL_ENABLED: 'false', INDEXNOW_SUBMIT_ENABLED: 'false', LOG_LEVEL: 'info', AIHOT_RELEASE: 'rwb-26d436497d9d' };
}
export function authenticated(given, expected) {
  const a = Buffer.from(String(given ?? '')), b = Buffer.from(String(expected ?? ''));
  return b.length > 0 && a.length === b.length && timingSafeEqual(a, b);
}
async function main() {
  const [command, flag, configFile, ...extra] = process.argv.slice(2);
  if (!['api', 'worker', 'migrate', 'seed', 'doctor', 'stage'].includes(command) || flag !== '--config' || !configFile || extra.length) throw new Error('usage_runtime_command_config');
  const c = loadConfig(configFile), origin = verifyOrigin(), env = environment(c);
  if (command === 'doctor') {
    const dependenciesInstalled = existsSync(path.join(c.dataDir, 'engine/node_modules/fastify'));
    console.log(JSON.stringify({ ok: supportedNode(process.versions.node) && dependenciesInstalled, engine: origin, nodeSupported: supportedNode(process.versions.node), dependenciesInstalled, collectionEnabled: env.COLLECT_ENABLED === 'true', modelCallsEnabled: env.MODEL_CALLS_ENABLED === 'true', configuredPending: ['x_search', 'mp_account'], serviceProbed: false }));
    return;
  }
  if (!supportedNode(process.versions.node)) throw new Error('node_24_required');
  const stage = stageEngine(c.dataDir);
  if (command === 'stage') { console.log(JSON.stringify({ ok: true, stage, installRequired: !existsSync(path.join(stage, 'node_modules')) })); return; }
  if (!existsSync(path.join(stage, 'node_modules/fastify'))) throw new Error('engine_dependencies_missing');
  mkdirSync(path.join(c.dataDir, 'logs'), { recursive: true, mode: 0o700 });
  const fd = openSync(path.join(c.dataDir, 'logs', `${command}.jsonl`), 'a', 0o600);
  const entry = command === 'api' ? path.join(ROOT, 'server.mjs') : command === 'worker' ? path.join(stage, 'apps/worker/src/main.ts') : command === 'migrate' ? path.join(stage, 'scripts/migrate.ts') : path.join(stage, 'scripts/seed.ts');
  const child = spawn(process.execPath, ['--import', path.join(ROOT, 'network-guard.mjs'), entry], { cwd: stage, env: { ...env, RWB_ENGINE_ROOT: stage }, stdio: ['ignore', fd, fd] });
  closeSync(fd);
  for (const signal of ['SIGTERM', 'SIGINT']) process.on(signal, () => child.kill(signal));
  child.on('error', () => { console.error(JSON.stringify({ ok: false, error: 'engine_spawn_failed' })); process.exitCode = 1; });
  child.on('exit', (code, signal) => { process.exitCode = code ?? (signal ? 1 : 0); });
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main().catch(error => { console.error(JSON.stringify({ ok: false, error: /^[a-z0-9_]+$/.test(error.message) ? error.message : 'ai_news_runtime_failed' })); process.exitCode = 1; });
