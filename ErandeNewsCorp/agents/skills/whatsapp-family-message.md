# Skill: WhatsApp Family Message

Write warm, intelligent WhatsApp messages from parents to their children.

## Voice rules
- Write as both parents speaking together — one unified warm voice
- Thoughtful modern Indian family tone — smart but not academic
- No preaching. No babyish language. No motivational clichés.
- Maximum 2 emojis in the entire message
- Factually accurate — never invent or embellish details

## Message structure
1. Catchy opening line — something that makes them want to read on
2. The story in 2–3 plain sentences (simple enough for an 11-year-old)
3. Why it's cool or why it matters
4. ONE standalone memorable lesson sentence
5. Optional: one short thought-prompt question to spark conversation
6. Sign-off: "Love, Mama & Papa"

## Hard constraints
- main_message: UNDER 180 WORDS including the sign-off (count carefully)
- shorter_variant: 3–4 lines maximum for quick sharing
- optional_thought_prompt: one genuine question, not rhetorical

## Output schema
{
  "main_message": "under 180 words including sign-off",
  "lesson_line": "the standalone lesson sentence",
  "shorter_variant": "3-4 lines max",
  "optional_thought_prompt": "one question",
  "signoff": "Love, Mama & Papa"
}
