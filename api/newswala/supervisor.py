"""
NewsWala — Supervisor Agent (newswala)

The supervisor orchestrates the full pipeline:
  1. news_scout     → gather candidate stories from the web
  2. family_fit_editor → score & filter to 1-2 best stories
  3. whatsapp_copywriter → write the WhatsApp message
  4. memory_cue_designer → design the cocker spaniel image concept
  5. image_maker    → generate the final image prompt

Returns a structured output package (JSON + human-readable render).
"""

import json
import textwrap
from datetime import date
import anthropic

from .config import FAMILY, MAX_STORIES, WHATSAPP_MAX_CHARS, MODEL
from .agents import (
    news_scout,
    family_fit_editor,
    whatsapp_copywriter,
    memory_cue_designer,
    image_maker,
)


client = anthropic.Anthropic()


# ─────────────────────────────────────────────────────────────────────────────
# Quality validator
# ─────────────────────────────────────────────────────────────────────────────

def _validate_output(package: dict) -> dict:
    """Run quality checks on the final package. Returns package with quality_checks filled."""
    wa = package.get("whatsapp_output", {})
    img = package.get("image_output", {})
    stories = package.get("selected_stories", [])

    main_msg = wa.get("main_message", "")
    image_prompt = img.get("image_prompt", "")
    lesson_line = wa.get("lesson_line", "")
    signoff = wa.get("signoff", "")

    # Age appropriateness: check for red-flag words
    red_flags = ["death", "murder", "rape", "war casualties", "terrorist attack", "suicide", "drug abuse"]
    age_ok = not any(flag in main_msg.lower() for flag in red_flags)

    # Comes from both parents
    from_both = (
        "mama" in main_msg.lower() or "papa" in main_msg.lower() or
        "yash" in main_msg.lower() or "pooja" in main_msg.lower() or
        "mama & papa" in signoff.lower() or "mama and papa" in signoff.lower()
    )

    # Cocker spaniel in image
    has_spaniel = "cocker spaniel" in image_prompt.lower()
    spaniel_only = "cocker spaniel" in image_prompt.lower() and (
        "labrador" not in image_prompt.lower() and
        "golden retriever" not in image_prompt.lower() and
        "poodle" not in image_prompt.lower()
    )

    # Story count
    story_count_ok = 1 <= len(stories) <= MAX_STORIES

    # WhatsApp length
    wa_length_ok = len(main_msg) <= WHATSAPP_MAX_CHARS

    # Lesson line
    lesson_ok = bool(lesson_line and len(lesson_line) > 10)

    # Factual confidence (based on source scores)
    avg_credibility = 0
    if stories:
        scores = [s.get("scores", {}).get("credibility", 5) for s in stories if "scores" in s]
        avg_credibility = sum(scores) / len(scores) if scores else 5
    factual_confidence = "high" if avg_credibility >= 7 else "medium"

    package["quality_checks"] = {
        "age_appropriate": age_ok,
        "comes_from_both_parents": from_both,
        "contains_cocker_spaniel": has_spaniel,
        "dog_is_always_cocker_spaniel": spaniel_only,
        "max_story_count_ok": story_count_ok,
        "whatsapp_length_ok": wa_length_ok,
        "lesson_line_present": lesson_ok,
        "factual_confidence": factual_confidence,
    }

    return package


# ─────────────────────────────────────────────────────────────────────────────
# Human-readable renderer
# ─────────────────────────────────────────────────────────────────────────────

