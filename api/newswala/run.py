#!/usr/bin/env python3
"""
NewsWala — CLI Runner

Usage:
    python -m newswala.run                    # Run for today
    python -m newswala.run --date 2025-10-24  # Run for a specific date
    python -m newswala.run --json-only        # Output raw JSON only (no render)
    python -m newswala.run --save             # Save output to newswala_output_YYYY-MM-DD.json

Environment:
    ANTHROPIC_API_KEY   required — your Anthropic API key
"""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="NewsWala — Daily family news digest agent system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Date to run for (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print only the raw JSON output (no pretty render).",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save the JSON output to a file.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress messages.",
    )
    args = parser.parse_args()

    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ Error: ANTHROPIC_API_KEY environment variable is not set.", file=sys.stderr)
        print("   Set it with: export ANTHROPIC_API_KEY=your-key-here", file=sys.stderr)
        sys.exit(1)

    run_date = args.date or date.today().isoformat()
    verbose = not args.quiet and not args.json_only

    # Import here so the CLI is fast to import even without anthropic installed
    from .supervisor import newswala

    try:
        package = newswala(run_date=run_date, verbose=verbose)
    except KeyboardInterrupt:
        print("\n\n⚡ Interrupted.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ NewsWala failed: {e}", file=sys.stderr)
        raise

    # Output
    output = {k: v for k, v in package.items() if k != "_rendered"}

    if args.json_only:
        print(json.dumps(output, indent=2, ensure_ascii=False))
    elif not verbose:
        # quiet mode: just print the WhatsApp message
        wa = output.get("whatsapp_output", {})
        print("\n── WHATSAPP MESSAGE ──")
        print(wa.get("main_message", ""))
        print("\n── IMAGE PROMPT ──")
        print(output.get("image_output", {}).get("image_prompt", ""))

    if args.save:
        filename = f"newswala_output_{run_date}.json"
        path = Path(filename)
        path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n💾 Output saved to {filename}")

    return output


if __name__ == "__main__":
    main()
