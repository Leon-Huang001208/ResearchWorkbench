CREATE TABLE hot.processing_items (
  material_id uuid NOT NULL,material_revision integer NOT NULL,prompt_version text NOT NULL,
  state text NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','ready','applied','blocked_budget','outcome_unknown','rejected','stale')),
  packet jsonb,packet_hash text,result_key text REFERENCES hot.model_results(result_key),error_code text,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),finished_at timestamptz,
  PRIMARY KEY(material_id,material_revision,prompt_version),
  FOREIGN KEY(material_id,material_revision) REFERENCES hot.material_versions(material_id,revision),
  CHECK((packet IS NULL)=(packet_hash IS NULL))
);
CREATE FUNCTION hot.freeze_processing_packet() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.packet IS NOT NULL AND (NEW.packet IS DISTINCT FROM OLD.packet OR NEW.packet_hash IS DISTINCT FROM OLD.packet_hash) THEN
    RAISE EXCEPTION 'hot_processing_packet_immutable';
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER freeze_processing_packet BEFORE UPDATE ON hot.processing_items FOR EACH ROW EXECUTE FUNCTION hot.freeze_processing_packet();
CREATE TABLE hot.processing_results (
  material_id uuid NOT NULL,material_revision integer NOT NULL,prompt_version text NOT NULL,
  result_key text NOT NULL REFERENCES hot.model_results(result_key),decision jsonb NOT NULL,event_ids uuid[] NOT NULL,
  applied_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY(material_id,material_revision,prompt_version),
  FOREIGN KEY(material_id,material_revision,prompt_version) REFERENCES hot.processing_items(material_id,material_revision,prompt_version)
);
CREATE TRIGGER immutable_processing_results BEFORE UPDATE OR DELETE ON hot.processing_results FOR EACH ROW EXECUTE FUNCTION hot.immutable_evidence();
