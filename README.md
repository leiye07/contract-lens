# ContractLens — System 2 of Agent Sandbox

An independent, bounded single-agent contract-evidence runtime. It investigates one approved termination question against three versioned fictional contract packages. It records actual plans, tool calls, context manifests, an evidence ledger, exact citations and persisted evaluations. It does not provide an enforceability decision or claim independently verified legal advice.

The requested build order is documented in [design](docs/01-design.md), [database design](docs/02-database.md), and [API contract](docs/03-api-contract.md). SQL migrations and exported OpenAPI/JSON Schemas accompany the implementation. See docs/VALIDATION.md for checks actually run and remaining limits.

## Independent startup

Prerequisites: Docker Engine with Compose v2 and Python 3 for the local bootstrap.

```sh
python3 scripts/init_demo.py
docker compose up --build
```

The API listens on laptop loopback http://127.0.0.1:8020. Default model execution is disabled; health and curated-source discovery work with the generated scoped integration credential. The helper never overwrites existing credentials and never prints values. It creates a private secrets directory and read-only secret files readable by the container UID. Keep the containing directory private. The database password in Compose is a documented local development value on a private network, not a production credential.

To enable real execution, provision your Anthropic key into `secrets/anthropic_api_key`, choose an explicit supported `CONTRACTLENS_MODEL` in `.env` using `.env.example`, and set `MODEL_EXECUTION_ENABLED=true`. Do not paste credentials into chat or source control. Only the worker receives the provider key; the API uses worker readiness to admit tasks. No built-in demo/model-output fallback exists. A missing key/model or stale worker heartbeat disables execution.

Production deployment needs private database credentials, TLS at the public boundary, backups and measured admission/resource limits. This task does not publish a live service or modify corerouters.com.

## Connect to Agent Sandbox

ContractLens remains a separate source project and deployment. No agent code is copied into the sandbox.

1. Create the shared private development bridge once: `docker network create --internal showroom-integration`.
2. Start ContractLens independently with `docker compose -f compose.yaml -f compose.integration.yaml up --build -d`.
3. Provision the same scoped `secrets/demo_token` value into sandbox `secrets/contractlens_demo_token`; keep the provider key only in ContractLens.
4. In sandbox set `CONTRACTLENS_URL=http://contractlens-demo:8020` and `CONTRACTLENS_EXECUTION_ENABLED=true`, then start its own Compose plus integration overlay.
5. Open ContractLens from the sandbox catalog. Document browsing is possible with the scoped integration even if the model is disabled. Submission requires downstream model/worker readiness. Choose a fixed scenario, start a run, inspect emitted events, and select a report citation to highlight the exact source text.

The three scenarios are `termination-complete`, `termination-missing-schedule`, and `termination-conflicting-amendments`. Visitors cannot change model names, prompts, URLs, tool definitions or upload private contracts. Existing EnergyOps routes and forecasts remain supported.

## Implementation

- `contractlens/contracts.py`: strict request, report, event, tool and evaluation types.
- `contractlens/migrations/`: PostgreSQL schema and worker-readiness revision.
- `contractlens/corpus.py`: authored fictional documents, immutable hashes, character offsets, typed references and PostgreSQL lexical retrieval.
- `contractlens/engine.py`: bounded model-directed loop, plan/ledger tools, observation-scoped citation checks and separate evaluation categories.
- `contractlens/provider.py`: fixed Anthropic Messages HTTPS boundary with tool-use handling, usage recording, bounded responses/timeouts and sanitized failures.
- `contractlens/api.py`: scoped discovery, fixed-scenario admission, idempotency, history and cancellation requests.
- `contractlens/worker.py`: application-owned subprocess controller with independent deadline timer, cancellation and explicit interrupted-run failure.

Prompt and tool-schema hashes, source hashes, selected model, scenario revision, actual calls and usage are retained. Source character offsets are Unicode code-point offsets; no PDF pages are invented. Search is lexical PostgreSQL search, not an embedding service. A citation-integrity pass does not mean the associated claim is semantically or legally correct. Semantic evaluation remains unknown without an independently configured qualified review process. Cost is unavailable without a versioned pricing table.

Working memory is a per-run append-only ledger. No cross-run learning, prompt self-modification, multi-agent team, uploads/OCR, external legal research, embeddings, checkpoint resume or automated contract action is implemented.

## Tests and development

Python 3.12 / Linux amd64 is the current tested target. Runtime and development dependencies are pinned/hash-locked. Use a disposable database: tests truncate execution/evidence tables.

```sh
python3 -m venv .venv
.venv/bin/pip install --require-hashes -r requirements-dev.lock
TEST_DATABASE_URL=postgresql://USER:PASSWORD@localhost/contractlens_test PYTHONPATH=. .venv/bin/pytest tests -q
PYTHONPATH=. .venv/bin/python scripts/export_contracts.py
```

For local development set `DATABASE_URL`, `DEMO_TOKEN_FILE`, `ANTHROPIC_API_KEY_FILE`, `CONTRACTLENS_MODEL` and `MODEL_EXECUTION_ENABLED`, then run `uvicorn contractlens.api:app --port 8020` and `python -m contractlens.worker` in separate processes. The API does not need the provider-key environment variable.

Tests inject explicitly scripted providers or HTTP mock transports; these never become a production provider mode. Subprocess timeout tests launch actual short-lived test processes. The real provider acceptance gate remains separate.

## Real acceptance checklist

Start the two independent Compose deployments, provision a model key without exposing it to the sandbox, and execute one approved question from the UI. Verify actual model usage, ordered event history, exact quoted spans, highlighted citations, persisted result/evaluations, cancellation/timeout and private-run isolation. Restart the sandbox and confirm its evidence survives; restart the worker mid-run and confirm interruption is recorded without paid-call replay. Stop ContractLens and confirm catalog/history remain available.

A completed run with failed retrieval/checklist evaluation is displayed as such. Unknown legal correctness must remain unknown. Do not substitute scripted test reports for this acceptance run.

## OpenRouter provider

Use `MODEL_PROVIDER=openrouter` in the runtime `.env` with an explicit OpenRouter model ID
(e.g. `openai/gpt-oss-120b`). The production Compose overlay passes this setting to the worker.
The existing `secrets/anthropic_api_key` file is the provider credential mount; for OpenRouter it must
contain the OpenRouter key. It is sent using bearer authentication only to `https://openrouter.ai/api/v1/messages`.
The default `MODEL_PROVIDER=anthropic` keeps the direct Anthropic endpoint and authentication.
Request/response bounds, tool schemas, execution budgets and sanitized errors remain enforced.

## Per-run budgets

Execution budgets are validated from `CONTRACTLENS_BUDGET_*` settings in `.env` and passed
to API/worker by Compose. Defaults: 24 model calls, 40 tool calls, 300 seconds, 160,000 context bytes,
4,096 output tokens per call, 30-second provider request timeout, 320 evidence events.
See `.env.example` for all settings. These are renewed per run; session/hourly admission quotas are separate.
Invalid/out-of-range settings or an evidence budget too small for the model/tool allowance fail validation.
Wire schemas retain fixed safety ceilings (500 events, eight plan revisions, 24 ledger entries).
The model receives the active limits and remaining model/tool calls each turn, with a reporting warning
in its final four calls. Existing failed runs remain immutable; retry as a new run after changing budgets.
After editing `.env`, recreate API and worker; a plain container restart does not reload Compose environment.
