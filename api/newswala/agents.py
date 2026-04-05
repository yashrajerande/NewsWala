"""
NewsWala — agent implementations.

Pipeline:
    news_scout → family_fit_editor → whatsapp_copywriter
                                   → memory_cue_designer → image_maker

Cost budget: < $5 / month (running daily)

Model assignments:
┌──────────────────────┬──────────────────┬──────────────────────────────┐
│ Agent                │ Model            │ Why                          │
├──────────────────────┼──────────────────┼──────────────────────────────┤
│ news_scout           │ Haiku 4.5        │ RSS fetch + scoring (cheap)  │
│ family_fit_editor    │ Haiku 4.5        │ structured filtering, cheap  │
│ whatsapp_copywriter  │ Sonnet 4.6       │ needs writing quality        │
│ memory_cue_designer  │ Haiku 4.5        │ simple creative task         │
│ image_maker          │ Haiku 4.5        │ mechanical prompt writing    │
└──────────────────────┴──────────────────┴──────────────────────────────┘

Pricing ($/1M tokens):  Sonnet: $3 in / $15 out   Haiku: $1 in / $5 out
NO adaptive thinking — thinking tokens multiply output cost 5-10x.

Estimated daily cost:  ~$0.01-0.02  (was $1.50+ when using web_search)
Estimated monthly:     ~$0.30-0.60  (well within $5 budget)

Why RSS instead of web_search:
  web_search returns full page content → 300k-500k tokens/run → ~$1.50/run
  RSS returns headline + summary only → ~3k tokens/run → ~$0.003/run
"""

import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
import anthropic

from .config import MAX_STORIES

# --- models ------------------------------------------------------------------
SCOUT_MODEL = "claude-haiku-4-5"   # RSS scoring — no web search needed → cheap
WRITE_MODEL = "claude-sonnet-4-6"  # WhatsApp copy needs quality
FAST_MODEL  = "claude-haiku-4-5"   # filtering, image prompts — cheap & fast

client = anthropic.Anthropic()

# --- story history file (prevents repeating news) ----------------------------
# Stored at project root: ~/NewsWala/newswala_history.json
_HISTORY_FILE = Path(__file__).resolve().parents[2] / "newswala_history.json"
_HISTORY_DAYS = 14   # remember stories from the last 14 days

# --- monthly spend tracker ---------------------------------------------------
# Stored at project root: ~/NewsWala/newswala_monthly_spend.json
_MONTHLY_SPEND_FILE = Path(__file__).resolve().parents[2] / "newswala_monthly_spend.json"
_MONTHLY_BUDGET_USD = 5.00

# --- agent directory — system prompts live here, editable without Python -----
# Agents live in ErandeNewsCorp/ at the repo root (visible on GitHub as employees)
# From api/newswala/agents.py → up 2 levels → repo root → ErandeNewsCorp/agents
_AGENTS_DIR = Path(__file__).resolve().parents[2] / "ErandeNewsCorp" / "agents"


def _load_prompt(agent_folder: str) -> str:
    """
    Load instructions from agents/<folder>/instructions.md.
    Edit that file to change the agent's task — no Python needed.
    """
    p = _AGENTS_DIR / agent_folder / "instructions.md"
    try:
        return p.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Instructions not found: {p}\n"
            f"Expected: api/newswala/agents/{agent_folder}/instructions.md"
        )


def _load_persona(agent_folder: str) -> str:
    """
    Load persona from agents/<folder>/<agent_name>_persona_and_resume.md.
    This shapes Claude's character, voice, and values — loaded into every system prompt.
    Edit the persona file to change how the agent thinks and talks.
    """
    folder = _AGENTS_DIR / agent_folder
    matches = list(folder.glob("*_persona_and_resume.md"))
    if not matches:
        return ""
    try:
        return matches[0].read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _build_system(agent_folder: str, skill_name: str = "") -> str:
    """
    Assemble the full system prompt for an agent:
      [persona_and_resume]  — who I am, my voice, my values
      ---
      [instructions]        — my task for this run
      ---
      [skill]               — the methodology I apply
    """
    persona      = _load_persona(agent_folder)
    instructions = _load_prompt(agent_folder)
    skill        = _load_skill(skill_name) if skill_name else ""

    parts = []
    if persona:
        parts.append(persona)
    if instructions:
        parts.append(instructions)
    if skill:
        parts.append(f"## SKILL: {skill_name}\n{skill}")

    return "\n\n---\n\n".join(parts)


