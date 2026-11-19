"""Provider fixtures are tests only. No fixture outputs are seeded into the public app."""

import hashlib, json, uuid, sys, subprocess
import pytest, httpx
from contractlens import db, corpus, worker
from contractlens.engine import Investigator, run, BudgetExceeded, TOOL_DEFINITIONS
from contractlens.provider import AnthropicProvider, ProviderFailure
from conftest import submit


class ScriptedProvider:
    def __init__(self, sid):
        self.sid = sid
        self.turn = 0
        self.requests = []

    def complete(self, system, messages, tools):
        self.requests.append(json.dumps(messages))
        self.turn += 1
        pid = corpus.SCENARIOS[self.sid]["package_id"]
        manifest, _ = corpus.materialize(self.sid)
        ids = [
            clause["id"] for doc in manifest["documents"] for clause in doc["clauses"]
        ]
        if self.turn == 1:
            calls = [
                (
                    "record_plan",
                    {
                        "steps": [
                            "Inspect document completeness",
                            "Read termination and linked obligations",
                            "Check amendments and report gaps",
                        ]
                    },
                ),
                ("list_documents", {}),
            ]
        elif self.turn == 2:
            calls = [
                ("read_clauses", {"clause_ids": ids[i : i + 4]})
                for i in range(0, len(ids), 4)
            ]
        else:
            ref = corpus.read(pid, "MSA-2")
            status = (
                "conflicting"
                if "conflicting" in self.sid
                else "qualified" if "missing" in self.sid else "supported"
            )
            calls = [
                (
                    "update_ledger",
                    {
                        "entries": [
                            {
                                "topic": topic,
                                "finding": "Test fixture observation from read source.",
                                "clause_ids": ["MSA-2"],
                            }
                            for topic in corpus.CHECKLIST
                        ]
                    },
                ),
                ("check_evidence_coverage", {}),
                (
                    "finish_report",
                    {
                        "conclusion_status": status,
                        "findings": [
                            {
                                "claim": "Test fixture finding: the document specifies a termination mechanism.",
                                "citations": [
                                    {"clause_id": "MSA-2", "quote": ref["text"]}
                                ],
                            }
                        ],
                        "conditions": ["Test-only condition"],
                        "gaps": (
                            ["Schedule A is missing"]
                            if "missing" in self.sid
                            else (
                                ["Conflicting amendments require review"]
                                if "conflicting" in self.sid
                                else []
                            )
                        ),
                        "review_questions": [
                            "Confirm interpretation with a qualified reviewer."
                        ],
                    },
                ),
            ]
        content = [
            {
                "type": "tool_use",
                "id": f"test-{self.turn}-{i}",
                "name": name,
                "input": args,
            }
            for i, (name, args) in enumerate(calls)
        ]
        return {
            "content": content,
            "calls": content,
            "usage": {"input_tokens": 100, "output_tokens": 30},
            "model": "test-model-not-production",
            "latency_ms": 1,
        }


@pytest.mark.parametrize("sid", list(corpus.SCENARIOS))
def test_full_agent_loop_persisted_evidence(client, sid):
    eid = submit(client, sid)
    with db.connect() as c:
        db.transition(c, eid, "running")
    provider = ScriptedProvider(sid)
    report = run(eid, provider)
    data = client.get("/demo/v1/executions/" + eid).json()
    assert data["status"] == "succeeded"
    assert report["model_usage"] == {
        "input_tokens": 300,
        "output_tokens": 90,
        "model_calls": 3,
    }
    events = data["events"]
    assert [e["seq"] for e in events] == list(range(1, len(events) + 1))
    assert {
        "plan_recorded",
        "tool_called",
        "tool_completed",
        "context_assembled",
        "ledger_recorded",
        "model_completed",
        "evaluation_recorded",
    }.issubset({e["kind"] for e in events})
    semantic = next(e for e in data["evaluations"] if e["category"] == "semantic")
    assert semantic["status"] == "unknown"
    assert (
        next(e for e in data["evaluations"] if e["category"] == "domain")["status"]
        == "passed"
    )
    assert "reference_evidence" not in "".join(provider.requests)
    assert len(report["plans"]) == 1
    # Re-open persisted record via a new connection, not an in-memory artifact.
    with db.connect() as c:
        assert (
            c.execute("SELECT result FROM executions WHERE id=%s", (eid,)).fetchone()[
                "result"
            ]["package_sha256"]
            == report["package_sha256"]
        )


