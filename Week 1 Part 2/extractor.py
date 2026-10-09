"""Job posting extractor built on OpenAI native function calling and Pydantic.

Pipeline::

    messy text -> LLM (forced, strict function call) -> Pydantic validation
        -> valid?  yes -> JobPosting
                   no  -> ONE retry with the validation errors as feedback
                          -> Pydantic validation -> JobPosting or ExtractionValidationError

Extraction is performed using native function calling with a strict tool schema
generated from the ``JobPosting`` Pydantic model. The model is forced to call the
``extract_job_posting`` tool, so its answer arrives as tool-call arguments rather
than free text. The application does not use regex or string manipulation to
recover JSON from model prose.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from dotenv import load_dotenv
from openai import OpenAI, pydantic_function_tool
from pydantic import ValidationError

from schema import JobPosting

DEFAULT_MODEL = "gpt-4o-mini"
TOOL_NAME = "extract_job_posting"
TOOL_DESCRIPTION = (
    "Record the structured details of the job posting. Only use information that is "
    "present in the text; use null, 'unknown' or an empty list when something is not stated."
)

SYSTEM_PROMPT = (
    "You are a precise information-extraction engine. You receive messy, unstructured "
    "job-posting text and must report its contents by calling the "
    f"`{TOOL_NAME}` function. Never invent facts that are not in the text. "
    "Normalise salaries to plain numbers (80k = 80000), use ISO 4217 currency codes, "
    "and use ISO dates (YYYY-MM-DD)."
)


# ---------------------------------------------------------------------- #
# Exceptions
# ---------------------------------------------------------------------- #
class ExtractionError(Exception):
    """Base class for all extractor errors."""


class ConfigurationError(ExtractionError):
    """Raised when the extractor is not configured correctly (e.g. missing API key)."""


class ModelOutputError(ExtractionError):
    """Raised when the model returns no function call (for example it refused)."""


class ExtractionValidationError(ExtractionError):
    """Raised when the model output still fails Pydantic validation after the retry.

    Attributes:
        attempts: Number of model calls made (always 2 when this is raised).
        errors: Structured Pydantic errors from the final attempt.
        raw_arguments: The function-call arguments from the final attempt.
        first_errors: Structured Pydantic errors from the first attempt.
    """

    def __init__(
        self,
        message: str,
        *,
        attempts: int,
        errors: list[dict[str, Any]],
        raw_arguments: str,
        first_errors: list[dict[str, Any]],
    ) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.errors = errors
        self.raw_arguments = raw_arguments
        self.first_errors = first_errors


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #
def format_validation_errors(error: ValidationError) -> str:
    """Render a Pydantic ValidationError as a readable list for the retry prompt."""
    lines = []
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"]) or "(root)"
        lines.append(f"- {location}: {item['msg']} (received: {item.get('input')!r})")
    return "\n".join(lines)


def _safe_errors(error: ValidationError) -> list[dict[str, Any]]:
    """Pydantic errors reduced to plain, serialisable values."""
    return [
        {"loc": [str(p) for p in e["loc"]], "msg": e["msg"], "type": e["type"], "input": repr(e.get("input"))}
        for e in error.errors()
    ]


def build_client(api_key: Optional[str] = None) -> OpenAI:
    """Create an OpenAI client from an explicit key or the OPENAI_API_KEY environment variable."""
    load_dotenv()
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key or key == "your_api_key_here":
        raise ConfigurationError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key, "
            "or export OPENAI_API_KEY in your shell."
        )
    return OpenAI(api_key=key)


# ---------------------------------------------------------------------- #
# Extractor
# ---------------------------------------------------------------------- #
class JobPostingExtractor:
    """Extract a validated :class:`JobPosting` from free-form text."""

    MAX_RETRIES = 1  # the assignment requires exactly one retry, never more

    def __init__(self, client: Optional[OpenAI] = None, model: Optional[str] = None) -> None:
        load_dotenv()
        self._client = client
        self.model = model or os.getenv("OPENAI_MODEL") or DEFAULT_MODEL
        # Strict function-calling tool generated directly from the Pydantic model.
        self._tool = pydantic_function_tool(JobPosting, name=TOOL_NAME, description=TOOL_DESCRIPTION)

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = build_client()
        return self._client

    # -- public API ---------------------------------------------------- #
    def extract(self, text: str) -> JobPosting:
        """Extract a JobPosting from ``text``, retrying once if validation fails.

        Raises:
            ValueError: if ``text`` is empty.
            ExtractionValidationError: if both attempts fail Pydantic validation.
            ModelOutputError: if the model does not return a function call.
            ConfigurationError: if no API key is available.
        """
        if not text or not text.strip():
            raise ValueError("Job posting text must not be empty.")

        # Attempt 1
        arguments = self._call_model(self._initial_messages(text))
        try:
            return self._validate(arguments)
        except ValidationError as first_error:
            # Attempt 2 (the one and only retry)
            return self._retry_extraction(text, arguments, first_error)

    # -- internals ----------------------------------------------------- #
    def _initial_messages(self, text: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract the job posting from this text:\n\n{text}"},
        ]

    def _call_model(self, messages: list[dict[str, str]]) -> str:
        """Call the API, forcing the extraction function, and return its raw arguments."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=[self._tool],
            tool_choice={"type": "function", "function": {"name": TOOL_NAME}},
        )
        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None)
        if not tool_calls:
            refusal = getattr(message, "refusal", None)
            detail = f" Model refusal: {refusal}" if refusal else ""
            raise ModelOutputError(f"The model did not return a function call.{detail}")
        return tool_calls[0].function.arguments

    def _validate(self, arguments: str) -> JobPosting:
        """Validate function-call arguments with Pydantic. Raises ValidationError on failure."""
        return JobPosting.model_validate_json(arguments)

    def _retry_extraction(self, text: str, bad_arguments: str, first_error: ValidationError) -> JobPosting:
        """Make the single retry call, passing the validation errors back to the model."""
        feedback = (
            "Your previous function call failed validation.\n\n"
            f"Previous arguments:\n{bad_arguments}\n\n"
            f"Validation errors:\n{format_validation_errors(first_error)}\n\n"
            "Call the function again with corrected values for the ORIGINAL job posting below. "
            "Fix every listed error and do not invent information.\n\n"
            f"Original job posting:\n{text}"
        )
        messages = self._initial_messages(text)[:1] + [{"role": "user", "content": feedback}]
        arguments = self._call_model(messages)
        try:
            return self._validate(arguments)
        except ValidationError as second_error:
            raise ExtractionValidationError(
                "Extraction failed Pydantic validation after 1 retry "
                f"({len(second_error.errors())} error(s) in final attempt):\n"
                f"{format_validation_errors(second_error)}",
                attempts=1 + self.MAX_RETRIES,
                errors=_safe_errors(second_error),
                raw_arguments=arguments,
                first_errors=_safe_errors(first_error),
            ) from second_error


def extract_job_posting(text: str, *, client: Optional[OpenAI] = None, model: Optional[str] = None) -> JobPosting:
    """Convenience wrapper: extract a validated JobPosting from messy text."""
    return JobPostingExtractor(client=client, model=model).extract(text)
