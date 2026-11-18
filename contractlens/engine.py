"""A bounded real model-directed tool loop. Scripted providers are injected by tests only."""

import hashlib, json, uuid, time
from pathlib import Path
from pydantic import ValidationError
from . import db, corpus, config
from .contracts import (
    PlanInput,
    EmptyInput,
    SearchInput,
    ReadInput,
    ReferenceInput,
    LedgerInput,
    AnswerInput,
    ContractReport,
    SourceClause,
    Usage,
)

PROMPT = Path(__file__).with_name("prompt.txt").read_text()
PROMPT_SHA = hashlib.sha256(PROMPT.encode()).hexdigest()
TOOLS = {
    "record_plan": (
        PlanInput,
        "Record or revise concise observable investigation steps. Must be called before retrieval.",
    ),
    "list_documents": (
        EmptyInput,
        "List this package, available document versions and explicitly missing attachments.",
    ),
    "search_clauses": (
        SearchInput,
        "Find clause pointers by PostgreSQL lexical search. Does not establish absence or supply citable text.",
    ),
    "read_clauses": (
        ReadInput,
        "Read exact clauses and typed references within this package. Only read evidence can be cited.",
    ),
    "resolve_reference": (
        ReferenceInput,
        "Return typed references from a previously read clause, including missing targets.",
    ),
    "compare_provisions": (
        ReadInput,
        "Read two to four related provisions side-by-side. Does not decide legal precedence.",
    ),
    "update_ledger": (
        LedgerInput,
        "Store evidence-backed working findings against the public checklist. Cite only previously read clauses.",
    ),
    "check_evidence_coverage": (
        EmptyInput,
        "Check checklist topic coverage by ledger entries; not a legal correctness grade.",
    ),
    "finish_report": (
        AnswerInput,
        "Submit a final structured report with exact quotations from previously read clauses. Validation errors can be corrected within the remaining budget.",
    ),
}
TOOL_DEFINITIONS = [
    {
        "name": name,
        "description": description,
        "input_schema": model.model_json_schema(),
    }
    for name, (model, description) in TOOLS.items()
]
TOOL_SHA = hashlib.sha256(
    json.dumps(TOOL_DEFINITIONS, sort_keys=True).encode()
).hexdigest()


def versions():
    return {
        "runtime": "1.0",
        "prompt_sha256": PROMPT_SHA,
        "tools_sha256": TOOL_SHA,
        "model": config.model(),
        "provider": config.model_provider() + "-messages",
        "corpus": "fictional-v1",
    }


class BudgetExceeded(RuntimeError):
    pass