def _render_output(package: dict) -> str:
    """Render the package as a pretty human-readable string."""
    lines = []
    run_date = package.get("run_date", "")
    stories = package.get("selected_stories", [])
    wa = package.get("whatsapp_output", {})
    img = package.get("image_output", {})
    qc = package.get("quality_checks", {})

    lines.append("=" * 60)
    lines.append(f"  📰 NEWSWALA — Daily Digest  |  {run_date}")
    lines.append("=" * 60)

    lines.append("\n── SELECTED STORIES ────────────────────────────────────")
    for i, s in enumerate(stories, 1):
        lines.append(f"\n  [{i}] {s.get('title', 'Untitled')}")
        lines.append(f"      Category : {s.get('category', '')}")
        lines.append(f"      Source   : {s.get('source', '')}")
        lines.append(f"      URL      : {s.get('url', '')}")
        lines.append(f"      Why      : {s.get('why_selected', s.get('why_interesting', ''))}")
        lines.append(f"      Lesson   : {s.get('lesson_or_moral', '')}")

    lines.append("\n── WHATSAPP MESSAGE ─────────────────────────────────────")
    lines.append("")
    main = wa.get("main_message", "")
    for para in main.split("\n"):
        lines.append(textwrap.fill(para, width=58) if para.strip() else "")
    lines.append("")
    lines.append(f"✦ Lesson: {wa.get('lesson_line', '')}")
    lines.append(f"✦ Thought prompt: {wa.get('optional_thought_prompt', '')}")

    lines.append("\n── SHORT VARIANT ────────────────────────────────────────")
    short = wa.get("shorter_variant", "")
    for para in short.split("\n"):
        lines.append(textwrap.fill(para, width=58) if para.strip() else "")

    lines.append("\n── IMAGE CONCEPT ────────────────────────────────────────")
    lines.append(f"  Concept : {img.get('concept', '')}")
    lines.append(f"  Alt text: {img.get('alt_text', '')}")
    lines.append("")
    lines.append("  FULL IMAGE PROMPT (paste into DALL-E / Midjourney):")
    prompt = img.get("image_prompt", "")
    for line in textwrap.wrap(prompt, width=56):
        lines.append(f"  {line}")

    lines.append("\n── QUALITY CHECKS ───────────────────────────────────────")
    for k, v in qc.items():
        icon = "✅" if v is True or v == "high" else ("⚠️" if v == "medium" else "❌")
        lines.append(f"  {icon}  {k}: {v}")

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Supervisor — main entry point
# ─────────────────────────────────────────────────────────────────────────────

def newswala(run_date: str | None = None, verbose: bool = True) -> dict:
    """
    Run the full NewsWala pipeline for a given date.

    Args:
        run_date: ISO date string (YYYY-MM-DD). Defaults to today.
        verbose: Whether to print progress and the final rendered output.

    Returns:
        A structured dict matching the NewsWala output schema.
    """
    if run_date is None:
        run_date = date.today().isoformat()

    if verbose:
        print(f"\n🐾 NewsWala starting for {run_date}...")
        print("─" * 50)

    # ── Step 1: news_scout ──────────────────────────────────
    if verbose:
        print("\n[1/5] news_scout — searching the web...")
    try:
        candidates = news_scout(run_date)
    except Exception as e:
        print(f"  ⚠️  news_scout failed: {e}. Using fallback.")
        candidates = _fallback_candidates(run_date)

    if not candidates:
        print("  ⚠️  No candidates found. Using fallback.")
        candidates = _fallback_candidates(run_date)

    # ── Step 2: family_fit_editor ───────────────────────────
    if verbose:
        print("\n[2/5] family_fit_editor — filtering stories...")
    try:
        selected_stories = family_fit_editor(candidates)
    except Exception as e:
        print(f"  ⚠️  family_fit_editor failed: {e}. Using top candidate.")
        selected_stories = candidates[:1]

    if not selected_stories:
        selected_stories = candidates[:1]

    # ── Step 3: whatsapp_copywriter ─────────────────────────
    if verbose:
        print("\n[3/5] whatsapp_copywriter — writing the message...")
    try:
        whatsapp_output = whatsapp_copywriter(selected_stories)
    except Exception as e:
        print(f"  ⚠️  whatsapp_copywriter failed: {e}")
        whatsapp_output = _fallback_whatsapp(selected_stories)

    # Ensure signoff is always correct
    whatsapp_output["signoff"] = FAMILY["signoff"]
    if FAMILY["signoff"] not in whatsapp_output.get("main_message", ""):
        whatsapp_output["main_message"] = (
            whatsapp_output.get("main_message", "") + f"\n\n{FAMILY['signoff']}"
        )

    # ── Step 4: memory_cue_designer ─────────────────────────
    if verbose:
        print("\n[4/5] memory_cue_designer — designing image concept...")
    try:
        concept = memory_cue_designer(selected_stories)
    except Exception as e:
        print(f"  ⚠️  memory_cue_designer failed: {e}")
        concept = {"concept": "A cocker spaniel reading the newspaper with wide curious eyes.", "visual_elements": ["cocker spaniel", "newspaper"], "colour_mood": "warm golden", "memory_hook": "curious dog = curious mind"}

    # ── Step 5: image_maker ──────────────────────────────────
    if verbose:
        print("\n[5/5] image_maker — generating image prompt...")
    try:
        image_output_raw = image_maker(concept, selected_stories)
    except Exception as e:
        print(f"  ⚠️  image_maker failed: {e}")
        image_output_raw = {"image_prompt": concept.get("concept", ""), "negative_prompt": "realistic, dark", "style_tags": ["digital illustration", "cocker spaniel"], "alt_text": "A cocker spaniel learning about the news"}

    image_output = {
        "concept": concept.get("concept", ""),
        "image_prompt": image_output_raw.get("image_prompt", ""),
        "alt_text": image_output_raw.get("alt_text", ""),
    }

    # ── Assemble final package ──────────────────────────────
    package = {
        "run_date": run_date,
        "selected_stories": [
            {
                "title": s.get("title", ""),
                "category": s.get("category", ""),
                "source": s.get("source", ""),
                "url": s.get("url", ""),
                "why_selected": s.get("why_selected", s.get("why_interesting", "")),
                "family_fit_notes": s.get("family_fit_notes", ""),
                "summary_for_internal_use": s.get("summary", ""),
                "lesson_or_moral": s.get("lesson_or_moral", ""),
            }
            for s in selected_stories
        ],
        "whatsapp_output": whatsapp_output,
        "image_output": image_output,
        "quality_checks": {},
    }

    # ── Validate ─────────────────────────────────────────────
    if verbose:
        print("\n[✓] Validating output quality...")
    package = _validate_output(package)

    # ── Render ───────────────────────────────────────────────
    rendered = _render_output(package)
    package["_rendered"] = rendered

    if verbose:
        print(rendered)

    return package


