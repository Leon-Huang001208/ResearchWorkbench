CREATE TABLE hot.follows (
  id uuid PRIMARY KEY,kind text NOT NULL CHECK(kind IN ('channel','event','keyword','institution','asset')),
  target text NOT NULL CHECK(length(target) BETWEEN 1 AND 200),
  current_version integer NOT NULL CHECK(current_version>0),UNIQUE(kind,target)
);
CREATE TABLE hot.follow_versions (
  follow_id uuid NOT NULL REFERENCES hot.follows(id),version integer NOT NULL CHECK(version>0),
  config jsonb NOT NULL CHECK(octet_length(config::text)<=2048),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),PRIMARY KEY(follow_id,version)
);
CREATE TABLE hot.follow_requests (
  request_id uuid PRIMARY KEY,follow_id uuid NOT NULL REFERENCES hot.follows(id),
  params_hash text NOT NULL CHECK(params_hash ~ '^[a-f0-9]{64}$'),
  actor text NOT NULL CHECK(actor='local_host'),reason text NOT NULL CHECK(length(reason) BETWEEN 1 AND 1000),
  before_state jsonb NOT NULL,after_state jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TRIGGER immutable_follow_versions BEFORE UPDATE OR DELETE ON hot.follow_versions FOR EACH ROW EXECUTE FUNCTION hot.immutable_evidence();
CREATE TRIGGER immutable_follow_requests BEFORE UPDATE OR DELETE ON hot.follow_requests FOR EACH ROW EXECUTE FUNCTION hot.immutable_evidence();