@pytest.mark.parametrize("sid", list(corpus.SCENARIOS))
def test_corpus_offsets_hashes_and_missing_references(client, sid):
    manifest, sha = corpus.materialize(sid)
    assert corpus.package(manifest["id"])["sha256"] == sha
    for doc in manifest["documents"]:
        assert hashlib.sha256(doc["body"].encode()).hexdigest() == doc["sha256"]
        for clause in doc["clauses"]:
            assert (
                doc["body"][clause["char_start"] : clause["char_end"]] == clause["text"]
            )
    if "missing" in sid:
        ref = corpus.read(manifest["id"], "MSA-2")
        assert any(
            x["target_id"] == "SCHEDULE-A-1" and not x["available"]
            for x in ref["references"]
        )
        with pytest.raises(ValueError):
            corpus.read(manifest["id"], "SCHEDULE-A-1")


def investigator():
    return Investigator(
        "unused",
        {
            "package_id": "fictional-complete-v1",
            "question": corpus.QUESTION,
            "checklist": corpus.CHECKLIST,
            "revision": "1",
        },
        emit=lambda *args: None,
    )


def test_tool_scope_and_planning(client):
    agent = investigator()
    with pytest.raises(ValueError):
        agent.invoke("search_clauses", {"query": "termination"})
    with pytest.raises(ValueError):
        agent.invoke("shell", {"command": "anything"})
    agent.invoke("record_plan", {"steps": ["Read before citing"]})
    with pytest.raises(ValueError):
        agent.invoke("read_clauses", {"clause_ids": ["OTHER-PACKAGE/SECRET"]})
    with pytest.raises(ValueError):
        agent.invoke("resolve_reference", {"clause_id": "MSA-2"})
    with pytest.raises(ValueError):
        agent.invoke(
            "update_ledger",
            {
                "entries": [
                    {
                        "topic": "termination",
                        "finding": "Unseen evidence",
                        "clause_ids": ["MSA-2"],
                    }
                ]
            },
        )
    assert not agent.observed


def test_citation_rejects_fabricated_and_unread_sources(client):
    agent = investigator()
    agent.invoke("record_plan", {"steps": ["Read evidence"]})
    agent.invoke("list_documents", {})
    payload = {
        "conclusion_status": "qualified",
        "findings": [
            {
                "claim": "Not verified",
                "citations": [
                    {
                        "clause_id": "MSA-2",
                        "quote": "Customer may terminate this Agreement",
                    }
                ],
            }
        ],
        "conditions": [],
        "gaps": ["Incomplete review"],
        "review_questions": [],
    }
    with pytest.raises(ValueError):
        agent.invoke("finish_report", payload)
    agent.invoke("read_clauses", {"clause_ids": ["MSA-2"]})
    payload["findings"][0]["citations"][0]["quote"] = "Fabricated source quotation."
    with pytest.raises(ValueError):
        agent.invoke("finish_report", payload)


def test_missing_package_cannot_claim_supported(client):
    agent = Investigator(
        "unused",
        {
            "package_id": "fictional-missing-schedule-v1",
            "question": corpus.QUESTION,
            "checklist": corpus.CHECKLIST,
        },
        emit=lambda *a: None,
    )
    agent.invoke("record_plan", {"steps": ["Check package"]})
    agent.invoke("list_documents", {})
    with pytest.raises(ValueError):
        agent.invoke(
            "finish_report",
            {
                "conclusion_status": "supported",
                "findings": [],
                "conditions": [],
                "gaps": [],
                "review_questions": [],
            },
        )


