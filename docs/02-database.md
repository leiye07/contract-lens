# PostgreSQL design

ContractLens owns a separate database; never query or migrate EnergyOps or showroom domain tables. SQL migration: contractlens/migrations/001_initial.sql. Migration marker and transactional advisory lock serialize initialization.

| Table | Purpose / keys |
|---|---|
| schema_migrations | Applied numeric schema revision. |
| packages | Immutable corpus ID and canonical manifest hash; public fictional label. |
| documents | Composite package/document key, version, body, SHA256 and availability. Missing expected schedules have available=false. |
| clauses | Composite package/clause key; document FK, section, exact text, character offsets and searchable generated tsvector. GIN index. |
| clause_links | Package-scoped typed source/target references; target can be missing and is resolved explicitly. |
| scenarios | Fixed question, package FK, public checklist, revision and private reference-evidence set. Private labels never leave evaluator. |
| executions | Stable UUID, fingerprint, scenario FK, lifecycle, configuration/version manifest, timestamps, cancellation flag, result/evaluation JSONB and next_seq. |
| runtime_health | Singleton worker heartbeat and execution_ready flag; migration 002 adds readiness. |
| evidence_events | (execution_id,seq) primary key, kind, optional observed lifecycle status, timestamp, sanitized JSONB. Ordered transactionally. |

Plans, tool invocations, context manifests, ledger additions and model usage are append-only typed events rather than separate tables. Final report and evaluation reports are atomically stored with terminal transition; no second mutable source of truth. Citations contain immutable clause/document references, quote and character offsets. Private history is scoped by the integration credential and further isolated by showroom authorization.

FTS is clause-level PostgreSQL English text search, not embeddings. Canonical package ingestion compares hashes on conflict and refuses silent mutation. New document text requires a new package revision. Reference labels can change only through a scenario/evaluator revision. DB connection/query timeouts prevent unconstrained reads. No private documents are stored in this public demo.

Lifecycle: created→queued; queued→running/cancelled/failed/timed_out; running→succeeded/failed/cancelled/timed_out. Terminal states cannot reopen. Each transition holds the execution row lock and appends an event in the same transaction. Controller restart marks stale running executions failed/interrupted; it does not resume an LLM transcript or retry paid calls.

Showroom migration 002 only adds artifact kind and negotiated artifact contract version. Application/scenario registries and availability become per-integration. Existing forecast rows retain kind=forecast and all existing lifecycle/evidence semantics.
