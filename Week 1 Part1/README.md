# Prompt Engineered Writing Assistant

A beginner-friendly Python command line tool that uses the **Google Gemini API** to summarize, formalize and simplify text. It is built to demonstrate core **prompt engineering** concepts: system prompts, few-shot prompting, output constraints, token logging and robust API handling.

## Project Overview

The assistant offers three writing modes, each driven by its own carefully designed system prompt:

| Mode | What it does |
|------|--------------|
| **Summarize** | Condenses text into 3-5 clear sentences |
| **Rewrite Formal** | Converts casual text into professional writing (uses few-shot prompting) |
| **Explain Simple** | Explains difficult ideas in plain language with an analogy |

## Features

- Gemini API integration (`google-generativeai`)
- Three distinct system prompts stored in `prompts.py`
- Few-shot prompting (two examples) in Rewrite Formal mode
- Token usage logging: input, output and total tokens (shown on screen and saved to `token_usage.log`)
- Retry handling with **exponential backoff** for rate limits, timeouts and API failures (`tenacity`)
- API key stored in an environment variable (`.env`)
- Professional terminal UI (`rich`)
- Friendly error messages and graceful exit (Ctrl+C / Ctrl+D)
- PEP 8 style, type hints, docstrings and explanatory comments

## Prompt Engineering Concepts Used

1. **Role prompting** - each prompt begins by assigning the model a role (editor, teacher, summarizer).
2. **System prompts** - behaviour is defined via Gemini's `system_instruction`, separate from user text.
3. **Explicit, numbered rules** - reduces ambiguity and makes behaviour testable.
4. **Output constraints** - "Return ONLY the result" removes chatty introductions.
5. **Few-shot prompting** - two worked input/output pairs teach the formal style.
6. **Temperature control** - lower for summarizing, slightly higher for explaining.

See [PROMPTS.md](PROMPTS.md) for details and [COMPARISON.md](COMPARISON.md) for a with/without few-shot comparison.

## Installation Steps

**Requirements:** Python 3.9+ and a Gemini API key.

```bash
# 1. Go into the project folder
cd prompt-writing-assistant
```

### Virtual Environment Setup

```bash
# Create the virtual environment
python -m venv venv

# Activate it
#   macOS / Linux:
source venv/bin/activate
#   Windows (PowerShell):
venv\Scripts\Activate.ps1
#   Windows (cmd):
venv\Scripts\activate.bat

# Install dependencies
pip install -r requirements.txt
```

### Gemini API Setup

1. Visit <https://aistudio.google.com/app/apikey> and create a free API key.
2. Copy the example environment file:
   ```bash
   cp .env.example .env        # Windows: copy .env.example .env
   ```
3. Open `.env` and replace the placeholder:
   ```
   GEMINI_API_KEY=your_real_key_here
   ```
4. *(Optional)* Choose a different model by adding `GEMINI_MODEL=<model-name>` to `.env`. The default is `gemini-2.5-flash`.

> Never commit your real `.env` file or share your API key.

## Running Instructions

```bash
python assistant.py
```

Choose a mode (1-3), paste or type your text, then type `END` on its own line to submit. Choose `4` to exit.

## Example Commands

```bash
python assistant.py                 # start the assistant
GEMINI_MODEL=gemini-2.5-flash python assistant.py   # macOS/Linux: pick a model for one run
cat token_usage.log                 # view logged token usage
```

## Example Outputs

> The outputs below are illustrative. Exact wording from Gemini will vary between runs.

**Menu**

```
╭─────────────────────────────────────╮
│ Prompt Engineered Writing Assistant │
╰─────────────────────────────────────╯
1. Summarize
2. Rewrite Formal
3. Explain Simple
4. Exit

Choice: 2
```

**Rewrite Formal**

```
Mode: Rewrite Formal
Paste the informal text to rewrite. Type END on a new line when finished.
hey, the meeting got moved to 3pm cuz the boss is busy. dont be late!
END

╭──────────────────── Rewrite Formal ────────────────────╮
│ Dear Team,                                             │
│                                                        │
│ Please be advised that the meeting has been            │
│ rescheduled to 3:00 PM due to the manager's prior      │
│ commitments. Kindly ensure that you arrive on time.    │
╰────────────────────────────────────────────────────────╯
                    Token Usage
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃ Input tokens ┃ Output tokens ┃ Total tokens ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━┩
│          412 │            43 │          455 │
└──────────────┴───────────────┴──────────────┘
```

Add your own real screenshots to the `screenshots/` folder before submitting.

## Error Handling

| Situation | Behaviour |
|-----------|-----------|
| Missing / placeholder API key | Clear setup instructions, then exit |
| Invalid API key | Friendly authentication message |
| Rate limit (429), timeout, 500/503/504 | Automatic retry with exponential backoff (2s, 4s, 8s, 16s; up to 5 attempts), then a clear message |
| Blocked or empty model response | Message explaining no text was returned |
| Unknown model name | Message telling you to set `GEMINI_MODEL` |
| Empty user input | Returns to the menu |
| Ctrl+C / Ctrl+D | Clean "Goodbye!" exit |

## Token Logging

After every successful request the app shows a table with **input**, **output** and **total** tokens (from Gemini's `usage_metadata`) and appends a line to `token_usage.log`:

```
2026-10-02 10:15:03,221 | mode=Rewrite Formal input=412 output=43 total=455
```

Note: some newer Gemini models use internal "thinking" tokens that count toward the total, so total may be higher than input + output. The total is taken directly from the API.

## Folder Structure

```
prompt-writing-assistant/
├── assistant.py        # CLI, Gemini connection, retries, token logging
├── prompts.py          # All system prompts (incl. few-shot examples)
├── requirements.txt    # Dependencies
├── .env.example        # Template for your API key
├── README.md           # This file
├── PROMPTS.md          # Prompt design explanation
├── COMPARISON.md       # With vs without few-shot comparison
└── screenshots/
    └── placeholder.txt
```

## Future Improvements

- Add a `--file` option to read input from text files
- Add more modes (translate, proofread, bullet points)
- Save a history of requests and responses
- Cost estimation from token counts
- Streaming responses for faster feedback
- Unit tests with a mocked Gemini client
- Migrate to the newer `google-genai` SDK (see Submission Notes)

## Submission Notes

- Tech stack follows the assignment: `google-generativeai`, `python-dotenv`, `rich`, `tenacity`.
- Google has announced `google-generativeai` as a legacy SDK; you may see a deprecation warning when running. It still works with the code provided.
- Before submitting: run the app with your own key, take screenshots into `screenshots/`, and replace the illustrative outputs in `COMPARISON.md` with your real results for extra credit.
- Do not include your real `.env` file in the submission ZIP.
