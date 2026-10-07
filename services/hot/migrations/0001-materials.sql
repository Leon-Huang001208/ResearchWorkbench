-- Hot owns its schema. Existing RWB Store and research state are not migrated.
CREATE TABLE hot.sources (
  id text PRIMARY KEY,
  operator text NOT NULL,
  config jsonb NOT NULL,
  cursor jsonb,
  last_success_at timestamptz,
  last_error_code text,
  enabled boolean NOT NULL DEFAULT true
);
CREATE TABLE hot.raw_pages (
  id uuid PRIMARY KEY,
  source_id text NOT NULL REFERENCES hot.sources(id),
  body bytea NOT NULL,
  body_hash text NOT NULL,
  acquired_at timestamptz NOT NULL,
  metadata jsonb NOT NULL,
  coverage text NOT NULL CHECK (coverage IN ('latest_snapshot','partial','verified_source_range','unknown')),
  oldest_published_at timestamptz,
  newest_published_at timestamptz,
  parsed_count integer NOT NULL,
  gap jsonb
);
CREATE TABLE hot.materials (
  id uuid PRIMARY KEY,
  identity text NOT NULL UNIQUE,
  original_url text NOT NULL,
  first_seen_at timestamptz NOT NULL,
  current_revision integer NOT NULL DEFAULT 0
);
CREATE TABLE hot.material_versions (
  material_id uuid NOT NULL REFERENCES hot.materials(id),
  revision integer NOT NULL,
  content_hash text NOT NULL,
  title text NOT NULL,
  excerpt text NOT NULL,
  acquired_at timestamptz NOT NULL,
  published_at timestamptz,
  published_raw text NOT NULL,
  source_updated_at timestamptz,
  source_updated_raw text NOT NULL,
  raw_page_id uuid NOT NULL REFERENCES hot.raw_pages(id),
  state text NOT NULL DEFAULT 'active' CHECK (state IN ('active','corrected','retracted')),
  PRIMARY KEY(material_id, revision)
);
CREATE TABLE hot.discoveries (
  source_id text NOT NULL REFERENCES hot.sources(id),
  material_id uuid NOT NULL REFERENCES hot.materials(id),
  page_id uuid NOT NULL REFERENCES hot.raw_pages(id),
  upstream_id text,
  revision integer NOT NULL,
  PRIMARY KEY(source_id, material_id, page_id),
  FOREIGN KEY(material_id, revision) REFERENCES hot.material_versions(material_id, revision)
);
CREATE INDEX hot_material_asof ON hot.material_versions(material_id, acquired_at DESC, revision DESC);
CREATE FUNCTION hot.immutable_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'hot_immutable_evidence';
END
$$;
CREATE TRIGGER immutable_versions BEFORE UPDATE OR DELETE ON hot.material_versions
FOR EACH ROW EXECUTE FUNCTION hot.immutable_evidence();
CREATE TRIGGER immutable_pages BEFORE UPDATE OR DELETE ON hot.raw_pages
FOR EACH ROW EXECUTE FUNCTION hot.immutable_evidence();
