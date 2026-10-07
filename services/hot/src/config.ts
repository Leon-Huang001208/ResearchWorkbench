/** Non-secret settings only. The authorized Host resolves secretRef separately. */
import type postgres from 'postgres';
import { isIP } from 'node:net';

export interface DatabaseConfig {
  mode: 'managed' | 'external'; host: string; port: number; name: string;
  schema: string; user: string; secretRef: string; controllerUser: string; controllerSecretRef: string;
  tls: 'disable' | 'verify-full'; poolMax: number;
}
export interface HotConfig {
  version: 1; enabled: boolean; timezone: string; database: DatabaseConfig;
  collection: { frequencySeconds: number; maxItems: number; backfillDays: number };
  worker: { concurrency: number; leaseSeconds: number; maxRetries: number };
  budget: { maxCallsPerDay: number; maxTokensPerDay: number; maxCostPerDay: number };
  retention: { days: number; backupDirectory: string };
}

function object(value: unknown, keys: string[]): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw Error('hot_config_invalid');
  const row = value as Record<string, unknown>;
  if (Object.keys(row).some(key => !keys.includes(key))) throw Error('hot_config_unknown_field');
  return row;
}
function bounded(value: unknown, fallback: number, minimum: number, maximum: number, integer = true): number {
  const number = value === undefined ? fallback : value;
  if (typeof number !== 'number' || !Number.isFinite(number) || number < minimum || number > maximum || (integer && !Number.isInteger(number))) throw Error('hot_config_invalid');
  return number;
}
function word(value: unknown, fallback: string, pattern: RegExp): string {
  const text = value === undefined ? fallback : value;
  if (typeof text !== 'string' || !pattern.test(text)) throw Error('hot_config_invalid');
  return text;
}
function hostName(value: unknown): string {
  const host = value === undefined ? '127.0.0.1' : value;
  if (typeof host !== 'string' || host.length > 253 || (!isIP(host) && !/^[a-zA-Z0-9][a-zA-Z0-9.\-]*$/.test(host))) throw Error('hot_database_host_invalid');
  return host;
}
export function schemaName(value: string): string {
  if (!/^[a-z][a-z0-9_]{0,47}$/.test(value) || value === 'public' || value.startsWith('pg_') || value === 'information_schema') throw Error('hot_schema_invalid');
  return value;
}
export function assertNodeRuntime(version = process.versions.node): void {
  const match = /^(\d+)\.(\d+)\.(\d+)$/.exec(version);
  if (!match || Number(match[1]) !== 24 || Number(match[2]) < 11) throw Error('hot_node_version_unsupported');
}

export function parseConfig(input: unknown): HotConfig {
  const row = object(input, ['version','enabled','timezone','database','collection','worker','budget','retention']);
  if (row.enabled !== undefined && typeof row.enabled !== 'boolean') throw Error('hot_config_invalid');
  if (row.version !== undefined && row.version !== 1) throw Error('hot_config_version_invalid');
  const timezone = word(row.timezone, 'Asia/Shanghai', /^[A-Za-z_]+(?:\/[A-Za-z0-9_+\-]+)*$/);
  try { new Intl.DateTimeFormat('en', { timeZone: timezone }); } catch { throw Error('hot_timezone_invalid'); }
  const db = object(row.database ?? {}, ['mode','host','port','name','schema','user','secretRef','controllerUser','controllerSecretRef','tls','poolMax']);
  const mode = word(db.mode, 'managed', /^(managed|external)$/) as DatabaseConfig['mode'];
  const tls = word(db.tls, mode === 'managed' ? 'disable' : 'verify-full', /^(disable|verify-full)$/) as DatabaseConfig['tls'];
  const host = hostName(db.host);
  // Managed service identity is checked separately; external connections verify TLS.
  if (mode === 'managed' && !['127.0.0.1','localhost','::1','rwb-hot-db'].includes(host)) throw Error('hot_managed_host_invalid');
  if (mode === 'external' && tls !== 'verify-full' && !['127.0.0.1','localhost','::1'].includes(host)) throw Error('hot_external_tls_required');
  const collection = object(row.collection ?? {}, ['frequencySeconds','maxItems','backfillDays']);
  const worker = object(row.worker ?? {}, ['concurrency','leaseSeconds','maxRetries']);
  const budget = object(row.budget ?? {}, ['maxCallsPerDay','maxTokensPerDay','maxCostPerDay']);
  const retention = object(row.retention ?? {}, ['days','backupDirectory']);
  const backupDirectory = word(retention.backupDirectory, 'hot/backups', /^[a-zA-Z0-9_\-]+(?:\/[a-zA-Z0-9_\-]+)*$/);
  if((db.user??'rwb_hot_worker')===(db.controllerUser??'rwb_hot_controller'))throw Error('hot_database_roles_overlap');
  return { version: 1, enabled: row.enabled === true, timezone,
    database: { mode, host,
      port: bounded(db.port, 55432, 1, 65535), name: word(db.name, 'rwb_hot', /^[a-zA-Z][a-zA-Z0-9_]{0,62}$/),
      schema: schemaName(word(db.schema, 'hot', /^[a-z][a-z0-9_]{0,47}$/)),
      user: word(db.user, 'rwb_hot_worker', /^[a-zA-Z][a-zA-Z0-9_]{0,62}$/),
      secretRef: word(db.secretRef, 'hot-database', /^[a-z][a-z0-9_\-]{0,63}$/),
      controllerUser: word(db.controllerUser, 'rwb_hot_controller', /^[a-zA-Z][a-zA-Z0-9_]{0,62}$/),
      controllerSecretRef: word(db.controllerSecretRef, 'hot-controller-database', /^[a-z][a-z0-9_\-]{0,63}$/),
      tls, poolMax: bounded(db.poolMax, 4, 1, 16) },
    collection: { frequencySeconds: bounded(collection.frequencySeconds, 600, 60, 86400), maxItems: bounded(collection.maxItems, 200, 1, 2000), backfillDays: bounded(collection.backfillDays, 30, 0, 3650) },
    worker: { concurrency: bounded(worker.concurrency, 2, 1, 8), leaseSeconds: bounded(worker.leaseSeconds, 120, 10, 1800), maxRetries: bounded(worker.maxRetries, 3, 0, 10) },
    budget: { maxCallsPerDay: bounded(budget.maxCallsPerDay, 0, 0, 10000), maxTokensPerDay: bounded(budget.maxTokensPerDay, 0, 0, 10_000_000), maxCostPerDay: bounded(budget.maxCostPerDay, 0, 0, 10000, false) },
    retention: { days: bounded(retention.days, 365, 1, 36500), backupDirectory } };
}

export function poolOptions(config: DatabaseConfig, password: string): postgres.Options<{}> {
  if (!password || password.length > 4096) throw Error('hot_database_secret_missing');
  return { host: config.host, port: config.port, database: config.name, username: config.user, password,
    ssl: config.tls === 'verify-full' ? { rejectUnauthorized: true } : false,
    max: config.poolMax, connect_timeout: 5, idle_timeout: 30, onnotice: () => {},
    connection: { application_name: 'rwb-hot', statement_timeout: 15000, lock_timeout: 5000 } };
}
