# Skill: Family Editorial Filter

Select the best stories from a candidate list for a specific family
with children aged 11 and 18.

## Selection rules
- Pick 1 story by default
- Pick 2 only if both are truly exceptional AND from different categories
- Divyana (11) sets the floor — if it would disturb her, it's out
- Manishka (18) sets the ceiling — it must still interest a young adult
- Reject anything dark, violent, partisan, scary, or anxiety-inducing
- Prefer uplifting and educational over dramatic or cautionary

## Evaluation criteria
- Is the lesson memorable and teachable?
- Is the emotional tone warm, not anxious?
- If picking 2, are they from different categories?
- Would both an 11-year-old and an 18-year-old genuinely care?

## Output additions
Add to each selected story:
  "why_selected": str   — editorial reasoning
  "family_fit_notes": str  — specific notes for Manishka and Divyana
  "lesson_or_moral": str   — the core lesson
