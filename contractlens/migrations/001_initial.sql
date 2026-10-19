CREATE TABLE IF NOT EXISTS schema_migrations(version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS packages(id text PRIMARY KEY, sha256 text NOT NULL, name text NOT NULL);
CREATE TABLE IF NOT EXISTS documents(
 package_id text NOT NULL REFERENCES packages(id), id text NOT NULL, title text NOT NULL, version text NOT NULL,
 available boolean NOT NULL, body text NOT NULL, sha256 text NOT NULL, PRIMARY KEY(package_id,id)
);
CREATE TABLE IF NOT EXISTS clauses(
 package_id text NOT NULL, id text NOT NULL, document_id text NOT NULL, section text NOT NULL, title text NOT NULL,
 body text NOT NULL, char_start integer NOT NULL, char_end integer NOT NULL,
 search_vector tsvector GENERATED ALWAYS AS (to_tsvector('english',title || ' ' || body)) STORED,
 PRIMARY KEY(package_id,id), FOREIGN KEY(package_id,document_id) REFERENCES documents(package_id,id),
 CHECK(char_start>=0 AND char_end>char_start)
);
CREATE INDEX IF NOT EXISTS clause_search ON clauses USING GIN(search_vector);
CREATE TABLE IF NOT EXISTS clause_links(
 package_id text NOT NULL, source_id text NOT NULL, target_id text NOT NULL, kind text NOT NULL,
 PRIMARY KEY(package_id,source_id,target_id,kind), FOREIGN KEY(package_id,source_id) REFERENCES clauses(package_id,id)
);
CREATE TABLE IF NOT EXISTS scenarios(
 id text PRIMARY KEY, package_id text NOT NULL REFERENCES packages(id), question text NOT NULL,
 checklist jsonb NOT NULL, revision text NOT NULL, reference_evidence jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS executions(
 id uuid PRIMARY KEY, fingerprint text NOT NULL, scenario_id text NOT NULL REFERENCES scenarios(id),
 status text NOT NULL CHECK(status IN ('created','queued','running','succeeded','failed','cancelled','timed_out')),
 created_at timestamptz NOT NULL DEFAULT now(), started_at timestamptz, completed_at timestamptz,
 cancel_requested boolean NOT NULL DEFAULT false, configuration jsonb NOT NULL, versions jsonb NOT NULL,
 result jsonb, evaluations jsonb NOT NULL DEFAULT '[]', failure_code text, next_seq integer NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS execution_queue ON executions(created_at) WHERE status='queued';
CREATE TABLE IF NOT EXISTS evidence_events(
 execution_id uuid NOT NULL REFERENCES executions(id), seq integer NOT NULL, occurred_at timestamptz NOT NULL DEFAULT now(),
 kind text NOT NULL, status text, data jsonb NOT NULL, PRIMARY KEY(execution_id,seq)
);
INSERT INTO schema_migrations(version) VALUES(1) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS runtime_health(id text PRIMARY KEY,last_seen timestamptz NOT NULL DEFAULT now());
