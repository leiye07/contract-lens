# Configurable budget validation — 2026-11-18

Defaults: 24 model calls, 40 tools, 300 seconds per run; full environment settings in ../.env.example.
All runtime consumers use the validated RunBudget: engine, provider, worker deadline, evidence store and scenario deadline metadata.
Portable execution schema expanded to a 500-event safety ceiling; default runtime evidence budget is 320.

31 ContractLens tests passed on disposable PostgreSQL, including configuration rejection, configured tool cap, remaining-budget context, a successful ten-turn regression, timeout/cancel and all three scenario fixtures.
82 shared API tests passed on a separate disposable database.

Live OpenRouter run 1d2ce128-c2ca-4122-8bd1-8f1423cff8aa (termination-complete) succeeded on the VM:
9 model calls, 9 tool calls, no rejected calls, 42 evidence events, 20.97 seconds, one synchronized report artifact.
This verifies one real scenario execution, not universal model reliability or legal correctness.
Original failed run 33c65fac-3b8e-494d-8ea0-c3d73820dba3 was preserved.

Changes deployed to ContractLens API/worker and shared API/sync without deleting volumes.
