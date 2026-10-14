/** Bounded live proof; private isolated resources, stable receipt, no paid calls. */
import { mkdir, writeFile, readFile, lstat } from 'node:fs/promises';
import { randomBytes } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import postgres from 'postgres';
import { PgBoss } from 'pg-boss';
import { parseFeed, PROBE_SOURCES } from '../src/feed.ts';
import { identityKeyForUrl, contentHash, sha256 } from '../src/material.ts';

const root = resolve(import.meta.dirname, '../../..');
const dir = resolve(root, 'logs/hot-stage-zero');
const image = 'postgres@sha256:3645570cccdfa447589da9f57dd740faa29b30938e861289a5574b6ca6b03826';
const name = 'rwb-hot-probe-6a5d3231';
const volume = `${name}-data`;
await mkdir(dir, { recursive: true, mode: 0o700 });
let sequence = 0;
async function log(event: string, detail: Record<string, unknown> = {}) {
  await writeFile(resolve(dir, `event-${++sequence}.json`), JSON.stringify({ event, ...detail }), { mode: 0o600 });
}
function docker(...args: string[]): string {
  return execFileSync('docker', args, { encoding: 'utf8', timeout: 30_000, stdio: ['ignore', 'pipe', 'pipe'] }).trim();
}
let sql: ReturnType<typeof postgres> | undefined;
let boss: PgBoss | undefined;
const result: Record<string, unknown> = { status: 'incomplete', node: process.version, image, container: name,
  volume, sources: [], database: 'NOT_RUN', queue: 'NOT_RUN', model: 'NOT_RUN' };