def _load_skill(skill_name: str) -> str:
    """
    Load a skill from agents/skills/<skill-name>.md.
    Skills are injected into agent system prompts at runtime.
    Add new skills by dropping a .md file into agents/skills/.
    """
    p = _AGENTS_DIR / "skills" / f"{skill_name}.md"
    try:
        return p.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        _step(f"⚠️  Skill not found: {skill_name} — running without it")
        return ""


# ---------------------------------------------------------------------------
# terminal helpers
# ---------------------------------------------------------------------------

BOLD    = "\033[1m"
DIM     = "\033[2m"
CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
BLUE    = "\033[94m"
MAGENTA = "\033[95m"
RESET   = "\033[0m"

def _bar(label: str, color: str = CYAN):
    print(f"\n{color}{BOLD}{'━' * 54}{RESET}")
    print(f"{color}{BOLD}  {label}{RESET}")
    print(f"{color}{BOLD}{'━' * 54}{RESET}")

def _handoff(from_agent: str, to_agent: str, summary: str):
    print(f"\n  {DIM}{'─' * 50}{RESET}")
    print(f"  {YELLOW}↳ {BOLD}{from_agent}{RESET}{YELLOW} → {BOLD}{to_agent}{RESET}")
    print(f"  {DIM}  {summary}{RESET}")
    print(f"  {DIM}{'─' * 50}{RESET}\n")

def _step(msg: str):
    print(f"  {DIM}▸ {msg}{RESET}", flush=True)

def _ok(msg: str):
    print(f"\n  {GREEN}✓ {msg}{RESET}", flush=True)

def _stream(chunk: str):
    sys.stdout.write(chunk)
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# cost tracker — module-level singleton so all agents can update it
# ---------------------------------------------------------------------------

_PRICES = {
    "claude-sonnet-4-6": {"in": 3.00,  "out": 15.00},
    "claude-haiku-4-5":  {"in": 1.00,  "out":  5.00},
    "claude-opus-4-6":   {"in": 5.00,  "out": 25.00},
}

class _CostTracker:
    def __init__(self):
        self.entries: list[dict] = []

    def add(self, agent: str, model: str, usage):
        """Record token usage from a response.usage object."""
        if usage is None:
            return
        inp  = getattr(usage, "input_tokens", 0) or 0
        out  = getattr(usage, "output_tokens", 0) or 0
        price = _PRICES.get(model, {"in": 3.0, "out": 15.0})
        cost  = (inp * price["in"] + out * price["out"]) / 1_000_000
        self.entries.append({"agent": agent, "model": model,
                             "in": inp, "out": out, "cost": cost})

    def total(self) -> float:
        return sum(e["cost"] for e in self.entries)

    def print_summary(self):
        if not self.entries:
            return
        print(f"\n  {'─'*56}")
        print(f"  {BOLD}COST BREAKDOWN{RESET}")
        print(f"  {'─'*56}")
        print(f"  {'Agent':<24} {'Model':<16} {'In':>6} {'Out':>6}  {'$':>8}")
        print(f"  {'─'*56}")
        for e in self.entries:
            m = (e["model"].replace("claude-","")
                           .replace("-4-6","4.6").replace("-4-5","4.5"))
            print(f"  {e['agent']:<24} {m:<16} {e['in']:>6} {e['out']:>6}  ${e['cost']:>7.4f}")
        t = self.total()
        print(f"  {'─'*56}")
        print(f"  {'TOTAL this run':<48} ${t:>7.4f}")
        print(f"  {GREEN}{'Est. monthly (30 days)':<48} ${t*30:>7.2f}{RESET}")
        print(f"  {'─'*56}\n")

    def reset(self):
        self.entries = []

# single shared instance — imported by supervisor too
cost_tracker = _CostTracker()


# ---------------------------------------------------------------------------
# story history — remember what we sent to avoid repeats
# ---------------------------------------------------------------------------

def load_history() -> list[dict]:
    """Load sent story history, pruning entries older than _HISTORY_DAYS."""
    if not _HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(_HISTORY_FILE.read_text())
        cutoff = (date.today() - timedelta(days=_HISTORY_DAYS)).isoformat()
        return [s for s in data if s.get("date", "9999") >= cutoff]
    except Exception:
        return []


