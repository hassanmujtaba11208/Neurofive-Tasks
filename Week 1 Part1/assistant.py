"""Prompt Engineered Writing Assistant - a Gemini-powered command line tool.

Modes:
    1. Summarize
    2. Rewrite Formal (few-shot prompting)
    3. Explain Simple

Highlights:
    * Distinct system prompt per mode (see ``prompts.py``)
    * Token usage logging (input / output / total)
    * Retry with exponential backoff (rate limits, timeouts, API failures)
    * API key loaded from an environment variable (.env file)
    * Rich terminal interface
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from typing import Optional

import google.generativeai as genai
from dotenv import load_dotenv
from google.api_core import exceptions as gexc
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from prompts import EXPLAIN_SIMPLE_PROMPT, REWRITE_FORMAL_PROMPT, SUMMARIZE_PROMPT

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# Model can be changed without editing code: set GEMINI_MODEL in your .env file.
DEFAULT_MODEL = "gemini-2.5-flash"
REQUEST_TIMEOUT_SECONDS = 60
MAX_RETRY_ATTEMPTS = 5
TOKEN_LOG_FILE = "token_usage.log"

console = Console()

# Token usage is written to a log file (not the screen) for later review.
logging.basicConfig(
    filename=TOKEN_LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
)
logger = logging.getLogger("writing-assistant")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Mode:
    """Describes one assistant mode."""

    label: str
    system_prompt: str
    temperature: float  # lower = more predictable, higher = more creative
    input_hint: str


@dataclass(frozen=True)
class TokenUsage:
    """Token counts reported by the Gemini API for one request."""

    input_tokens: int
    output_tokens: int
    total_tokens: int


class EmptyResponseError(Exception):
    """Raised when Gemini returns no usable text (e.g. blocked by safety filters)."""


# Menu choice -> mode configuration.
MODES: dict[str, Mode] = {
    "1": Mode("Summarize", SUMMARIZE_PROMPT, 0.3, "Paste the text you want summarized."),
    "2": Mode("Rewrite Formal", REWRITE_FORMAL_PROMPT, 0.4, "Paste the informal text to rewrite."),
    "3": Mode("Explain Simple", EXPLAIN_SIMPLE_PROMPT, 0.6, "Paste the text or concept to explain."),
}

# Errors worth retrying: they are usually temporary.
RETRYABLE_ERRORS = (
    gexc.ResourceExhausted,    # rate limit / quota (gRPC)
    gexc.TooManyRequests,      # HTTP 429
    gexc.DeadlineExceeded,     # timeout
    gexc.GatewayTimeout,       # HTTP 504
    gexc.ServiceUnavailable,   # HTTP 503
    gexc.InternalServerError,  # HTTP 500
    gexc.Aborted,
    TimeoutError,
    ConnectionError,
)


# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------
def load_api_key() -> str:
    """Read GEMINI_API_KEY from the environment (.env is loaded automatically)."""
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "your_api_key_here":
        console.print(
            Panel(
                "[bold red]GEMINI_API_KEY is missing.[/bold red]\n\n"
                "1. Copy [cyan].env.example[/cyan] to [cyan].env[/cyan]\n"
                "2. Put your real key in it: GEMINI_API_KEY=...\n"
                "3. Get a free key at https://aistudio.google.com/app/apikey",
                title="Configuration error",
                border_style="red",
            )
        )
        sys.exit(1)
    return api_key


def show_menu() -> None:
    """Print the main menu."""
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]Prompt Engineered Writing Assistant[/bold cyan]",
            border_style="cyan",
        )
    )
    console.print("[bold]1.[/bold] Summarize")
    console.print("[bold]2.[/bold] Rewrite Formal")
    console.print("[bold]3.[/bold] Explain Simple")
    console.print("[bold]4.[/bold] Exit\n")


def read_multiline_input(hint: str) -> str:
    """Read multi-line text from the user. A line containing only END finishes input."""
    console.print(f"[dim]{hint} Type [bold]END[/bold] on a new line when finished.[/dim]")
    lines: list[str] = []
    while True:
        line = input()
        if line.strip().upper() == "END":
            break
        lines.append(line)
    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Gemini API call with retry handling
# ---------------------------------------------------------------------------
def _log_retry(retry_state: RetryCallState) -> None:
    """Tell the user a retry is about to happen (called by tenacity)."""
    error = retry_state.outcome.exception() if retry_state.outcome else None
    wait_seconds = retry_state.next_action.sleep if retry_state.next_action else 0
    console.print(
        f"[yellow]Temporary error ({type(error).__name__}). "
        f"Retry {retry_state.attempt_number}/{MAX_RETRY_ATTEMPTS - 1} "
        f"in {wait_seconds:.0f}s...[/yellow]"
    )
    logger.warning("Retry %d after %s", retry_state.attempt_number, type(error).__name__)


@retry(
    retry=retry_if_exception_type(RETRYABLE_ERRORS),
    wait=wait_exponential(multiplier=2, min=2, max=30),  # 2s, 4s, 8s, 16s...
    stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
    before_sleep=_log_retry,
    reraise=True,  # after the final failure, raise the original error
)
def call_gemini(mode: Mode, user_text: str, model_name: str) -> genai.types.GenerateContentResponse:
    """Send one request to Gemini. Retries automatically on temporary errors."""
    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=mode.system_prompt,  # the mode's system prompt
        generation_config=genai.GenerationConfig(temperature=mode.temperature),
    )
    return model.generate_content(
        user_text,
        request_options={"timeout": REQUEST_TIMEOUT_SECONDS},
    )


def extract_text(response: genai.types.GenerateContentResponse) -> str:
    """Return the response text or raise EmptyResponseError if there is none."""
    try:
        text = response.text
    except ValueError as exc:  # raised when the response was blocked or empty
        raise EmptyResponseError(
            "Gemini returned no text. The content may have been blocked by safety filters."
        ) from exc
    if not text or not text.strip():
        raise EmptyResponseError("Gemini returned an empty response.")
    return text.strip()


def get_token_usage(response: genai.types.GenerateContentResponse) -> Optional[TokenUsage]:
    """Read token counts from the response metadata, if available."""
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return None
    return TokenUsage(
        input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
        output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
        total_tokens=getattr(usage, "total_token_count", 0) or 0,
    )


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------
def show_result(mode: Mode, text: str) -> None:
    """Display the model's answer in a panel."""
    console.print()
    console.print(Panel(text, title=f"[bold green]{mode.label}[/bold green]", border_style="green"))


