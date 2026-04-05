"""
NewsWala — agent implementations.

Pipeline:
    news_scout → family_fit_editor → whatsapp_copywriter
                                   → memory_cue_designer → image_maker

Cost budget: < $5 / month (running daily)

Model assignments — chosen for cost/quality tradeoff:
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
NO adaptive thinking anywhere — thinking tokens multiply output cost 5-10x.

Estimated daily cost:  ~$0.05-0.08
Estimated monthly:     ~$1.50-2.50  (well within $5 budget)
"""

import json
import sys
import anthropic

from .config import MAX_STORIES

# --- models ------------------------------------------------------------------
SCOUT_MODEL = "claude-sonnet-4-6"   # web search + research
WRITE_MODEL = "claude-sonnet-4-6"   # WhatsApp copy needs quality
FAST_MODEL  = "claude-haiku-4-5"    # filtering, image prompts — cheap & fast

client = anthropic.Anthropic()


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
    # last resort: ask Claude to clean it up
    _step("JSON parse failed — asking Claude to reformat...")
    resp = client.messages.create(
        model=FAST_MODEL, max_tokens=2000,
        messages=[{"role": "user",
                   "content": f"Extract the JSON {shape} from this text. Return ONLY valid JSON:\n\n{text[:4000]}"}],
    )
    clean = resp.content[0].text
    s = clean.find(open_c)
    e = clean.rfind(close_c) + 1
    if s != -1 and e > s:
        return json.loads(clean[s:e])
    return [] if shape == "array" else {}


# ---------------------------------------------------------------------------
# Agent 1 — news_scout
# Uses Sonnet + live web search. Streams search queries as they fire.
# Cost: ~$0.03-0.05/day (Sonnet, ~2k in + 2k out)
# ---------------------------------------------------------------------------

_SCOUT_SYSTEM = """You are news_scout for NewsWala, a daily family digest.

Search the web for today's best news across Economics, STEM, and India Current Affairs.
The audience: daughters Manishka (18) and Divyana (11), parents Yash & Pooja, India.

Good stories: India-relevant, inspiring, educational, age-safe, have a clear lesson.
Avoid: crime, graphic violence, partisan politics, celebrity gossip, pure market noise.

Return ONLY a JSON array of 4-6 stories:
[{
  "title": str, "category": "Economics|STEM|Current Affairs",
  "source": str, "url": str, "summary": "2-3 sentences",
  "why_interesting": str, "india_relevance": str,
  "scores": {"credibility":N,"novelty":N,"inspiration":N,"educational_value":N,
             "india_relevance":N,"child_suitability":N,"memorability":N,
             "lesson_potential":N,"total":N},
  "lesson_or_moral": str
}]"""


def news_scout(run_date: str) -> list[dict]:
    """Search live web for candidate stories. Streams search queries live."""
    _bar(f"🔍  news_scout  |  {run_date}  |  {SCOUT_MODEL}", CYAN)
    _step("Searching Economics, STEM, India Current Affairs...")

    messages = [{"role": "user", "content": (
        f"Today is {run_date}. Search the web for the most interesting inspiring news "
        f"from Economics, STEM, and India current affairs in the last 24-48 hours. "
        f"Do 3 separate searches across the categories. Use BBC, Reuters, The Hindu, "
        f"Mint, ISRO, Nature as sources. Return a JSON array of 4-6 scored stories."
    )}]
    tools    = [{"type": "web_search_20260209", "name": "web_search"}]
    text     = ""
    n_search = 0

    for attempt in range(2):   # max 2 server passes
        with client.messages.stream(
            model=SCOUT_MODEL, max_tokens=3000,
            system=_SCOUT_SYSTEM, tools=tools, messages=messages,
        ) as stream:
            for event in stream:
                # show each web search query as it fires (skip empty input blocks)
                if (event.type == "content_block_start"
                        and hasattr(event, "content_block")
                        and getattr(event.content_block, "type", "") == "server_tool_use"):
                    inp = getattr(event.content_block, "input", None)
                    if isinstance(inp, dict):
                        query_str = inp.get("query", "").strip()
                    elif inp:
                        query_str = str(inp).strip()
                    else:
                        query_str = ""
                    if query_str and query_str != "{}":
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

        # guard against None text blocks before string membership test
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
    _ok(f"Found {len(candidates)} candidate stories:")
    for i, s in enumerate(candidates, 1):
        score = s.get("scores", {}).get("total", "?")
        print(f"    {DIM}[{i}] {s.get('title','?')}  ({s.get('category','')})  {score}/80{RESET}")
    return candidates


# ---------------------------------------------------------------------------
# Agent 2 — family_fit_editor
# Uses Haiku — structured filtering, no creativity needed.
# Cost: ~$0.003-0.005/day (Haiku, ~1.5k in + 600 out)
# ---------------------------------------------------------------------------

_EDITOR_SYSTEM = """You are family_fit_editor for NewsWala.

Pick the BEST 1 story (2 only if two are truly exceptional) from candidates.
Requirements: age-safe for an 11-year-old, clear lesson, emotionally uplifting,
no graphic violence, no partisan politics, no adult themes.
If picking 2, choose different categories.

Return ONLY a JSON array of selected stories with original fields plus:
  "why_selected": str
  "family_fit_notes": str
  "lesson_or_moral": str"""


