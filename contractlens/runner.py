import sys, uuid
from . import db
from .engine import run, BudgetExceeded
from .provider import create_provider, ProviderFailure, ModelOutputRejected


def main(eid):
    provider = create_provider()
    try:
        run(eid, provider)
    except Exception as exc:
        code = (
            "budget_exhausted"
            if isinstance(exc, BudgetExceeded)
            else (
                "invalid_model_output" if isinstance(exc, ModelOutputRejected) else "provider_failure"
                if isinstance(exc, ProviderFailure)
                else "execution_error"
            )
        )
        category = exc.category if isinstance(exc, ProviderFailure) else "budget_exhausted" if isinstance(exc, BudgetExceeded) else "runtime_validation" if isinstance(exc, ValueError) else "unexpected_runtime_error"
        reason = "Execution stopped: " + category + "; private details withheld."
        if isinstance(exc, ProviderFailure) and exc.diagnostic:
            reason += " " + __import__("json").dumps(exc.diagnostic, sort_keys=True)
        with db.connect() as c:
            db.append(c, eid, "validation_rejected", {"tool": "unrecognized", "reason": reason})
            c.execute(
                "UPDATE executions SET failure_code=%s WHERE id=%s AND status='running'",
                (code, eid),
            )
        raise SystemExit(1) from None
    finally:
        provider.close()


if __name__ == "__main__":
    main(uuid.UUID(sys.argv[1]))
