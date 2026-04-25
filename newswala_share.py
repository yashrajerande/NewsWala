#!/usr/bin/env python3
"""
newswala_share.py — Share a news article, YouTube video, or pasted text with the family.

Usage:
    python newswala_share.py "https://bbc.com/..."      # any article URL
    python newswala_share.py "https://youtu.be/..."     # YouTube video
    python newswala_share.py                             # interactive: paste text

The content is rewritten in the family's voice and sent via email (and Telegram if configured).

Reads from .env in the project root:
    ANTHROPIC_API_KEY     (required)
    GMAIL_ADDRESS         (optional — for email)
    GMAIL_APP_PASSWORD    (optional — for email)
    TELEGRAM_BOT_TOKEN    (optional — for Telegram)
    TELEGRAM_CHAT_ID      (optional — for Telegram)
    OPENAI_API_KEY        (optional — for DALL-E 3 image)
"""

import sys
import os
import re
import json
import argparse
import urllib.request
import urllib.parse
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "api"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import anthropic
from newswala.agents import (
    whatsapp_copywriter,
    memory_cue_designer,
    image_maker,
    image_generator,
    cost_tracker,
    FAST_MODEL,
    BOLD, DIM, RESET, GREEN, BLUE,
    _bar, _step, _ok,
)
from newswala.email_sender import send_digest as email_send
from newswala.telegram_sender import send_digest as telegram_send
from newswala.config import FAMILY

client = anthropic.Anthropic()

_YT_RE = re.compile(r'(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{11})')


# ---------------------------------------------------------------------------
# Content extraction
# ---------------------------------------------------------------------------

def _is_url(s: str) -> bool:
    return s.startswith(("http://", "https://"))


def _is_youtube(s: str) -> bool:
    return bool(_YT_RE.search(s))


