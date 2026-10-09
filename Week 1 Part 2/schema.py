"""Pydantic schema for the Job Posting Structured Data Extractor.

This module contains only data definitions: enums, the ``JobPosting`` model,
field descriptions and validation rules. It has no knowledge of the LLM or of
the extraction logic (see ``extractor.py``), so it can be reused anywhere.

The field descriptions are sent to the model as part of the function/tool
schema, so they are written as instructions for the model as well as
documentation for humans.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class EmploymentType(str, Enum):
    """Contract type of the position."""

    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    TEMPORARY = "temporary"
    FREELANCE = "freelance"
    UNKNOWN = "unknown"


class WorkplaceType(str, Enum):
    """Where the work is performed."""

    ONSITE = "onsite"
    HYBRID = "hybrid"
    REMOTE = "remote"
    UNKNOWN = "unknown"


class SalaryPeriod(str, Enum):
    """The time period a salary figure refers to."""

    HOURLY = "hourly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    UNKNOWN = "unknown"


MAX_EXPERIENCE_YEARS = 60


class JobPosting(BaseModel):
    """A structured representation of a single job posting."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(
        description="Job title exactly as the role is named in the posting, e.g. 'Senior Backend Engineer'."
    )
    company: Optional[str] = Field(
        default=None,
        description="Name of the hiring company or organisation. Null if the text does not name one.",
    )
    location: Optional[str] = Field(
        default=None,
        description="Physical location of the job as 'City, Country' when available. "
        "Null for fully remote roles that name no location.",
    )
    employment_type: EmploymentType = Field(
        default=EmploymentType.UNKNOWN,
        description="Contract type. Use 'unknown' if the text does not state or clearly imply it.",
    )
    workplace_type: WorkplaceType = Field(
        default=WorkplaceType.UNKNOWN,
        description="onsite, hybrid or remote. Use 'unknown' if the text does not state it.",
    )
    description: Optional[str] = Field(
        default=None,
        description="One or two sentence neutral summary of the role. Do not invent details.",
    )
    responsibilities: list[str] = Field(
        default_factory=list,
        description="Day-to-day duties, one short item per list entry. Empty list if none are stated.",
    )
    required_skills: list[str] = Field(
        default_factory=list,
        description="Skills, tools, languages or certifications that are mandatory. "
        "One item per entry, e.g. 'Python', 'FastAPI'.",
    )
    preferred_skills: list[str] = Field(
        default_factory=list,
        description="Skills described as preferred, a plus, nice to have or an advantage.",
    )
    education: Optional[str] = Field(
        default=None,
        description="Education requirement as written, e.g. \"Bachelor's degree in Nursing\". Null if absent.",
    )
    minimum_experience_years: Optional[float] = Field(
        default=None,
        description="Minimum years of experience required. Convert months to years (6 months = 0.5). "
        "Null if not stated.",
    )
    maximum_experience_years: Optional[float] = Field(
        default=None,
        description="Upper end of an experience range such as '1-2 years' (here 2). "
        "Null if no upper bound is stated.",
    )
    salary_min: Optional[float] = Field(
        default=None,
        description="Lower bound of the salary as a plain number with no currency symbol "
        "(80k becomes 80000). Null if no salary is stated.",
    )
    salary_max: Optional[float] = Field(
        default=None,
        description="Upper bound of the salary as a plain number. If only one figure is given, "
        "use it for both salary_min and salary_max. Null if no salary is stated.",
    )
    salary_currency: Optional[str] = Field(
        default=None,
        description="Three-letter ISO 4217 currency code in capitals, e.g. 'PKR', 'USD', 'EUR'. "
        "Null if no salary is stated.",
    )
    salary_period: SalaryPeriod = Field(
        default=SalaryPeriod.UNKNOWN,
        description="Period the salary figures refer to: hourly, monthly or yearly. "
        "Use 'unknown' if there is no salary or the period is not stated.",
    )
    application_email: Optional[EmailStr] = Field(
        default=None,
        description="Email address to send applications to. Null if none is given.",
    )
    application_url: Optional[str] = Field(
        default=None,
        description="Full http(s) URL of the application page. Null if none is given.",
    )
    application_deadline: Optional[date] = Field(
        default=None,
        description="Application deadline as an ISO date (YYYY-MM-DD). "
        "Null if no deadline is stated or the date is ambiguous.",
    )
    benefits: list[str] = Field(
        default_factory=list,
        description="Perks and benefits offered (health insurance, paid leave, etc.), one per entry.",
    )

    # ------------------------------------------------------------------ #
    # Field validators
    # ------------------------------------------------------------------ #
    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be empty")
        return value

    @field_validator("responsibilities", "required_skills", "preferred_skills", "benefits")
    @classmethod
    def _clean_string_list(cls, values: list[str]) -> list[str]:
        """Strip whitespace, drop blank entries and remove case-insensitive duplicates."""
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in values:
            item = item.strip()
            if item and item.lower() not in seen:
                seen.add(item.lower())
                cleaned.append(item)
        return cleaned

    @field_validator("minimum_experience_years", "maximum_experience_years")
    @classmethod
    def _experience_in_range(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return value
        if not 0 <= value <= MAX_EXPERIENCE_YEARS:
            raise ValueError(f"experience years must be between 0 and {MAX_EXPERIENCE_YEARS}, got {value}")
        return value

    @field_validator("salary_min", "salary_max")
    @classmethod
    def _salary_not_negative(cls, value: Optional[float]) -> Optional[float]:
        if value is not None and value < 0:
            raise ValueError(f"salary must not be negative, got {value}")
        return value

    @field_validator("salary_currency")
    @classmethod
    def _currency_code(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip().upper()
        if len(value) != 3 or not value.isalpha():
            raise ValueError(f"salary_currency must be a 3-letter ISO 4217 code such as 'USD', got '{value}'")
        return value

    @field_validator("application_url")
    @classmethod
    def _url_is_http(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not (value.startswith("http://") or value.startswith("https://")) or " " in value or "." not in value:
            raise ValueError(f"application_url must be a full http(s) URL, got '{value}'")
        return value

    # ------------------------------------------------------------------ #
    # Cross-field validators
    # ------------------------------------------------------------------ #
    @model_validator(mode="after")
    def _ranges_are_consistent(self) -> "JobPosting":
        if (
            self.minimum_experience_years is not None
            and self.maximum_experience_years is not None
            and self.minimum_experience_years > self.maximum_experience_years
        ):
            raise ValueError(
                "minimum_experience_years must not be greater than maximum_experience_years "
                f"({self.minimum_experience_years} > {self.maximum_experience_years})"
            )
        if self.salary_min is not None and self.salary_max is not None and self.salary_min > self.salary_max:
            raise ValueError(f"salary_min must not be greater than salary_max ({self.salary_min} > {self.salary_max})")
        has_salary = self.salary_min is not None or self.salary_max is not None
        if has_salary and self.salary_currency is None:
            raise ValueError("salary_currency is required when a salary amount is given")
        return self
