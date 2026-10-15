-- Research uses the existing cumulative model ledger, with immutable call ownership.
CREATE TABLE hot.research_model_calls (
  id uuid PRIMARY KEY,run_id uuid NOT NULL REFERENCES hot.research_inputs(id),
  attempt_id uuid NOT NULL UNIQUE REFERENCES hot.model_attempts(id),
  params_hash text NOT NULL CHECK(params_hash ~ '^[a-f0-9]{64}$'),
  request_hash text NOT NULL CHECK(request_hash ~ '^[a-f0-9]{64}$'),
  provider text NOT NULL CHECK(provider='deepseek-official'),model text NOT NULL,
  input_token_bound integer NOT NULL CHECK(input_token_bound BETWEEN 1 AND 1000000),
  max_output_tokens integer NOT NULL CHECK(max_output_tokens BETWEEN 1 AND 4096),
  tariff_hash text NOT NULL CHECK(tariff_hash ~ '^[a-f0-9]{64}$'),tariff jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX research_model_calls_run ON hot.research_model_calls(run_id,created_at);
CREATE TRIGGER immutable_research_model_calls BEFORE UPDATE OR DELETE ON hot.research_model_calls FOR EACH ROW EXECUTE FUNCTION hot.immutable_evidence();
