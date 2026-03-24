#!/usr/bin/env python3
"""
NewsWala — Top-level runner script.

Run from the project root:
    python newswala.py                    # Today's digest
    python newswala.py --date 2025-10-24  # Specific date
    python newswala.py --save             # Save JSON output
    python newswala.py --json-only        # Raw JSON only

Requires:
    ANTHROPIC_API_KEY environment variable (or .env file in project root)
    pip install anthropic python-dotenv
"""

import sys
import os

# Load .env from project root if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Make api/newswala importable as a top-level package called 'newswala'
# by inserting api/ into the path — this bypasses api/__init__.py
# (which has legacy openai imports from the old gpt3-sandbox codebase)
_api_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api")
if _api_dir not in sys.path:
    sys.path.insert(0, _api_dir)

from newswala.run import main  # noqa: E402

if __name__ == "__main__":
    main()
