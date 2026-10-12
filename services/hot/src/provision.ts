/** Called only with migration-owner privileges; never exposed as an Agent SQL tool. */
import type postgres from 'postgres';
import { schemaName } from './config.ts';

type Sql = ReturnType<typeof postgres>;
export const WORKER_TABLES = ['raw_pages','materials','material_versions','discoveries','job_claims','job_attempts','material_inbox','collection_runs','model_attempts','model_receipts','model_results','events','event_versions','event_materials','event_links','channel_judgments','processing_items','processing_results','channel_rule_evidence'] as const;
export const SOURCE_WRITE_COLUMNS = ['cursor','last_success_at','last_error_code','next_due_at','schedule_sequence','consecutive_failures'] as const;
export const WORKER_UPDATES: Record<string, string[]> = {
  materials: ['current_revision','last_acquired_at'],
  job_claims: ['job_id','attempt','lease_token','worker_id','generation','lease_until','state','result','completed_at'],
  job_attempts: ['finished_at','outcome']
  ,material_inbox:['processed'],collection_runs:['finished_at','state','error_code','raw_page_id','item_count'],
  model_budgets:['charged_calls','charged_tokens','charged_cost_micros','paused'],model_attempts:['state','dispatched_at','finished_at','day_key'],events:['current_revision'],
  processing_items:['state','packet','packet_hash','result_key','error_code','finished_at'],channel_rule_cursor:['after_key']
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
    await tx`grant update(cursor,last_success_at,last_error_code,next_due_at,schedule_sequence,consecutive_failures) on ${tx(schema)}.sources to ${tx(role)}`;
    await tx`grant update(processed) on ${tx(schema)}.material_inbox to ${tx(role)}`;
    await tx`grant update(finished_at,state,error_code,raw_page_id,item_count) on ${tx(schema)}.collection_runs to ${tx(role)}`;
    await tx`grant update(charged_calls,charged_tokens,charged_cost_micros,paused) on ${tx(schema)}.model_budgets to ${tx(role)}`;
    await tx`grant update(state,dispatched_at,finished_at,day_key) on ${tx(schema)}.model_attempts to ${tx(role)}`;
    await tx`grant update(current_revision) on ${tx(schema)}.events to ${tx(role)}`;
    await tx`grant update(after_key) on ${tx(schema)}.channel_rule_cursor to ${tx(role)}`;
    await tx`grant update(state,packet,packet_hash,result_key,error_code,finished_at) on ${tx(schema)}.processing_items to ${tx(role)}`;
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
  await db`grant delete on ${db(schema)}.job_dependency to ${db(role)}`;
  await db`grant update(monitor_backoff_on) on ${db(schema)}.version to ${db(role)}`;
  await db`grant update(enabled,frequency_seconds,config_revision) on ${db(schema)}.sources to ${db(role)}`;
  await db`grant insert on ${db(schema)}.source_control_requests to ${db(role)}`;
  await db`grant insert on ${db(schema)}.channels,${db(schema)}.channel_versions,${db(schema)}.event_corrections,${db(schema)}.channel_control_requests to ${db(role)}`;
  await db`grant update(current_version) on ${db(schema)}.channels to ${db(role)}`;
  await db`grant insert on ${db(schema)}.briefs,${db(schema)}.brief_versions,${db(schema)}.brief_requests to ${db(role)}`;
  await db`grant update(current_version) on ${db(schema)}.briefs to ${db(role)}`;
  await db`grant insert on ${db(schema)}.research_inputs,${db(schema)}.research_runs,${db(schema)}.research_operations to ${db(role)}`;
  await db`grant insert on ${db(schema)}.research_model_calls to ${db(role)}`;
  await db`grant update(revision,state,dataset_id,dataset_manifest_hash,delivery_key,report_run_id,error_code,updated_at) on ${db(schema)}.research_runs to ${db(role)}`;
}