def save_history(stories: list[dict], run_date: str):
    """Append newly selected stories to the history file."""
    history = load_history()
    for s in stories:
        history.append({
            "date":  run_date,
            "title": s.get("title", ""),
            "url":   s.get("url", ""),
        })
    try:
        _HISTORY_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False))
    except Exception as e:
        _step(f"Could not save history: {e}")


def load_monthly_spend() -> dict:
    """Load the monthly spend ledger keyed by YYYY-MM."""
    if not _MONTHLY_SPEND_FILE.exists():
        return {}
    try:
        return json.loads(_MONTHLY_SPEND_FILE.read_text())
    except Exception:
        return {}


def record_monthly_spend(run_cost: float, run_date: str) -> dict:
    """Accumulate this run's cost into the monthly ledger. Returns the updated month entry."""
    month_key = run_date[:7]
    ledger = load_monthly_spend()
    entry = ledger.get(month_key, {"total_usd": 0.0, "runs": 0, "last_run": ""})
    entry["total_usd"]  = round(entry["total_usd"] + run_cost, 6)
    entry["runs"]       = entry["runs"] + 1
    entry["last_run"]   = run_date
    entry["budget_usd"] = _MONTHLY_BUDGET_USD
    ledger[month_key]   = entry
    try:
        _MONTHLY_SPEND_FILE.write_text(json.dumps(ledger, indent=2, ensure_ascii=False))
    except Exception as e:
        _step(f"Could not save monthly spend: {e}")
    return entry


# ---------------------------------------------------------------------------
# helper: pull JSON out of a response that may contain prose around it
# ---------------------------------------------------------------------------

def _parse_json(text: str, shape: str = "object") -> dict | list:
    open_c, close_c = ("{", "}") if shape == "object" else ("[", "]")
    start = text.find(open_c)
    end   = text.rfind(close_c) + 1
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    _step("JSON parse failed — asking Claude to reformat...")
    resp = client.messages.create(
        model=FAST_MODEL, max_tokens=2000,
        messages=[{"role": "user",
                   "content": f"Extract the JSON {shape}. Return ONLY valid JSON:\n\n{text[:4000]}"}],
    )
    cost_tracker.add("_json_retry", FAST_MODEL, resp.usage)
    clean = resp.content[0].text
    s = clean.find(open_c)
    e = clean.rfind(close_c) + 1
    if s != -1 and e > s:
        return json.loads(clean[s:e])
    return [] if shape == "array" else {}


# ---------------------------------------------------------------------------
# Agent 1 — news_scout
# Fetches RSS feeds from trusted sources (free, no tokens used for fetching).
# Passes headlines to Haiku for scoring — ~3k tokens vs 300k+ with web_search.
# Cost: ~$0.003/day  (was ~$1.50/day with web_search)
# ---------------------------------------------------------------------------

# RSS feeds — split into primary and backup tiers per category.
# Primary feeds are tried first. If fewer than _MIN_STORIES_PER_CATEGORY stories
# are collected, backup feeds are tried automatically at runtime.
_MIN_STORIES_PER_CATEGORY = 3

