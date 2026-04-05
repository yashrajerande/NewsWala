#!/usr/bin/env python3
"""
NewsWala — CLI Runner

Usage:
    python newswala.py                        # Run for today, print to terminal
    python newswala.py --telegram             # Run + send to Telegram
    python newswala.py --setup-telegram       # Test Telegram connection only
    python newswala.py --date 2025-10-24      # Run for a specific date
    python newswala.py --json-only            # Raw JSON output only
    python newswala.py --save                 # Save JSON to file

Environment variables required:
    ANTHROPIC_API_KEY       Your Anthropic API key
    TELEGRAM_BOT_TOKEN      Your Telegram bot token (from @BotFather)
    TELEGRAM_CHAT_ID        Your Telegram chat ID

Quick Telegram setup:
    1. Open Telegram → search @BotFather → /newbot → follow prompts → copy token
    2. Start a chat with your bot
    3. Visit https://api.telegram.org/bot<TOKEN>/getUpdates → find your chat ID
    4. export TELEGRAM_BOT_TOKEN=...  TELEGRAM_CHAT_ID=...
    5. python newswala.py --setup-telegram     (sends a test message)
    6. python newswala.py --telegram           (runs the full digest)
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
        "--telegram",
        action="store_true",
        help="Send the digest to Telegram after generating it.",
    )
    parser.add_argument(
        "--setup-telegram",
        action="store_true",
        dest="setup_telegram",
        help="Send a test message to verify Telegram bot is configured. Does not run the full pipeline.",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        dest="json_only",
        help="Print only the raw JSON output (no pretty render).",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save the JSON output to newswala_output_YYYY-MM-DD.json.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress messages (useful for scheduled runs).",
    )
    args = parser.parse_args()

    # ── Telegram setup test (no API key needed) ──────────────────────────────
    if args.setup_telegram:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            print("❌ TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set.", file=sys.stderr)
            print("\nQuick setup:", file=sys.stderr)
            print("  1. Open Telegram → @BotFather → /newbot → copy token", file=sys.stderr)
            print("  2. Start a chat with your bot", file=sys.stderr)
            print("  3. Visit https://api.telegram.org/bot<TOKEN>/getUpdates", file=sys.stderr)
            print("     Find 'chat':{'id': XXXXXXX} → that's your CHAT_ID", file=sys.stderr)
            print("  4. export TELEGRAM_BOT_TOKEN=...  TELEGRAM_CHAT_ID=...", file=sys.stderr)
            sys.exit(1)
        from .telegram_sender import send_setup_instructions
        send_setup_instructions(token, chat_id)
        return

    # ── Check Anthropic API key ──────────────────────────────────────────────
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY environment variable is not set.", file=sys.stderr)
        print("   export ANTHROPIC_API_KEY=sk-ant-...", file=sys.stderr)
        sys.exit(1)

    # ── Run the pipeline ─────────────────────────────────────────────────────
    run_date = args.date or date.today().isoformat()
    verbose = not args.quiet and not args.json_only

    from .supervisor import newswala

    try:
        package = newswala(run_date=run_date, verbose=verbose)
    except KeyboardInterrupt:
        print("\n\n⚡ Interrupted.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ NewsWala pipeline failed: {e}", file=sys.stderr)
        raise

    output = {k: v for k, v in package.items() if k != "_rendered"}

    # ── Terminal output ──────────────────────────────────────────────────────
    if args.json_only:
        print(json.dumps(output, indent=2, ensure_ascii=False))
    elif args.quiet:
        # Scheduled/silent mode: just print the WhatsApp message to stdout
        wa = output.get("whatsapp_output", {})
        print(wa.get("main_message", ""))

    # ── Save to file ─────────────────────────────────────────────────────────
    if args.save:
        filename = f"newswala_output_{run_date}.json"
        Path(filename).write_text(
            json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"\n💾 Saved to {filename}")

    # ── Telegram delivery ────────────────────────────────────────────────────
    if args.telegram:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            print(
                "\n⚠️  Telegram not configured — skipping delivery.\n"
                "   Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID, then run:\n"
                "   python newswala.py --setup-telegram",
                file=sys.stderr,
            )
        else:
            if verbose:
                print("\n📲 Sending to Telegram...")
            from .telegram_sender import send_digest
            try:
                ok = send_digest(output, token=token, chat_id=chat_id)
                if verbose:
                    print("✅ Digest sent to Telegram!" if ok else "⚠️  Some Telegram messages failed.")
            except Exception as e:
                print(f"\n❌ Telegram delivery failed: {e}", file=sys.stderr)

    return output


if __name__ == "__main__":
    main()
