"""
NewsWala — Individual agent implementations.

Agents:
  news_scout          — searches the web for candidate stories
  family_fit_editor   — scores & filters stories for this family
  whatsapp_copywriter — writes the WhatsApp-ready message
  memory_cue_designer — designs the cocker spaniel image concept
  image_maker         — generates the final image prompt

Each agent is a function that takes a typed input and returns a typed output.
All agents use Claude Opus 4.6 with adaptive thinking and web search where needed.
"""

import json
import anthropic

from .config import FAMILY, CATEGORIES, PREFERRED_SOURCES, AVOID_TOPICS, MAX_STORIES, MODEL


client = anthropic.Anthropic()


# ─────────────────────────────────────────────────────────────────────────────
# Agent 1 — news_scout
# ─────────────────────────────────────────────────────────────────────────────

NEWS_SCOUT_SYSTEM = f"""You are news_scout, an elite news researcher for a curated family digest called NewsWala.

Your job: search the web RIGHT NOW for today's most interesting, inspiring, high-signal news stories.

FAMILY CONTEXT:
- Two daughters: Manishka (turning 18, 24 October) and Divyana (turning 11, 12 July)
- Parents: Yash and Pooja
- Based in India

TARGET CATEGORIES (pick the best stories across all three):
{json.dumps(CATEGORIES, indent=2)}

PREFERRED SOURCE QUALITY:
{json.dumps(PREFERRED_SOURCES, indent=2)}

AVOID:
{json.dumps(AVOID_TOPICS, indent=2)}

SELECTION CRITERIA — score each story on:
1. Credibility (is the source reliable?)
2. Novelty (is this genuinely new / surprising?)
3. Inspiration (does it spark wonder or ambition?)
4. Educational value (does it teach something real?)
5. India relevance (direct impact on or from India, or global context India students should know)
6. Emotional suitability for children (safe, uplifting, not disturbing)
7. Memorability (dinner-table conversation worthy)
8. Lesson potential (is there a clear moral or takeaway?)

OUTPUT: Return a JSON array of 4-6 candidate stories. Each story object MUST include:
{{
  "title": "string",
  "category": "Economics | STEM | Current Affairs",
  "source": "string",
  "url": "string",
  "summary": "2-3 sentence plain-English summary",
  "why_interesting": "1 sentence on why this is worth sharing",
  "india_relevance": "1 sentence — direct or indirect",
  "scores": {{
    "credibility": 1-10,
    "novelty": 1-10,
    "inspiration": 1-10,
    "educational_value": 1-10,
    "india_relevance": 1-10,
    "child_suitability": 1-10,
    "memorability": 1-10,
    "lesson_potential": 1-10,
    "total": 1-80
  }},
  "lesson_or_moral": "one crisp sentence capturing the lesson"
}}

Search across Economics, STEM, and India/Global Current Affairs. Return ONLY valid JSON.
"""


def news_scout(run_date: str) -> list[dict]:
    """Search the web for candidate news stories and return scored candidates."""
    print("  [news_scout] Searching the web for today's best stories...")

    # web_search_20260209 is a server-side tool — Anthropic runs the search
    # automatically. No manual tool-use loop needed. Just stream and get
    # the final message. Handle pause_turn by re-sending to continue.
    tools = [
        {"type": "web_search_20260209", "name": "web_search"},
    ]

    messages = [
        {
            "role": "user",
            "content": (
                f"Today is {run_date}. Search the web for the most interesting, "
                f"inspiring news stories from Economics, STEM, and India-relevant current affairs "
                f"published in the last 24-48 hours. Search multiple times across different topics. "
                f"Find stories from credible sources like BBC, Reuters, The Hindu, Mint, ISRO, Nature. "
                f"Return your findings as a JSON array of 4-6 candidate stories with all required fields."
            ),
        }
    ]

    max_continuations = 5
    for _ in range(max_continuations):
        with client.messages.stream(
            model=MODEL,
            max_tokens=8000,
            system=NEWS_SCOUT_SYSTEM,
            tools=tools,
            messages=messages,
        ) as stream:
            response = stream.get_final_message()

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "pause_turn":
            # Server-side tool hit its iteration limit — append and continue
            messages.append({"role": "assistant", "content": response.content})
            continue

        # Any other stop reason — break and use what we have
        break

    # Extract JSON from the response
    text = ""
    for block in response.content:
        if hasattr(block, "text"):
            text += block.text

    # Parse JSON — find the array
    try:
        start = text.find("[")
        end = text.rfind("]") + 1
        if start != -1 and end > start:
            candidates = json.loads(text[start:end])
        else:
            candidates = json.loads(text)
    except json.JSONDecodeError:
        # Fallback: ask Claude to re-format
        print("  [news_scout] JSON parse failed, retrying clean extraction...")
        candidates = _extract_json_retry(text)

    print(f"  [news_scout] Found {len(candidates)} candidate stories.")
    return candidates