_RSS_FEEDS: dict[str, dict[str, list[tuple[str, str]]]] = {
    "Economics": {
        "primary": [
            ("Bloomberg",       "https://feeds.bloomberg.com/markets/news.rss"),
            ("Financial Times", "https://www.ft.com/rss/home"),
            ("The Economist",   "https://www.economist.com/finance-and-economics/rss.xml"),
            ("Livemint",        "https://www.livemint.com/rss/news"),
            ("CNBC",            "https://www.cnbc.com/id/10001147/device/rss/rss.html"),
        ],
        "backup": [
            ("Times of India Business", "https://timesofindia.indiatimes.com/rssfeeds/1898055.cms"),
            ("NDTV Profit",             "https://feeds.feedburner.com/ndtvprofit-latest"),
            ("WSJ Markets",             "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
            ("Yahoo Finance",           "https://finance.yahoo.com/rss/"),
        ],
    },
    "STEM": {
        "primary": [
            ("MIT Technology Review", "https://www.technologyreview.com/feed/"),
            ("BBC Science",           "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"),
            ("The Verge",             "https://www.theverge.com/rss/index.xml"),
            ("Ars Technica",          "https://feeds.arstechnica.com/arstechnica/index"),
        ],
        "backup": [
            ("Wired",         "https://www.wired.com/feed/rss"),
            ("Phys.org",      "https://phys.org/rss-feed/"),
            ("Science Daily", "https://www.sciencedaily.com/rss/top/technology.xml"),
            ("Nature",        "https://www.nature.com/nature.rss"),
        ],
    },
    "Current Affairs": {
        "primary": [
            ("BBC India",     "https://feeds.bbci.co.uk/news/world/asia/india/rss.xml"),
            ("BBC World",     "https://feeds.bbci.co.uk/news/world/rss.xml"),
            ("The Economist", "https://www.economist.com/the-world-this-week/rss.xml"),
            ("Al Jazeera",    "https://www.aljazeera.com/xml/rss/all.xml"),
        ],
        "backup": [
            ("Times of India", "https://timesofindia.indiatimes.com/rssfeeds/296589292.cms"),
            ("NDTV India",     "https://feeds.feedburner.com/ndtvnews-india-news"),
            ("Indian Express", "https://indianexpress.com/feed/"),
            ("Scroll.in",      "https://scroll.in/feed"),
        ],
    },
}

# Priority sources get a credibility bonus in scoring
_PRIORITY_SOURCES = {
    "Bloomberg", "Financial Times", "The Economist",
    "MIT Technology Review", "Livemint", "Ars Technica",
}

_SCOUT_SYSTEM = _load_prompt("01_news_scout")


def _fetch_rss(url: str, source: str, category: str, cutoff: datetime) -> list[dict]:
    """
    Fetch one RSS feed and return stories published after cutoff.
    Pure stdlib — no tokens used, no API calls.
    """
    def _tag(text: str, tag: str) -> str:
        m = re.search(
            rf'<{tag}[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{tag}>',
            text, re.DOTALL | re.IGNORECASE,
        )
        return m.group(1).strip() if m else ""

    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (NewsWala/2.0 RSS Reader)"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        _step(f"  ✗ {source}: {e}")
        return []

    items = re.findall(r'<item[^>]*>(.*?)</item>', content, re.DOTALL | re.IGNORECASE)
    if not items:
        items = re.findall(r'<entry[^>]*>(.*?)</entry>', content, re.DOTALL | re.IGNORECASE)

    stories = []
    for item in items[:10]:
        title = _tag(item, "title")
        link  = _tag(item, "link") or _tag(item, "guid")
        desc  = _tag(item, "description") or _tag(item, "summary")
        pub   = _tag(item, "pubDate") or _tag(item, "published") or _tag(item, "updated")

        if not title:
            continue

        desc = re.sub(r'<[^>]+>', '', desc)[:300].strip()

        pub_str = "recent"
        try:
            pub_dt = parsedate_to_datetime(pub)
            if pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
            if pub_dt < cutoff:
                continue
            pub_str = pub_dt.strftime("%Y-%m-%d")
        except Exception:
            pass   # include story if date unparseable

        stories.append({
            "title":          title,
            "url":            link,
            "description":    desc,
            "source":         source,
            "category":       category,
            "published_date": pub_str,
            "priority":       source in _PRIORITY_SOURCES,
        })

    return stories


def news_scout(run_date: str) -> list[dict]:
    """
    Fetch headlines from RSS feeds, then use Haiku to score and select.
    No web_search calls → no runaway token costs.
    """
    _bar(f"📡  news_scout  |  {run_date}  |  RSS + {SCOUT_MODEL}", CYAN)

    history = load_history()
    avoid_titles = {h["title"].lower()[:60] for h in history[-10:]}
    if avoid_titles:
        _step(f"History: will skip {len(avoid_titles)} recently sent stories")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

    # --- fetch all RSS feeds (no AI, no cost) --------------------------------
    # Primary feeds tried first; backups used automatically if < _MIN_STORIES_PER_CATEGORY
    all_stories: list[dict] = []
    for category, tier_feeds in _RSS_FEEDS.items():
        _step(f"Fetching {category}...")
        seen_titles: set[str] = set()
        cat_stories: list[dict] = []

        def _collect(feeds_list: list[tuple[str, str]], label: str) -> None:
            for source, url in feeds_list:
                stories = _fetch_rss(url, source, category, cutoff)
                added = 0
                for s in stories:
                    key = s["title"].lower()[:60]
                    if key not in seen_titles and key not in avoid_titles:
                        seen_titles.add(key)
                        cat_stories.append(s)
                        added += 1
                if stories:
                    _step(f"  ✓ {source}: {added} fresh stories{label}")
                else:
                    _step(f"  ✗ {source}: no stories / failed{label}")

        _collect(tier_feeds["primary"], "")
        if len(cat_stories) < _MIN_STORIES_PER_CATEGORY:
            _step(f"  Only {len(cat_stories)} stories — trying backup feeds...")
            _collect(tier_feeds["backup"], " (backup)")

        all_stories.extend(cat_stories)
        _step(f"  → {len(cat_stories)} unique stories in {category}")

    _ok(f"Total: {len(all_stories)} fresh stories fetched via RSS (0 tokens used)")

    if not all_stories:
        _step("⚠️  No RSS stories found — returning empty")
        return []

    # --- ask Haiku to score and select best 4-6 (tiny token cost) -----------
    _step(f"Scoring with {SCOUT_MODEL} (~{len(all_stories[:25])} stories)...")
    _SCOUT = _build_system("01_news_scout", "india-news-scoring")

    story_list = "\n\n".join(
        f"[{i+1}] [{s['category']}] {'⭐ ' if s['priority'] else ''}{s['source']}\n"
        f"Title: {s['title']}\n"
        f"Desc:  {s['description']}\n"
        f"Date:  {s['published_date']}  URL: {s['url']}"
        for i, s in enumerate(all_stories[:25])
    )

    avoid_note = ""
    if avoid_titles:
        avoid_note = f"\n\nALREADY SENT RECENTLY — do not select:\n" + \
                     "\n".join(f"- {t}" for t in list(avoid_titles)[:10])

    text = ""
    with client.messages.stream(
        model=SCOUT_MODEL, max_tokens=3000,
        system=_SCOUT,
        messages=[{"role": "user", "content": (
            f"Today: {run_date}. ⭐ marks priority sources.\n\n"
            f"Stories to score:\n{story_list}"
            f"{avoid_note}\n\n"
            f"Return JSON array of the best 4-6 stories (at least 1 per category)."
        )}],
    ) as stream:
        for event in stream:
            if (event.type == "content_block_delta"
                    and hasattr(event, "delta")
                    and getattr(event.delta, "type", "") == "text_delta"):
                text += event.delta.text or ""
                if not text.lstrip().startswith("["):
                    _stream(event.delta.text or "")
        response = stream.get_final_message()

    cost_tracker.add("news_scout", SCOUT_MODEL, response.usage)

    for b in response.content:
        b_text = getattr(b, "text", None)
        if b_text and b_text not in text:
            text += b_text

    print()
    candidates = _parse_json(text, shape="array")

    _ok(f"Selected {len(candidates)} candidate stories:")
    for i, s in enumerate(candidates, 1):
        score = s.get("scores", {}).get("total", "?")
        print(f"    {DIM}[{i}] [{s.get('category','?')}] {s.get('title','?')[:65]}"
              f"  score:{score}  {s.get('published_date','')}{RESET}")

    for cat in ["Economics", "STEM", "Current Affairs"]:
        if not any(cat.lower() in s.get("category", "").lower() for s in candidates):
            _step(f"⚠️  No {cat} story found")

    return candidates


# ---------------------------------------------------------------------------
# Agent 2 — family_fit_editor
# Uses Haiku — structured filtering.
# Cost: ~$0.003-0.005/day
# ---------------------------------------------------------------------------

_EDITOR_SYSTEM = _load_prompt("02_family_fit_editor")


def family_fit_editor(candidates: list[dict]) -> list[dict]:
    """Filter to best 1-2 stories. Uses Haiku for speed and cost."""
    _bar(f"🧐  family_fit_editor  |  {len(candidates)} candidates  |  {FAST_MODEL}", MAGENTA)
    _step("Evaluating age-safety, lesson quality, category spread...")
    _EDITOR = _build_system("02_family_fit_editor", "family-editorial-filter")
    print(f"\n  {MAGENTA}Filtering:{RESET}\n  {'─'*50}\n  ", end="")

    text = ""
    with client.messages.stream(
        model=FAST_MODEL, max_tokens=2000,
        system=_EDITOR,
        messages=[{"role": "user", "content": (
            f"Candidates:\n{json.dumps(candidates, indent=2)}\n\n"
            f"Pick the best 1 (or at most 2 from different categories)."
        )}],
    ) as stream:
        for event in stream:
            if (event.type == "content_block_delta"
                    and hasattr(event, "delta")
                    and getattr(event.delta, "type", "") == "text_delta"):
                text += event.delta.text or ""
                if not text.lstrip().startswith("["):
                    _stream(event.delta.text or "")
        response = stream.get_final_message()

    cost_tracker.add("family_fit_editor", FAST_MODEL, response.usage)

    for b in response.content:
        b_text = getattr(b, "text", None)
        if b_text and b_text not in text:
            text += b_text

    print("\n")
    selected = _parse_json(text, shape="array")
    selected = selected[:MAX_STORIES]

    _ok(f"Selected {len(selected)} story/stories:")
    for s in selected:
        print(f"    {GREEN}→ [{s.get('category','?')}] {s.get('title','?')}{RESET}")
        print(f"    {DIM}  {s.get('why_selected','')}{RESET}")
    return selected


# ---------------------------------------------------------------------------
# Agent 3 — whatsapp_copywriter
# Uses Sonnet. Strict 180-word limit to keep WhatsApp length OK.
# Cost: ~$0.01-0.015/day
# ---------------------------------------------------------------------------

_COPY_SYSTEM = _load_prompt("03_whatsapp_copywriter")


def whatsapp_copywriter(selected_stories: list[dict]) -> dict:
    """Write the WhatsApp message. Streams the draft live."""
    _bar(f"✍️   whatsapp_copywriter  |  {WRITE_MODEL}", BLUE)
    _step("Writing family message (max 180 words)...")
    _COPY = _build_system("03_whatsapp_copywriter", "whatsapp-family-message")
    print(f"\n  {BLUE}Draft:{RESET}\n  {'─'*50}\n  ", end="")

    text = ""
    with client.messages.stream(
        model=WRITE_MODEL, max_tokens=1000,
        system=_COPY,
        messages=[{"role": "user", "content":
                   f"Stories:\n{json.dumps(selected_stories, indent=2)}"}],
    ) as stream:
        for event in stream:
            if (event.type == "content_block_delta"
                    and hasattr(event, "delta")
                    and getattr(event.delta, "type", "") == "text_delta"):
                text += event.delta.text or ""
                if not text.lstrip().startswith("{"):
                    _stream(event.delta.text or "")
        response = stream.get_final_message()

    cost_tracker.add("whatsapp_copywriter", WRITE_MODEL, response.usage)

    for b in response.content:
        b_text = getattr(b, "text", None)
        if b_text and b_text not in text:
            text += b_text

    print("\n")
    result = _parse_json(text, shape="object")
    if not result:
        result = {"main_message": text.strip(), "lesson_line": "",
                  "shorter_variant": "", "optional_thought_prompt": "",
                  "signoff": "Love, Mama & Papa"}

    word_count = len(result.get("main_message", "").split())
    _ok(f"Message drafted ({word_count} words):")
    for line in result.get("main_message", "")[:250].split("\n"):
        print(f"    {DIM}{line}{RESET}")
    return result


# ---------------------------------------------------------------------------
# Agent 4 — memory_cue_designer
# Uses Haiku. Cost: ~$0.001/day
# ---------------------------------------------------------------------------

_CUE_SYSTEM = _load_prompt("04_memory_cue_designer")


def memory_cue_designer(selected_stories: list[dict]) -> dict:
    """Design the cocker spaniel image concept."""
    _bar(f"🎨  memory_cue_designer  |  {FAST_MODEL}", YELLOW)
    _step("Designing cocker spaniel visual memory cue...")
    _CUE = _build_system("04_memory_cue_designer", "visual-memory-cue")
    print(f"\n  {YELLOW}Concept:{RESET}\n  {'─'*50}\n  ", end="")

    text = ""
    with client.messages.stream(
        model=FAST_MODEL, max_tokens=500,
        system=_CUE,
        messages=[{"role": "user", "content":
                   f"Design concept for:\n{json.dumps(selected_stories, indent=2)}"}],
    ) as stream:
        for event in stream:
            if (event.type == "content_block_delta"
                    and hasattr(event, "delta")
                    and getattr(event.delta, "type", "") == "text_delta"):
                text += event.delta.text or ""
                if not text.lstrip().startswith("{"):
                    _stream(event.delta.text or "")
        response = stream.get_final_message()

    cost_tracker.add("memory_cue_designer", FAST_MODEL, response.usage)

    for b in response.content:
        b_text = getattr(b, "text", None)
        if b_text and b_text not in text:
            text += b_text

    print("\n")
    result = _parse_json(text, shape="object")
    _ok(f"Concept: {result.get('concept','')[:90]}...")
    return result


# ---------------------------------------------------------------------------
# Agent 5 — image_maker
# Uses Haiku. Cost: ~$0.001/day
# ---------------------------------------------------------------------------

_IMG_SYSTEM = _load_prompt("05_image_maker")


def image_maker(concept: dict, selected_stories: list[dict]) -> dict:
    """Write the image prompt — injects the tintin-type-image skill at runtime."""
    _bar(f"🖼️   image_maker  |  {FAST_MODEL}", GREEN)
    _step("Building system prompt (persona + instructions + skill)...")
    system = _build_system("05_image_maker", "tintin-type-image")

    print(f"\n  {GREEN}Prompt:{RESET}\n  {'─'*50}\n  ", end="")

    text = ""
    with client.messages.stream(
        model=FAST_MODEL, max_tokens=600,
        system=system,
        messages=[{"role": "user", "content":
                   f"Concept:\n{json.dumps(concept, indent=2)}\n"
                   f"Story titles: {[s.get('title','') for s in selected_stories]}"}],
    ) as stream:
        for event in stream:
            if (event.type == "content_block_delta"
                    and hasattr(event, "delta")
                    and getattr(event.delta, "type", "") == "text_delta"):
                text += event.delta.text or ""
                if not text.lstrip().startswith("{"):
                    _stream(event.delta.text or "")
        response = stream.get_final_message()

    cost_tracker.add("image_maker", FAST_MODEL, response.usage)

    for b in response.content:
        b_text = getattr(b, "text", None)
        if b_text and b_text not in text:
            text += b_text

    print("\n")
    result = _parse_json(text, shape="object")
    _ok("Image prompt ready.")
    return result


# ---------------------------------------------------------------------------
# Agent 6 — image_generator
# Calls DALL-E 3 (OpenAI) to generate the actual image.
# Style: Hergé Tintin ligne claire — clean bold outlines, flat colours.
# Cost: $0.04 per image (standard 1024×1024) ≈ $1.20/month
# Requires OPENAI_API_KEY in environment. Skips gracefully if not set.
# ---------------------------------------------------------------------------

def image_generator(image_prompt: str) -> dict:
    """
    Generate the actual image using DALL-E 3.

    Style is controlled by agents/06_image_generator/system_prompt.txt —
    edit the first line of that file to change art style (no Python needed).

    Returns:
        {"url": str, "revised_prompt": str}   on success
        {}                                     if OPENAI_API_KEY not set or generation fails
    """
    import os
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        _step("OPENAI_API_KEY not set — skipping image generation (sending text prompt instead)")
        return {}

    # Load settings from agents/06_image_generator/system_prompt.txt
    # First line = style prefix. Lines with "key: value" = model settings.
    config_text = _load_prompt("06_image_generator")
    config_lines = config_text.split("\n")
    style_guide  = config_lines[0].strip()

    settings = {"model": "gpt-image-1", "size": "1024x1024", "quality": "medium"}
    for line in config_lines:
        for key in settings:
            if line.strip().lower().startswith(f"{key}:"):
                settings[key] = line.split(":", 1)[1].strip()

    _bar(f"🎨  image_generator  |  {settings['model']}  ({settings['quality']})", GREEN)
    _step(f"Skill: Tintin type image")
    _step(f"Model: {settings['model']}  size: {settings['size']}  quality: {settings['quality']}")
    _step("Generating image...")

    try:
        import openai
        oa_client = openai.OpenAI(api_key=api_key)

        full_prompt = style_guide + " " + image_prompt
        if len(full_prompt) > 3900:
            full_prompt = full_prompt[:3900]

        # Build kwargs — gpt-image-1 and dall-e-3 share the same API surface
        gen_kwargs = dict(model=settings["model"], prompt=full_prompt,
                         size=settings["size"], n=1)
        if settings["model"] == "dall-e-3":
            gen_kwargs["quality"] = settings["quality"]  # standard | hd
        else:
            gen_kwargs["quality"] = settings["quality"]  # low | medium | high | auto

        response = oa_client.images.generate(**gen_kwargs)
        url = response.data[0].url
        revised = getattr(response.data[0], "revised_prompt", "")
        _ok("Image generated successfully")
        _step(f"URL: {url[:80]}...")
        return {"url": url, "revised_prompt": revised}

    except ImportError:
        _step("openai package not installed — run: pip install openai")
        return {}
    except Exception as e:
        _step(f"Image generation failed: {e}")
        return {}
