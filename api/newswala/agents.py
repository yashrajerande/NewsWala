"""
NewsWala — agent implementations.

Six agents working as a newsroom pipeline:

    news_scout → family_fit_editor → whatsapp_copywriter
                                   → memory_cue_designer → image_maker

Each agent is a plain function: takes input, returns output, prints
everything it's thinking to the terminal so there are no black boxes.

Speed note: news_scout uses Sonnet (faster web search). The creative
agents that need taste and judgment use Opus.
"""

import json
import sys
import anthropic

from .config import FAMILY, CATEGORIES, PREFERRED_SOURCES, AVOID_TOPICS, MAX_STORIES

# model for search / fast tasks — Sonnet is much quicker here
SCOUT_MODEL  = "claude-sonnet-4-6"
# model for creative / editorial tasks — Opus for taste and judgment
WRITE_MODEL  = "claude-opus-4-6"

client = anthropic.Anthropic()


# ---------------------------------------------------------------------------
# terminal helpers — color + streaming
# ---------------------------------------------------------------------------

BOLD    = "\033[1m"
DIM     = "\033[2m"
CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
BLUE    = "\033[94m"
MAGENTA = "\033[95m"
RED     = "\033[91m"
RESET   = "\033[0m"

def _bar(label: str, color: str = CYAN):
    """Print a clear agent header bar."""
    print(f"\n{color}{BOLD}{'━' * 54}{RESET}")
    print(f"{color}{BOLD}  {label}{RESET}")
    print(f"{color}{BOLD}{'━' * 54}{RESET}")

def _handoff(from_agent: str, to_agent: str, summary: str):
    """Print a handoff message between agents."""
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
# helper: extract JSON from Claude's response text
# ---------------------------------------------------------------------------

def _parse_json(text: str, shape: str = "object") -> dict | list:
    """
    Pull the first JSON object or array out of `text`.
    shape = "object" → look for { ... }
    shape = "array"  → look for [ ... ]
    Falls back to asking Claude to reformat if parsing fails.
    """
    open_c, close_c = ("{", "}") if shape == "object" else ("[", "]")
    start = text.find(open_c)
    end   = text.rfind(close_c) + 1
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

    # fallback: ask Claude to clean it up
    _step("JSON parse failed — asking Claude to reformat...")
    resp = client.messages.create(
        model=SCOUT_MODEL,
        max_tokens=4000,
        messages=[{
            "role": "user",
            "content": f"Extract the JSON {shape} from this text. Return ONLY valid JSON:\n\n{text[:6000]}",
        }],
    )
    clean = resp.content[0].text
    s = clean.find(open_c)
    e = clean.rfind(close_c) + 1
    if s != -1 and e > s:
        return json.loads(clean[s:e])
    return [] if shape == "array" else {}


# ---------------------------------------------------------------------------
# Agent 1 — news_scout
# searches the live web for today's best stories
# ---------------------------------------------------------------------------

_SCOUT_SYSTEM = f"""You are news_scout. Search the web for today's most interesting,
inspiring news from Economics, STEM, and India-relevant Current Affairs.

Family: daughters Manishka (18) and Divyana (11), parents Yash & Pooja, India-based.

Preferred sources: {', '.join(PREFERRED_SOURCES[:8])}
Avoid: {', '.join(AVOID_TOPICS[:5])}

Score each story on: credibility, novelty, inspiration, educational_value,
india_relevance, child_suitability, memorability, lesson_potential (each 1-10, total /80).

Return ONLY a JSON array of 4-6 stories. Each story:
{{
  "title": str, "category": "Economics|STEM|Current Affairs",
  "source": str, "url": str,
  "summary": "2-3 sentences",
  "why_interesting": str, "india_relevance": str,
  "scores": {{"credibility":N,"novelty":N,"inspiration":N,"educational_value":N,
              "india_relevance":N,"child_suitability":N,"memorability":N,
              "lesson_potential":N,"total":N}},
  "lesson_or_moral": str
}}"""


