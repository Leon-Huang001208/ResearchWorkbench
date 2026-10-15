-- Deterministic one-shot report identity; immutable evidence, no model or second scheduler.
CREATE TABLE hot.periodic_report_executions (
  run_id uuid PRIMARY KEY REFERENCES hot.periodic_runs(id),
  execution_id text UNIQUE NOT NULL CHECK(execution_id ~ '^[a-f0-9]{64}$'),
  brief_id uuid NOT NULL, brief_version integer NOT NULL,
  input_hash text NOT NULL CHECK(input_hash ~ '^[a-f0-9]{64}$'),
  renderer text NOT NULL CHECK(renderer='rwb-report-documents-v1'),
  markdown text NOT NULL CHECK(octet_length(markdown)<=4000000),
  markdown_hash text NOT NULL CHECK(markdown_hash ~ '^[a-f0-9]{64}$'),
  docx bytea NOT NULL CHECK(octet_length(docx) BETWEEN 1 AND 5242880),
  docx_hash text NOT NULL CHECK(docx_hash ~ '^[a-f0-9]{64}$'),
  completed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  FOREIGN KEY(brief_id,brief_version) REFERENCES hot.brief_versions(brief_id,version)
);
CREATE TRIGGER immutable_periodic_reports BEFORE UPDATE OR DELETE ON hot.periodic_report_executions
  FOR EACH ROW EXECUTE FUNCTION hot.immutable_evidence();