# ─────────────────────────────────────────────────────────────────────────────
# Fallback helpers (used when agents fail)
# ─────────────────────────────────────────────────────────────────────────────

def _fallback_candidates(run_date: str) -> list[dict]:
    """Ask Claude to recall a notable recent story as fallback."""
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": (
                    f"It's {run_date}. Name one recent, inspiring news story from India in Economics, "
                    f"STEM, or current affairs that would be appropriate for an 11-year-old and a "
                    f"17-year-old. Return a single JSON object with title, category, source, url (best guess), "
                    f"summary (2-3 sentences), why_interesting, india_relevance, lesson_or_moral, "
                    f"and scores (all fields set to 7, total: 56)."
                ),
            }],
        )
        text = response.content[0].text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1:
            return [json.loads(text[start:end])]
    except Exception:
        pass
    return [{
        "title": "India's Science & Technology Progress",
        "category": "STEM",
        "source": "PIB India",
        "url": "https://pib.gov.in",
        "summary": "India continues to make strides in science and technology.",
        "why_interesting": "Shows India's growing role in global innovation.",
        "india_relevance": "Directly from India.",
        "lesson_or_moral": "Curiosity and persistence open doors that talent alone cannot.",
        "scores": {"credibility": 7, "novelty": 6, "inspiration": 8, "educational_value": 8, "india_relevance": 10, "child_suitability": 10, "memorability": 7, "lesson_potential": 8, "total": 64},
    }]


def _fallback_whatsapp(stories: list[dict]) -> dict:
    story = stories[0] if stories else {}
    title = story.get("title", "something amazing")
    lesson = story.get("lesson_or_moral", "Curiosity and persistence open doors that talent alone cannot.")
    msg = (
        f"Hey Manishka & Divyana! 🌟\n\n"
        f"Today's find: {title}\n\n"
        f"{story.get('summary', '')}\n\n"
        f"{lesson}\n\n"
        f"What do you think — could this change something in how you see the world?\n\n"
        f"{FAMILY['signoff']}"
    )
    return {
        "main_message": msg,
        "lesson_line": lesson,
        "shorter_variant": f"Today's gem: {title}. {lesson}\n{FAMILY['signoff']}",
        "optional_thought_prompt": "Could this change something in how you see the world?",
        "signoff": FAMILY["signoff"],
    }
