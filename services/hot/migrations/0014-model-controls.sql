ALTER TABLE hot.model_attempts DROP CONSTRAINT model_attempts_state_check;
ALTER TABLE hot.model_attempts ADD CONSTRAINT model_attempts_state_check
CHECK(state IN ('reserved','dispatching','outcome_unknown','received','cancelled','abandoned'));
DROP INDEX hot.hot_model_pending_key;
CREATE UNIQUE INDEX hot_model_pending_key ON hot.model_attempts(result_key)
WHERE state IN ('reserved','dispatching','outcome_unknown','abandoned');
CREATE FUNCTION hot.guard_model_abandonment() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='UPDATE' THEN
    IF NEW.state IS DISTINCT FROM OLD.state AND NOT (
      (OLD.state='reserved' AND NEW.state IN ('dispatching','cancelled')) OR
      (OLD.state='dispatching' AND NEW.state IN ('outcome_unknown','received','abandoned')) OR
      (OLD.state='outcome_unknown' AND NEW.state IN ('received','abandoned')) OR
      (OLD.state='abandoned' AND NEW.state='received')
    ) THEN RAISE EXCEPTION 'hot_model_state_transition_denied'; END IF;
    IF NEW.day_key IS DISTINCT FROM OLD.day_key AND OLD.state<>'reserved' THEN
      RAISE EXCEPTION 'hot_model_dispatched_day_immutable';
    END IF;
    IF NEW.state='received' AND OLD.state<>'received' AND NOT EXISTS (
      SELECT 1 FROM hot.model_receipts WHERE attempt_id=OLD.id
    ) THEN RAISE EXCEPTION 'hot_model_receipt_required'; END IF;
  END IF;
  IF NEW.state='abandoned' AND NOT has_schema_privilege(current_user,TG_TABLE_SCHEMA,'CREATE') THEN
    RAISE EXCEPTION 'hot_model_control_denied';
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER guard_model_abandonment BEFORE INSERT OR UPDATE ON hot.model_attempts
FOR EACH ROW EXECUTE FUNCTION hot.guard_model_abandonment();
CREATE TABLE hot.model_control_requests (
  request_id uuid PRIMARY KEY,
  operation text NOT NULL CHECK(operation IN ('authorize','terminate')),
  input_hash text NOT NULL CHECK(length(input_hash)=64),
  operator text NOT NULL,reason text NOT NULL,
  before_state jsonb,after_state jsonb NOT NULL,
  response jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TRIGGER immutable_model_control_requests BEFORE UPDATE OR DELETE ON hot.model_control_requests
FOR EACH ROW EXECUTE FUNCTION hot.immutable_evidence();
