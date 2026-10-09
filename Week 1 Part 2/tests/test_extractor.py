"""Tests for the extractor.

* Retry/validation tests use a scripted stand-in for the OpenAI *client* so they
  are fast and free. The extractor code under test is the real implementation.
* ``test_live_*`` tests call the real OpenAI API and are skipped automatically
  when OPENAI_API_KEY is not set.
"""

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from extractor import (
    TOOL_NAME,
    ExtractionValidationError,
    JobPostingExtractor,
    ModelOutputError,
    extract_job_posting,
)
from schema import EmploymentType, JobPosting, SalaryPeriod, WorkplaceType

FIXTURES = Path(__file__).parent / "fixtures"
CASES = sorted(p.stem for p in FIXTURES.glob("case_*.txt"))


# ---------------------------------------------------------------------- #
# Test double for the OpenAI client (test code only)
# ---------------------------------------------------------------------- #
class ScriptedClient:
    """Returns pre-scripted function-call arguments, one per API call, and records the requests."""

    def __init__(self, *argument_strings, refuse=False):
        self._queue = list(argument_strings)
        self._refuse = refuse
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._refuse:
            message = SimpleNamespace(tool_calls=None, refusal="I cannot help with that.")
        else:
            arguments = self._queue.pop(0)
            tool_call = SimpleNamespace(function=SimpleNamespace(name=TOOL_NAME, arguments=arguments))
            message = SimpleNamespace(tool_calls=[tool_call], refusal=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def args(**overrides) -> str:
    data = {"title": "Backend Developer", "company": "TechNova"}
    data.update(overrides)
    return json.dumps(data)


def extractor_with(client) -> JobPostingExtractor:
    return JobPostingExtractor(client=client, model="test-model")


# ---------------------------------------------------------------------- #
# Native function calling is used
# ---------------------------------------------------------------------- #
def test_request_uses_forced_strict_function_call():
    client = ScriptedClient(args())
    extractor_with(client).extract("We are hiring a backend developer at TechNova.")

    request = client.calls[0]
    assert request["model"] == "test-model"
    tool = request["tools"][0]
    assert tool["type"] == "function"
    assert tool["function"]["name"] == TOOL_NAME
    assert tool["function"]["strict"] is True
    # The schema sent to the model is generated from the Pydantic model.
    assert set(tool["function"]["parameters"]["properties"]) == set(JobPosting.model_fields)
    assert request["tool_choice"] == {"type": "function", "function": {"name": TOOL_NAME}}
    assert "response_format" not in request


# ---------------------------------------------------------------------- #
# Successful extraction
# ---------------------------------------------------------------------- #
@pytest.mark.parametrize("case", CASES)
def test_valid_response_returns_jobposting_without_retry(case):
    expected = (FIXTURES / f"{case}.json").read_text(encoding="utf-8")
    text = (FIXTURES / f"{case}.txt").read_text(encoding="utf-8")
    client = ScriptedClient(expected)

    result = extractor_with(client).extract(text)

    assert isinstance(result, JobPosting)
    assert result.title
    assert len(client.calls) == 1


def test_extract_job_posting_function():
    result = extract_job_posting("hiring", client=ScriptedClient(args()), model="test-model")
    assert isinstance(result, JobPosting)
    assert result.company == "TechNova"


def test_empty_text_rejected_before_any_api_call():
    client = ScriptedClient()
    with pytest.raises(ValueError):
        extractor_with(client).extract("   \n ")
    assert client.calls == []


def test_missing_function_call_raises_model_output_error():
    with pytest.raises(ModelOutputError, match="refusal"):
        extractor_with(ScriptedClient(refuse=True)).extract("some text")


# ---------------------------------------------------------------------- #
# Validation + retry (the key requirement)
# ---------------------------------------------------------------------- #
def test_retries_exactly_once_after_validation_failure_then_succeeds():
    bad = args(application_email="not-an-email", salary_min=500, salary_max=100, salary_currency="USD")
    good = args(application_email="jobs@technova.example", salary_min=100, salary_max=500, salary_currency="USD")
    client = ScriptedClient(bad, good)

    result = extractor_with(client).extract("Backend developer at TechNova. Apply jobs@technova.example")

    assert len(client.calls) == 2  # one initial call + exactly one retry
    assert result.application_email == "jobs@technova.example"
    assert result.salary_min == 100


def test_retry_prompt_contains_original_text_and_validation_feedback():
    original = "Backend developer at TechNova. Apply jobs@technova.example"
    client = ScriptedClient(args(application_email="not-an-email"), args())

    extractor_with(client).extract(original)

    retry_messages = client.calls[1]["messages"]
    retry_text = "\n".join(m["content"] for m in retry_messages)
    assert original in retry_text
    assert "application_email" in retry_text  # which field failed
    assert "not-an-email" in retry_text  # the bad value the model produced
    assert "failed validation" in retry_text


def test_raises_clear_error_when_second_attempt_also_fails():
    client = ScriptedClient(args(application_email="bad-1"), args(application_email="bad-2"))

    with pytest.raises(ExtractionValidationError) as excinfo:
        extractor_with(client).extract("Backend developer")

    assert len(client.calls) == 2  # never a third call
    error = excinfo.value
    assert error.attempts == 2
    assert error.errors[0]["loc"] == ["application_email"]
    assert error.first_errors[0]["loc"] == ["application_email"]
    assert "bad-2" in error.raw_arguments
    assert "application_email" in str(error)


def test_no_retry_when_first_response_is_valid():
    client = ScriptedClient(args())
    extractor_with(client).extract("Backend developer")
    assert len(client.calls) == 1


def test_max_retries_constant_is_one():
    assert JobPostingExtractor.MAX_RETRIES == 1


def test_unparseable_arguments_also_trigger_the_single_retry():
    client = ScriptedClient("{not valid json", args())
    result = extractor_with(client).extract("Backend developer")
    assert len(client.calls) == 2
    assert isinstance(result, JobPosting)


# ---------------------------------------------------------------------- #
# Live API tests (skipped without a key)
# ---------------------------------------------------------------------- #
live = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "your_api_key_here",
    reason="OPENAI_API_KEY not set; skipping live OpenAI tests",
)


