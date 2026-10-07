/** Called only with migration-owner privileges; never exposed as an Agent SQL tool. */
import type postgres from 'postgres';
import { schemaName } from './config.ts';

type Sql = ReturnType<typeof postgres>;
export const WORKER_TABLES = ['raw_pages','materials','material_versions','discoveries','job_claims','job_attempts'] as const;
export const SOURCE_WRITE_COLUMNS = ['cursor','last_success_at','last_error_code'] as const;
export const WORKER_UPDATES: Record<string, string[]> = {
  materials: ['current_revision','last_acquired_at'],
  job_claims: ['job_id','attempt','lease_token','worker_id','generation','lease_until','state','result','completed_at'],
  job_attempts: ['finished_at','outcome']
};
export async function grantWorker(db: Sql, schema: string, role: string): Promise<void> {
  schemaName(schema);
  if (!/^[a-zA-Z][a-zA-Z0-9_]{0,62}$/.test(role)) throw Error('hot_role_invalid');
  await db.begin(async tx => {
    const [permission] = await tx`select has_schema_privilege(current_user,${schema},'CREATE') as allowed`;
    if (!permission.allowed) throw Error('hot_provision_denied');
    const roles = await tx`select rolsuper,rolcreatedb,rolcreaterole,
      exists(select 1 from pg_roles privileged where (privileged.rolsuper or privileged.rolcreatedb or privileged.rolcreaterole)
        and pg_has_role(${role},privileged.oid,'SET')) as elevated
      from pg_roles where rolname=${role}`;
    if (roles.length !== 1 || roles[0].rolsuper || roles[0].rolcreatedb || roles[0].rolcreaterole || roles[0].elevated) throw Error('hot_worker_role_not_scoped');
    await tx`grant usage on schema ${tx(schema)} to ${tx(role)}`;
    await tx`grant select on all tables in schema ${tx(schema)} to ${tx(role)}`;
    for (const table of WORKER_TABLES) await tx`grant insert on ${tx(schema)}.${tx(table)} to ${tx(role)}`;
    await tx`grant update(current_revision,last_acquired_at) on ${tx(schema)}.materials to ${tx(role)}`;
    await tx`grant update(cursor,last_success_at,last_error_code) on ${tx(schema)}.sources to ${tx(role)}`;
    await tx`grant update on ${tx(schema)}.job_claims,${tx(schema)}.job_attempts to ${tx(role)}`;
    const queueSchema = schema;
    await tx`grant usage on schema ${tx(queueSchema)} to ${tx(role)}`;
    await tx`grant select on all tables in schema ${tx(queueSchema)} to ${tx(role)}`;
    await tx`grant insert,update,delete on ${tx(queueSchema)}.job,${tx(queueSchema)}.job_common to ${tx(role)}`;
    await tx`grant update on ${tx(queueSchema)}.queue to ${tx(role)}`;
  });
}

export async function grantController(db: Sql, schema: string, role: string): Promise<void> {
  await grantWorker(db,schema,role);
  await db`grant update(mode,generation,paused,owner_until) on ${db(schema)}.runtime_identity to ${db(role)}`;
}
