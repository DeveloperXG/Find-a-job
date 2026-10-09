from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel


class LLMTask(StrEnum):
    SCORE = "score"
    EXTRACT = "extract"
    TAILOR = "tailor"
    CLASSIFY_EMAIL = "classify_email"
    ANSWER = "answer"


class LLMUsage(BaseModel):
    model: str
    input_tokens: int
    cached_input_tokens: int = 0
    output_tokens: int
    cost_usd: Decimal


class LLMResult[T: BaseModel](BaseModel):
    data: T
    usage: LLMUsage


class LLMError(Exception):
    """Provider failure after retries (network, 5xx, overloaded)."""


class LLMOutputInvalid(LLMError):
    """The model's output failed schema validation even after the repair retry."""


class BudgetExceeded(LLMError):
    """Today's spend (in the user's timezone) has reached the daily budget. Stop cleanly."""


class LLMProvider(Protocol):
    async def structured[T: BaseModel](
        self,
        *,
        task: LLMTask,
        system: str,
        cached_context: str,
        user: str,
        schema: type[T],
        max_tokens: int,
    ) -> LLMResult[T]:
        """Return `schema`-validated output for `task`.

        - The model id comes from config per task (`LLM_MODEL_<TASK>`), never from the caller.
        - `cached_context` (profile + rubric) is sent with a prompt-cache breakpoint.
        - `user` carries untrusted text (job postings, emails) already wrapped in delimiters.
        - Validates with Pydantic; one repair retry; then raises LLMOutputInvalid.
        - Checks the budget before calling and raises BudgetExceeded; records every call.
        """
        ...
