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
│ news_scout           │ Sonnet 4.6       │ needs web search tool        │
│ family_fit_editor    │ Haiku 4.5        │ structured filtering, cheap  │
│ whatsapp_copywriter  │ Sonnet 4.6       │ needs writing quality        │
│ memory_cue_designer  │ Haiku 4.5        │ simple creative task         │
│ image_maker          │ Haiku 4.5        │ mechanical prompt writing    │
└──────────────────────┴──────────────────┴──────────────────────────────┘

Pricing ($/1M tokens):  Sonnet: $3 in / $15 out   Haiku: $1 in / $5 out
NO adaptive thinking — thinking tokens multiply output cost 5-10x.

Estimated daily cost:  ~$0.05-0.08
Estimated monthly:     ~$1.50-2.50  (well within $5 budget)
"""

import json
import sys
from datetime import date, timedelta
from pathlib import Path
import anthropic

from .config import MAX_STORIES

# --- models ------------------------------------------------------------------
SCOUT_MODEL = "claude-sonnet-4-6"   # web search + research
WRITE_MODEL = "claude-sonnet-4-6"   # WhatsApp copy needs quality
FAST_MODEL  = "claude-haiku-4-5"    # filtering, image prompts — cheap & fast

client = anthropic.Anthropic()

# --- story history file (prevents repeating news) ----------------------------
# Stored at project root: ~/NewsWala/newswala_history.json
_HISTORY_FILE = Path(__file__).resolve().parents[2] / "newswala_history.json"
_HISTORY_DAYS = 14   # remember stories from the last 14 days


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
# Strict date-filtered searches, equal spread across all 3 categories,
# history-aware to avoid repeating stories.
# Cost: ~$0.03-0.05/day
# ---------------------------------------------------------------------------

_SCOUT_SYSTEM = """You are news_scout for NewsWala, a daily family digest.

STRICT RULES:
1. ONLY stories published TODAY or yesterday (last 48 hours). Reject anything older.
2. MUST find stories across ALL THREE categories — at least 1-2 from each:
   - Economics & Business (India economy, markets, policy, startups, trade)
   - STEM & Science (space, AI, medicine, climate, tech breakthroughs)
   - Current Affairs & Policy (governance, education, India on world stage,
     social progress, geopolitics with educational angle)
3. Age-safe for an 11-year-old. No crime, violence, partisan politics.
4. Each story must have a clear lesson or moral.
5. Prefer India-relevant stories. Global stories must have clear India connection.