def family_fit_editor(candidates: list[dict]) -> list[dict]:
    """Filter to best 1-2 stories. Uses Haiku for speed and cost."""
    _bar(f"🧐  family_fit_editor  |  {len(candidates)} candidates  |  {FAST_MODEL}", MAGENTA)
    _step("Evaluating age-safety, lesson quality, and family fit...")
    print(f"\n  {MAGENTA}Filtering:{RESET}\n  {'─'*50}\n  ", end="")

    text = ""
    with client.messages.stream(
        model=FAST_MODEL, max_tokens=2000,
        system=_EDITOR_SYSTEM,
        messages=[{"role": "user", "content": (
            f"Candidates:\n{json.dumps(candidates, indent=2)}\n\n"
            f"Pick the best 1 (or at most 2) stories."
        )}],
    ) as stream:
        for event in stream:
            if (event.type == "content_block_delta"
                    and hasattr(event, "delta")
                    and getattr(event.delta, "type", "") == "text_delta"):
                text += event.delta.text
                if not text.lstrip().startswith("["):
                    _stream(event.delta.text)
        response = stream.get_final_message()

    for b in response.content:
        b_text = getattr(b, "text", None)
        if b_text and b_text not in text:
            text += b_text

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
# Uses Sonnet — the one place where writing quality really matters.
# NO thinking — saves ~$0.05-0.10/day vs Opus+thinking.
# Cost: ~$0.01-0.015/day (Sonnet, ~1k in + 600 out)
# ---------------------------------------------------------------------------

_COPY_SYSTEM = """You are whatsapp_copywriter for NewsWala.

Write a short warm WhatsApp message from Yash and Pooja to daughters Manishka (18) and Divyana (11).

Voice: thoughtful modern Indian family. Warm but smart. Max 200 words.
No preaching. No babyish tone. No clichés. Max 2 emojis. Factually accurate.

Structure: catchy opening → story in 3 plain sentences → why it's cool →
one memorable lesson sentence → optional question → "Love, Mama & Papa"

Return ONLY valid JSON:
{
  "main_message": str,
  "lesson_line": str,
  "shorter_variant": "3-4 lines max",
  "optional_thought_prompt": str,
  "signoff": "Love, Mama & Papa"
}"""


def whatsapp_copywriter(selected_stories: list[dict]) -> dict:
    """Write the WhatsApp message. Streams the draft live."""
    _bar(f"✍️   whatsapp_copywriter  |  {WRITE_MODEL}", BLUE)
    _step("Writing family message for Manishka & Divyana...")
    print(f"\n  {BLUE}Draft:{RESET}\n  {'─'*50}\n  ", end="")

    text = ""
    with client.messages.stream(
        model=WRITE_MODEL, max_tokens=1200,
        system=_COPY_SYSTEM,
        messages=[{"role": "user", "content":
                   f"Stories:\n{json.dumps(selected_stories, indent=2)}"}],
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
        b_text = getattr(b, "text", None)
        if b_text and b_text not in text:
            text += b_text

    print("\n")
    result = _parse_json(text, shape="object")
    if not result:
        result = {"main_message": text.strip(), "lesson_line": "",
                  "shorter_variant": "", "optional_thought_prompt": "",
                  "signoff": "Love, Mama & Papa"}

    _ok("Message drafted:")
    for line in result.get("main_message", "")[:250].split("\n"):
        print(f"    {DIM}{line}{RESET}")
    return result


# ---------------------------------------------------------------------------
# Agent 4 — memory_cue_designer
# Uses Haiku — straightforward creative task.
# Cost: ~$0.001/day
# ---------------------------------------------------------------------------

_CUE_SYSTEM = """You are memory_cue_designer for NewsWala.

Design a charming image concept using the family's cocker spaniel as a visual
memory hook for the news story. The dog MUST be a cocker spaniel doing something
directly tied to the story. Warm, whimsical, simple (1-3 elements), square format.

Return ONLY valid JSON:
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
                text += event.delta.text
                if not text.lstrip().startswith("{"):
                    _stream(event.delta.text)
        response = stream.get_final_message()

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
# Uses Haiku — pure mechanical prompt writing.
# Cost: ~$0.001/day
# ---------------------------------------------------------------------------

_IMG_SYSTEM = """You are image_maker for NewsWala.

Turn an image concept into a DALL-E 3 / Midjourney prompt.
Requirements: square 1:1, cocker spaniel as visual centre, warm digital
illustration style, bright family-friendly palette, clean composition.

Return ONLY valid JSON:
{"image_prompt": str, "negative_prompt": str, "style_tags": [str], "alt_text": str}"""


def image_maker(concept: dict, selected_stories: list[dict]) -> dict:
    """Write the image generation prompt."""
    _bar(f"🖼️   image_maker  |  {FAST_MODEL}", GREEN)
    _step("Writing DALL-E / Midjourney prompt...")
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
                text += event.delta.text
                if not text.lstrip().startswith("{"):
                    _stream(event.delta.text)
        response = stream.get_final_message()

    for b in response.content:
        b_text = getattr(b, "text", None)
        if b_text and b_text not in text:
            text += b_text

    print("\n")
    result = _parse_json(text, shape="object")
    _ok("Image prompt ready.")
    return result
