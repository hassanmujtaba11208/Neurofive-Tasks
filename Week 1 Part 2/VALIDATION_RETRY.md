# Validation and Retry Note

This note explains how the extractor validates model output with Pydantic and why it retries exactly once.

## Why Pydantic validation is needed

The model is forced to answer through a strict function call, so the arguments it returns match the *shape* of the `JobPosting` schema (field names, types, enum values). Shape is not the same as correctness. A response can still break the rules we care about:

- an invalid email address (`"jobs at technova"`)
- `salary_min` larger than `salary_max`
- `minimum_experience_years` larger than `maximum_experience_years`
- a salary amount with no currency code
- a malformed URL or an impossible date

Pydantic is the application's validation layer. `JobPosting.model_validate_json()` runs every field and cross-field rule in `schema.py`. Nothing is returned to the caller unless it passes.

## What happens when validation fails

1. The extractor catches the Pydantic `ValidationError` from the first attempt.
2. It builds a feedback message containing the previous arguments, the list of errors (field name, message, and the received value) and the original job-posting text.
3. It calls the model a second time, again with the forced function call.
4. The new arguments are validated again.

## Why one retry is performed

Most validation failures are small slips that the model can fix once it is told exactly what is wrong (for example, swapped salary bounds). A single corrective attempt recovers these cases cheaply. The constant `JobPostingExtractor.MAX_RETRIES = 1` documents this rule.

## How the error is passed back as feedback

The retry request is `system prompt` + one user message containing:

```
Your previous function call failed validation.

Previous arguments:
<the arguments the model produced>

Validation errors:
- application_email: value is not a valid email address ... (received: 'not-an-email')

Call the function again with corrected values for the ORIGINAL job posting below. ...

Original job posting:
<the original text>
```

Because the original text is included, the model corrects the value from the source instead of guessing.

## Why retries are limited to one

- **Cost and latency:** every retry is another paid API call.
- **Predictability:** a loop could run indefinitely if the text genuinely cannot satisfy the schema.
- **Diminishing returns:** if the model cannot fix the output after seeing the exact errors, a third attempt rarely helps. It is better to report the failure.

The implementation has no loop. It is two explicit calls, so the limit cannot be exceeded by accident.

## What happens if the second attempt also fails

The extractor raises `ExtractionValidationError`. It carries:

| Attribute | Meaning |
|-----------|---------|
| `attempts` | Number of model calls made (2) |
| `errors` | Structured Pydantic errors from the final attempt |
| `first_errors` | Structured Pydantic errors from the first attempt |
| `raw_arguments` | The final function-call arguments, for debugging |

The CLI prints the message and exits with status 1. If the model returns no function call at all (for example, it refuses), `ModelOutputError` is raised instead.

## Example validation failure

First attempt arguments (abridged):

```json
{ "title": "Backend Developer", "salary_min": 120000, "salary_max": 80000, "salary_currency": "PKR" }
```

Pydantic reports:

```
salary_min must not be greater than salary_max (120000.0 > 80000.0)
```

## Example retry flow

```
Attempt 1: model returns salary_min=120000, salary_max=80000
           -> Pydantic: FAIL (salary_min > salary_max)
Retry:     model receives the arguments, the error and the original text
           model returns salary_min=80000, salary_max=120000
           -> Pydantic: PASS -> JobPosting returned
```

If the retry had also failed, `ExtractionValidationError(attempts=2, ...)` would be raised.

## How it is tested

`tests/test_extractor.py` uses a scripted stand-in for the OpenAI client so no API call is made. The tests prove that:

- a valid first response makes exactly 1 call (no retry)
- an invalid first response makes exactly 2 calls and returns the corrected result
- the retry request contains the original text and the validation errors
- two failures raise `ExtractionValidationError` after exactly 2 calls, never 3

The extractor code under test is the real implementation. Only the network client is replaced.
