# Skill: India News Scoring

Score and select news stories for an Indian family digest.

## RSS resilience
Stories are fetched automatically from primary feeds. If a category yields fewer
than 3 stories, backup feeds are tried at runtime — no intervention needed.
Work with whatever stories arrive. Never abort or return empty because one feed failed.
If a category has only 1 story, score it honestly — it may still be selected.

## Priority sources
Give higher credibility scores to:
Bloomberg, Financial Times, Livemint, MIT Technology Review,
Ars Technica, The Economist

## Selection rules
- Return at least 1 story from EACH category: Economics, STEM, Current Affairs
- Only accept stories from the last 48 hours
- Age-safe for an 11-year-old — reject crime, violence, partisan politics, tragedy
- Every story must have a clear lesson or moral
- Prefer direct India stories. Global stories must have a clear India connection.
- Uplifting and educational — not anxiety-inducing

## Scoring dimensions (each 0–10, total out of 80)
- credibility: source reliability and factual accuracy
- novelty: how new or surprising
- inspiration: uplifting or motivating quality
- educational_value: how much it teaches
- india_relevance: connection to India (10 = directly about India)
- child_suitability: safe and appropriate for an 11-year-old
- memorability: will it stick in the mind?
- lesson_potential: how clearly it illustrates a life lesson

## Output schema
[{
  "title": str,
  "category": "Economics | STEM | Current Affairs",
  "source": str,
  "url": str,
  "published_date": "YYYY-MM-DD",
  "summary": "2-3 sentences expanding on the headline",
  "why_interesting": str,
  "india_relevance": str,
  "scores": {
    "credibility": N, "novelty": N, "inspiration": N,
    "educational_value": N, "india_relevance": N,
    "child_suitability": N, "memorability": N,
    "lesson_potential": N, "total": N
  },
  "lesson_or_moral": str
}]
