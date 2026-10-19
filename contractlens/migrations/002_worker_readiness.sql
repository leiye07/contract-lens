ALTER TABLE runtime_health ADD COLUMN IF NOT EXISTS execution_ready boolean NOT NULL DEFAULT false;
INSERT INTO schema_migrations(version) VALUES(2) ON CONFLICT DO NOTHING;