def test_tool_budget(client, monkeypatch):
    monkeypatch.setenv("CONTRACTLENS_BUDGET_TOOL_CALLS", "12")
    agent = investigator()
    agent.invoke("record_plan", {"steps": ["Bounded investigation"]})
    for _ in range(11):
        agent.invoke("check_evidence_coverage", {})
    with pytest.raises(BudgetExceeded):
        agent.invoke("list_documents", {})


def test_schema_exports_and_private_reference_boundary(client):
    data = client.get("/demo/v1/scenarios").json()
    assert "reference_evidence" not in str(data)
    package = client.get("/demo/v1/packages/fictional-complete-v1").json()
    assert package["fictional"] is True
    assert "reference_evidence" not in str(package)
    assert client.get("/demo/v1/packages/arbitrary-path").status_code == 404
    assert (
        client.get(
            "/demo/v1/capabilities", headers={"Authorization": "Bearer wrong"}
        ).status_code
        == 401
    )


def test_api_idempotency_restrictions_and_disabled_model(client, monkeypatch):
    eid = submit(client)
    body = {"id": eid, "scenario_id": "termination-complete"}
    assert len(client.post("/demo/v1/executions", json=body).json()["events"]) == 1
    assert (
        client.post(
            "/demo/v1/executions",
            json={**body, "scenario_id": "termination-missing-schedule"},
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/demo/v1/executions", json={**body, "prompt": "override"}
        ).status_code
        == 422
    )
    assert client.post("/demo/v1/executions", content="x" * 5000).status_code == 413
    monkeypatch.setenv("MODEL_EXECUTION_ENABLED", "false")
    assert (
        client.post(
            "/demo/v1/executions",
            json={"id": str(uuid.uuid4()), "scenario_id": "termination-complete"},
        ).status_code
        == 503
    )
    assert client.get("/demo/v1/capabilities").json()["execution_ready"] is False


def test_global_quota(client):
    for _ in range(4):
        submit(client)
    assert (
        client.post(
            "/demo/v1/executions",
            json={"id": str(uuid.uuid4()), "scenario_id": "termination-complete"},
        ).status_code
        == 429
    )


def test_queued_cancel(client):
    eid = submit(client)
    data = client.post(f"/demo/v1/executions/{eid}/cancel", json={}).json()
    assert data["status"] == "cancelled"
    with pytest.raises(ValueError):
        with db.connect() as c:
            db.transition(c, eid, "running")


@pytest.mark.parametrize("outcome", ["timed_out", "cancelled", "failed"])
def test_real_subprocess_deadline_and_cancel(client, monkeypatch, outcome):
    eid = submit(client)
    with db.connect() as c:
        db.transition(c, eid, "running")
        if outcome == "cancelled":
            c.execute("UPDATE executions SET cancel_requested=true WHERE id=%s", (eid,))
    monkeypatch.setattr(worker, "STOP", False)
    original = subprocess.Popen
    children = []

    def child(*args, **kwargs):
        p = original(
            [
                sys.executable,
                "-c",
                (
                    "import time; time.sleep(10)"
                    if outcome != "failed"
                    else "raise SystemExit(1)"
                ),
            ],
            **kwargs,
        )
        children.append(p)
        return p

    monkeypatch.setattr(worker.subprocess, "Popen", child)
    worker.execute(eid, timeout_seconds=0.1)
    assert client.get(f"/demo/v1/executions/{eid}").json()["status"] == outcome
    assert all(p.poll() is not None for p in children)


