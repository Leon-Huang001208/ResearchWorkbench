CREATE TABLE hot.channel_rule_evidence (
  judgment_id uuid PRIMARY KEY REFERENCES hot.channel_judgments(id),
  algorithm_version text NOT NULL,input_hash text NOT NULL,
  observed_at timestamptz NOT NULL,source_context_hash text NOT NULL,
  details jsonb NOT NULL
);
CREATE TRIGGER immutable_channel_rule_evidence BEFORE UPDATE OR DELETE ON hot.channel_rule_evidence FOR EACH ROW EXECUTE FUNCTION hot.immutable_evidence();
CREATE TABLE hot.channel_rule_cursor (
  singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
  after_key text NOT NULL DEFAULT ''
);
INSERT INTO hot.channel_rule_cursor(singleton) VALUES(true);