try {
  let password: string;
  try {
    const stat = await lstat(resolve(dir, 'password'));
    if (!stat.isFile() || stat.isSymbolicLink() || (stat.mode & 0o777) !== 0o600 || stat.uid !== process.getuid!()) throw Error('probe_credentials_unsafe');
    password = await readFile(resolve(dir, 'password'), 'utf8');
  }
  catch (error: any) {
    if (error.code !== 'ENOENT') throw error;
    password = randomBytes(32).toString('hex');
    await writeFile(resolve(dir, 'password'), password, { mode: 0o600, flag: 'wx' });
    await writeFile(resolve(dir, 'postgres.env'), `POSTGRES_PASSWORD=${password}\nPOSTGRES_DB=hot_probe\n`, { mode: 0o600, flag: 'wx' });
  }
  for (const file of ['password', 'postgres.env']) {
    const stat = await lstat(resolve(dir, file));
    if (!stat.isFile() || stat.isSymbolicLink() || (stat.mode & 0o777) !== 0o600 || stat.uid !== process.getuid!()) throw Error('probe_credentials_unsafe');
  }
  const volumes = docker('volume', 'ls', '--filter', `name=${volume}`, '--format', '{{.Name}}').split('\n');
  if (!volumes.includes(volume)) docker('volume', 'create', '--label', 'rwb.hot.probe=6a5d3231', volume);
  const volumeInfo = JSON.parse(docker('volume', 'inspect', volume))[0];
  if (volumeInfo.Labels?.['rwb.hot.probe'] !== '6a5d3231') throw Error('probe_volume_foreign');
  // Exact instance only; an existing container must carry our label and image.
  const existing = docker('ps', '-a', '--filter', `name=^/${name}$`, '--format', '{{.ID}}');
  if (existing) {
    const owned = JSON.parse(docker('inspect', name))[0];
    if (owned.Config.Labels?.['rwb.hot.probe'] !== '6a5d3231' || owned.Config.Image !== image) throw Error('probe_container_foreign');
    if (!owned.Mounts.some((mount: any) => mount.Type === 'volume' && mount.Name === volume && mount.Destination === '/var/lib/postgresql/data')) throw Error('probe_volume_foreign');
    if (!owned.State.Running) docker('start', name);
  } else {
    docker('run', '-d', '--name', name, '--label', 'rwb.hot.probe=6a5d3231',
      '--env-file', resolve(dir, 'postgres.env'), '-p', '127.0.0.1::5432',
      '-v', `${volume}:/var/lib/postgresql/data`, image);
  }
  const container = JSON.parse(docker('inspect', name))[0];
  if (container.NetworkSettings.Ports['5432/tcp'][0].HostIp !== '127.0.0.1') throw Error('probe_database_public');
  const port = Number(container.NetworkSettings.Ports['5432/tcp'][0].HostPort);
  result.port = port;
  sql = postgres({ host: '127.0.0.1', port, database: 'hot_probe', username: 'postgres', password,
    max: 2, connect_timeout: 3, idle_timeout: 5, onnotice: () => {} });
  // Bounded readiness probes on this same owned instance; no restarting on timeout.
  let ready = false;
  for (let attempt = 0; attempt < 15; attempt++) {
    try { await sql`select 1`; ready = true; break; }
    catch { await new Promise(resolve => setTimeout(resolve, 1000)); }
  }
  if (!ready) throw Error('probe_database_not_ready');
  const [version] = await sql`select version()`;
  result.postgres = version.version;
  await sql`create table if not exists probe_material (
    identity text primary key, source text not null, url text not null, hash text not null,
    payload jsonb not null, acquired_at timestamptz not null default now())`;
  const responses = await Promise.all(PROBE_SOURCES.map(async source => {
    const requestStartedAt = new Date();
    try {
      const res = await fetch(source.url, { signal: AbortSignal.timeout(25_000), redirect: 'error',
        headers: { 'User-Agent': 'ResearchWorkbench-Hot/0.1 (bounded local research)', accept: 'application/rss+xml, application/atom+xml, application/xml' } });
      if (!res.ok) throw Error(`http_${res.status}`);
      const reader = res.body!.getReader();
      const chunks: Uint8Array[] = [];
      let size = 0;
      while (true) {
        const next = await reader.read();
        if (next.done) break;
        size += next.value.length;
        if (size > 4_194_304) { await reader.cancel(); throw Error('feed_body_limit'); }
        chunks.push(next.value);
      }
      const raw = Buffer.concat(chunks);
      const seen = new Date();
      await writeFile(resolve(dir, `${source.id}.xml`), raw, { mode: 0o600 });
      const all = parseFeed(raw.toString('utf8'), source.url, seen);
      return { source, all, summary: { id: source.id, operator: source.operator, channel: source.channel,
        official: source.official, status: 'PASS', bytes: raw.length, sha256: sha256(raw),
        count: all.length, timeKnown: all.filter(item => item.publishedAt).length,
        coverage: 'latest_snapshot', requestStartedAt: requestStartedAt.toISOString(), acquiredAt: seen.toISOString() } };
    } catch (error: any) {
      const code = /^http_\d+$|^feed_/.test(error.message) ? error.message : error.name;
      await log('source_failed', { id: source.id, code });
      return { source, all: [], summary: { id: source.id, channel: source.channel, status: 'FAIL', code } };
    }
  }));
  result.sources = responses.map(response => response.summary);
  const selected = responses.find(response => response.all.length)?.all[0];
  const owner = responses.find(response => response.all.length)?.source;
  if (!selected || !owner) throw Error('probe_no_real_material');
  const identity = identityKeyForUrl(selected.url)!;
  const hash = contentHash({ title: selected.title, excerpt: selected.excerpt });
  for (let repeat = 0; repeat < 2; repeat++) {
    await sql`insert into probe_material (identity, source, url, hash, payload)
      values (${identity}, ${owner.id}, ${selected.url}, ${hash}, ${sql.json(selected as any)})
      on conflict (identity) do nothing`;
  }
  const [count] = await sql`select count(*)::int as n from probe_material where identity = ${identity} and hash = ${hash}`;
  if (count.n !== 1) throw Error('probe_identity_duplicate');
  result.database = { status: 'PASS', identityStable: true, rawResponsePersisted: true, materialHash: hash };
  boss = new PgBoss({ host: '127.0.0.1', port, database: 'hot_probe', user: 'postgres', password, schema: 'hot_probe_queue' });
  boss.on('error', () => { void log('queue_error'); });
  await boss.start();
  await boss.createQueue('probe.material', { policy: 'short', retryLimit: 0, expireInSeconds: 60 });
  const job = await boss.send('probe.material', { identity, hash }, { singletonKey: hash });
  if (!job) throw Error('probe_queue_duplicate');
  const jobs = await boss.fetch('probe.material');
  if (jobs.length !== 1 || jobs[0].id !== job) throw Error('probe_queue_claim_failed');
  await boss.complete('probe.material', job, { hash });
  result.queue = { status: 'PASS', jobId: job, mechanism: 'pg-boss@12.34.0' };
  result.status = 'bounded_proof_passed';
  await log('probe_passed');
} catch (error: any) {
  result.error = /^probe_/.test(error.message) ? error.message : String(error.code ?? error.name);
  await log('probe_failed', { code: result.error });
  process.exitCode = 1;
} finally {
  if (boss) {
    try { await boss.stop(); } catch { result.queueShutdown = 'FAIL'; process.exitCode = 1; }
  }
  if (sql) {
    try { await sql.end({ timeout: 5 }); } catch { result.databaseShutdown = 'FAIL'; process.exitCode = 1; }
  }
  await writeFile(resolve(dir, 'receipt.json'), JSON.stringify(result, null, 2), { mode: 0o600 });
  // Print only non-secret fixed receipt fields; raw publisher responses stay local.
  console.log(JSON.stringify(result));
}
