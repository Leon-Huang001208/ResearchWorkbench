-- Every successful observation participates in order fencing, even unchanged content.
ALTER TABLE hot.materials ADD COLUMN last_acquired_at timestamptz;
UPDATE hot.materials m SET last_acquired_at = coalesce(
  (SELECT max(p.acquired_at) FROM hot.discoveries d JOIN hot.raw_pages p ON p.id=d.page_id WHERE d.material_id=m.id),
  m.first_seen_at);
ALTER TABLE hot.materials ALTER COLUMN last_acquired_at SET NOT NULL;