Return ONLY a JSON array of 4-6 stories — at least 1 per category:
[{
  "title": str,
  "category": "Economics | STEM | Current Affairs",
  "source": str,
  "url": str,
  "published_date": "YYYY-MM-DD or 'today'",
  "summary": "2-3 sentences",
  "why_interesting": str,
  "india_relevance": str,
  "scores": {
    "credibility": N, "novelty": N, "inspiration": N,
    "educational_value": N, "india_relevance": N,
    "child_suitability": N, "memorability": N,
    "lesson_potential": N, "total": N
  },
  "lesson_or_moral": str
}]"""


def news_scout(run_date: str) -> list[dict]:
    """
    Search live web for today's candidate stories.
    - Searches are date-stamped to get only fresh news
    - Explicitly covers all 3 categories in separate searches
    - Filters out stories already sent (from history file)
    """
    _bar(f"🔍  news_scout  |  {run_date}  |  {SCOUT_MODEL}", CYAN)

    # load history to tell Claude what to avoid
    history = load_history()
    avoid_titles = [h["title"] for h in history[-10:]]  # last 10 sent stories
    if avoid_titles:
        _step(f"History: avoiding {len(avoid_titles)} recently sent stories")
        for t in avoid_titles:
            _step(f"  ↳ skip: {t[:70]}")

    avoid_block = ""
    if avoid_titles:
        avoid_block = (
            f"\n\nAVOID these topics — already sent recently:\n"
            + "\n".join(f"- {t}" for t in avoid_titles)
        )

    messages = [{"role": "user", "content": (
        f"Today's date: {run_date}.\n\n"
        f"Search for news published ON {run_date} or yesterday only.\n\n"
        f"Do EXACTLY these 3 searches — one per category:\n"
        f"1. Economics & Business: India economy, policy, startups, trade, RBI, budget news {run_date}\n"
        f"2. STEM & Science: India space, AI, science breakthrough, technology, health {run_date}\n"
        f"3. Current Affairs & Policy: India governance, education reform, geopolitics, "
        f"   social progress, India world stage {run_date}\n\n"
        f"Use sources: The Hindu, LiveMint, Reuters, BBC, Business Standard, ISRO, PIB.\n"
        f"Return a JSON array of 4-6 stories with at least 1 from each category."
        f"{avoid_block}"
    )}]

    tools    = [{"type": "web_search_20260209", "name": "web_search"}]
    text     = ""
    n_search = 0

    for attempt in range(2):
        with client.messages.stream(
            model=SCOUT_MODEL, max_tokens=3000,
            system=_SCOUT_SYSTEM, tools=tools, messages=messages,
        ) as stream:
            for event in stream:
                if (event.type == "content_block_start"
                        and hasattr(event, "content_block")
                        and getattr(event.content_block, "type", "") == "server_tool_use"):
                    inp = getattr(event.content_block, "input", None)
                    query_str = ""
                    if isinstance(inp, dict):
                        query_str = inp.get("query", "").strip()
                    elif inp:
                        query_str = str(inp).strip()
                    if query_str and query_str not in ("{}", ""):
                        n_search += 1
                        _step(f"🌐  search #{n_search}: \"{query_str}\"")

                elif (event.type == "content_block_delta"
                        and hasattr(event, "delta")
                        and getattr(event.delta, "type", "") == "text_delta"):
                    chunk = event.delta.text or ""
                    text += chunk
                    if not text.lstrip().startswith("["):
                        _stream(chunk)

            response = stream.get_final_message()

        cost_tracker.add("news_scout", SCOUT_MODEL, response.usage)

        for b in response.content:
            b_text = getattr(b, "text", None)
            if b_text and b_text not in text:
                text += b_text

        if response.stop_reason == "end_turn":
            break
        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
            _step("Server paused — continuing...")
            continue
        break

    print()
    candidates = _parse_json(text, shape="array")

    # show category spread
    categories = {}
    for s in candidates:
        c = s.get("category", "Unknown")
        categories[c] = categories.get(c, 0) + 1

    _ok(f"Found {len(candidates)} candidate stories:")
    for i, s in enumerate(candidates, 1):
        score = s.get("scores", {}).get("total", "?")
        pub   = s.get("published_date", "")
        print(f"    {DIM}[{i}] [{s.get('category','?')}] {s.get('title','?')[:60]}  "
              f"score:{score}/80  {pub}{RESET}")

    # warn if a category is missing
    for cat in ["Economics", "STEM", "Current Affairs"]:
        if not any(cat.lower() in s.get("category","").lower() for s in candidates):
            _step(f"⚠️  No {cat} story found — consider re-running")

    return candidates


# ---------------------------------------------------------------------------
# Agent 2 — family_fit_editor
# Uses Haiku — structured filtering.
# Cost: ~$0.003-0.005/day
# ---------------------------------------------------------------------------

_EDITOR_SYSTEM = """You are family_fit_editor for NewsWala.

Pick the BEST 1 story (2 only if two are truly exceptional and from DIFFERENT categories).
Requirements:
- Age-safe for an 11-year-old
- Clear memorable lesson
- Emotionally uplifting, not scary or negative
- No partisan politics, no graphic content
- Prefer variety: if picking 2, choose different categories

Return ONLY a JSON array of selected stories with original fields plus:
  "why_selected": str
  "family_fit_notes": str
  "lesson_or_moral": str"""


def family_fit_editor(candidates: list[dict]) -> list[dict]:
    """Filter to best 1-2 stories. Uses Haiku for speed and cost."""
    _bar(f"🧐  family_fit_editor  |  {len(candidates)} candidates  |  {FAST_MODEL}", MAGENTA)
    _step("Evaluating age-safety, lesson quality, category spread...")
    print(f"\n  {MAGENTA}Filtering:{RESET}\n  {'─'*50}\n  ", end="")

    text = ""
    with client.messages.stream(
        model=FAST_MODEL, max_tokens=2000,
        system=_EDITOR_SYSTEM,
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

_COPY_SYSTEM = """You are whatsapp_copywriter for NewsWala.

Write a short warm WhatsApp message from Yash and Pooja to daughters Manishka (18) and Divyana (11).

HARD LIMIT: main_message must be under 180 words. Count carefully.
Voice: thoughtful modern Indian family. Warm but smart.
No preaching. No babyish tone. No clichés. Max 2 emojis. Factually accurate.

Structure:
1. Catchy opening line
2. Story in 2-3 plain sentences (accurate, simple for an 11-year-old)
3. Why it's cool / why it matters
4. ONE memorable lesson sentence
5. Optional: one short thought-prompt question
6. Sign-off: "Love, Mama & Papa"

