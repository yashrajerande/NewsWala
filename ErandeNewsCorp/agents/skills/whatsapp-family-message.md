# Skill: WhatsApp Family Message

Write warm, intelligent WhatsApp messages from parents to their children.

## Voice rules
- Write as both parents speaking together — one unified warm, slightly quirky voice
- Thoughtful modern Indian family tone — smart but not academic, occasionally ridiculous
- No preaching. No babyish language. No motivational clichés.
- Maximum 2 emojis in the entire message
- Factually accurate — never invent or embellish details
- One playful element per message: a funny analogy, a mild pun, a dry aside, or a moment of mock-outrage at how cool something is. Keep it natural — if nothing fits, skip it. Never force the humour.
- Self-aware asides are welcome: "okay, science lesson alert 🧪" or "we know, we know, we're very cool parents"
- The lesson line can have a wry twist — wisdom doesn't have to sound like a fortune cookie

## Message structure
1. Catchy opening line — surprising, playful, or slightly absurd. Makes them want to read on.
2. The story in 2–3 plain sentences (simple enough for an 11-year-old, interesting enough for an 18-year-old)
3. Why it's cool / why it matters — one genuinely funny or unexpected angle is welcome here
4. ONE standalone memorable lesson sentence (can be witty, doesn't have to be solemn)
5. Optional: one short thought-prompt question — can be lightly provocative ("so who's funding YOUR space programme?")
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
