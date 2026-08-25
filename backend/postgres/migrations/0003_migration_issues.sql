-- Canonical-import safety controls. A non-empty blocking issue list prevents cutover.
CREATE TABLE IF NOT EXISTS migration_issues (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  migration_run_id uuid NOT NULL REFERENCES migration_runs(id) ON DELETE CASCADE,
  severity text NOT NULL CHECK(severity IN ('INFO','WARNING','BLOCKING')),
  collection_name text NOT NULL,
  legacy_id text,
  code text NOT NULL,
  detail jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  resolved_at timestamptz
);
CREATE INDEX IF NOT EXISTS migration_issues_open_idx
  ON migration_issues(migration_run_id,severity) WHERE resolved_at IS NULL;