def test_restart_marks_interrupted_without_model_retry(client, monkeypatch):
    eid = submit(client)
    with db.connect() as c:
        db.transition(c, eid, "running")
    monkeypatch.setattr(worker, "STOP", False)

    def stop_after_one(*args):
        worker.STOP = True

    monkeypatch.setattr(worker.time, "sleep", stop_after_one)
    worker.main()
    data = client.get(f"/demo/v1/executions/{eid}").json()
    assert (
        data["status"] == "failed"
        and data["failure_code"] == "interrupted_no_automatic_retry"
    )


def test_provider_protocol_and_no_secret_errors(client):
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "stop_reason": "tool_use",
                "model": "test-model",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "1",
                        "name": "list_documents",
                        "input": {},
                    }
                ],
                "usage": {"input_tokens": 12, "output_tokens": 3},
            },
        )

    provider = AnthropicProvider(httpx.MockTransport(handler))
    result = provider.complete(
        "instruction", [{"role": "user", "content": "question"}], TOOL_DEFINITIONS
    )
    provider.close()
    assert result["calls"][0]["name"] == "list_documents"
    assert seen[0]["model"] == "test-model-not-production"
    provider = AnthropicProvider(
        httpx.MockTransport(
            lambda request: httpx.Response(401, text="secret-provider-error")
        )
    )
    with pytest.raises(ProviderFailure) as exc:
        provider.complete("instruction", [], TOOL_DEFINITIONS)
    assert "secret-provider-error" not in str(exc.value)
    provider.close()


def test_investigation_can_finish_beyond_old_eight_turn_limit(client):
    eid = submit(client)
    with db.connect() as c:
        db.transition(c, eid, "running")
    class ExtendedProvider(ScriptedProvider):
        def __init__(self):
            super().__init__("termination-complete")
            self.actual_turns = 0
        def complete(self, system, messages, tools):
            self.actual_turns += 1
            if 3 <= self.actual_turns <= 9:
                return {"content":[{"type":"tool_use","id":f"extra-{self.actual_turns}","name":"check_evidence_coverage","input":{}}], "calls":[{"id":f"extra-{self.actual_turns}","name":"check_evidence_coverage","input":{}}], "usage":{"input_tokens":10,"output_tokens":10}, "model":"test-model", "latency_ms":1}
            return super().complete(system,messages,tools)
    provider = ExtendedProvider()
    report = run(eid, provider)
    assert provider.actual_turns == 10
    assert report["model_usage"]["model_calls"] == 10
    assert client.get("/demo/v1/executions/"+eid).json()["status"] == "succeeded"


def test_provider_schema_rejection_consumes_a_turn_and_recovers(client):
    from contractlens.provider import ModelOutputRejected
    class RejectedOnce(ScriptedProvider):
        rejected=False
        def complete(self,*args):
            if not self.rejected:
                self.rejected=True
                raise ModelOutputRejected(category='upstream_tool_schema')
            return super().complete(*args)
    eid=submit(client)
    with db.connect() as c:db.transition(c,eid,'running')
    result=run(eid,RejectedOnce('termination-complete'))
    assert result['model_usage']['model_calls']==4
    assert result['model_usage']['input_tokens']==300


def test_plan_accepts_sixteen_steps_but_remains_bounded():
    from contractlens.contracts import PlanInput,ReadInput
    assert len(PlanInput(steps=['Investigate']*16).steps)==16
    with pytest.raises(ValueError):PlanInput(steps=['Investigate']*17)
    assert len(ReadInput(clause_ids=['clause']*12).clause_ids)==12


def test_temporary_provider_retry_is_bounded_and_counts_requests(client):
    from contractlens.provider import RetryableProviderFailure
    class TemporaryFailure(ScriptedProvider):
        failures=0
        def complete(self,*args):
            if self.failures<2:
                self.failures+=1
                raise RetryableProviderFailure(category='transient_http_502')
            return super().complete(*args)
    eid=submit(client)
    with db.connect() as c:db.transition(c,eid,'running')
    report=run(eid,TemporaryFailure('termination-complete'))
    assert report['model_usage']['model_calls']==5
