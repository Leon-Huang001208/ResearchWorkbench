/** Single migration and ingestion owner. Callers pass an authorized pooled connection. */
import type postgres from 'postgres';
import { readFile } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
import { sha256, contentHash, identityKeyForUrl } from './material.ts';
import type { FeedMaterial } from './feed.ts';
import { logEvent } from './log.ts';
import { schemaName } from './config.ts';

type Sql = ReturnType<typeof postgres>;
type Tx = postgres.TransactionSql;
export const SCHEMA_VERSION = 20;
type Page = { source: string; raw: string; acquiredAt: Date; materials: FeedMaterial[];
  cursor: Record<string, postgres.JSONValue>; metadata?: Record<string, postgres.JSONValue>; existingPageId?: string };

function safeError(error: unknown, fallback: string): Error {
  if (error instanceof Error && /^hot_[a-z_]+$/.test(error.message)) return error;
  return Error(fallback);
}

function materialVersionHash(item: FeedMaterial): string {
  return sha256([contentHash(item), item.publishedRaw, item.updatedRaw,
    item.publishedAt?.toISOString() ?? '', item.sourceUpdatedAt?.toISOString() ?? ''].join('\u0001'));
}

export async function migrate(db: Sql, schema = 'hot'): Promise<void> {
  schemaName(schema);
  try {
  await db.begin(async tx => {
    // Same schema migration lock across connections and execution modes.
    await tx`select pg_advisory_xact_lock(714278901)`;
    await tx`select pg_advisory_xact_lock(hashtextextended(${schema},231501))`;
    await tx`create schema if not exists ${tx(schema)}`;
    const [existing] = await tx`select to_regclass(${`${schema}.migrations`}) as migration_table,
      (select count(*)::int from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname=${schema}) as relation_count,
      (select count(*)::int from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname=${schema}) as function_count,
      (select nspowner=(select oid from pg_roles where rolname=current_user) from pg_namespace where nspname=${schema}) as owned`;
    if (!existing.migration_table && (!existing.owned || existing.relation_count > 0 || existing.function_count > 0)) throw Error('hot_schema_not_empty');
    const [runtimeTable]=await tx`select to_regclass(${`${schema}.runtime_identity`}) as name`;
    if(runtimeTable.name){
      const [live]=await tx`select not paused and owner_until>clock_timestamp() as active from ${tx(schema)}.runtime_identity where singleton`;
      if(live?.active)throw Error('hot_migration_requires_stopped');
    }
    await tx`create table if not exists ${tx(schema)}.migrations (version integer primary key, checksum text not null, applied_at timestamptz not null default now())`;
    for (const [version, file] of [[1, '0001-materials.sql'], [2, '0002-acquisition-watermark.sql'], [3, '0003-runtime-fences.sql'], [4, '0004-queue-binding.sql'], [5,'0005-collection-inbox.sql'],[6,'0006-source-control.sql'],[7,'0007-model-budget.sql'],[8,'0008-provider-receipt-id.sql'],[9,'0009-model-daily-admission.sql'],[10,'0010-events-channels.sql'],[11,'0011-material-processing.sql'],[12,'0012-channel-rule-evidence.sql'],[13,'0013-channel-control.sql'],[14,'0014-model-controls.sql'],[15,'0015-brief-versions.sql'],[16,'0016-research-runs.sql'],[17,'0017-research-model-calls.sql'],[18,'0018-model-token-amendment.sql'],[19,'0019-follows.sql'],[20,'0020-periodic-briefs.sql']] as const) {
    const raw = await readFile(new URL(`../migrations/${file}`, import.meta.url), 'utf8');
    const checksum = sha256(raw);
    const rows = await tx`select checksum from ${tx(schema)}.migrations where version=${version}`;
    if (rows.length) {
      if (rows[0].checksum !== checksum) throw Error('hot_migration_checksum_changed');
      continue;
    }
    // Only the exact migration namespace is substituted; schemaName rejects SQL syntax.
    await tx.unsafe(raw.replace(/\bhot\./g, `"${schema}".`));
    await tx`insert into ${tx(schema)}.migrations (version, checksum) values (${version}, ${checksum})`;
    }
  });
  logEvent('migration_ready');
  } catch (error) {
    logEvent('migration_failed');
    throw safeError(error, 'hot_migration_failed');
  }
}