def news_scout(run_date: str) -> list[dict]:
    """
    Scan the live web for candidate stories.
    Uses Sonnet + web_search for speed. Streams search queries live.
    Returns list of scored candidate dicts.
    """
    _bar(f"🔍  news_scout  |  {run_date}", CYAN)
    _step(f"Using {SCOUT_MODEL} with live web search")
    _step("Searching Economics, STEM, and India Current Affairs...")

    messages = [{
        "role": "user",
        "content": (
            f"Today is {run_date}. Search the web for the most interesting inspiring news "
            f"from Economics, STEM, and India current affairs in the last 24-48 hours. "
            f"Search at least 3 different queries across the categories. "
            f"Use credible sources. Return a JSON array of 4-6 scored candidate stories."
        ),
    }]

    tools  = [{"type": "web_search_20260209", "name": "web_search"}]
    text   = ""
    n_searches = 0

    for attempt in range(4):  # max 4 server-side passes
        with client.messages.stream(
            model=SCOUT_MODEL,
            max_tokens=6000,
            system=_SCOUT_SYSTEM,
            tools=tools,
            messages=messages,
        ) as stream:
            for event in stream:
                # show each web search query as it fires
                if (event.type == "content_block_start"
                        and hasattr(event, "content_block")
                        and getattr(event.content_block, "type", "") == "server_tool_use"):
                    q = getattr(event.content_block, "input", {})
                    query_str = q.get("query", str(q)) if isinstance(q, dict) else str(q)
                    n_searches += 1
                    _step(f"🌐  search #{n_searches}: \"{query_str}\"")

                # stream Claude's commentary (not the JSON blob)
                elif (event.type == "content_block_delta"
                      and hasattr(event, "delta")
                      and getattr(event.delta, "type", "") == "text_delta"):
                    chunk = event.delta.text
                    text += chunk
                    if not text.lstrip().startswith("["):
                        _stream(chunk)

            response = stream.get_final_message()

        # collect any text blocks we might have missed
        for block in response.content:
            if hasattr(block, "text") and block.text not in text:
                text += block.text

        if response.stop_reason == "end_turn":
            break
        if response.stop_reason == "pause_turn":
            # server hit its loop limit — append and ask it to continue
            messages.append({"role": "assistant", "content": response.content})
            _step("Server paused — continuing...")
            continue
        break  # any other stop reason → done

    print()
    candidates = _parse_json(text, shape="array")
    _ok(f"Found {len(candidates)} candidate stories:")
    for i, s in enumerate(candidates, 1):
        score = s.get("scores", {}).get("total", "?")
        print(f"    {DIM}[{i}] {s.get('title','?')}  ({s.get('category','')})  {score}/80{RESET}")

    return candidates


# ---------------------------------------------------------------------------
# Agent 2 — family_fit_editor
# picks the best 1 (or at most 2) stories for this family
# ---------------------------------------------------------------------------

_EDITOR_SYSTEM = f"""You are family_fit_editor for NewsWala.

Pick the BEST 1 story (or 2 if two are exceptional) from the candidates.
Every selected story must be age-safe for an 11-year-old, have a clear lesson,
and spark curiosity in both daughters at once.

Reject: graphic violence, partisan politics, adult themes, trivial content.
If picking 2, choose stories from different categories.

Think out loud before deciding. Then return ONLY a JSON array of selected stories,
each with the original fields plus:
  "why_selected": str   — why this beat the others
  "family_fit_notes": str — how it works specifically for this family
  "lesson_or_moral": str  — one crisp, memorable sentence"""