def _extract_json_retry(raw_text: str) -> list[dict]:
    """Ask Claude to extract clean JSON from messy text."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        messages=[{
            "role": "user",
            "content": (
                f"Extract the JSON array of news stories from this text and return ONLY valid JSON:\n\n{raw_text[:6000]}"
            ),
        }],
    )
    text = response.content[0].text
    start = text.find("[")
    end = text.rfind("]") + 1
    if start != -1 and end > start:
        return json.loads(text[start:end])
    return []


# ─────────────────────────────────────────────────────────────────────────────
# Agent 2 — family_fit_editor
# ─────────────────────────────────────────────────────────────────────────────

FAMILY_FIT_SYSTEM = f"""You are family_fit_editor for NewsWala — a curated daily family digest.

FAMILY:
- Daughters: Manishka (turning 18) and Divyana (turning 11)
- Parents: Yash and Pooja, India-based
- The message must work for BOTH daughters simultaneously

YOUR JOB:
Evaluate the candidate stories and select the BEST 1 story, or at most 2 if there are two genuinely exceptional ones.

SELECTION RULES:
- Max {MAX_STORIES} stories
- Every selected story MUST be age-appropriate for an 11-year-old
- The story must have a clear lesson or moral that can be expressed in one sentence
- The story must be emotionally safe: no fear, no graphic content, no divisive politics
- Prefer stories that make both girls say "wow, I didn't know that"
- If two stories are selected, they should be from different categories

REJECTION CRITERIA (disqualify immediately):
- Graphic violence or crime
- Partisan political framing
- Adult/disturbing themes
- Purely negative market news with no educational angle
- Trivial celebrity content
- No clear lesson or takeaway

For each selected story, add:
- "why_selected": why this beat others
- "family_fit_notes": specific notes on how it works for this family
- "lesson_or_moral": one crisp, memorable sentence (the moral of the story)

Return ONLY a JSON array of selected stories (1 or 2 max), each with all original fields plus the three new ones.
"""


def family_fit_editor(candidates: list[dict]) -> list[dict]:
    """Score and filter stories for family appropriateness. Returns 1-2 selected stories."""
    print(f"  [family_fit_editor] Evaluating {len(candidates)} candidates...")

    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        thinking={"type": "adaptive"},
        system=FAMILY_FIT_SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                f"Here are the candidate stories. Select the best 1 (or at most 2 exceptional ones):\n\n"
                f"{json.dumps(candidates, indent=2)}"
            ),
        }],
    )

    text = ""
    for block in response.content:
        if hasattr(block, "text"):
            text += block.text

    try:
        start = text.find("[")
        end = text.rfind("]") + 1
        selected = json.loads(text[start:end]) if start != -1 else []
    except json.JSONDecodeError:
        selected = _extract_json_retry(text)

    # Safety cap
    selected = selected[:MAX_STORIES]
    print(f"  [family_fit_editor] Selected {len(selected)} story/stories.")
    return selected


# ─────────────────────────────────────────────────────────────────────────────
# Agent 3 — whatsapp_copywriter
# ─────────────────────────────────────────────────────────────────────────────

COPYWRITER_SYSTEM = f"""You are whatsapp_copywriter for NewsWala.

You write beautiful, short, memorable WhatsApp messages for Yash and Pooja to send to their daughters.

FAMILY:
- Daughters: Manishka (turning 18) and Divyana (turning 11)
- The message comes from BOTH PARENTS: Yash and Pooja
- Sign-off: "Love, Mama & Papa"

VOICE & STYLE:
- Warm but intelligent — thoughtful modern Indian family
- Short: under 250 words total for the main message
- No babyish tone, no cringe, no preachy moralising
- No excessive emojis (1-2 max, only if they add meaning)
- No fake facts or exaggeration
- No motivational-poster clichés
- Naturally bilingual register is fine (occasional Hindi word is okay if it flows)
- Factually accurate — do not embellish the story

STRUCTURE:
1. A catchy opening line (makes them want to read on)
2. The core story in 2-4 simple sentences (accurate, clear for an 11-year-old)
3. Why it matters / what's cool about it
4. ONE memorable standalone lesson sentence (this should be poetic enough to remember)
5. An optional short thought-prompt question (makes them think)
6. Sign-off: "Love, Mama & Papa"

OUTPUT: Return a JSON object with exactly these fields:
{{
  "main_message": "the full WhatsApp message text (including sign-off)",
  "lesson_line": "the standalone lesson/moral sentence (repeated from inside the message)",
  "shorter_variant": "a very short 3-4 line version of the same message for quick sharing",
  "optional_thought_prompt": "one optional question to spark family conversation",
  "signoff": "Love, Mama & Papa"
}}

