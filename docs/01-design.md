# ContractLens — design v1

Status: implementation specification. System 2 of Agent Sandbox; an independent single-agent contract-evidence runtime. It is not a multi-agent team, a legal advice service, or an EnergyOps extension.

## Vertical scope

A visitor selects a fixed question and a curated fictional contract package, starts a bounded execution, watches actual model/tool events, and receives cited findings, qualifications and gaps. The first question is: "Can the customer terminate early, and what payments or obligations remain?" Three presets cover a complete package, a missing fee schedule and conflicting amendments. No visitor uploads, free-form system prompts, external legal search or operational actions are enabled.

The independent runtime owns its PostgreSQL database, corpus, retrieval, model calls, tool execution, working memory, outputs and graders. Agent Sandbox owns anonymous visitor sessions, capabilities, quotas and normalized evidence. It calls ContractLens's scoped /demo/v1 integration over HTTP. Existing EnergyOps behavior and API remain compatible.

## Single-agent loop

Validate admission → queue → worker starts a bounded process → model chooses tools → deterministic validation and tool execution → observation enters context → model updates plan/evidence ledger → more retrieval or final structured answer → citation/coverage evaluation → persist terminal result.

The model chooses queries, references to inspect, plans and findings. Deterministic code enforces scenario/role access, tool schemas, package scoping, limits, citation integrity, observed-evidence provenance, event sequencing and lifecycle. Tools cannot access other packages or arbitrary network/file locations. Plans and ledger entries are model-produced public task artifacts; private reasoning is neither requested nor displayed.

## Source and context design

Sources are authored fictional agreements in structured JSON: clause IDs, document IDs, titles, exact text, sections and typed references. Canonical per-document text and character offsets are generated during immutable ingestion. Package, document, prompt, tool and runtime hashes accompany each run. Page numbers are unavailable for this JSON corpus and are not invented.

Initial context is the approved question and checklist, not the entire contract. Each read returns exact text plus references. Search uses PostgreSQL full-text ranking, with explicit lexical fallback. Embeddings/semantic search and PDF/OCR ingestion are deferred rather than claimed. Context manifests record actual tool-result evidence, byte counts and prompt hash. A hard request/context byte ceiling and per-turn output limit prevent uncontrolled growth; no invisible model-based compaction is performed in v1.

Working memory is a per-run, append-only evidence ledger. Each entry cites clauses that this run actually read. No cross-run lessons or shared legal facts are learned. Model history and provider message IDs are runtime-private; sanitized plans, calls, context metadata and ledger entries are visitor-visible.

## Output and evaluation

A structured report includes conclusion status (supported, qualified, conflicting, insufficient_evidence), findings with exact cited quotations, conditions, gaps and human review questions. Citations resolve to clause IDs/document versions/character offsets within the selected package and must have been observed by the agent. Citation validation proves source existence/quotation integrity, not legal entailment.

Persist distinct deterministic citation checks, public-checklist coverage checks, operational usage and reference-case retrieval coverage. Reference evidence sets are runtime-private test/evaluation data and are never passed to the acting model. Semantic/legal correctness remains unknown without a qualified reviewer or independently configured calibrated grader. A run may complete with failed evaluation; never infer evaluation passed from HTTP success.

## Reliability and public boundaries

A distinct 32+ character scoped integration token protects demo execution/history. No model credentials reach the showroom. Start is idempotent on UUID and immutable request fingerprint; incompatible reuse returns 409. Global admission: four active, sixty/hour. Default model execution disabled until explicit model name, mounted provider key and worker readiness exist. No synthetic model fallback exists in production.

A single application-owned controller holds a PostgreSQL advisory lock, claims queued runs, launches the fixed inference module and enforces a 120-second deadline with an independent process timer. Cancellation kills that fixed child and records terminal evidence after confirmation. Restarts fail interrupted runs without automatic model reruns. Provider requests have bounded timeouts and no automatic retries; ambiguous paid calls are not blindly repeated. Model usage is provider-reported; monetary cost is unavailable without a versioned price table.

Public documents are fixed fictional data. Retrieved instructions are untrusted source text. Invalid tool requests become recorded errors with bounded recovery; unknown executable tools, arbitrary URLs, unrestricted files and cross-package reads are rejected. Source text can contain an explicit injection test without being promoted to system instructions. Renderer uses React text, not raw HTML. The token authorizes a trusted sandbox integration; visitors require sandbox session plus short-lived run capability for private evidence.

## Provider choice and deferred work

The first provider boundary uses the documented Anthropic Messages tool-use protocol through httpx. The operator selects an explicit CONTRACTLENS_MODEL and mounted key; no moving model alias is silently selected. The provider is replaceable behind a small interface. All provider tests use explicit test doubles and are not live agent demonstrations.

Deferred: uploads/OCR, embeddings, jurisdiction-specific law, drafting/redlines, enforceability decisions, persistent learning, independent semantic judge, multi-agent roles and checkpoint resume. No real provider run can be verified without configured credentials. Docker startup is separately verified only where an engine exists.

## Acceptance

Design/schema/contracts precede implementation. Required checks include corpus offset/hash integrity, reference resolution, missing/conflicting document behavior, schema and tool access validation, citation provenance, event persistence/order, lifecycle/idempotency/cancellation/timeouts/restart, evaluation status, provider protocol, sandbox isolation and UI navigation. One actual configured model run is the final integration gate; fixtures do not satisfy it.

## Implementation references

- Anthropic tool-use lifecycle: https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls
- PostgreSQL text-search controls: https://www.postgresql.org/docs/17/textsearch-controls.html
