#!/usr/bin/env python3
"""
NewsWala — Top-level runner script.

Run from the project root:
    python newswala.py                    # Today's digest (terminal output)
    python newswala.py --telegram         # Generate + send to Telegram
    python newswala.py --setup-telegram   # Test Telegram connection
    python newswala.py --save             # Save JSON output to file
    python newswala.py --json-only        # Raw JSON only

Environment variables:
    ANTHROPIC_API_KEY       required
    TELEGRAM_BOT_TOKEN      required for --telegram
    TELEGRAM_CHAT_ID        required for --telegram

Put these in a .env file in this directory and they'll load automatically.
"""

import sys
import os

# Load .env from project root if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Make api/newswala importable as the top-level 'newswala' package.
# We insert api/ into sys.path to bypass api/__init__.py which has
# legacy openai imports from the original gpt3-sandbox codebase.
_api_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api")
if _api_dir not in sys.path:
    sys.path.insert(0, _api_dir)

from newswala.run import main  # noqa: E402

if __name__ == "__main__":
    main()
