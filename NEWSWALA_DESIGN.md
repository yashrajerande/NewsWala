# NewsWala — How This Project Works

**Version:** 2.0  
**Updated:** April 2026  
**Owners:** Yash & Pooja  
**Repo:** github.com/yashrajerande/NewsWala

---

## What Is NewsWala?

NewsWala is an automated daily news digest for a family.

Every morning at **6 AM IST**, it:
1. Scans the internet for today's best news across Economics, STEM, and Current Affairs
2. Picks the most educational, age-safe story for Manishka (18) and Divyana (11)
3. Writes a short, warm WhatsApp message in the voice of both parents
4. Generates a Hergé/Tintin-style illustration featuring the family dog as a memory cue
5. Sends everything directly to Telegram — ready to copy-paste to WhatsApp in under 60 seconds

No laptop needs to be on. No manual input. It just happens.

---

## The Family

| Person | Role | Notes |
|---|---|---|
| Yash | Parent / Owner | Co-author of every message |
| Pooja | Parent | Co-author of every message |
| Manishka | Elder daughter | Turning 18 on 24 October — handles nuance and adult context |
| Divyana | Younger daughter | Turning 11 on 12 July — needs warmth, simplicity, wonder |
| Caramel | Cocker Spaniel | Always appears in the daily image as the family's memory cue |

**Sign-off on every message:** *Love, Mama & Papa*

---

## How It Runs

NewsWala is scheduled on **GitHub Actions** — a free cloud service built into GitHub.

Every morning:
```
6:00 AM IST
    │
    ▼
GitHub's cloud server wakes up
    │
    ▼
Downloads the NewsWala code
    │
    ▼
Runs the 6-agent pipeline (~3 minutes)
    │
    ▼
Sends the digest to Telegram
    │
    ▼
Server shuts down
```

Your devices don't need to be on. It runs even when you're travelling.

**Cost of running:** Free. GitHub gives 2,000 free compute minutes per month. NewsWala uses ~90 minutes per month.

**The schedule is defined in** `.github/workflows/daily_news.yml`:
```yaml
on:
  schedule:
    - cron: "30 0 * * *"   # 00:30 UTC = 6:00 AM IST
  workflow_dispatch:         # also allows manual trigger from GitHub
```

The five numbers in `cron` mean: `minute hour day month weekday`. So `30 0 * * *` means "at minute 30 of hour 0, every day." To change the time, change these numbers.

---

## The Six Agents

NewsWala works like a small newsroom. Each agent is a specialist with a fixed job. They pass their work to the next agent in sequence.

```
GitHub Actions triggers run
         │
         ▼
┌─────────────────┐
│   newswala      │  Supervisor — runs the pipeline, validates output
│   supervisor    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  01_news_scout  │  Searches the web. Returns 4-6 scored stories.
└────────┬────────┘
         │  4-6 candidate stories
         ▼
┌─────────────────┐
│  02_family_fit  │  Picks the best 1-2 stories for this family.
│  _editor        │
└────────┬────────┘
         │  1-2 selected stories
    ┌────┴────┐
    │         │
    ▼         ▼
┌───────┐  ┌──────────────────┐
│  03   │  │  04_memory_cue   │  Designs the dog image concept.
│whatsapp  │  _designer        │
│copywriter└────────┬─────────┘
│       │           │  concept
└───┬───┘           ▼
    │       ┌──────────────────┐
    │       │  05_image_maker  │  Writes the DALL-E 3 prompt.
    │       └────────┬─────────┘
    │                │  prompt text
    │                ▼
    │       ┌──────────────────┐
    │       │  06_image_       │  Generates the actual image via DALL-E 3.
    │       │  generator       │  Hergé/Tintin ligne claire style.
    │       └────────┬─────────┘
    │                │  image URL
    └────────────────┤
                     ▼
              ┌─────────────┐
              │   Telegram  │  Message + image arrive on phone.
              └─────────────┘
```

---

## The Agent Directory

Each agent has its own folder in `api/newswala/agents/`:

```
api/newswala/agents/
├── README.md                      ← Team org chart and budget tracker
├── 01_news_scout/
│   ├── README.md                  ← Agent profile: persona, skills, handoffs
│   └── system_prompt.txt          ← The exact instructions Claude receives ← EDIT THIS
├── 02_family_fit_editor/
│   ├── README.md
│   └── system_prompt.txt          ← EDIT THIS
├── 03_whatsapp_copywriter/
│   ├── README.md
│   └── system_prompt.txt          ← EDIT THIS (voice, word limit, sign-off)
├── 04_memory_cue_designer/
│   ├── README.md
│   └── system_prompt.txt          ← EDIT THIS (dog breed, scene style)
├── 05_image_maker/
│   ├── README.md
│   └── system_prompt.txt          ← EDIT THIS
└── 06_image_generator/
    ├── README.md                  ← Has 4 ready-to-swap art style examples
    └── system_prompt.txt          ← Change FIRST LINE to switch art style
```

