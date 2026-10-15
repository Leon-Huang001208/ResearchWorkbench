CREATE TABLE hot.channel_control_requests (
  request_id uuid PRIMARY KEY,channel_id text NOT NULL REFERENCES hot.channels(id),params_hash text NOT NULL,
  actor text NOT NULL CHECK(actor='local_host'),before_state jsonb NOT NULL,after_state jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TRIGGER immutable_channel_control_requests BEFORE UPDATE OR DELETE ON hot.channel_control_requests FOR EACH ROW EXECUTE FUNCTION hot.immutable_evidence();
