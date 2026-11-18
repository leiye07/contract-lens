import os
from pathlib import Path


def secret(name, default):
    try:
        return Path(os.getenv(name, default)).read_text().strip()
    except OSError:
        return ""


def demo_token():
    return secret("DEMO_TOKEN_FILE", "/run/secrets/demo_token")


def provider_key():
    return secret("MODEL_API_KEY_FILE", os.getenv("ANTHROPIC_API_KEY_FILE", "/run/secrets/anthropic_api_key"))


def model():
    return os.getenv("CONTRACTLENS_MODEL", "").strip()


def configured():
    return (
        os.getenv("MODEL_EXECUTION_ENABLED", "false").lower() == "true"
        and bool(model())
        and bool(provider_key())
        and len(demo_token()) >= 32
    )


def admission_configured():
    # API does not need the provider key; worker readiness certifies its configuration.
    return (
        os.getenv("MODEL_EXECUTION_ENABLED", "false").lower() == "true"
        and bool(model())
        and len(demo_token()) >= 32
    )


def model_provider():
    return os.getenv("MODEL_PROVIDER", "anthropic").strip().lower()


from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class RunBudget:
    model_calls: int = 24
    tool_calls: int = 40
    timeout_seconds: int = 300
    context_bytes: int = 160000
    output_tokens: int = 4096
    request_timeout_seconds: int = 30
    response_bytes: int = 128000
    tool_input_bytes: int = 16000
    evidence_events: int = 320
    evidence_payload_bytes: int = 24000
    plan_revisions: int = 8
    ledger_entries: int = 24
    tools_per_turn: int = 6

    def public(self):
        return asdict(self)


def run_budget():
    defaults = RunBudget()
    # Wire-schema ceilings are independent safety bounds, not run allowances.
    bounds = {
        "model_calls": (4, 48), "tool_calls": (8, 64),
        "timeout_seconds": (30, 900), "context_bytes": (16000, 256000),
        "output_tokens": (1024, 8192), "request_timeout_seconds": (5, 120),
        "response_bytes": (16000, 256000), "tool_input_bytes": (1024, 24000),
        "evidence_events": (32, 500), "evidence_payload_bytes": (1024, 24000),
        "plan_revisions": (1, 8), "ledger_entries": (1, 24), "tools_per_turn": (1, 6),
    }
    values = {}
    for field, (low, high) in bounds.items():
        name = "CONTRACTLENS_BUDGET_" + field.upper()
        try:
            value = int(os.getenv(name, str(getattr(defaults, field))))
        except ValueError:
            raise ValueError(name + " must be an integer") from None
        if not low <= value <= high:
            raise ValueError(name + f" must be between {low} and {high}")
        values[field] = value
    budget = RunBudget(**values)
    if budget.request_timeout_seconds > budget.timeout_seconds:
        raise ValueError("Request timeout exceeds run deadline")
    if budget.evidence_events < 2 * budget.model_calls + 4 * budget.tool_calls + 10:
        raise ValueError("Evidence budget must cover model/tool events and terminal state")
    return budget
