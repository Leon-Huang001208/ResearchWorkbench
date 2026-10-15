CREATE TABLE hot.briefs (
  id uuid PRIMARY KEY,current_version integer NOT NULL DEFAULT 0 CHECK(current_version>=0)
);
CREATE TABLE hot.brief_versions (
  brief_id uuid NOT NULL REFERENCES hot.briefs(id),version integer NOT NULL CHECK(version>0),
  payload jsonb NOT NULL,content_hash text NOT NULL CHECK(content_hash ~ '^[a-f0-9]{64}$'),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY(brief_id,version),CHECK(octet_length(payload::text)<=524288)
);
CREATE TABLE hot.brief_requests (
  request_id uuid PRIMARY KEY,params_hash text NOT NULL CHECK(params_hash ~ '^[a-f0-9]{64}$'),
  brief_id uuid NOT NULL,version integer NOT NULL,actor text NOT NULL CHECK(actor='local_host'),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  FOREIGN KEY(brief_id,version) REFERENCES hot.brief_versions(brief_id,version)
);
CREATE TRIGGER immutable_brief_versions BEFORE UPDATE OR DELETE ON hot.brief_versions FOR EACH ROW EXECUTE FUNCTION hot.immutable_evidence();
CREATE TRIGGER immutable_brief_requests BEFORE UPDATE OR DELETE ON hot.brief_requests FOR EACH ROW EXECUTE FUNCTION hot.immutable_evidence();
