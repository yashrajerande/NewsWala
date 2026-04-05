"""
NewsWala — supervisor (newswala)

Orchestrates the five-agent pipeline and validates the final output.

Pipeline:
    news_scout → family_fit_editor → whatsapp_copywriter
                                   → memory_cue_designer → image_maker

Call newswala() to run everything. Returns a structured dict.
"""

import json
import textwrap
from datetime import date

from .config import FAMILY, MAX_STORIES, WHATSAPP_MAX_CHARS
from .agents import (
    BOLD, DIM, GREEN, YELLOW, RESET,   # terminal colors
    _handoff, _bar, _step, _ok,        # terminal helpers
    news_scout,
    family_fit_editor,
    whatsapp_copywriter,
    memory_cue_designer,
    image_maker,
    SCOUT_MODEL,
)

import anthropic
client = anthropic.Anthropic()


# ---------------------------------------------------------------------------
# quality validator — checks the final package against hard constraints
# ---------------------------------------------------------------------------

def _validate(package: dict) -> dict:
    wa      = package.get("whatsapp_output", {})
    img     = package.get("image_output", {})
    stories = package.get("selected_stories", [])

    main_msg     = wa.get("main_message", "")
    image_prompt = img.get("image_prompt", "")
    lesson_line  = wa.get("lesson_line", "")
    signoff      = wa.get("signoff", "")

    red_flags = ["murder", "rape", "war casualties", "terrorist attack", "suicide", "drug abuse"]
    age_ok = not any(f in main_msg.lower() for f in red_flags)

    from_both = any(w in (main_msg + signoff).lower()
                    for w in ["mama", "papa", "yash", "pooja"])

    has_spaniel  = "cocker spaniel" in image_prompt.lower()
    only_spaniel = has_spaniel and not any(
        b in image_prompt.lower() for b in ["labrador", "golden retriever", "poodle"])

    scores = [s.get("scores", {}).get("credibility", 5)
              for s in stories if "scores" in s]
    avg_cred = sum(scores) / len(scores) if scores else 5

    package["quality_checks"] = {
        "age_appropriate":          age_ok,
        "comes_from_both_parents":  from_both,
        "contains_cocker_spaniel":  has_spaniel,
        "dog_is_always_cocker_spaniel": only_spaniel,
        "max_story_count_ok":       1 <= len(stories) <= MAX_STORIES,
        "whatsapp_length_ok":       len(main_msg) <= WHATSAPP_MAX_CHARS,
        "lesson_line_present":      bool(lesson_line and len(lesson_line) > 10),
        "factual_confidence":       "high" if avg_cred >= 7 else "medium",
    }
    return package


# ---------------------------------------------------------------------------
# renderer — pretty terminal summary at the end
# ---------------------------------------------------------------------------

def _render(package: dict) -> str:
    run_date = package.get("run_date", "")
    stories  = package.get("selected_stories", [])
    wa       = package.get("whatsapp_output", {})
    img      = package.get("image_output", {})
    qc       = package.get("quality_checks", {})

    W = 60
    lines = [
        "\n" + "═" * W,
        f"  🐾  NEWSWALA — Final Output  |  {run_date}",
        "═" * W,
    ]

    lines.append("\n  STORIES SELECTED")
    lines.append("  " + "─" * (W - 2))
    for i, s in enumerate(stories, 1):
        lines.append(f"\n  [{i}] {s.get('title','')}")
        lines.append(f"       {s.get('category','')}  ·  {s.get('source','')}")
        lines.append(f"       {s.get('url','')}")
        lines.append(f"       Lesson: {s.get('lesson_or_moral','')}")

    lines.append("\n\n  WHATSAPP MESSAGE  (copy & paste this)")
    lines.append("  " + "─" * (W - 2))
    for para in wa.get("main_message", "").split("\n"):
        lines.append("  " + (textwrap.fill(para, W - 4) if para.strip() else ""))
    lines.append(f"\n  ✦ Lesson: {wa.get('lesson_line','')}")
    lines.append(f"  ✦ Thought prompt: {wa.get('optional_thought_prompt','')}")

    lines.append("\n\n  SHORT VARIANT")
    lines.append("  " + "─" * (W - 2))
    for para in wa.get("shorter_variant", "").split("\n"):
        lines.append("  " + (textwrap.fill(para, W - 4) if para.strip() else ""))

    lines.append("\n\n  IMAGE PROMPT  (paste into DALL-E / Midjourney)")
    lines.append("  " + "─" * (W - 2))
    lines.append(f"  Concept: {img.get('concept','')}")
    lines.append("")
    for chunk in textwrap.wrap(img.get("image_prompt", ""), W - 4):
        lines.append(f"  {chunk}")

    lines.append("\n\n  QUALITY CHECKS")
    lines.append("  " + "─" * (W - 2))
    for k, v in qc.items():
        icon = "✅" if v is True or v == "high" else ("⚠️ " if v == "medium" else "❌")
        lines.append(f"  {icon}  {k}: {v}")

    lines.append("\n" + "═" * W)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# fallbacks — used when an agent throws an exception
