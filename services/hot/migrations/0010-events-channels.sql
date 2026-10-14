CREATE TABLE hot.channels (id text PRIMARY KEY,current_version integer NOT NULL DEFAULT 0);
CREATE TABLE hot.channel_versions (
  channel_id text NOT NULL REFERENCES hot.channels(id),version integer NOT NULL,
  config jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY(channel_id,version)
);
CREATE TABLE hot.events (id uuid PRIMARY KEY,current_revision integer NOT NULL DEFAULT 0);
CREATE TABLE hot.event_versions (
  event_id uuid NOT NULL REFERENCES hot.events(id),revision integer NOT NULL,
  snapshot jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY(event_id,revision)
);
CREATE TABLE hot.event_materials (
  event_id uuid NOT NULL,event_revision integer NOT NULL,material_id uuid NOT NULL,material_revision integer NOT NULL,
  relation text NOT NULL CHECK(relation IN ('same_occurrence','composite')),
  PRIMARY KEY(event_id,event_revision,material_id,material_revision),
  FOREIGN KEY(event_id,event_revision) REFERENCES hot.event_versions(event_id,revision),
  FOREIGN KEY(material_id,material_revision) REFERENCES hot.material_versions(material_id,revision)
);
CREATE TABLE hot.event_links (
  event_id uuid NOT NULL,event_revision integer NOT NULL,target_id uuid NOT NULL REFERENCES hot.events(id),
  relation text NOT NULL CHECK(relation IN ('direct_followup','related','pending_review')),
  PRIMARY KEY(event_id,event_revision,target_id),
  FOREIGN KEY(event_id,event_revision) REFERENCES hot.event_versions(event_id,revision),
  CHECK(event_id<>target_id)
);
CREATE TABLE hot.event_corrections (
  request_id uuid PRIMARY KEY,params_hash text NOT NULL,actor text NOT NULL CHECK(actor='local_host'),
  reason text NOT NULL,before_state jsonb NOT NULL,after_state jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE hot.channel_judgments (
  id uuid PRIMARY KEY,event_id uuid NOT NULL,event_revision integer NOT NULL,channel_id text NOT NULL,channel_version integer NOT NULL,
  input_hash text NOT NULL,authority text NOT NULL CHECK(authority IN ('rule','model','human')),judgment jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  model_attempt_id uuid REFERENCES hot.model_receipts(attempt_id),
  CHECK((authority='model')=(model_attempt_id IS NOT NULL)),
  UNIQUE(event_id,event_revision,channel_id,channel_version,input_hash),
  FOREIGN KEY(event_id,event_revision) REFERENCES hot.event_versions(event_id,revision),
  FOREIGN KEY(channel_id,channel_version) REFERENCES hot.channel_versions(channel_id,version)
);
CREATE TRIGGER immutable_channel_versions BEFORE UPDATE OR DELETE ON hot.channel_versions FOR EACH ROW EXECUTE FUNCTION hot.immutable_evidence();
CREATE TRIGGER immutable_event_versions BEFORE UPDATE OR DELETE ON hot.event_versions FOR EACH ROW EXECUTE FUNCTION hot.immutable_evidence();
CREATE TRIGGER immutable_event_materials BEFORE UPDATE OR DELETE ON hot.event_materials FOR EACH ROW EXECUTE FUNCTION hot.immutable_evidence();
CREATE TRIGGER immutable_event_links BEFORE UPDATE OR DELETE ON hot.event_links FOR EACH ROW EXECUTE FUNCTION hot.immutable_evidence();
CREATE TRIGGER immutable_event_corrections BEFORE UPDATE OR DELETE ON hot.event_corrections FOR EACH ROW EXECUTE FUNCTION hot.immutable_evidence();
CREATE TRIGGER immutable_channel_judgments BEFORE UPDATE OR DELETE ON hot.channel_judgments FOR EACH ROW EXECUTE FUNCTION hot.immutable_evidence();
CREATE FUNCTION hot.authorize_human_judgment() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.authority='human' AND NOT has_table_privilege(current_user,TG_TABLE_SCHEMA||'.event_corrections','INSERT') THEN
    RAISE EXCEPTION 'hot_event_control_denied';
  END IF;
  IF NEW.authority='model' AND NOT EXISTS (
    SELECT 1 FROM hot.model_receipts r JOIN hot.model_results m ON m.attempt_id=r.attempt_id
    WHERE r.attempt_id=NEW.model_attempt_id AND m.result_key=NEW.input_hash
      AND r.response->>'rejected' IS DISTINCT FROM 'true'
      AND (r.response->>'text')::jsonb=NEW.judgment
  ) THEN
    RAISE EXCEPTION 'hot_channel_model_receipt_invalid';
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER authorize_human_judgment BEFORE INSERT ON hot.channel_judgments FOR EACH ROW EXECUTE FUNCTION hot.authorize_human_judgment();
