CREATE TABLE hot.periodic_plans (
  id uuid PRIMARY KEY,current_version integer NOT NULL CHECK(current_version>0),
  next_due_at timestamptz NOT NULL
);
CREATE TABLE hot.periodic_plan_versions (
  plan_id uuid NOT NULL REFERENCES hot.periodic_plans(id),version integer NOT NULL CHECK(version>0),
  config jsonb NOT NULL CHECK(octet_length(config::text)<=4096),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),PRIMARY KEY(plan_id,version)
);
CREATE TABLE hot.periodic_plan_requests (
  request_id uuid PRIMARY KEY,plan_id uuid NOT NULL REFERENCES hot.periodic_plans(id),
  params_hash text NOT NULL CHECK(params_hash ~ '^[a-f0-9]{64}$'),
  actor text NOT NULL CHECK(actor='local_host'),reason text NOT NULL CHECK(length(reason) BETWEEN 1 AND 1000),
  before_state jsonb NOT NULL,after_state jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE hot.periodic_runs (
  id uuid PRIMARY KEY,plan_id uuid NOT NULL,plan_version integer NOT NULL,
  due_at timestamptz NOT NULL,brief_id uuid NOT NULL,request_id uuid NOT NULL,
  config jsonb NOT NULL,missed_periods integer NOT NULL CHECK(missed_periods>=0),
  state text NOT NULL CHECK(state IN ('queued','completed','empty','cancelled','failed')),
  error_code text,brief_version integer,content_hash text,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),finished_at timestamptz,
  UNIQUE(plan_id,plan_version,due_at),
  FOREIGN KEY(plan_id,plan_version) REFERENCES hot.periodic_plan_versions(plan_id,version),
  FOREIGN KEY(brief_id,brief_version) REFERENCES hot.brief_versions(brief_id,version),
  CHECK(content_hash IS NULL OR content_hash ~ '^[a-f0-9]{64}$')
);
CREATE TABLE hot.periodic_selections (
  run_id uuid PRIMARY KEY REFERENCES hot.periodic_runs(id),selection jsonb NOT NULL CHECK(octet_length(selection::text)<=4096),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TRIGGER immutable_periodic_versions BEFORE UPDATE OR DELETE ON hot.periodic_plan_versions FOR EACH ROW EXECUTE FUNCTION hot.immutable_evidence();
CREATE TRIGGER immutable_periodic_requests BEFORE UPDATE OR DELETE ON hot.periodic_plan_requests FOR EACH ROW EXECUTE FUNCTION hot.immutable_evidence();
CREATE TRIGGER immutable_periodic_selections BEFORE UPDATE OR DELETE ON hot.periodic_selections FOR EACH ROW EXECUTE FUNCTION hot.immutable_evidence();
CREATE FUNCTION hot.immutable_periodic_inputs() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF ROW(NEW.id,NEW.plan_id,NEW.plan_version,NEW.due_at,NEW.brief_id,NEW.request_id,NEW.config,NEW.missed_periods,NEW.created_at)
     IS DISTINCT FROM ROW(OLD.id,OLD.plan_id,OLD.plan_version,OLD.due_at,OLD.brief_id,OLD.request_id,OLD.config,OLD.missed_periods,OLD.created_at)
  THEN RAISE EXCEPTION 'hot_immutable_evidence'; END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER immutable_periodic_inputs BEFORE UPDATE ON hot.periodic_runs FOR EACH ROW EXECUTE FUNCTION hot.immutable_periodic_inputs();
ALTER TABLE hot.brief_requests DROP CONSTRAINT brief_requests_actor_check;
ALTER TABLE hot.brief_requests ADD CONSTRAINT brief_requests_actor_check CHECK(actor IN ('local_host','hot_scheduler'));
