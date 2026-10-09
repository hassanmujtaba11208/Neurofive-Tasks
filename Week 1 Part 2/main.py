"""Command-line interface for the Job Posting Structured Data Extractor."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from extractor import (
    ConfigurationError,
    ExtractionValidationError,
    JobPostingExtractor,
    ModelOutputError,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Extract structured, validated JSON from a messy job posting using "
        "OpenAI function calling and Pydantic.",
        epilog="Examples:\n"
        "  python main.py                                   # paste text interactively\n"
        "  python main.py --input tests/fixtures/case_01_software_engineer.txt\n"
        "  python main.py --input posting.txt --output result.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-i", "--input", type=Path, help="path to a text file containing the job posting")
    parser.add_argument("-o", "--output", type=Path, help="write the JSON result to this file as well as printing it")
    parser.add_argument("-m", "--model", help="OpenAI model to use (default: OPENAI_MODEL from .env)")
    return parser


def read_text(path: Path | None) -> str:
    if path is not None:
        return path.read_text(encoding="utf-8")
    if sys.stdin.isatty():
        end_key = "Ctrl+Z then Enter" if sys.platform.startswith("win") else "Ctrl+D"
        print(f"Paste the job posting below, then press {end_key} on a new line to finish:\n", file=sys.stderr)
    return sys.stdin.read()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        text = read_text(args.input)
    except OSError as exc:
        print(f"Error: cannot read input file: {exc}", file=sys.stderr)
        return 2

    if not text.strip():
        print("Error: no job posting text was provided.", file=sys.stderr)
        return 2

    try:
        posting = JobPostingExtractor(model=args.model).extract(text)
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    except ExtractionValidationError as exc:
        print(f"Extraction failed after {exc.attempts} attempts.\n{exc}", file=sys.stderr)
        return 1
    except ModelOutputError as exc:
        print(f"Model error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # network/auth/rate-limit errors from the API client
        print(f"API error ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 1

    output = posting.model_dump_json(indent=2)
    print(output)
    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")
        print(f"\nSaved to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