export async function ingestPage(db: Sql | Tx, page: Page, schema = 'hot'): Promise<{ materialIds: string[]; newVersions: number }> {
  schemaName(schema);
  try {
  if (!Number.isFinite(page.acquiredAt.getTime()) || Buffer.byteLength(page.raw) > 4_194_304 || page.materials.length > 2000) {
    throw Error('hot_page_invalid');
  }
  const operation = async (tx: Tx) => {
    const sources = await tx`select id,last_success_at from ${tx(schema)}.sources where id=${page.source} for update`;
    if (!sources.length) throw Error('hot_source_unknown');
    if (sources[0].last_success_at && page.acquiredAt < sources[0].last_success_at) throw Error('hot_page_obsolete');
    const pageId = page.existingPageId ?? randomUUID();
    const dates = page.materials.map(item => item.publishedAt).filter((date): date is Date => date !== null).sort((a, b) => a.getTime() - b.getTime());
    if(page.existingPageId){
      const rows=await tx`select id from ${tx(schema)}.raw_pages where id=${pageId} and source_id=${page.source}
        and body_hash=${sha256(page.raw)} and acquired_at=${page.acquiredAt}`;
      if(rows.length!==1)throw Error('hot_raw_page_mismatch');
    }else await tx`insert into ${tx(schema)}.raw_pages (id, source_id, body, body_hash, acquired_at, metadata, coverage, oldest_published_at, newest_published_at, parsed_count)
      values (${pageId}, ${page.source}, ${Buffer.from(page.raw)}, ${sha256(page.raw)}, ${page.acquiredAt},
      ${tx.json(page.metadata ?? {})}, 'latest_snapshot', ${dates[0] ?? null}, ${dates.at(-1) ?? null}, ${page.materials.length})`;
    const materialIds: string[] = [];
    let newVersions = 0;
    // Lock material identities in stable order to avoid cross-source deadlock.
    const items = page.materials.map(item => ({ item, identity: identityKeyForUrl(item.url) }));
    if (items.some(({ identity }) => !identity)) throw Error('hot_material_url_invalid');
    items.sort((a, b) => a.identity!.localeCompare(b.identity!));
    const pageHashes = new Map<string, string>();
    for (const { item, identity } of items) {
      const hash = materialVersionHash(item);
      if (pageHashes.has(identity!) && pageHashes.get(identity!) !== hash) throw Error('hot_page_identity_conflict');
      pageHashes.set(identity!, hash);
    }
    const idsByIdentity = new Map<string, string>();
    for (const { item, identity } of items) {
      await tx`insert into ${tx(schema)}.materials (id, identity, original_url, first_seen_at,last_acquired_at)
        values (${randomUUID()}, ${identity!}, ${item.url}, ${page.acquiredAt}, ${page.acquiredAt}) on conflict(identity) do nothing`;
      const [material] = await tx`select id, current_revision, first_seen_at,last_acquired_at from ${tx(schema)}.materials where identity=${identity!} for update`;
      if (page.acquiredAt < material.last_acquired_at) throw Error('hot_acquisition_order_invalid');
      const existing = await tx`select content_hash, acquired_at from ${tx(schema)}.material_versions where material_id=${material.id} and revision=${material.current_revision}`;
      if (existing.length && page.acquiredAt < existing[0].acquired_at) throw Error('hot_acquisition_order_invalid');
      // Timestamp corrections affect the immutable version too.
      const hash = materialVersionHash(item);
      let revision = material.current_revision;
      if (!existing.length || existing[0].content_hash !== hash) {
        revision++;
        await tx`insert into ${tx(schema)}.material_versions (material_id, revision, content_hash, title, excerpt, acquired_at,
          published_at, published_raw, source_updated_at, source_updated_raw, raw_page_id)
          values (${material.id}, ${revision}, ${hash}, ${item.title}, ${item.excerpt}, ${page.acquiredAt},
          ${item.publishedAt}, ${item.publishedRaw}, ${item.sourceUpdatedAt}, ${item.updatedRaw}, ${pageId})`;
        await tx`update ${tx(schema)}.materials set current_revision=${revision} where id=${material.id}`;
        newVersions++;
      }
      await tx`insert into ${tx(schema)}.discoveries (source_id, material_id, page_id, upstream_id, revision)
        values (${page.source}, ${material.id}, ${pageId}, ${item.upstreamId}, ${revision}) on conflict do nothing`;
      idsByIdentity.set(identity!, material.id);
      await tx`update ${tx(schema)}.materials set last_acquired_at=${page.acquiredAt} where id=${material.id}`;
    }
    for (const item of page.materials) materialIds.push(idsByIdentity.get(identityKeyForUrl(item.url)!)!);
    // Publication of raw bytes, every entry, discoveries and watermark is one commit.
    await tx`update ${tx(schema)}.sources set cursor=${tx.json(page.cursor)}, last_success_at=${page.acquiredAt}, last_error_code=null where id=${page.source}`;
    return { materialIds, newVersions };
  };
  const result = 'begin' in db ? await db.begin(operation) : await db.savepoint(operation);
  logEvent('page_committed', page.materials.length);
  return result;
  } catch (error) {
    logEvent('ingest_failed');
    throw safeError(error, 'hot_ingest_failed');
  }
}

export async function versionsAt(db: Sql, ids: string[], cutoff: Date, schema = 'hot'): Promise<any[]> {
  schemaName(schema);
  if (!Number.isFinite(cutoff.getTime()) || ids.length > 200) throw Error('hot_asof_invalid');
  if (ids.length === 0) return [];
  return db`select distinct on (material_id) * from ${db(schema)}.material_versions
    where material_id in ${db(ids)} and acquired_at <= ${cutoff}
    order by material_id, acquired_at desc, revision desc`;
}