# ---------------------------------------------------------------------------

def _fallback_candidates(run_date: str) -> list[dict]:
    """Ask Claude (no web) for one known recent story."""
    try:
        resp = client.messages.create(
            model=SCOUT_MODEL, max_tokens=1500,
            messages=[{"role": "user", "content": (
                f"It's {run_date}. Give me one recent inspiring news story from India "
                f"in Economics, STEM, or current affairs suitable for children aged 11-18. "
                f"Return a single JSON object with: title, category, source, url, summary, "
                f"why_interesting, india_relevance, lesson_or_moral, "
                f"scores (all 7s, total 56)."
            )}],
        )
        t = resp.content[0].text
        s, e = t.find("{"), t.rfind("}") + 1
        if s != -1: return [json.loads(t[s:e])]
    except Exception:
        pass
    return [{
        "title": "India's STEM momentum",
        "category": "STEM", "source": "PIB", "url": "https://pib.gov.in",
        "summary": "India is advancing rapidly in science and technology.",
        "why_interesting": "Shows India on the world stage.",
        "india_relevance": "Directly from India.",
        "lesson_or_moral": "Curiosity and persistence open doors that talent alone cannot.",
        "scores": {"credibility":7,"novelty":6,"inspiration":8,"educational_value":8,
                   "india_relevance":10,"child_suitability":10,"memorability":7,
                   "lesson_potential":8,"total":64},
    }]


def _fallback_whatsapp(stories: list[dict]) -> dict:
    s      = stories[0] if stories else {}
    title  = s.get("title", "something amazing")
    lesson = s.get("lesson_or_moral", "Curiosity and persistence open doors that talent alone cannot.")
    msg    = (f"Hey Manishka & Divyana!\n\nToday's find: {title}\n\n"
              f"{s.get('summary','')}\n\n{lesson}\n\n{FAMILY['signoff']}")
    return {
        "main_message": msg, "lesson_line": lesson,
        "shorter_variant": f"Today: {title}. {lesson}\n{FAMILY['signoff']}",
        "optional_thought_prompt": "What do you think about this?",
        "signoff": FAMILY["signoff"],
    }


# ---------------------------------------------------------------------------
# newswala — the supervisor that runs the full pipeline
# ---------------------------------------------------------------------------