@live
@pytest.mark.parametrize("case", CASES)
def test_live_extraction_matches_key_fields(case):
    text = (FIXTURES / f"{case}.txt").read_text(encoding="utf-8")
    expected = JobPosting.model_validate_json((FIXTURES / f"{case}.json").read_text(encoding="utf-8"))

    result = extract_job_posting(text)

    assert isinstance(result, JobPosting)
    assert result.title
    assert result.employment_type == expected.employment_type
    assert result.workplace_type == expected.workplace_type
    assert result.salary_period == expected.salary_period
    assert result.application_email == expected.application_email
    assert result.application_deadline == expected.application_deadline
    assert (result.salary_min is None) == (expected.salary_min is None)


@live
def test_live_readme_example():
    text = (
        "We're hiring a junior backend developer at TechNova.\n"
        "Location: Islamabad, Pakistan.\n"
        "The candidate should have 1-2 years of experience with Python,\n"
        "FastAPI and PostgreSQL. Bachelor's degree preferred.\n"
        "Salary is PKR 80k-120k per month.\n"
        "Hybrid role. Apply by email at jobs@technova.example."
    )
    result = extract_job_posting(text)
    assert result.company == "TechNova"
    assert result.workplace_type is WorkplaceType.HYBRID
    assert (result.salary_min, result.salary_max, result.salary_currency) == (80000, 120000, "PKR")
    assert result.salary_period is SalaryPeriod.MONTHLY
    assert (result.minimum_experience_years, result.maximum_experience_years) == (1, 2)
    assert result.employment_type in (EmploymentType.FULL_TIME, EmploymentType.UNKNOWN)
