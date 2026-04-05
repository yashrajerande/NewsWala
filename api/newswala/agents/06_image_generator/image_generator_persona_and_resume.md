# 🎭 image_generator

> *"I'm the one who actually picks up the paintbrush. Everyone else describes the picture. I make it real."*

---

## Profile

| | |
|---|---|
| **Role** | Staff Illustrator |
| **Model** | `DALL-E 3` (OpenAI) — NOT a Claude model |
| **Reports to** | `image_maker` output |
| **Passes to** | `supervisor` → Telegram (the image is sent directly) |
| **Daily cost** | ~$0.04 (standard 1024×1024) |
| **Requires** | `OPENAI_API_KEY` in `.env` |

---

## Persona

**Character:** The silent artist. Doesn't talk much — just produces. Takes the carefully worded DALL-E 3 prompt from `image_maker`, prepends the Hergé/Tintin style guide, and calls the OpenAI image API. The resulting image URL goes directly to Telegram as a photo.

If `OPENAI_API_KEY` is not set, this agent gracefully steps aside and the text prompt is sent instead — so you can paste it into DALL-E yourself.

**Voice in terminal:**
```
🎨  image_generator  |  DALL-E 3  (~$0.04)
  ▸ Generating Hergé/Tintin style image...
  ✓ Image generated successfully
  ▸ URL: https://oaidalleapiprodscus.blob.core...
```

**Values:**
- Hergé/Tintin ligne claire is the house style (bold outlines, flat colours, no gradients)
- The style can be changed — it lives in `instructions.md`, not in Python code
- Graceful degradation — never crashes the pipeline if image generation fails
- Fast — one API call, no retries needed

---

## Skills

| Skill | Description |
|-------|-------------|
| 🎨 **DALL-E 3 generation** | Calls OpenAI Images API with `model="dall-e-3"` |
| 🖌️ **Style prefix injection** | Prepends the Hergé/Tintin style guide from `instructions.md` |
| 📤 **URL extraction** | Returns the generated image URL for Telegram to send |
| ⚡ **Graceful fallback** | Returns `{}` if key not set or API fails — pipeline continues |

---

## Handoff

**Receives from:** `image_maker` — a plain string (the DALL-E 3 prompt)

**Passes to:** `supervisor` → `telegram_sender` (as a photo, not a link)

**What it produces:**
```json
{
  "url": "https://oaidalleapiprodscus.blob.core.windows.net/...",
  "revised_prompt": "DALL-E's own rewrite of the prompt (informational)"
}
```

---

## Change the Art Style

Open [`instructions.md`](./instructions.md) — the **first line** is the style prefix added to every image.

**Currently:** Hergé/Tintin ligne claire
```
Hergé Tintin ligne claire style comic illustration: clean bold black outlines, flat bright colours...
```

**Examples of other styles you can switch to:**
```
Studio Ghibli watercolour style: soft pastel tones, hand-drawn warmth, gentle nature backgrounds.
```
```
Pixar 3D animation style: rounded shapes, warm cinematic lighting, expressive eyes.
```
```
Indian miniature painting style: rich jewel tones, ornate gold borders, flat perspective.
```
```
Vintage 1960s Indian film poster style: bold typography, bright primary colours, hand-painted look.
```

No Python knowledge needed. Just replace the first line and the next image will use the new style.

---

## Setup

1. Go to [platform.openai.com](https://platform.openai.com) → API Keys → Create new key
2. Add to your `.env` file:
   ```
   OPENAI_API_KEY=sk-your-key-here
   ```
3. Run `pip install openai` (only needed once)
4. The next `python newswala.py --telegram` will generate and send the image automatically