class Investigator:
    def __init__(self, eid, scenario, emit=None):
        self.id = eid
        self.scenario = scenario
        self.pid = scenario["package_id"]
        self.observed = {}
        self.ledger = []
        self.plans = []
        self.calls = 0
        self.emit = emit or (lambda kind, data: db.record(eid, kind, data))
        self.documents_inspected = False

    def coverage(self):
        covered = {e["topic"] for e in self.ledger}
        return {
            "covered": [t for t in self.scenario["checklist"] if t in covered],
            "unresolved": [t for t in self.scenario["checklist"] if t not in covered],
            "scope": "ledger_topic_presence_only",
        }

    def invoke(self, name, raw):
        self.calls += 1
        if self.calls > 12:
            raise BudgetExceeded("Tool budget exhausted")
        if name not in TOOLS:
            raise ValueError("Tool not permitted")
        if len(json.dumps(raw).encode()) > 6000:
            raise ValueError("Tool input too large")
        args = TOOLS[name][0].model_validate(raw)
        self.emit(
            "tool_called",
            {"name": name, "arguments": args.model_dump(), "call_number": self.calls},
        )
        if name != "record_plan" and not self.plans:
            raise ValueError("Record an investigation plan first")
        if name == "record_plan":
            if len(self.plans) >= 8:
                raise BudgetExceeded("Plan budget exhausted")
            self.plans.append(args.model_dump())
            self.emit(
                "plan_recorded", {"revision": len(self.plans), **args.model_dump()}
            )
            result = {"recorded": True, "revision": len(self.plans)}
        elif name == "list_documents":
            result = corpus.package(self.pid)
            self.documents_inspected = True
        elif name == "search_clauses":
            result = corpus.search(self.pid, args.query, args.limit)
        elif name in {"read_clauses", "compare_provisions"}:
            if name == "compare_provisions" and len(args.clause_ids) < 2:
                raise ValueError("Compare at least two clauses")
            result = {"clauses": []}
            for cid in args.clause_ids:
                row = corpus.read(self.pid, cid)
                self.observed[cid] = row
                result["clauses"].append(row)
        elif name == "resolve_reference":
            if args.clause_id not in self.observed:
                raise ValueError("Read the source clause first")
            result = {
                "clause_id": args.clause_id,
                "references": self.observed[args.clause_id]["references"],
            }
        elif name == "update_ledger":
            if len(self.ledger) + len(args.entries) > 24:
                raise BudgetExceeded("Ledger budget exhausted")
            entries = [e.model_dump() for e in args.entries]
            if any(
                e["topic"] not in self.scenario["checklist"]
                or not set(e["clause_ids"]).issubset(self.observed)
                for e in entries
            ):
                raise ValueError(
                    "Ledger requires public checklist topics and observed clauses"
                )
            self.ledger.extend(entries)
            self.emit("ledger_recorded", {"entries": entries})
            result = {"recorded": len(entries), "coverage": self.coverage()}
        elif name == "check_evidence_coverage":
            result = self.coverage()
        elif name == "finish_report":
            result = self.finish(args)
        self.emit(
            "tool_completed",
            {
                "name": name,
                "result": (
                    result
                    if name != "finish_report"
                    else {
                        "accepted": True,
                        "conclusion_status": result["conclusion_status"],
                    }
                ),
            },
        )
        return result

    def finish(self, answer):
        if not self.documents_inspected:
            raise ValueError("Inspect package completeness first")
        if answer.conclusion_status != "insufficient_evidence" and not answer.findings:
            raise ValueError("A supported conclusion requires findings")
        if answer.conclusion_status == "supported" and self.coverage()["unresolved"]:
            raise ValueError("Checklist topics remain unresolved")
        package = corpus.package(self.pid)
        if any(not d["available"] for d in package["documents"]) and (
            answer.conclusion_status == "supported" or not answer.gaps
        ):
            raise ValueError(
                "Missing attachments require an explicit gap and qualified/insufficient conclusion"
            )
        findings = []
        for finding in answer.findings:
            citations = []
            for citation in finding.citations:
                row = self.observed.get(citation.clause_id)
                if not row or citation.quote not in row["text"]:
                    raise ValueError(
                        "Citation must exactly quote a clause read by this execution"
                    )
                offset = row["text"].index(citation.quote)
                citations.append(
                    {
                        **citation.model_dump(),
                        "document_id": row["document_id"],
                        "document_version": row["document_version"],
                        "document_sha256": row["document_sha256"],
                        "char_start": row["char_start"] + offset,
                        "char_end": row["char_start"] + offset + len(citation.quote),
                    }
                )
            findings.append({"claim": finding.claim, "citations": citations})
        return {
            **answer.model_dump(),
            "findings": findings,
            "question": self.scenario["question"],
            "package_id": self.pid,
            "package_sha256": package["sha256"],
            "evidence_ledger": self.ledger,
            "source_clauses": [
                SourceClause(
                    **{k: v for k, v in row.items() if k in SourceClause.model_fields}
                ).model_dump()
                for row in self.observed.values()
            ],
            "plans": self.plans,
            "versions": versions(),
        }


def evaluate(report, scenario, latency):
    citation_count = sum(len(f["citations"]) for f in report["findings"])
    observed = {s["id"] for s in report["source_clauses"]}
    required = set(scenario["reference_evidence"])
    hits = len(required & observed)
    topics = {e["topic"] for e in report["evidence_ledger"]}
    complete = set(scenario["checklist"]).issubset(topics)
    values = [
        (
            "deterministic",
            "passed",
            "exact-citation-integrity",
            {"validated_citations": citation_count},
            "All submitted quotations match observed immutable source spans. This does not verify claim entailment.",
        ),
        (
            "trajectory",
            "passed" if complete else "failed",
            "public-checklist-coverage",
            {
                "covered_topics": len(topics),
                "required_topics": len(scenario["checklist"]),
            },
            "Measures recorded topic presence, not legal completeness.",
        ),
        (
            "domain",
            "passed" if hits == len(required) else "failed",
            "reference-evidence-retrieval",
            {"retrieved_reference_clauses": hits, "reference_clauses": len(required)},
            "Coverage of private reference-evidence set. It does not grade legal correctness.",
        ),
        (
            "semantic",
            "unknown",
            "qualified-review-unavailable",
            {},
            "No independent legal/semantic reviewer is configured. Claim support and legal interpretation remain unverified.",
        ),
        (
            "operational",
            "passed",
            "provider-usage",
            {"latency_seconds": latency, **report["model_usage"]},
            "Usage is provider reported. Monetary cost is unavailable without a versioned price table.",
        ),
    ]
    return [
        {
            "id": str(uuid.uuid4()),
            "category": category,
            "status": status,
            "evaluator": name,
            "evaluator_version": "1.0",
            "configuration": {"scenario_revision": scenario["revision"]},
            "metrics": metrics,
            "provenance": {
                "package_id": report["package_id"],
                "package_sha256": report["package_sha256"],
                "prompt_sha256": PROMPT_SHA,
                "cost": "unavailable",
            },
            "reason": reason,
        }
        for category, status, name, metrics, reason in values
    ]


