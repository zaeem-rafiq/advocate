"""Draft-and-check loop: regenerate until the email passes the binary eval suite.

This is the enforcement layer behind FR-7 / slice #2: a draft is regenerated when
it fails any check and is NEVER surfaced unless it passes all of them. The actual
text generation is injected as a callable so this control flow stays pure and
unit-testable without an LLM; the agent layer passes a Gemini-backed generator.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from advocate.core.email_eval import EmailEval, evaluate_email

# generate(attempt_index) -> draft text. attempt_index lets the generator vary
# its prompt (e.g. "the previous draft failed X, try again") across retries.
Generator = Callable[[int], str]

# revise(failing_draft, its_eval) -> minimally-edited draft. Lets a later attempt
# repair the previous draft (fixing only the failed checks) instead of regenerating
# it from scratch. The reviser only PROPOSES; evaluate_email still decides.
Reviser = Callable[[str, "EmailEval"], str]

DEFAULT_MAX_ATTEMPTS = 4


@dataclass(frozen=True)
class DraftResult:
    """A draft that passed the eval suite, plus how many attempts it took."""

    email: str
    evaluation: EmailEval
    attempts: int


class DraftRejected(Exception):
    """Raised when no attempt produced a passing draft. Carries the last eval."""

    def __init__(self, attempts: int, last_eval: EmailEval) -> None:
        self.attempts = attempts
        self.last_eval = last_eval
        super().__init__(
            f"No compliant draft after {attempts} attempts; "
            f"last failures: {last_eval.failures}"
        )


def draft_until_passing(
    generate: Generator,
    connection_terms: Sequence[str],
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    revise: Reviser | None = None,
) -> DraftResult:
    """Generate drafts until one passes the eval suite, or raise DraftRejected.

    The first attempt is always generated fresh. On later attempts, if `revise` is
    supplied, the previous failing draft is minimally edited toward compliance
    instead of regenerated from scratch; otherwise `generate` is called again. Every
    attempt — generated or revised — is re-checked by `evaluate_email`, which remains
    the sole authority on whether a draft may be surfaced.
    """
    last_eval: EmailEval | None = None
    last_text: str | None = None
    for attempt in range(max_attempts):
        if attempt == 0 or revise is None or last_text is None or last_eval is None:
            text = generate(attempt)
        else:
            text = revise(last_text, last_eval)
        last_eval = evaluate_email(text, connection_terms)
        last_text = text
        if last_eval.passed:
            return DraftResult(email=text, evaluation=last_eval, attempts=attempt + 1)
    raise DraftRejected(attempts=max_attempts, last_eval=last_eval)