**To change an agent's behaviour:** open its `system_prompt.txt` on GitHub, click the pencil icon (edit), make your change, commit. The next run will use your new instructions. No Python needed.

**To change the image style:** open `06_image_generator/system_prompt.txt` and replace the first line. Examples already in the file:
- `Studio Ghibli watercolour style: soft pastel tones, hand-drawn warmth.`
- `Pixar 3D animation style: rounded shapes, warm cinematic lighting.`
- `Indian miniature painting style: rich jewel tones, ornate gold borders.`

**To add a new agent:** create a new folder `07_your_agent/` with a `README.md` and `system_prompt.txt`, then add one function in `agents.py` and call it from `supervisor.py`.

---

## What Each Agent Does

### Agent 1 — news_scout
Wakes up, searches the web, and returns 4-6 fresh stories.

- Runs **3 targeted searches** — one per category (Economics, STEM, Current Affairs)
- Only accepts stories from the **last 48 hours** — nothing older
- Scores each story on 8 dimensions: credibility, novelty, inspiration, educational value, India relevance, child suitability, memorability, lesson potential
- Reads `newswala_history.json` and skips stories sent in the last 14 days
- Preferred sources: The Hindu, LiveMint, Reuters, BBC, Business Standard, ISRO, PIB

### Agent 2 — family_fit_editor
Reads every candidate story through the eyes of an 11-year-old and an 18-year-old simultaneously.

- Picks **1 story** (or at most 2 if both are exceptional and from different categories)
- Rejects anything dark, political, violent, or anxiety-inducing
- Adds a `why_selected` note explaining the choice

### Agent 3 — whatsapp_copywriter
Writes the message in the voice of Yash and Pooja.

- **Hard 180-word limit** — WhatsApp is not an essay
- Warm, smart, modern Indian family tone
- Structure: catchy opening → story in simple sentences → why it matters → one lesson → optional question → *Love, Mama & Papa*
- Also writes a 3-4 line `shorter_variant` for quick sharing

### Agent 4 — memory_cue_designer
Designs the daily image concept.

- The **cocker spaniel must appear in every image** doing something directly tied to the story
- 1-3 visual elements maximum — simple and memorable
- Space story → dog in spacesuit. Economics story → dog arranging coins. Science story → dog in lab coat.

### Agent 5 — image_maker
Translates the concept into precise DALL-E 3 instructions.

