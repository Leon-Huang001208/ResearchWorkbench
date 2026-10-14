CREATE TABLE hot.queue_binding (
  singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
  schema_name text NOT NULL UNIQUE,
  instance_id uuid NOT NULL,
  engine text NOT NULL,
  provisioned boolean NOT NULL DEFAULT false
);
