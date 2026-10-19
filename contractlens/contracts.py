from typing import Literal
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


ScenarioId = Literal[
    "termination-complete",
    "termination-missing-schedule",
    "termination-conflicting-amendments",
]


class StartRequest(Strict):
    id: UUID
    scenario_id: ScenarioId


class PlanInput(Strict):
    steps: list[str] = Field(min_length=1, max_length=8)


class EmptyInput(Strict):
    pass


class SearchInput(Strict):
    query: str = Field(min_length=1, max_length=160)
    limit: int = Field(default=4, ge=1, le=6)


class ReadInput(Strict):
    clause_ids: list[str] = Field(min_length=1, max_length=4)


class ReferenceInput(Strict):
    clause_id: str = Field(min_length=1, max_length=100)


class LedgerEntry(Strict):
    topic: str = Field(min_length=1, max_length=60)
    finding: str = Field(min_length=1, max_length=700)
    clause_ids: list[str] = Field(min_length=1, max_length=6)


class LedgerInput(Strict):
    entries: list[LedgerEntry] = Field(min_length=1, max_length=8)


class CitationInput(Strict):
    clause_id: str = Field(min_length=1, max_length=100)
    quote: str = Field(min_length=12, max_length=1200)


class FindingInput(Strict):
    claim: str = Field(min_length=1, max_length=1200)
    citations: list[CitationInput] = Field(min_length=1, max_length=6)


class AnswerInput(Strict):
    conclusion_status: Literal[
        "supported", "qualified", "conflicting", "insufficient_evidence"
    ]
    findings: list[FindingInput] = Field(max_length=8)
    conditions: list[str] = Field(max_length=8)
    gaps: list[str] = Field(max_length=8)
    review_questions: list[str] = Field(max_length=8)


class Citation(CitationInput):
    document_id: str
    document_version: str
    document_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)


class Finding(Strict):
    claim: str = Field(min_length=1, max_length=1200)
    citations: list[Citation] = Field(min_length=1, max_length=6)


class SourceClause(Strict):
    id: str
    document_id: str
    document_title: str
    document_version: str
    document_sha256: str
    section: str
    title: str
    text: str
    char_start: int
    char_end: int


class Usage(Strict):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    model_calls: int = Field(ge=0)


class ContractReport(Strict):
    contract_version: Literal["1.0"] = "1.0"
    artifact_type: Literal["contract_report"] = "contract_report"
    question: str
    conclusion_status: Literal[
        "supported", "qualified", "conflicting", "insufficient_evidence"
    ]
    findings: list[Finding] = Field(max_length=8)
    conditions: list[str] = Field(max_length=8)
    gaps: list[str] = Field(max_length=8)
    review_questions: list[str] = Field(max_length=8)
    package_id: str
    package_sha256: str
    evidence_ledger: list[LedgerEntry] = Field(max_length=24)
    source_clauses: list[SourceClause] = Field(max_length=40)
    plans: list[PlanInput] = Field(max_length=8)
    model_usage: Usage
    versions: dict[str, str]


class Event(Strict):
    seq: int = Field(ge=1)
    occurred_at: AwareDatetime
    kind: Literal[
        "state_transition",
        "plan_recorded",
        "tool_called",
        "tool_completed",
        "context_assembled",
        "model_completed",
        "ledger_recorded",
        "validation_rejected",
        "evaluation_recorded",
    ]
    status: (
        Literal["queued", "running", "succeeded", "failed", "cancelled", "timed_out"]
        | None
    ) = None
    data: dict


class Evaluation(Strict):
    id: str
    category: Literal[
        "deterministic", "trajectory", "semantic", "domain", "operational"
    ]
    status: Literal["passed", "failed", "unknown", "skipped", "errored"]
    evaluator: str
    evaluator_version: str
    configuration: dict
    metrics: dict
    provenance: dict
    reason: str


class Execution(Strict):
    integration_version: Literal["1.1"] = "1.1"
    id: UUID
    status: Literal[
        "queued", "running", "succeeded", "failed", "cancelled", "timed_out"
    ]
    events: list[Event] = Field(max_length=120)
    result: ContractReport | None = None
    evaluations: list[Evaluation]
    failure_code: str | None = None
