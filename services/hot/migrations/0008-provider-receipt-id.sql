-- The pinned successful DSH stream exposes usage but not the HTTP request id.
-- Unknown provider identity stays NULL rather than a fabricated local UUID.
ALTER TABLE hot.model_receipts ALTER COLUMN provider_request_id DROP NOT NULL;