- Writes the prompt that image_generator will send to OpenAI
- Always in **Hergé/Tintin ligne claire style** (unless you've changed it in `system_prompt.txt`)
- Includes a negative prompt (what NOT to draw)

### Agent 6 — image_generator
The only agent that isn't Claude — it calls OpenAI's DALL-E 3 API.

- Prepends the style guide from its `system_prompt.txt` to the prompt
- Generates a **1024×1024 standard quality** image (~$0.04)
- Returns the image URL → Telegram sends it as a photo directly to your phone
- If `OPENAI_API_KEY` is not set, it skips gracefully and sends the text prompt instead

---

## What Arrives on Telegram Each Morning

1. **Header** — date, story titles, categories
2. **WhatsApp message** — the full text, ready to copy-paste
3. **Short variant** — 3-4 lines for quick sharing
4. **Lesson line** — the standalone memorable sentence
5. **The image** — actual Tintin-style illustration sent as a photo (or the text prompt if no OpenAI key)
6. **Quality summary** — age-appropriate ✅, length OK ✅, factual confidence ✅

---

## No Repeat News

NewsWala remembers what it has sent. After each run it saves the story titles to `newswala_history.json` at the project root. On the next run, news_scout reads this file and explicitly avoids those topics.

- History window: **14 days**
- If the file doesn't exist yet (first run), it starts fresh

---

## Cost

| Component | What it does | Model | ~Daily | ~Monthly |
|---|---|---|---|---|
| news_scout | Web search + story selection | Sonnet 4.6 | $0.030 | $0.90 |
| family_fit_editor | Pick best stories | Haiku 4.5 | $0.003 | $0.09 |
| whatsapp_copywriter | Write the message | Sonnet 4.6 | $0.010 | $0.30 |
| memory_cue_designer | Design image concept | Haiku 4.5 | $0.001 | $0.03 |
| image_maker | Write DALL-E prompt | Haiku 4.5 | $0.001 | $0.03 |
| image_generator | Generate image | DALL-E 3 | $0.040 | $1.20 |
| GitHub Actions | Cloud scheduler | — | free | free |
| **Total** | | | **~$0.085** | **~$2.55** |

Budget: **$5/month**. Current spend: **~$2.55/month** ✅

---

## Technology Stack

| Component | Technology |
|---|---|
| AI agents | Claude Sonnet 4.6 + Haiku 4.5 (Anthropic) |
| Web search | Claude's built-in `web_search` tool (server-side, no extra cost) |
| Image generation | DALL-E 3 (OpenAI) |
| Language | Python 3.11 |
| Delivery | Telegram Bot API (no extra libraries — uses Python's built-in `urllib`) |
| Scheduling | GitHub Actions (free tier — 2,000 min/month) |
| Code hosting | GitHub — github.com/yashrajerande/NewsWala |

---

## Secret Keys

Three keys are required. They live as **GitHub Secrets** (Settings → Secrets → Actions) — never in the code.

| Secret name | What it's for | Where to get it |
|---|---|---|
| `ANTHROPIC_API_KEY` | Runs all Claude agents | console.anthropic.com |
| `TELEGRAM_BOT_TOKEN` | Sends messages to your phone | @BotFather on Telegram |
| `TELEGRAM_CHAT_ID` | Identifies your chat | api.telegram.org/bot{token}/getUpdates |
| `OPENAI_API_KEY` | Generates the daily image | platform.openai.com *(optional)* |

If `OPENAI_API_KEY` is not set, the image step is skipped and the DALL-E prompt is sent as text instead.

---

## File Structure

```
NewsWala/
├── .github/
│   └── workflows/
│       └── daily_news.yml       ← GitHub Actions schedule (runs at 6 AM IST)
│
├── newswala.py                  ← Run manually: python newswala.py --telegram
├── newswala_daily.py            ← Silent runner used by GitHub Actions
├── .env.example                 ← Template for secret keys
│
├── api/
│   └── newswala/
│       ├── agents/              ← One folder per agent — edit behaviour here
│       │   ├── README.md        ← Team org chart + budget
│       │   ├── 01_news_scout/
│       │   │   ├── README.md    ← Agent profile card
│       │   │   └── system_prompt.txt  ← Agent instructions (editable)
│       │   ├── 02_family_fit_editor/
│       │   ├── 03_whatsapp_copywriter/
│       │   ├── 04_memory_cue_designer/
│       │   ├── 05_image_maker/
│       │   └── 06_image_generator/
│       │
│       ├── agents.py            ← Agent functions (loads prompts from agents/ folder)
│       ├── supervisor.py        ← Pipeline orchestrator
│       ├── config.py            ← Family names, ages, sources, constraints
│       ├── telegram_sender.py   ← Telegram delivery
│       └── run.py               ← CLI flags (--telegram, --date, --save, etc.)
│
├── newswala_history.json        ← Auto-created. Stories sent in the last 14 days.
└── NEWSWALA_DESIGN.md           ← This document
```

---

## How to Run Manually

```bash
# Full run — generates digest and sends to Telegram
python newswala.py --telegram

# Full run — saves output to a JSON file as well
python newswala.py --telegram --save

# Test a specific date
python newswala.py --date 2026-04-01 --telegram

# Check Telegram is connected (sends a test message)
python newswala.py --setup-telegram
```

---

## What Yash & Pooja Do Each Morning

1. Open **Telegram**
2. See the digest and image already waiting
3. Long-press the WhatsApp message → **Copy**
4. Open WhatsApp → paste into the family group
5. Optionally forward the image too

Total time: under 60 seconds.

---

## Future Ideas

- [ ] Birthday edition — special digest on Manishka's (24 Oct) and Divyana's (12 Jul) birthdays
- [ ] Weekly "best of the week" summary every Sunday
- [ ] Let Manishka and Divyana reply with reactions that shape future story selection
- [ ] Hindi/Hinglish mode
- [ ] Track which stories got the best engagement
- [ ] Audio version — short voice note read by an AI voice

---

*Built with Claude Sonnet 4.6 & Haiku 4.5 · Images by DALL-E 3 · Delivered via Telegram · Scheduled on GitHub Actions · Made with love by Yash & Pooja*
