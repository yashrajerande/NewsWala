# Erande News Corp

*A six-person AI newsroom that delivers a daily family digest every morning at 6 AM.*

---

## Our Team

| Employee | Role | Folder |
|---|---|---|
| 📡 news_scout | Scans the internet for today's best stories | [01_news_scout](./agents/01_news_scout/) |
| 🧐 family_fit_editor | Picks the right stories for the family | [02_family_fit_editor](./agents/02_family_fit_editor/) |
| ✍️ whatsapp_copywriter | Writes the daily message in Mama & Papa's voice | [03_whatsapp_copywriter](./agents/03_whatsapp_copywriter/) |
| 🎨 memory_cue_designer | Designs the dog image concept | [04_memory_cue_designer](./agents/04_memory_cue_designer/) |
| 🖼️ image_maker | Writes the image generation prompt | [05_image_maker](./agents/05_image_maker/) |
| 🎭 image_generator | Generates the actual illustration via DALL-E | [06_image_generator](./agents/06_image_generator/) |

Each employee has a **persona & resume**, a set of **skills**, and a brief **instructions** file.

---

## Skills Library

Reusable skills that agents apply. Edit a skill to change how all agents using it behave.

| Skill | Used by |
|---|---|
| [india-news-scoring](./agents/skills/india-news-scoring.md) | news_scout |
| [family-editorial-filter](./agents/skills/family-editorial-filter.md) | family_fit_editor |
| [whatsapp-family-message](./agents/skills/whatsapp-family-message.md) | whatsapp_copywriter |
| [visual-memory-cue](./agents/skills/visual-memory-cue.md) | memory_cue_designer |
| [tintin-type-image](./agents/skills/tintin-type-image.md) | image_maker, image_generator |
| [openai-image-generation](./agents/skills/openai-image-generation.md) | image_generator |

---

## How to edit an employee

Each agent folder contains three files:

| File | What it does | Who reads it |
|---|---|---|
| `<name>_persona_and_resume.md` | Character, voice, values, backstory | You + Claude (loaded into every run) |
| `instructions.md` | The agent's specific task | Claude (loaded into every run) |
| `../skills/<skill>.md` | The methodology the agent applies | Claude (loaded into every run) |

All three are loaded and combined into Claude's system prompt on each run.
Edit any file on GitHub → takes effect on the next morning's digest.

---

## How the pipeline works

```
6:00 AM IST — GitHub Actions triggers the run
        │
        ▼
news_scout        fetches RSS headlines from Bloomberg, FT, ET, MIT TR, HBR, Reuters...
        │
family_fit_editor picks the best 1–2 stories for Manishka & Divyana
        │
        ├──▶ whatsapp_copywriter   writes the family message (≤180 words)
        │
        ├──▶ memory_cue_designer   designs the cocker spaniel visual
                │
        image_maker               writes the DALL-E prompt
                │
        image_generator           generates the actual Tintin-style image
                │
        Telegram                  message + image arrive on your phone
```

---

## Company brief

**Client:** Yash & Pooja Erande
**Audience:** Manishka (18) and Divyana (11)
**Delivery:** Telegram, every morning at 6 AM IST
**Budget:** Under $5/month
**Style:** Warm, smart, modern Indian family — never preachy, never babyish

*For a full technical overview, see [NEWSWALA_DESIGN.md](./NEWSWALA_DESIGN.md)*
*(for understanding only — does not control the system)*
