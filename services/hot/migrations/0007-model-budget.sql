CREATE TABLE hot.model_budgets (
  scope_id text PRIMARY KEY,
  authorization_hash text NOT NULL CHECK(length(authorization_hash)=64),
  max_calls integer NOT NULL CHECK(max_calls>=0),
  max_tokens bigint NOT NULL CHECK(max_tokens>=0),
  max_cost_micros bigint NOT NULL CHECK(max_cost_micros>=0),
  charged_calls integer NOT NULL DEFAULT 0 CHECK(charged_calls>=0),
  charged_tokens bigint NOT NULL DEFAULT 0 CHECK(charged_tokens>=0),
  charged_cost_micros bigint NOT NULL DEFAULT 0 CHECK(charged_cost_micros>=0),
  paused boolean NOT NULL DEFAULT false
);
CREATE TABLE hot.model_attempts (
  id uuid PRIMARY KEY,
  scope_id text NOT NULL REFERENCES hot.model_budgets(scope_id),
  result_key text NOT NULL CHECK(length(result_key)=64),
  spec_hash text NOT NULL CHECK(length(spec_hash)=64),
  dispatch_token_hash text NOT NULL CHECK(length(dispatch_token_hash)=64),
  generation bigint NOT NULL,
  max_tokens bigint NOT NULL CHECK(max_tokens>0),
  max_cost_micros bigint NOT NULL CHECK(max_cost_micros>=0),
  state text NOT NULL CHECK(state IN ('reserved','dispatching','outcome_unknown','received','cancelled')),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  dispatched_at timestamptz,
  finished_at timestamptz
);
CREATE UNIQUE INDEX hot_model_pending_key ON hot.model_attempts(result_key)
WHERE state IN ('reserved','dispatching','outcome_unknown');
CREATE TABLE hot.model_receipts (
  attempt_id uuid PRIMARY KEY REFERENCES hot.model_attempts(id),
  response jsonb NOT NULL,
  response_hash text NOT NULL CHECK(length(response_hash)=64),
  tokens bigint NOT NULL CHECK(tokens>=0),
  cost_micros bigint NOT NULL CHECK(cost_micros>=0),
  provider_request_id text NOT NULL,
  received_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE hot.model_results (
  result_key text PRIMARY KEY,
  spec_hash text NOT NULL,
  attempt_id uuid NOT NULL UNIQUE REFERENCES hot.model_receipts(attempt_id)
);
CREATE TRIGGER immutable_model_receipts BEFORE UPDATE OR DELETE ON hot.model_receipts
FOR EACH ROW EXECUTE FUNCTION hot.immutable_evidence();
CREATE TRIGGER immutable_model_results BEFORE UPDATE OR DELETE ON hot.model_results
FOR EACH ROW EXECUTE FUNCTION hot.immutable_evidence();
