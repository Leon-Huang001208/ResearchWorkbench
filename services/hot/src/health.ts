import postgres from 'postgres';
import type { HotConfig } from './config.ts';
import { poolOptions, schemaName } from './config.ts';
import { logEvent } from './log.ts';
import { SCHEMA_VERSION } from './database.ts';
import { WORKER_TABLES, SOURCE_WRITE_COLUMNS, WORKER_UPDATES } from './provision.ts';

export interface DatabaseHealth { state: 'disabled' | 'unconfigured' | 'ready' | 'migration_required' | 'permission_denied' | 'unavailable';
  code?: string; schemaVersion?: number; postgresMajor?: number; durationMs: number }

export async function checkDatabase(config: HotConfig, resolveSecret: (ref: string) => Promise<string | null>): Promise<DatabaseHealth> {
  const started = performance.now();
  const finish = (result: Omit<DatabaseHealth, 'durationMs'>): DatabaseHealth => ({ ...result, durationMs: Math.round(performance.now() - started) });
  if (!config.enabled) return finish({ state: 'disabled' });
  let db: ReturnType<typeof postgres> | undefined;
  try {
    const password = await resolveSecret(config.database.secretRef);
    if (!password) return finish({ state: 'unconfigured', code: 'hot_database_secret_missing' });
    schemaName(config.database.schema);
    db = postgres(poolOptions(config.database, password));
    const [role] = await db`select r.rolsuper, r.rolcreatedb, r.rolcreaterole,
      exists(select 1 from pg_roles privileged where (privileged.rolsuper or privileged.rolcreatedb or privileged.rolcreaterole)
        and pg_has_role(current_user,privileged.oid,'SET')) as elevated,
      current_setting('server_version_num')::int as version from pg_roles r where r.rolname=current_user`;
    if (role.rolsuper || role.rolcreatedb || role.rolcreaterole || role.elevated) return finish({ state: 'permission_denied', code: 'hot_database_role_not_scoped' });
    if (Math.floor(role.version / 10000) !== 17) return finish({ state: 'unavailable', code: 'hot_postgres_version_unsupported' });
    const [namespace] = await db`select to_regnamespace(${config.database.schema}) as name`;
    if (!namespace.name) return finish({ state: 'migration_required', code: 'hot_migration_required' });
    const [permission] = await db`select has_schema_privilege(current_user,${config.database.schema},'USAGE') as allowed`;
    if (!permission.allowed) return finish({ state: 'permission_denied', code: 'hot_database_role_not_scoped' });
    const [relation] = await db`select to_regclass(${`${config.database.schema}.migrations`}) as name`;
    if (!relation.name) return finish({ state: 'migration_required', code: 'hot_migration_required' });
    const [migration] = await db`select max(version)::int as version from ${db(config.database.schema)}.migrations`;
    if (migration.version !== SCHEMA_VERSION) return finish({ state: 'migration_required', code: 'hot_migration_required', schemaVersion: migration.version ?? 0 });
    for (const table of WORKER_TABLES) {
      const [dml] = await db`select has_table_privilege(current_user,${`${config.database.schema}.${table}`},'INSERT')
        and has_table_privilege(current_user,${`${config.database.schema}.${table}`},'SELECT') as allowed`;
      if (!dml.allowed) return finish({ state: 'permission_denied', code: 'hot_database_write_permission_missing' });
    }
    for (const column of SOURCE_WRITE_COLUMNS) {
      const [dml] = await db`select has_column_privilege(current_user,${`${config.database.schema}.sources`},${column},'UPDATE') as allowed`;
      if (!dml.allowed) return finish({ state: 'permission_denied', code: 'hot_database_write_permission_missing' });
    }
    for (const [table, column] of Object.entries(WORKER_UPDATES).flatMap(([table, columns]) => columns.map(column => [table,column]))) {
      const [dml] = await db`select has_column_privilege(current_user,${`${config.database.schema}.${table}`},${column},'UPDATE') as allowed`;
      if (!dml.allowed) return finish({ state: 'permission_denied', code: 'hot_database_write_permission_missing' });
    }
    const [scope] = await db`select has_schema_privilege(current_user,${config.database.schema},'CREATE')
      or has_database_privilege(current_user,current_database(),'CREATE')
      or has_table_privilege(current_user,${`${config.database.schema}.runtime_identity`},'UPDATE') as excessive`;
    if (scope.excessive) return finish({ state: 'permission_denied', code: 'hot_database_role_not_scoped' });
    for (const table of ['sources','runtime_identity','migrations','queue_binding']) {
      const [read] = await db`select has_table_privilege(current_user,${`${config.database.schema}.${table}`},'SELECT') as allowed`;
      if (!read.allowed) return finish({ state: 'permission_denied', code: 'hot_database_read_permission_missing' });
    }
    const queueSchema = config.database.schema;
    const [queue] = await db`select to_regnamespace(${queueSchema}) as name`;
    if (!queue.name) return finish({ state: 'migration_required', code: 'hot_queue_not_provisioned' });
    const bound = await db`select singleton from ${db(config.database.schema)}.queue_binding where singleton and provisioned and schema_name=${queueSchema} and engine='pg-boss@12.34.0'`;
    if (bound.length !== 1) return finish({ state: 'migration_required', code: 'hot_queue_not_provisioned' });
    const [queueAccess] = await db`select has_schema_privilege(current_user,${queueSchema},'USAGE')
      and has_table_privilege(current_user,${`${queueSchema}.queue`},'SELECT')
      and has_table_privilege(current_user,${`${queueSchema}.queue`},'UPDATE')
      and has_table_privilege(current_user,${`${queueSchema}.version`},'SELECT') as allowed`;
    if (!queueAccess.allowed) return finish({ state: 'permission_denied', code: 'hot_queue_permission_missing' });
    for (const table of ['job','job_common']) {
      const [dml] = await db`select has_table_privilege(current_user,${`${queueSchema}.${table}`},'SELECT')
        and has_table_privilege(current_user,${`${queueSchema}.${table}`},'INSERT')
        and has_table_privilege(current_user,${`${queueSchema}.${table}`},'UPDATE') as allowed`;
      if (!dml.allowed) return finish({ state: 'permission_denied', code: 'hot_queue_permission_missing' });
    }
    return finish({ state: 'ready', schemaVersion: migration.version, postgresMajor: 17 });
  } catch {
    logEvent('database_check_failed');
    return finish({ state: 'unavailable', code: 'hot_database_unavailable' });
  } finally {
    if (db) await db.end({ timeout: 5 });
  }
}