def run(eid, provider):
    with db.connect() as c:
        scenario = c.execute(
            "SELECT s.* FROM scenarios s JOIN executions e ON s.id=e.scenario_id WHERE e.id=%s",
            (eid,),
        ).fetchone()
    investigator = Investigator(eid, scenario)
    messages = [
        {
            "role": "user",
            "content": json.dumps(
                {
                    "question": scenario["question"],
                    "package_id": scenario["package_id"],
                    "checklist": scenario["checklist"],
                    "limits": {"model_turns": 8, "tool_calls": 12},
                    "data_classification": "fictional demonstration documents",
                }
            ),
        }
    ]
    usage = {"input_tokens": 0, "output_tokens": 0, "model_calls": 0}
    started = time.monotonic()
    for turn in range(1, 9):
        context_size = len(
            (PROMPT + json.dumps(messages) + json.dumps(TOOL_DEFINITIONS)).encode()
        )
        if context_size > 80000:
            raise BudgetExceeded("Context byte budget exhausted")
        with db.connect() as c:
            row = c.execute(
                "SELECT status,cancel_requested FROM executions WHERE id=%s", (eid,)
            ).fetchone()
            if row["status"] != "running" or row["cancel_requested"]:
                raise RuntimeError("Execution stopped")
        investigator.emit(
            "context_assembled",
            {
                "turn": turn,
                "utf8_bytes": context_size,
                "byte_limit": 80000,
                "prompt_sha256": PROMPT_SHA,
                "source_clause_ids": list(investigator.observed),
                "ledger_entries": len(investigator.ledger),
                "messages": len(messages),
                "output_token_limit": 2400,
            },
        )
        response = provider.complete(PROMPT, messages, TOOL_DEFINITIONS)
        for k in ["input_tokens", "output_tokens"]:
            count = response["usage"][k]
            if not isinstance(count, int) or count < 0:
                raise ValueError("Invalid provider usage")
            usage[k] += count
        usage["model_calls"] += 1
        investigator.emit(
            "model_completed",
            {
                "turn": turn,
                "model": response["model"],
                "usage": response["usage"],
                "latency_ms": response["latency_ms"],
            },
        )
        if len(response["calls"]) > 6:
            raise BudgetExceeded("Too many tool calls in one turn")
        messages.append({"role": "assistant", "content": response["content"]})
        results = []
        for call in response["calls"]:
            name = call.get("name", "")
            raw = call.get("input", {})
            call_id = call["id"]
            try:
                result = investigator.invoke(name, raw)
                if name == "finish_report":
                    report = ContractReport(
                        **result, model_usage=Usage(**usage)
                    ).model_dump(mode="json")
                    evaluations = evaluate(report, scenario, time.monotonic() - started)
                    with db.connect() as c:
                        row = c.execute(
                            "SELECT status,cancel_requested FROM executions WHERE id=%s FOR UPDATE",
                            (eid,),
                        ).fetchone()
                        if row["status"] != "running" or row["cancel_requested"]:
                            raise RuntimeError("Execution stopped before commit")
                        db.append(
                            c, eid, "evaluation_recorded", {"reports": evaluations}
                        )
                        c.execute(
                            "UPDATE executions SET result=%s,evaluations=%s WHERE id=%s",
                            (
                                __import__("psycopg").types.json.Jsonb(report),
                                __import__("psycopg").types.json.Jsonb(evaluations),
                                eid,
                            ),
                        )
                        db.transition(c, eid, "succeeded")
                    return report
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call_id,
                        "content": json.dumps(result, default=str),
                    }
                )
            except (ValueError, ValidationError) as e:
                investigator.emit(
                    "validation_rejected",
                    {
                        "tool": name if name in TOOLS else "unrecognized",
                        "reason": "Invalid input, access, evidence or citation; correct using observed package evidence.",
                    },
                )
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call_id,
                        "is_error": True,
                        "content": "Rejected: invalid input, package access, evidence or citation. Use exact observed source evidence and approved schemas.",
                    }
                )
        messages.append({"role": "user", "content": results})
    raise BudgetExceeded("Model turn budget exhausted")
