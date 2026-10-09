"""Unit tests for the JobPosting Pydantic schema."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from schema import EmploymentType, JobPosting, SalaryPeriod, WorkplaceType

FIXTURES = Path(__file__).parent / "fixtures"


def make(**overrides):
    data = {"title": "Backend Developer"}
    data.update(overrides)
    return JobPosting(**data)


def test_valid_minimal_posting_uses_defaults():
    posting = make()
    assert posting.title == "Backend Developer"
    assert posting.employment_type is EmploymentType.UNKNOWN
    assert posting.workplace_type is WorkplaceType.UNKNOWN
    assert posting.salary_period is SalaryPeriod.UNKNOWN
    assert posting.required_skills == []


def test_valid_full_posting():
    posting = make(
        company="TechNova",
        location="Islamabad, Pakistan",
        employment_type="full_time",
        workplace_type="hybrid",
        minimum_experience_years=1,
        maximum_experience_years=2,
        salary_min=80000,
        salary_max=120000,
        salary_currency="pkr",
        salary_period="monthly",
        application_email="jobs@technova.example",
        application_deadline="2026-12-01",
    )
    assert posting.salary_currency == "PKR"
    assert str(posting.application_deadline) == "2026-12-01"


def test_title_is_required():
    with pytest.raises(ValidationError):
        JobPosting()


def test_blank_title_rejected():
    with pytest.raises(ValidationError):
        make(title="   ")


@pytest.mark.parametrize("bad", ["not-an-email", "jobs@", "@technova.example", "jobs technova.example"])
def test_invalid_email_rejected(bad):
    with pytest.raises(ValidationError):
        make(application_email=bad)


def test_negative_salary_rejected():
    with pytest.raises(ValidationError):
        make(salary_min=-5, salary_currency="USD")


def test_salary_min_greater_than_max_rejected():
    with pytest.raises(ValidationError, match="salary_min"):
        make(salary_min=200, salary_max=100, salary_currency="USD")


def test_salary_requires_currency():
    with pytest.raises(ValidationError, match="salary_currency"):
        make(salary_min=100, salary_max=200)


@pytest.mark.parametrize("bad", ["US", "DOLLARS", "12$", "P K"])
def test_bad_currency_code_rejected(bad):
    with pytest.raises(ValidationError):
        make(salary_min=1, salary_max=2, salary_currency=bad)


def test_negative_experience_rejected():
    with pytest.raises(ValidationError):
        make(minimum_experience_years=-1)


def test_absurd_experience_rejected():
    with pytest.raises(ValidationError):
        make(maximum_experience_years=500)


def test_min_experience_greater_than_max_rejected():
    with pytest.raises(ValidationError, match="minimum_experience_years"):
        make(minimum_experience_years=5, maximum_experience_years=2)


@pytest.mark.parametrize(
    "field,value",
    [("employment_type", "weekend_only"), ("workplace_type", "moon"), ("salary_period", "weekly")],
)
def test_invalid_enum_values_rejected(field, value):
    with pytest.raises(ValidationError):
        make(**{field: value})


def test_invalid_deadline_rejected():
    with pytest.raises(ValidationError):
        make(application_deadline="31/13/2026")


def test_application_url_must_be_http():
    with pytest.raises(ValidationError):
        make(application_url="ftp://example.com/job")
    assert make(application_url="https://example.com/jobs/1").application_url == "https://example.com/jobs/1"


def test_string_lists_are_cleaned_and_deduplicated():
    posting = make(required_skills=[" Python ", "python", "", "SQL"])
    assert posting.required_skills == ["Python", "SQL"]


def test_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        make(favourite_colour="blue")


def test_json_roundtrip():
    posting = make(company="Acme", salary_min=1, salary_max=2, salary_currency="USD")
    assert JobPosting.model_validate_json(posting.model_dump_json()) == posting


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*.json")), ids=lambda p: p.stem)
def test_saved_fixture_outputs_match_schema(path):
    posting = JobPosting.model_validate(json.loads(path.read_text(encoding="utf-8")))
    assert isinstance(posting, JobPosting)