def family_fit_editor(candidates: list[dict]) -> list[dict]:
    """
    Filter candidates to the best 1-2 stories for Manishka & Divyana.
    Streams the reasoning so you can see the editorial judgment live.
    """
    _bar(f"🧐  family_fit_editor  |  {len(candidates)} candidates", MAGENTA)
    _step(f"Using {WRITE_MODEL} with adaptive thinking")
    _step("Reading all candidates and judging family fit...")
    print(f"\n  {MAGENTA}Reasoning:{RESET}")
    print(f"  {'─'*50}")
    print("  ", end="")

    text = ""

    with client.messages.stream(
        model=WRITE_MODEL,
        max_tokens=4000,
        thinking={"type": "adaptive"},
        system=_EDITOR_SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                f"Candidates:\n{json.dumps(candidates, indent=2)}\n\n"
                f"Think through each story, then pick the best 1 (or at most 2)."
            ),
        }],
    ) as stream:
        for event in stream:
            if event.type == "content_block_delta" and hasattr(event, "delta"):
                dt = getattr(event.delta, "type", "")
                if dt == "thinking_delta":
                    _stream(f"{DIM}{event.delta.thinking}{RESET}")
                elif dt == "text_delta":
                    text += event.delta.text
                    if not text.lstrip().startswith("["):
                        _stream(event.delta.text)
        response = stream.get_final_message()

    for b in response.content:
        if hasattr(b, "text") and b.text not in text:
            text += b.text

    print("\n")
    selected = _parse_json(text, shape="array")
    selected = selected[:MAX_STORIES]

    _ok(f"Selected {len(selected)} story/stories:")
    for s in selected:
        print(f"    {GREEN}→ {s.get('title','?')}{RESET}")
        print(f"    {DIM}  {s.get('why_selected','')}{RESET}")

    return selected


# ---------------------------------------------------------------------------
# Agent 3 — whatsapp_copywriter
# turns the selected story into a family message
# ---------------------------------------------------------------------------

_COPY_SYSTEM = """You are whatsapp_copywriter for NewsWala.

Write a short, warm, intelligent WhatsApp message from Yash and Pooja to their
daughters Manishka (18) and Divyana (11).

Voice: thoughtful modern Indian family. Under 250 words. No preaching.
No babyish tone. No motivational clichés. Max 1-2 emojis. Factually accurate.

Structure:
1. Catchy opening
2. Core story in 2-4 plain sentences
3. Why it's cool
4. ONE memorable lesson sentence
5. Optional thought-prompt question
6. Sign-off: "Love, Mama & Papa"

Return ONLY valid JSON — no markdown, no preamble:
{
  "main_message": str,
  "lesson_line": str,
  "shorter_variant": str,
  "optional_thought_prompt": str,
  "signoff": "Love, Mama & Papa"
}"""


def whatsapp_copywriter(selected_stories: list[dict]) -> dict:
    """
    Write the WhatsApp-ready family message. Streams the draft live
    so you can watch it being written.
    """
    _bar("✍️   whatsapp_copywriter", BLUE)
    _step(f"Using {WRITE_MODEL} with adaptive thinking")
    _step("Drafting message for Manishka & Divyana from Yash & Pooja...")
    print(f"\n  {BLUE}Draft:{RESET}")
    print(f"  {'─'*50}")
    print("  ", end="")

    text = ""

    with client.messages.stream(
        model=WRITE_MODEL,
        max_tokens=3000,
        thinking={"type": "adaptive"},
        system=_COPY_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"Stories:\n{json.dumps(selected_stories, indent=2)}",
        }],
    ) as stream:
        for event in stream:
            if event.type == "content_block_delta" and hasattr(event, "delta"):
                dt = getattr(event.delta, "type", "")
                if dt == "thinking_delta":
                    _stream(f"{DIM}{event.delta.thinking}{RESET}")
                elif dt == "text_delta":
                    text += event.delta.text
                    if not text.lstrip().startswith("{"):
                        _stream(event.delta.text)
        response = stream.get_final_message()

    for b in response.content:
        if hasattr(b, "text") and b.text not in text:
            text += b.text

    print("\n")
    result = _parse_json(text, shape="object")

    if not result:
        result = {"main_message": text.strip(), "lesson_line": "",
                  "shorter_variant": "", "optional_thought_prompt": "",
                  "signoff": "Love, Mama & Papa"}

    _ok("Message drafted. Preview:")
    for line in result.get("main_message", "")[:220].split("\n"):
        print(f"    {DIM}{line}{RESET}")
    print(f"    {DIM}...{RESET}")

    return result


