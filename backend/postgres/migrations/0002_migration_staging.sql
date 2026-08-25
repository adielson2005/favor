-- Additive staging area for the offline MongoDB -> PostgreSQL migration worker.
-- This preserves every source document losslessly before canonical table mapping.
CREATE TABLE IF NOT EXISTS migration_staging (
  migration_run_id uuid NOT NULL REFERENCES migration_runs(id) ON DELETE CASCADE,
  collection_name text NOT NULL,
  legacy_id text NOT NULL,
  source_hash char(64) NOT NULL,
  payload jsonb NOT NULL,
  source_created_at timestamptz,
  staged_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (migration_run_id, collection_name, legacy_id)
);
CREATE INDEX IF NOT EXISTS migration_staging_collection_idx
  ON migration_staging(migration_run_id, collection_name);