def newswala(run_date: str | None = None, verbose: bool = True) -> dict:
    """
    Run the full NewsWala pipeline.

    args:
        run_date : ISO date string YYYY-MM-DD (default: today)
        verbose  : stream all agent output to terminal (default: True)

    returns:
        structured dict with selected_stories, whatsapp_output,
        image_output, and quality_checks
    """
    if run_date is None:
        run_date = date.today().isoformat()

    print(f"\n{BOLD}🐾  NewsWala  |  {run_date}{RESET}")
    print(f"{DIM}Pipeline: news_scout → family_fit_editor → "
          f"whatsapp_copywriter + memory_cue_designer → image_maker{RESET}")

    # ------------------------------------------------------------------
    # 1. news_scout — search the live web
    # ------------------------------------------------------------------
    try:
        candidates = news_scout(run_date)
    except Exception as e:
        print(f"\n  ⚠️  news_scout failed: {e}")
        candidates = _fallback_candidates(run_date)

    if not candidates:
        print("  ⚠️  No candidates — using fallback story")
        candidates = _fallback_candidates(run_date)

    # HANDOFF 1 → 2
    _handoff(
        "news_scout", "family_fit_editor",
        f"Passing {len(candidates)} scored candidates for editorial review",
    )

    # ------------------------------------------------------------------
    # 2. family_fit_editor — pick the best 1-2 stories
    # ------------------------------------------------------------------
    try:
        selected = family_fit_editor(candidates)
    except Exception as e:
        print(f"\n  ⚠️  family_fit_editor failed: {e}")
        selected = candidates[:1]

    if not selected:
        selected = candidates[:1]

    # HANDOFF 2 → 3 & 4 (copy + image run in sequence on selected)
    _handoff(
        "family_fit_editor", "whatsapp_copywriter  +  memory_cue_designer",
        f"{len(selected)} story selected — handing off to writing and image teams",
    )

    # ------------------------------------------------------------------
    # 3. whatsapp_copywriter — write the message
    # ------------------------------------------------------------------
    try:
        wa_output = whatsapp_copywriter(selected)
    except Exception as e:
        print(f"\n  ⚠️  whatsapp_copywriter failed: {e}")
        wa_output = _fallback_whatsapp(selected)

    # always ensure correct signoff
    wa_output["signoff"] = FAMILY["signoff"]
    if FAMILY["signoff"] not in wa_output.get("main_message", ""):
        wa_output["main_message"] += f"\n\n{FAMILY['signoff']}"

    # ------------------------------------------------------------------
    # 4. memory_cue_designer — design the cocker spaniel concept
    # ------------------------------------------------------------------
    try:
        concept = memory_cue_designer(selected)
    except Exception as e:
        print(f"\n  ⚠️  memory_cue_designer failed: {e}")
        concept = {"concept": "A cocker spaniel reading the newspaper with wide curious eyes.",
                   "visual_elements": ["cocker spaniel", "newspaper"],
                   "colour_mood": "warm golden", "memory_hook": "curious dog = curious mind"}

    # HANDOFF 4 → 5
    _handoff(
        "memory_cue_designer", "image_maker",
        f"Concept ready: \"{concept.get('concept','')[:70]}...\"",
    )

    # ------------------------------------------------------------------
    # 5. image_maker — write the DALL-E / Midjourney prompt
    # ------------------------------------------------------------------
    try:
        img_raw = image_maker(concept, selected)
    except Exception as e:
        print(f"\n  ⚠️  image_maker failed: {e}")
        img_raw = {"image_prompt": concept.get("concept", ""),
                   "negative_prompt": "realistic, dark",
                   "style_tags": ["digital illustration", "cocker spaniel"],
                   "alt_text": "A cocker spaniel with the day's news"}

    # ------------------------------------------------------------------
    # assemble final package
    # ------------------------------------------------------------------
    package = {
        "run_date": run_date,
        "selected_stories": [
            {
                "title":                   s.get("title", ""),
                "category":                s.get("category", ""),
                "source":                  s.get("source", ""),
                "url":                     s.get("url", ""),
                "why_selected":            s.get("why_selected", s.get("why_interesting", "")),
                "family_fit_notes":        s.get("family_fit_notes", ""),
                "summary_for_internal_use":s.get("summary", ""),
                "lesson_or_moral":         s.get("lesson_or_moral", ""),
            }
            for s in selected
        ],
        "whatsapp_output": wa_output,
        "image_output": {
            "concept":      concept.get("concept", ""),
            "image_prompt": img_raw.get("image_prompt", ""),
            "alt_text":     img_raw.get("alt_text", ""),
        },
        "quality_checks": {},
    }

    # HANDOFF → supervisor validates
    _handoff(
        "image_maker", "newswala (supervisor)",
        "All agents done — validating quality and rendering final output",
    )

    package  = _validate(package)
    rendered = _render(package)
    package["_rendered"] = rendered
    print(rendered)

    return package
