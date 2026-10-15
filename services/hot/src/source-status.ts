/** Read-only catalog eligibility; never changes configuration or starts collection. */
import type postgres from 'postgres';
import type {PublicSource} from './collection.ts';
import {schemaName} from './config.ts';
type Sql=ReturnType<typeof postgres>;
export async function catalogControlReady(db:Sql,schema:string){
  schemaName(schema);
  const [row]=await db`select has_column_privilege(current_user,${`${schema}.sources`},'config','UPDATE') allowed`;
  return row?.allowed===true;
}
export function sourceEligibility(row:{id:string;operator:string;enabled:boolean;adapter:string|null;catalog_id:string|null},catalog:PublicSource[],permission:boolean){
  const match=catalog.some(source=>source.id===row.id&&source.operator===row.operator);
  const bound=match&&row.adapter==='public_feed'&&row.catalog_id===row.id;
  return {collection_state:!match?'catalog_mismatch':!bound?'awaiting_catalog':row.enabled?'scheduled':'paused',
    catalog_activation_allowed:permission&&match&&['public_feed','frozen_acceptance_subset'].includes(row.adapter??''),
    catalog_activation_code:permission?null:'hot_source_catalog_permission_missing'};
}
