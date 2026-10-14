/** Stage-one minimum recovery rehearsal on the exact stage-zero owned instance. */
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { execFileSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import postgres from 'postgres';
import { sha256 } from '../src/material.ts';

const dir = resolve(import.meta.dirname, '../../../logs/hot-stage-zero');
const receipt = JSON.parse(await readFile(resolve(dir, 'receipt.json'), 'utf8'));
const name = 'rwb-hot-probe-6a5d3231';
const owned = JSON.parse(execFileSync('docker', ['inspect', name], { encoding: 'utf8', timeout: 10_000 }))[0];
if (owned.Config.Labels?.['rwb.hot.probe'] !== '6a5d3231' || owned.Config.Image !== receipt.image) throw Error('probe_container_foreign');
const mounts = owned.Mounts.filter((mount: any) => mount.Destination === '/var/lib/postgresql/data');
if (mounts.length !== 1 || mounts[0].Type !== 'volume' || mounts[0].Name !== `${name}-data`) throw Error('probe_volume_foreign');
const volumeInfo = JSON.parse(execFileSync('docker', ['volume', 'inspect', `${name}-data`], { encoding: 'utf8', timeout: 10_000 }))[0];
if (volumeInfo.Labels?.['rwb.hot.probe'] !== '6a5d3231') throw Error('probe_volume_foreign');
if (owned.NetworkSettings.Ports['5432/tcp'][0].HostIp !== '127.0.0.1' || Number(owned.NetworkSettings.Ports['5432/tcp'][0].HostPort) !== receipt.port) throw Error('probe_database_identity_mismatch');
const backupDir = resolve(dir, `recovery-${randomBytes(5).toString('hex')}`);
await mkdir(backupDir, { mode: 0o700 });
const password = await readFile(resolve(dir, 'password'), 'utf8');
const options = { host: '127.0.0.1', port: receipt.port, username: 'postgres', password,
  max: 1, connect_timeout: 3, onnotice: () => {} };
const source = postgres({ ...options, database: 'hot_probe' });
let target: ReturnType<typeof postgres> | undefined;
const database = `hot_restored_${randomBytes(5).toString('hex')}`;
const outcome: Record<string, unknown> = { status: 'FAIL', scope: 'stage_one_hot_schema_only', research: 'NOT_RUN', restoredDatabase: database };
async function inventory(db: ReturnType<typeof postgres>) {
  const tables = await db`select tablename from pg_tables where schemaname='hot' order by tablename`;
  const content: Record<string, unknown[]> = {};
  for (const { tablename } of tables) {
    const rows = await db`select to_jsonb(t) as data from hot.${db(tablename)} as t order by to_jsonb(t)::text`;
    // enabled is the sole permitted restore delta and is independently checked below.
    content[tablename] = rows.map(row => {
      if (tablename === 'sources') delete row.data.enabled;
      return row.data;
    });
  }
  const [schema] = await db`select max(version)::int as version from hot.migrations`;
  return { schemaVersion: schema.version, tables: Object.fromEntries(Object.entries(content).map(([name, rows]) => [name, rows.length])),
    sha256: sha256(JSON.stringify(content)) };
}
try {
  const before = await inventory(source);
  const dump = execFileSync('docker', ['exec', name, 'pg_dump', '-U', 'postgres', '-d', 'hot_probe', '--schema=hot', '--format=custom'], { timeout: 30_000, maxBuffer: 20_000_000 });
  await writeFile(resolve(backupDir, 'hot.dump'), dump, { mode: 0o600, flag: 'wx' });
  await source.unsafe(`CREATE DATABASE ${database}`);
  execFileSync('docker', ['exec', '-i', name, 'pg_restore', '-U', 'postgres', '-d', database, '--exit-on-error'], { input: dump, timeout: 30_000, stdio: ['pipe', 'pipe', 'pipe'] });
  target = postgres({ ...options, database });
  await target`update hot.sources set enabled=false`;
  const after = await inventory(target);
  if (before.sha256 !== after.sha256) throw Error('probe_recovery_mismatch');
  const [paused] = await target`select count(*)::int n from hot.sources where enabled=true`;
  if (paused.n !== 0) throw Error('probe_restored_not_paused');
  Object.assign(outcome, { status: 'PASS', archiveSha256: sha256(dump), before, after,
    collectionPaused: true, schemaVersion: after.schemaVersion });
} catch (error: any) {
  outcome.error = /^probe_/.test(error.message) ? error.message : error.code ?? error.name;
  process.exitCode = 1;
} finally {
  if (target) await target.end({ timeout: 5 });
  await source.end({ timeout: 5 });
  await writeFile(resolve(backupDir, 'manifest.json'), JSON.stringify(outcome, null, 2), { mode: 0o600 });
  console.log(JSON.stringify(outcome));
}
