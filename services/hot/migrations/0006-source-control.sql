ALTER TABLE hot.sources ADD COLUMN frequency_seconds integer CHECK(frequency_seconds BETWEEN 60 AND 86400);
ALTER TABLE hot.sources ADD COLUMN config_revision bigint NOT NULL DEFAULT 0;
CREATE TABLE hot.source_control_requests (
  request_id uuid PRIMARY KEY,
  source_id text NOT NULL REFERENCES hot.sources(id),
  params_hash text NOT NULL CHECK(length(params_hash)=64),
  generation bigint NOT NULL,
  actor text NOT NULL CHECK(actor='local_host'),
  before_state jsonb NOT NULL,
  after_state jsonb NOT NULL,
  applied_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TRIGGER immutable_source_controls BEFORE UPDATE OR DELETE ON hot.source_control_requests
FOR EACH ROW EXECUTE FUNCTION hot.immutable_evidence();