class _StripHTML(HTMLParser):
    """Minimal HTML → plain text converter."""

    def __init__(self):
        super().__init__()
        self._skip = False
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "header", "footer", "aside"):
            self._skip = True
        if tag in ("p", "h1", "h2", "h3", "li", "br"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "header", "footer", "aside"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            text = data.strip()
            if text:
                self.parts.append(text)

    def result(self) -> str:
        return " ".join(self.parts)


def _fetch_article(url: str) -> tuple[str, str]:
    """Fetch a web article and return (title, body_text)."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = re.sub(r"\s+", " ", title_m.group(1)).strip() if title_m else "Article"

    parser = _StripHTML()
    parser.feed(html)
    body = parser.result()[:5000]
    return title, body


def _fetch_youtube(url: str) -> tuple[str, str]:
    """Fetch YouTube transcript. Falls back to manual paste if library missing."""
    m = _YT_RE.search(url)
    if not m:
        raise ValueError(f"Cannot parse YouTube video ID from: {url}")
    video_id = m.group(1)

    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        entries = YouTubeTranscriptApi.get_transcript(video_id)
        transcript = " ".join(e["text"] for e in entries)[:5000]
    except ImportError:
        print("\n  youtube-transcript-api not installed.")
        print("  Install it with:  pip install youtube-transcript-api\n")
        print("  For now, paste a summary of the video (press Enter twice when done):\n")
        transcript = _read_multiline()

    # Try to get the real title via YouTube oEmbed (no API key needed)
    title = f"YouTube: {video_id}"
    try:
        oembed = f"https://www.youtube.com/oembed?url={urllib.parse.quote(url)}&format=json"
        with urllib.request.urlopen(oembed, timeout=5) as resp:
            title = json.loads(resp.read()).get("title", title)
    except Exception:
        pass

    return title, transcript


def _read_multiline() -> str:
    """Read lines from stdin until two consecutive blank lines or EOF."""
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        lines.append(line)
        if len(lines) >= 2 and lines[-1] == "" and lines[-2] == "":
            break
    return "\n".join(lines).strip()


def _extract(source: str) -> tuple[str, str, str]:
    """Return (title, body, url) from a URL, YouTube link, or raw text."""
    source = source.strip()
    if _is_url(source):
        if _is_youtube(source):
            title, body = _fetch_youtube(source)
        else:
            title, body = _fetch_article(source)
        return title, body, source
    # Raw text — use first line as title
    first, rest = (source.split("\n", 1) + [""])[:2]
    return first[:100] or "Shared article", source, ""


# ---------------------------------------------------------------------------
# Build a story dict from raw content (Claude Haiku call)
# ---------------------------------------------------------------------------

def _build_story(title: str, body: str, url: str) -> dict:
    """Ask Claude Haiku to distill raw content into the standard story dict."""
    youngest_age = min(d["age_turning"] for d in FAMILY["daughters"])

    prompt = (
        f"You are a story editor for a family newsletter. A parent has shared this content.\n"
        f"Extract the key information and return a JSON story object.\n\n"
        f"Title: {title}\n"
        f"Content:\n{body[:3500]}\n\n"
        f"Return JSON with these exact fields:\n"
        f'{{\n'
        f'  "title": "clear engaging title (max 15 words)",\n'
        f'  "summary": "2-3 factual sentences, clear enough for a {youngest_age}-year-old",\n'
        f'  "category": "Economics or STEM or Current Affairs",\n'
        f'  "source": "publication or website name (infer from content)",\n'
        f'  "url": "{url}",\n'
        f'  "why_selected": "one specific reason this is interesting or relevant for the family",\n'
        f'  "lesson_or_moral": "one memorable takeaway sentence",\n'
        f'  "relevance_score": 9,\n'
        f'  "age_appropriate": true\n'
        f'}}\n\n'
        f"Return ONLY valid JSON, no prose."
    )

    resp = client.messages.create(
        model=FAST_MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    cost_tracker.add("content_extractor", FAST_MODEL, resp.usage)

    raw = resp.content[0].text.strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        story = json.loads(m.group())
    else:
        story = {
            "title": title,
            "summary": body[:300],
            "category": "Current Affairs",
            "source": "Shared by Papa",
            "url": url,
            "why_selected": "Papa shared this specially for you",
            "lesson_or_moral": "Curiosity and persistence open doors.",
            "relevance_score": 9,
            "age_appropriate": True,
        }

    story["url"] = url  # always keep the original URL
    return story


# ---------------------------------------------------------------------------
# Package assembly
# ---------------------------------------------------------------------------

def _assemble_package(
    story: dict,
    wa_out: dict,
    img_out: dict,
    run_date: str,
) -> dict:
    return {
        "run_date": run_date,
        "selected_stories": [
            {
                "title":                    story.get("title", ""),
                "category":                 story.get("category", ""),
                "source":                   story.get("source", ""),
                "url":                      story.get("url", ""),
                "why_selected":             story.get("why_selected", ""),
                "family_fit_notes":         "Shared directly by Papa",
                "summary_for_internal_use": story.get("summary", ""),
                "lesson_or_moral":          story.get("lesson_or_moral", ""),
            }
        ],
        "whatsapp_output": wa_out,
        "image_output": img_out,
        "quality_checks": {"share_mode": True},
        "run_cost": cost_tracker.total(),
        "monthly_spend": {"note": "share mode — not counted against daily budget"},
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Share an article, YouTube video, or text with the family via NewsWala."
    )
    parser.add_argument(
        "content", nargs="?",
        help="URL, YouTube link, or leave blank to paste text interactively",
    )
    parser.add_argument("--no-email", action="store_true", help="Skip email delivery")
    parser.add_argument("--no-telegram", action="store_true", help="Skip Telegram delivery")
    parser.add_argument("--no-image", action="store_true", help="Skip DALL-E 3 image generation")
    args = parser.parse_args()

    run_date = date.today().isoformat()
    print(f"\n{BOLD}📎  NewsWala Share  |  {run_date}{RESET}")
    print(f"{DIM}Pipeline: extract → story → copywriter → deliver{RESET}\n")

    # ── 1. get input ─────────────────────────────────────────────────────────
    if args.content:
        source = args.content
    else:
        print("Paste an article URL, YouTube link, or text.")
        print("Press Enter twice when done.\n")
        source = _read_multiline()
        if not source:
            print("No content provided. Exiting.")
            sys.exit(1)

    # ── 2. extract content ───────────────────────────────────────────────────
    _bar("📥  content extractor", BLUE)
    _step(f"Source: {source[:80]}{'...' if len(source) > 80 else ''}")
    title, body, url = _extract(source)
    _ok(f"Extracted: \"{title}\" ({len(body)} chars)")

    # ── 3. build story dict ──────────────────────────────────────────────────
    _bar(f"📋  story builder  |  {FAST_MODEL}", BLUE)
    _step("Summarising content into story format...")
    story = _build_story(title, body, url)
    _ok(f"[{story['category']}] {story['title']}")

    # ── 4. write the family message ──────────────────────────────────────────
    wa_out = whatsapp_copywriter([story])
    wa_out["signoff"] = FAMILY["signoff"]
    if FAMILY["signoff"] not in wa_out.get("main_message", ""):
        wa_out["main_message"] += f"\n\n{FAMILY['signoff']}"

    # ── 5. generate image (optional) ─────────────────────────────────────────
    img_out = {"concept": "", "image_prompt": "", "alt_text": "", "generated_image_url": ""}
    skip_image = args.no_image or not os.environ.get("OPENAI_API_KEY")
    if skip_image:
        reason = "--no-image flag" if args.no_image else "OPENAI_API_KEY not set"
        _step(f"Skipping image generation ({reason})")
    else:
        try:
            concept = memory_cue_designer([story])
            img_raw = image_maker(concept, [story])
            generated = image_generator(img_raw.get("image_prompt", ""))
            img_out = {
                "concept":             concept.get("concept", ""),
                "image_prompt":        img_raw.get("image_prompt", ""),
                "alt_text":            img_raw.get("alt_text", ""),
                "generated_image_url": generated.get("url", ""),
            }
        except Exception as e:
            _step(f"Image generation failed: {e}")

    # ── 6. assemble package ──────────────────────────────────────────────────
    package = _assemble_package(story, wa_out, img_out, run_date)

    # ── 7. deliver ───────────────────────────────────────────────────────────
    gmail    = os.environ.get("GMAIL_ADDRESS")
    gmail_pw = os.environ.get("GMAIL_APP_PASSWORD")
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    tg_chat  = os.environ.get("TELEGRAM_CHAT_ID")

    delivered = False

    if not args.no_email:
        if gmail and gmail_pw:
            _bar("📧  email delivery", GREEN)
            email_send(package, gmail, gmail_pw)
            delivered = True
        else:
            _step("Email skipped — GMAIL_ADDRESS or GMAIL_APP_PASSWORD not set")

    if not args.no_telegram:
        if tg_token and tg_chat:
            _bar("✈️   Telegram delivery", GREEN)
            telegram_send(package, tg_token, tg_chat)
            delivered = True
        else:
            _step("Telegram skipped — TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")

    if not delivered:
        # At minimum, print the message to stdout so it's not lost
        print(f"\n{'─'*60}")
        print("  No delivery channels configured. Here's the message:\n")
        print(wa_out.get("main_message", ""))
        print(f"{'─'*60}")

    print(f"\n  Total cost: ${cost_tracker.total():.4f}")
    cost_tracker.reset()
    print()


if __name__ == "__main__":
    main()