def show_and_log_tokens(mode: Mode, usage: Optional[TokenUsage]) -> None:
    """Show a token usage table and write the same numbers to the log file."""
    if usage is None:
        console.print("[dim]Token usage was not reported for this request.[/dim]")
        return

    table = Table(title="Token Usage", border_style="blue")
    table.add_column("Input tokens", justify="right")
    table.add_column("Output tokens", justify="right")
    table.add_column("Total tokens", justify="right")
    table.add_row(str(usage.input_tokens), str(usage.output_tokens), str(usage.total_tokens))
    console.print(table)

    logger.info(
        "mode=%s input=%d output=%d total=%d",
        mode.label, usage.input_tokens, usage.output_tokens, usage.total_tokens,
    )


# ---------------------------------------------------------------------------
# Request handling with error handling
# ---------------------------------------------------------------------------
def handle_request(mode: Mode, user_text: str, model_name: str) -> None:
    """Run one request end to end and show friendly messages for any error."""
    try:
        with console.status("[bold cyan]Thinking...[/bold cyan]"):
            response = call_gemini(mode, user_text, model_name)
        show_result(mode, extract_text(response))
        show_and_log_tokens(mode, get_token_usage(response))

    except EmptyResponseError as exc:
        console.print(f"[red]{exc}[/red]")
    except (gexc.PermissionDenied, gexc.Unauthenticated):
        console.print("[red]Authentication failed. Check that your GEMINI_API_KEY is correct.[/red]")
    except gexc.InvalidArgument as exc:
        # Gemini reports a bad API key as InvalidArgument as well.
        console.print(f"[red]Invalid request or API key: {exc.message}[/red]")
    except gexc.NotFound:
        console.print(
            f"[red]Model '{model_name}' was not found. "
            "Set a valid GEMINI_MODEL in your .env file.[/red]"
        )
    except (gexc.ResourceExhausted, gexc.TooManyRequests):
        console.print("[red]Rate limit still exceeded after several retries. Wait a minute and try again.[/red]")
    except (gexc.DeadlineExceeded, gexc.GatewayTimeout, TimeoutError):
        console.print("[red]The request kept timing out. Check your connection and try again.[/red]")
    except gexc.GoogleAPIError as exc:
        console.print(f"[red]Gemini API error: {exc}[/red]")
        logger.error("API error: %s", exc)
    except ConnectionError:
        console.print("[red]Network error. Please check your internet connection.[/red]")


# ---------------------------------------------------------------------------
# Main program
# ---------------------------------------------------------------------------
def main() -> None:
    """Configure the API and run the interactive menu loop."""
    genai.configure(api_key=load_api_key())
    model_name = os.getenv("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL

    while True:
        show_menu()
        choice = Prompt.ask("Choice", choices=["1", "2", "3", "4"], show_choices=False)

        if choice == "4":
            console.print("[bold cyan]Goodbye![/bold cyan]")
            break

        mode = MODES[choice]
        console.print(f"\n[bold]Mode:[/bold] {mode.label}")
        user_text = read_multiline_input(mode.input_hint)

        if not user_text:
            console.print("[yellow]No text entered. Returning to menu.[/yellow]")
            continue

        handle_request(mode, user_text, model_name)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        # Ctrl+C / Ctrl+D exit cleanly instead of showing a traceback.
        console.print("\n[bold cyan]Goodbye![/bold cyan]")
        sys.exit(0)
