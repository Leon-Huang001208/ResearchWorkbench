-- Immutable input/reserved target identity precedes any ResearchService/DSH side effect.
CREATE TABLE hot.research_inputs (
  id uuid PRIMARY KEY,request_id uuid NOT NULL UNIQUE,params_hash text NOT NULL CHECK(params_hash ~ '^[a-f0-9]{64}$'),
  brief_id uuid NOT NULL,brief_version integer NOT NULL,material_ids jsonb NOT NULL,
  target_mode text NOT NULL CHECK(target_mode IN ('fingpt','claw')),session_id uuid NOT NULL UNIQUE,
  manifest_body bytea NOT NULL CHECK(octet_length(manifest_body)<=700000),manifest_hash text NOT NULL CHECK(manifest_hash ~ '^[a-f0-9]{64}$'),
  actor text NOT NULL CHECK(actor='local_host'),created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  FOREIGN KEY(brief_id,brief_version) REFERENCES hot.brief_versions(brief_id,version),
  CHECK(jsonb_typeof(material_ids)='array' AND jsonb_array_length(material_ids) BETWEEN 1 AND 20)
);
CREATE TABLE hot.research_runs (
  id uuid PRIMARY KEY REFERENCES hot.research_inputs(id),revision integer NOT NULL DEFAULT 1 CHECK(revision>0),
  state text NOT NULL DEFAULT 'prepared' CHECK(state IN ('prepared','session_creating','session_outcome_unknown','session_ready',
    'snapshot_ready','execution_starting','execution_outcome_unknown','running','completed','failed','abandoned')),
  dataset_id uuid,dataset_manifest_hash text CHECK(dataset_manifest_hash ~ '^[a-f0-9]{64}$'),
  delivery_key text CHECK(length(delivery_key) BETWEEN 8 AND 128),report_run_id text,
  error_code text CHECK(error_code ~ '^[a-z][a-z0-9_]{0,99}$'),updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  CHECK((dataset_id IS NULL)=(dataset_manifest_hash IS NULL))
);
CREATE TABLE hot.research_operations (
  request_id uuid PRIMARY KEY,run_id uuid NOT NULL REFERENCES hot.research_runs(id),params_hash text NOT NULL CHECK(params_hash ~ '^[a-f0-9]{64}$'),
  before_state text NOT NULL,after_state text NOT NULL,result jsonb NOT NULL,
  actor text NOT NULL CHECK(actor='local_host'),generation bigint NOT NULL,created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TRIGGER immutable_research_inputs BEFORE UPDATE OR DELETE ON hot.research_inputs FOR EACH ROW EXECUTE FUNCTION hot.immutable_evidence();
CREATE TRIGGER immutable_research_operations BEFORE UPDATE OR DELETE ON hot.research_operations FOR EACH ROW EXECUTE FUNCTION hot.immutable_evidence();