Return ONLY valid JSON. No markdown, no preamble.
"""


def whatsapp_copywriter(selected_stories: list[dict]) -> dict:
    """Write the WhatsApp-ready family message."""
    print("  [whatsapp_copywriter] Writing the family message...")

    stories_text = json.dumps(selected_stories, indent=2)

    response = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        thinking={"type": "adaptive"},
        system=COPYWRITER_SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                f"Write a beautiful, short WhatsApp message for Manishka and Divyana based on "
                f"these selected stories. The message must feel like it comes from both Yash and Pooja.\n\n"
                f"Stories:\n{stories_text}"
            ),
        }],
    )

    text = ""
    for block in response.content:
        if hasattr(block, "text"):
            text += block.text

    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        result = json.loads(text[start:end]) if start != -1 else {}
    except json.JSONDecodeError:
        result = {"main_message": text.strip(), "lesson_line": "", "shorter_variant": "", "optional_thought_prompt": "", "signoff": "Love, Mama & Papa"}

    print("  [whatsapp_copywriter] Message written.")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Agent 4 — memory_cue_designer
# ─────────────────────────────────────────────────────────────────────────────

MEMORY_CUE_SYSTEM = f"""You are memory_cue_designer for NewsWala.

Your job: design a charming, memorable image concept that visually encodes the news story for the daughters.

RULES:
- ALWAYS include a cocker spaniel (the family's pet)
- The cocker spaniel MUST be doing something directly connected to the story
- The dog is ALWAYS a cocker spaniel — never any other breed
- The scene should be charming, warm, slightly whimsical — not hyper-realistic
- The image should work as a memory hook: see the image → remember the story
- Keep the composition simple — 1-3 elements max
- Bright, family-friendly colour palette
- Square composition (WhatsApp-friendly)

EXAMPLES OF GOOD CONCEPTS:
- Space story: "A fluffy cocker spaniel in a tiny astronaut helmet, paw raised, gazing at a rocket launch against a golden sky"
- Economics/markets: "A cocker spaniel sitting on a tall stool, carefully arranging golden coins into a rising bar graph on a wooden table"
- Indian science breakthrough: "A cocker spaniel in a tiny lab coat, looking delighted at a glowing blue holographic device labelled 'Made in India'"
- Climate/nature: "A cocker spaniel planting a small sapling in a sunlit garden, surrounded by colourful butterflies"

OUTPUT: Return a JSON object:
{{
  "concept": "1-2 sentence description of the scene and what memory it reinforces",
  "visual_elements": ["element1", "element2", "element3"],
  "colour_mood": "warm golden | cool blue | vibrant | soft pastel | etc.",
  "memory_hook": "why this image will make them remember the story"
}}

Return ONLY valid JSON.
"""


def memory_cue_designer(selected_stories: list[dict]) -> dict:
    """Design the cocker spaniel image concept."""
    print("  [memory_cue_designer] Designing image concept...")

    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        thinking={"type": "adaptive"},
        system=MEMORY_CUE_SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                f"Design a cocker spaniel image concept that helps Manishka and Divyana remember this news:\n\n"
                f"{json.dumps(selected_stories, indent=2)}"
            ),
        }],
    )

    text = ""
    for block in response.content:
        if hasattr(block, "text"):
            text += block.text

    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        result = json.loads(text[start:end]) if start != -1 else {}
    except json.JSONDecodeError:
        result = {"concept": text.strip(), "visual_elements": [], "colour_mood": "warm", "memory_hook": ""}

    print("  [memory_cue_designer] Concept designed.")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Agent 5 — image_maker
# ─────────────────────────────────────────────────────────────────────────────

IMAGE_MAKER_SYSTEM = """You are image_maker for NewsWala.

Your job: turn an image concept into a production-quality image generation prompt.

TARGET: The prompt should work beautifully with DALL-E 3, Midjourney, or Stable Diffusion.

REQUIREMENTS:
- Square aspect ratio (1:1)
- The cocker spaniel MUST be the visual centre
- Bright, premium, family-friendly look
- Warm, optimistic mood
- Digital illustration style (not hyper-realistic photography)
- Clean composition — not cluttered
- WhatsApp-friendly: works at small size (legible key elements)

PROMPT STRUCTURE: Subject + Action + Setting + Style + Mood + Lighting + Colour palette

OUTPUT: Return a JSON object:
{
  "image_prompt": "the complete image generation prompt (under 200 words)",
  "negative_prompt": "things to avoid: realistic, dark, scary, cluttered, text, watermark",
  "style_tags": ["digital illustration", "warm lighting", "cocker spaniel", "family-friendly"],
  "alt_text": "a short alt-text description of the image for accessibility"
}

Return ONLY valid JSON.
"""


def image_maker(concept: dict, selected_stories: list[dict]) -> dict:
    """Generate the final image prompt from the concept."""
    print("  [image_maker] Generating image prompt...")

    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=IMAGE_MAKER_SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                f"Create a production-ready image generation prompt from this concept:\n\n"
                f"Concept: {json.dumps(concept, indent=2)}\n\n"
                f"News context: {json.dumps([s.get('title', '') for s in selected_stories])}"
            ),
        }],
    )

    text = ""
    for block in response.content:
        if hasattr(block, "text"):
            text += block.text

    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        result = json.loads(text[start:end]) if start != -1 else {}
    except json.JSONDecodeError:
        result = {"image_prompt": text.strip(), "negative_prompt": "", "style_tags": [], "alt_text": ""}

    print("  [image_maker] Image prompt ready.")
    return result