Return ONLY valid JSON (no markdown, no code blocks):
{
  "main_message": "under 180 words including sign-off",
  "lesson_line": "the standalone lesson sentence",
  "shorter_variant": "3-4 lines max",
  "optional_thought_prompt": "one question",
  "signoff": "Love, Mama & Papa"
}"""


def whatsapp_copywriter(selected_stories: list[dict]) -> dict:
    """Write the WhatsApp message. Streams the draft live."""
    _bar(f"✍️   whatsapp_copywriter  |  {WRITE_MODEL}", BLUE)
    _step("Writing family message (max 180 words)...")
    print(f"\n  {BLUE}Draft:{RESET}\n  {'─'*50}\n  ", end="")

    text = ""
    with client.messages.stream(
        model=WRITE_MODEL, max_tokens=1000,
        system=_COPY_SYSTEM,
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

_CUE_SYSTEM = """You are memory_cue_designer for NewsWala.

Design a charming image concept using the family's cocker spaniel as a visual
memory hook for the news story. The dog MUST be a cocker spaniel doing something
directly tied to the story. Warm, whimsical, simple (1-3 elements), square format.

Return ONLY valid JSON (no markdown, no code blocks):
{"concept": str, "visual_elements": [str], "colour_mood": str, "memory_hook": str}"""


def memory_cue_designer(selected_stories: list[dict]) -> dict:
    """Design the cocker spaniel image concept."""
    _bar(f"🎨  memory_cue_designer  |  {FAST_MODEL}", YELLOW)
    _step("Designing cocker spaniel visual memory cue...")
    print(f"\n  {YELLOW}Concept:{RESET}\n  {'─'*50}\n  ", end="")

    text = ""
    with client.messages.stream(
        model=FAST_MODEL, max_tokens=500,
        system=_CUE_SYSTEM,
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

_IMG_SYSTEM = """You are image_maker for NewsWala.

Turn an image concept into a DALL-E 3 prompt.
Requirements: square 1:1, cocker spaniel as visual centre, Hergé Tintin ligne
claire style (clean bold outlines, flat bright colours, no gradients),
warm family-friendly palette, clean simple composition, 3 elements max.

Return ONLY valid JSON (no markdown, no code blocks):
{"image_prompt": str, "negative_prompt": str, "style_tags": [str], "alt_text": str}"""


def image_maker(concept: dict, selected_stories: list[dict]) -> dict:
    """Write the DALL-E 3 prompt in Tintin/Hergé style."""
    _bar(f"🖼️   image_maker  |  {FAST_MODEL}", GREEN)
    _step("Writing DALL-E 3 prompt (Hergé/Tintin ligne claire style)...")
    print(f"\n  {GREEN}Prompt:{RESET}\n  {'─'*50}\n  ", end="")

    text = ""
    with client.messages.stream(
        model=FAST_MODEL, max_tokens=500,
        system=_IMG_SYSTEM,
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

_TINTIN_PREFIX = (
    "Hergé Tintin ligne claire style comic illustration: "
    "clean bold black outlines, flat bright colours, no gradients, no shading, "
    "simple geometric background, square comic panel format. "
)


def image_generator(image_prompt: str) -> dict:
    """
    Generate the actual image using DALL-E 3.

    Returns:
        {"url": str, "revised_prompt": str}   on success
        {}                                     if OPENAI_API_KEY not set or generation fails
    """
    import os
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        _step("OPENAI_API_KEY not set — skipping image generation (sending text prompt instead)")
        return {}

    _bar("🎨  image_generator  |  DALL-E 3  (~$0.04)", GREEN)
    _step("Generating Hergé/Tintin style image...")

    try:
        import openai
        oa_client = openai.OpenAI(api_key=api_key)

        full_prompt = _TINTIN_PREFIX + image_prompt
        # DALL-E 3 prompt limit: 4000 chars
        if len(full_prompt) > 3900:
            full_prompt = full_prompt[:3900]

        response = oa_client.images.generate(
            model="dall-e-3",
            prompt=full_prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        url = response.data[0].url
        revised = getattr(response.data[0], "revised_prompt", "")
        _ok(f"Image generated successfully")
        _step(f"URL: {url[:80]}...")
        return {"url": url, "revised_prompt": revised}

    except ImportError:
        _step("openai package not installed — run: pip install openai")
        return {}
    except Exception as e:
        _step(f"Image generation failed: {e}")
        return {}
