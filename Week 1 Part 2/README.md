# Structured Data Extractor with Function Calling

A Job Posting extractor that turns messy, unstructured text into a validated, strongly typed `JobPosting` object using **OpenAI native function calling** and **Pydantic v2**.

> Extraction is performed using native structured output/function calling. The application does not rely on regex-based JSON parsing.

## Project Overview

You give the program the raw text of a job advert (any format, any level of messiness). It asks an OpenAI model to report the contents by calling a function whose parameter schema is generated from the `JobPosting` Pydantic model. The returned arguments are validated by Pydantic. If validation fails, the extractor retries **once**, sending the validation errors back to the model. The result is printed as clean JSON.

Example input:

```
We're hiring a junior backend developer at TechNova.
Location: Islamabad, Pakistan.
The candidate should have 1-2 years of experience with Python,
FastAPI and PostgreSQL. Bachelor's degree preferred.
Salary is PKR 80k-120k per month.
Hybrid role. Apply by email at jobs@technova.example.
```

## Assignment Requirements

| # | Requirement | Where it is satisfied |
|---|-------------|-----------------------|
| 1 | Define a real extraction schema | `JobPosting` (plus `EmploymentType`, `WorkplaceType`, `SalaryPeriod`) in [`schema.py`](schema.py) |
| 2 | Native structured output / function calling, not regex JSON parsing | [`extractor.py`](extractor.py): `pydantic_function_tool(JobPosting, ...)` builds a strict tool; `tool_choice` forces the model to call it |
| 3 | Pydantic validation + retry once | [`extractor.py`](extractor.py): `_validate()`, `_retry_extraction()`, `MAX_RETRIES = 1`, `ExtractionValidationError` |
| 4 | At least 5 varied real-world samples | [`tests/fixtures/`](tests/fixtures/): five `.txt` inputs with saved `.json` outputs |

Submission checklist: GitHub repository, test cases (`tests/`), schema (`schema.py`), `extractor.py`, five saved input/output cases, validation-retry note ([`VALIDATION_RETRY.md`](VALIDATION_RETRY.md)).

### How an instructor can verify the function-calling requirement

1. Open `extractor.py` and find `_call_model()`. It calls `client.chat.completions.create(..., tools=[self._tool], tool_choice={"type": "function", ...})` and reads `message.tool_calls[0].function.arguments`.
2. Search the repository for `re.` / `import re`: there is no regex anywhere in the application code.
3. The model's text content is never parsed. The only parser is Pydantic's `model_validate_json` on the function-call arguments, which is the validation step itself.
4. `tests/test_extractor.py::test_request_uses_forced_strict_function_call` asserts the request carries a strict function tool built from the Pydantic model.

## Features

- Rich `JobPosting` schema: 20 fields, enums, `EmailStr`, `date`, numeric ranges, string lists
- Strict function-calling schema generated from the Pydantic model (field descriptions guide the model)
- Field-level and cross-field validation (salary range, experience range, currency requirement, URL format)
- Explicit single retry with validation feedback; custom exceptions with diagnostic details
- Beginner-friendly CLI (file or interactive input, optional output file)
- Pytest suite: schema tests, mocked retry tests, optional live API tests
- Secrets via environment variables only

## Architecture

```
Input Text
   ↓
LLM  (OpenAI chat model)
   ↓
Native Structured Output / Function Calling  (forced strict tool call)
   ↓
Pydantic  (field + cross-field validation)
   ↓  valid ──────────────→ Validated JobPosting → JSON
   ↓  invalid
Retry ONCE with errors as feedback → Pydantic → JobPosting or ExtractionValidationError
```

## Project Structure

```
structured-data-extractor/
├── README.md
├── VALIDATION_RETRY.md
├── requirements.txt
├── .env.example
├── .gitignore
├── schema.py
├── extractor.py
├── main.py
└── tests/
    ├── __init__.py
    ├── test_schema.py
    ├── test_extractor.py
    └── fixtures/
        ├── case_01_software_engineer.txt / .json
        ├── case_02_marketing_manager.txt / .json
        ├── case_03_nurse.txt / .json
        ├── case_04_data_analyst.txt / .json
        └── case_05_internship.txt / .json
```

## Installation

Requires Python 3.11 or newer.

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Then:

```bash
pip install -r requirements.txt
```

## Environment Setup

```bash
cp .env.example .env        # Windows: copy .env.example .env
```

Edit `.env`:

```
OPENAI_API_KEY=sk-...your key...
OPENAI_MODEL=gpt-4o-mini
```

`OPENAI_MODEL` can be any OpenAI chat model that supports strict function calling. `.env` is git-ignored.

## Running

Interactive (paste text, then press Ctrl+D on Linux/macOS or Ctrl+Z then Enter on Windows):

```bash
python main.py
```

From a file:

```bash
python main.py --input tests/fixtures/case_01_software_engineer.txt
```

Save the result too:

```bash
python main.py --input tests/fixtures/case_04_data_analyst.txt --output result.json
```

Help:

```bash
python main.py --help
```

Output looks like:

```json
{
  "title": "Software Engineer (Backend)",
  "company": "TechNova Pvt. Ltd.",
  "location": "Islamabad, Pakistan",
  "employment_type": "full_time",
  "workplace_type": "hybrid",
  "...": "..."
}
```

## Running Tests

```bash
pytest -q
```

The schema and retry tests need no API key or network. The `test_live_*` tests call the real OpenAI API and are skipped automatically unless `OPENAI_API_KEY` is set.

## Five Test Cases

Each case has an input (`.txt`) and a saved expected output (`.json`) in `tests/fixtures/`. The JSON files are reference outputs used by tests; the extractor never reads them.

| Case | Input style | What it exercises |
|------|-------------|-------------------|
| 01 Software Engineer | Formal posting | Company, location, experience range 2-4, monthly PKR salary range, skills, deadline, email |
| 02 Marketing Manager | Informal, lowercase chatty text | Hybrid work, many responsibilities, benefits, **no salary**, preferred skill |
| 03 Registered Nurse (ICU) | Healthcare terminology | Credentials, education, shift information, onsite, single salary figure |
| 04 Remote Data Analyst | International (EUR) | Remote, **yearly** salary, SQL/Python/Excel, application **URL**, deadline |
| 05 Web Dev Intern | Incomplete, mixed formatting | Internship, unpaid, student requirement, phone + email contact |

## Validation Retry

If Pydantic rejects the first response, the extractor sends the model its previous arguments, the exact validation errors and the original text, then validates the second response. A second failure raises `ExtractionValidationError`. Retries are capped at one. Full details: [VALIDATION_RETRY.md](VALIDATION_RETRY.md).

## Security

- The API key is read from the `OPENAI_API_KEY` environment variable (loaded from `.env` via `python-dotenv`).
- No key is stored in the code, and `.env` is listed in `.gitignore`.
- `.env.example` contains only a placeholder.

## Limitations

- Extraction quality depends on the model's output and on the quality and completeness of the source text.
- Information that is not in the text is left null or `unknown` by design, so sparse postings give sparse results.
- Dates written without a year or in ambiguous formats may be left null.
- Job text is sent to the OpenAI API; do not use it for confidential content without appropriate approval.

## Future Improvements

- Batch mode for processing a folder of postings
- Support for multiple currencies and salary normalisation
- Language detection and non-English postings
- Confidence scores and source-span citations per field
- Optional alternative providers behind the same schema
