ALTER TABLE hot.sources ADD COLUMN next_due_at timestamptz;
ALTER TABLE hot.sources ADD COLUMN schedule_sequence bigint NOT NULL DEFAULT 0;
ALTER TABLE hot.sources ADD COLUMN consecutive_failures integer NOT NULL DEFAULT 0;
CREATE TABLE hot.collection_runs (
  id uuid PRIMARY KEY,
  source_id text NOT NULL REFERENCES hot.sources(id),
  generation bigint NOT NULL,
  input_key text NOT NULL REFERENCES hot.job_claims(input_key),
  attempt integer NOT NULL,
  lease_token uuid NOT NULL,
  started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  finished_at timestamptz,
  state text NOT NULL CHECK(state IN ('running','acquired','failed')),
  error_code text,
  raw_page_id uuid REFERENCES hot.raw_pages(id),
  item_count integer NOT NULL DEFAULT 0,
  UNIQUE(input_key,attempt)
);
CREATE TABLE hot.material_inbox (
  page_id uuid NOT NULL REFERENCES hot.raw_pages(id),
  ordinal integer NOT NULL,
  payload jsonb NOT NULL,
  processed boolean NOT NULL DEFAULT false,
  PRIMARY KEY(page_id,ordinal)
);
CREATE FUNCTION hot.inbox_payload_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.page_id IS DISTINCT FROM OLD.page_id OR NEW.ordinal IS DISTINCT FROM OLD.ordinal
     OR NEW.payload IS DISTINCT FROM OLD.payload OR (OLD.processed AND NOT NEW.processed) THEN
    RAISE EXCEPTION 'hot_immutable_inbox';
  END IF;
  RETURN NEW;
END
$$;
CREATE TRIGGER immutable_inbox BEFORE UPDATE ON hot.material_inbox
FOR EACH ROW EXECUTE FUNCTION hot.inbox_payload_immutable();
CREATE INDEX hot_inbox_pending ON hot.material_inbox(page_id,ordinal) WHERE NOT processed;
