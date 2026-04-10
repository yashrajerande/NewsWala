#!/usr/bin/env python3
"""
NewsWala — Daily scheduled runner.

This script is designed to be called by an automated scheduler (cron, cloud scheduler, etc.).
It runs the full pipeline and delivers the digest to Telegram and via email.

Usage (scheduled, silent):
    python newswala_daily.py

It loads credentials from the .env file in the same directory.
Logs are written to newswala.log in the same directory.
"""

import sys
import os
import logging
from datetime import date
from pathlib import Path

# ── Logging setup ─────────────────────────────────────────────────────────────
log_path = Path(__file__).parent / "newswala.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("newswala_daily")

# ── Load .env ─────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
    log.info(".env loaded")
except ImportError:
    log.info("python-dotenv not installed — relying on system environment variables")

# ── Path setup ────────────────────────────────────────────────────────────────
_api_dir = str(Path(__file__).parent / "api")
if _api_dir not in sys.path:
    sys.path.insert(0, _api_dir)

# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    run_date = date.today().isoformat()
    log.info(f"NewsWala daily run starting for {run_date}")

    # Validate environment
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.error("ANTHROPIC_API_KEY not set — aborting")
        sys.exit(1)

    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    telegram_chat  = os.environ.get("TELEGRAM_CHAT_ID")
    gmail_address  = os.environ.get("GMAIL_ADDRESS")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not telegram_token or not telegram_chat:
        log.warning(
            "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — "
            "will run pipeline but skip Telegram delivery"
        )
    if not gmail_address or not gmail_password:
        log.warning(
            "GMAIL_ADDRESS or GMAIL_APP_PASSWORD not set — "
            "will run pipeline but skip email delivery"
        )

    # Run the pipeline
    try:
        from newswala.supervisor import newswala
        package = newswala(run_date=run_date, verbose=True)
        log.info("Pipeline completed successfully")
    except Exception as e:
        log.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)

    # Deliver via Telegram
    if telegram_token and telegram_chat:
        try:
            from newswala.telegram_sender import send_digest
            output = {k: v for k, v in package.items() if k != "_rendered"}
            ok = send_digest(output, token=telegram_token, chat_id=telegram_chat)
            if ok:
                log.info("Digest delivered to Telegram successfully")
            else:
                log.warning("Some Telegram messages failed to send")
        except Exception as e:
            log.error(f"Telegram delivery failed: {e}", exc_info=True)
    else:
        log.info("Telegram delivery skipped (credentials not configured)")

    # Deliver via email
    if gmail_address and gmail_password:
        try:
            from newswala.email_sender import send_digest as send_email
            output = {k: v for k, v in package.items() if k != "_rendered"}
            ok = send_email(output, gmail_address=gmail_address, gmail_app_password=gmail_password)
            if ok:
                log.info("Digest emailed to all recipients successfully")
            else:
                log.warning("Some emails failed to send")
        except Exception as e:
            log.error(f"Email delivery failed: {e}", exc_info=True)
    else:
        log.info("Email delivery skipped (GMAIL_ADDRESS / GMAIL_APP_PASSWORD not configured)")

    # Save JSON output for the day
    try:
        import json
        out_path = Path(__file__).parent / f"newswala_output_{run_date}.json"
        clean = {k: v for k, v in package.items() if k != "_rendered"}
        out_path.write_text(json.dumps(clean, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info(f"JSON output saved to {out_path}")
    except Exception as e:
        log.warning(f"Could not save JSON output: {e}")

    log.info("NewsWala daily run complete")


if __name__ == "__main__":
    run()
