# Integration API contract v1.1

Transport: JSON over private HTTP; fixed configured service origin; no redirects. Authorization: Bearer scoped demo token, unrelated to EnergyOps operator token. Body limit 4096 bytes. All request/response objects are validated; structured tool outputs have independent byte limits. OpenAPI and JSON Schema are exported to docs/contracts/ by scripts/export_contracts.py.

| Method / path | Behavior |
|---|---|
| GET /healthz | Process liveness; no credentials. |
| GET /readyz | Database/schema readiness. |
| GET /demo/v1/capabilities | application_id=contractlens, integration_version=1.1, scenario IDs, supported evidence/artifact versions, cancellation and execution readiness. |
| GET /demo/v1/scenarios | Approved questions, package IDs, public checklists and available-document metadata; no reference answers. |
| GET /demo/v1/packages/{id} | Curated public package manifest and exact clauses; no evaluator labels. Available with scoped integration auth. |
| POST /demo/v1/executions | {id: UUID, scenario_id: approved ID}; 202. Same request/id is idempotent; changed request for same ID=409. Unconfigured model=503; full quota=429. |
| GET /demo/v1/executions/{id} | Recorded state and bounded complete event history, report if completed, persisted evaluations and safe failure code. Unknown=404. |
| POST /demo/v1/executions/{id}/cancel | queued→cancelled immediately; running→request flag until controller confirms termination. Terminal state unchanged. |

Scenario IDs: termination-complete, termination-missing-schedule, termination-conflicting-amendments. Visitors cannot pass a package URL, model name, tool configuration, prompt or arbitrary question. Scenario selection maps deterministically to a frozen fictional package.

Event envelope: seq>=1, occurred_at aware UTC timestamp, kind, optional status for state_transition, and data. Kinds: state_transition, plan_recorded, tool_called, tool_completed, context_assembled, model_completed, ledger_recorded, validation_rejected and evaluation_recorded. Each event is actual execution evidence, not an inferred internal step. Source seq is authoritative; showroom assigns its own durable presentation seq and retains source IDs.

Report v1.0: artifact_type=contract_report; question; conclusion_status; findings[{claim,citations[{clause_id,quote,document_id,document_version,document_sha256,char_start,char_end}]}]; conditions[]; gaps[]; review_questions[]; package_id/package_sha256; evidence_ledger; source_clauses[]; plans[]; model_usage; version manifest. Claim support remains unevaluated unless independent semantic evaluation is configured.

Evaluations preserve id, category, status, evaluator/version/configuration, metrics, provenance and reason. Citation checks, evidence coverage, operational usage and private-reference retrieval coverage are separate from semantic/legal correctness. Unknown is a real state. Errors never return provider exception strings or credentials.

Showroom submission stays /api/v1/runs with application_id plus scenario_id. ContractLens artifact/event capabilities are additive; existing EnergyOps v1.0 continues working. Plan/text/source payloads pass a strict typed ContractLens normalizer before visitor presentation. Every private output still requires session and run capability. Generic API OpenAPI reflects the expanded allowlist; no unrestricted application execution is introduced.
