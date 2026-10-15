CREATE TABLE hot.runtime_identity (
  singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
  instance_id uuid NOT NULL UNIQUE,
  controller_token_hash text NOT NULL CHECK (length(controller_token_hash)=64),
  mode text NOT NULL DEFAULT 'native' CHECK (mode IN ('native','docker')),
  generation bigint NOT NULL DEFAULT 0,
  paused boolean NOT NULL DEFAULT true,
  owner_until timestamptz
);
-- Commit fences and reusable outcomes, not a second queue: pg-boss owns job state.
CREATE TABLE hot.job_claims (
  input_key text PRIMARY KEY,
  job_id uuid NOT NULL,
  attempt integer NOT NULL DEFAULT 0,
  lease_token uuid,
  worker_id uuid,
  generation bigint,
  lease_until timestamptz,
  state text NOT NULL DEFAULT 'vacant' CHECK (state IN ('vacant','running','completed','failed')),
  result jsonb,
  completed_at timestamptz
);
CREATE TABLE hot.job_attempts (
  input_key text NOT NULL REFERENCES hot.job_claims(input_key),
  attempt integer NOT NULL,
  job_id uuid NOT NULL,
  worker_id uuid NOT NULL,
  lease_token uuid NOT NULL UNIQUE,
  generation bigint NOT NULL,
  started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  finished_at timestamptz,
  outcome text NOT NULL DEFAULT 'running' CHECK(outcome IN ('running','completed','expired','superseded','failed')),
  PRIMARY KEY(input_key,attempt)
);