# ---------------------------------------------------------------------------
# Agent 4 — memory_cue_designer
# creates the cocker spaniel image concept
# ---------------------------------------------------------------------------

_CUE_SYSTEM = """You are memory_cue_designer for NewsWala.

Design a charming image concept that uses the family's cocker spaniel as a
visual memory hook for the news story.

Rules:
- ALWAYS cocker spaniel, always doing something tied to the story
- Warm, whimsical, not hyper-realistic
- Simple composition (1-3 elements)
- Square format

Return ONLY valid JSON:
{
  "concept": str,
  "visual_elements": [str, ...],
  "colour_mood": str,
  "memory_hook": str
}"""


def memory_cue_designer(selected_stories: list[dict]) -> dict:
    """
    Design the cocker spaniel image concept. Streams the output live.
    """
    _bar("🎨  memory_cue_designer", YELLOW)
    _step(f"Using {SCOUT_MODEL}")
    _step("Designing cocker spaniel visual memory cue...")
    print(f"\n  {YELLOW}Concept:{RESET}")
    print(f"  {'─'*50}")
    print("  ", end="")

    text = ""

    with client.messages.stream(
        model=SCOUT_MODEL,
        max_tokens=1000,
        system=_CUE_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"Design a cocker spaniel image concept for:\n{json.dumps(selected_stories, indent=2)}",
        }],
    ) as stream:
        for event in stream:
            if (event.type == "content_block_delta"
                    and hasattr(event, "delta")
                    and getattr(event.delta, "type", "") == "text_delta"):
                text += event.delta.text
                if not text.lstrip().startswith("{"):
                    _stream(event.delta.text)
        response = stream.get_final_message()

    for b in response.content:
        if hasattr(b, "text") and b.text not in text:
            text += b.text

    print("\n")
    result = _parse_json(text, shape="object")
    _ok(f"Concept: {result.get('concept','')[:90]}...")
    return result


# ---------------------------------------------------------------------------
# Agent 5 — image_maker
# turns the concept into a DALL-E / Midjourney prompt
# ---------------------------------------------------------------------------

_IMG_SYSTEM = """You are image_maker for NewsWala.

Turn an image concept into a production-ready prompt for DALL-E 3 / Midjourney.

Requirements: square 1:1, cocker spaniel as visual centre, warm digital
illustration style, bright family-friendly palette, clean composition.

Prompt structure: Subject + Action + Setting + Style + Mood + Lighting + Colours

Return ONLY valid JSON:
{
  "image_prompt": str,
  "negative_prompt": str,
  "style_tags": [str, ...],
  "alt_text": str
}"""


def image_maker(concept: dict, selected_stories: list[dict]) -> dict:
    """
    Write the final image generation prompt. Streams the output live.
    """
    _bar("🖼️   image_maker", GREEN)
    _step(f"Using {SCOUT_MODEL}")
    _step("Writing DALL-E / Midjourney prompt...")
    print(f"\n  {GREEN}Prompt:{RESET}")
    print(f"  {'─'*50}")
    print("  ", end="")

    text = ""

    with client.messages.stream(
        model=SCOUT_MODEL,
        max_tokens=1000,
        system=_IMG_SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                f"Concept:\n{json.dumps(concept, indent=2)}\n\n"
                f"Stories: {[s.get('title','') for s in selected_stories]}"
            ),
        }],
    ) as stream:
        for event in stream:
            if (event.type == "content_block_delta"
                    and hasattr(event, "delta")
                    and getattr(event.delta, "type", "") == "text_delta"):
                text += event.delta.text
                if not text.lstrip().startswith("{"):
                    _stream(event.delta.text)
        response = stream.get_final_message()

    for b in response.content:
        if hasattr(b, "text") and b.text not in text:
            text += b.text

    print("\n")
    result = _parse_json(text, shape="object")
    _ok("Image prompt ready.")
    return result
