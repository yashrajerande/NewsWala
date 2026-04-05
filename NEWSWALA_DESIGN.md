# NewsWala — Product Design Document

**Version:** 1.0  
**Date:** April 2026  
**Owner:** Yash & Pooja  

---

## 1. What Is NewsWala?

NewsWala is a personal AI-powered daily news digest system built for a family.

Every morning it automatically:
- Scans the internet for the best news from Economics, Science & Technology, and India Current Affairs
- Filters and rewrites the news in language suitable for children aged 11 and 18
- Composes a short, warm WhatsApp-ready message from both parents
- Creates an image prompt featuring the family's cocker spaniel as a memory cue
- Delivers everything to Telegram so it's ready to copy-paste into WhatsApp

---

## 2. Family Context

| Person | Role | Notes |
|---|---|---|
| Yash | Parent / Owner | Co-author of all messages |
| Pooja | Parent | Co-author of all messages |
| Manishka | Elder daughter | Turning 18 on 24 October — can handle nuance and complexity |
| Divyana | Younger daughter | Turning 11 on 12 July — needs warmth, clarity, simplicity |
| Caramel | Cocker Spaniel Family pet | Always appears in the daily image as a memory cue |

**Sign-off on every message:** *Love, Mama & Papa*

---

## 3. What Problem Does It Solve?

Yash and Pooja want to share interesting, educational news with their daughters every day on WhatsApp. But:

- Finding good stories takes time
- Rewriting them for children takes skill
- Doing it consistently every single day is hard
- The message needs to feel personal, not copy-pasted from a news site

NewsWala automates all of this while keeping the human, family feel.

---

## 4. System Architecture

NewsWala is a **multi-agent pipeline** — six specialised AI agents that work together like a small newsroom team.

```
                        ┌─────────────┐
                        │  newswala   │
                        │ (Supervisor)│
                        └──────┬──────┘
                               │ orchestrates
           ┌───────────────────┼───────────────────┐
           │                   │                   │
    ┌──────▼──────┐    ┌───────▼──────┐   ┌───────▼────────┐
    │ news_scout  │    │family_fit_   │   │  whatsapp_     │
    │             │    │editor        │   │  copywriter    │
    │ Searches    │    │              │   │                │
    │ the web for │───▶│ Scores &     │──▶│ Writes the     │
    │ 4-6 stories │    │ filters to   │   │ WhatsApp       │
    │             │    │ best 1-2     │   │ message        │
    └─────────────┘    └──────────────┘   └───────┬────────┘
                                                  │
                                    ┌─────────────▼──────────┐
                                    │  memory_cue_designer   │
                                    │                        │
                                    │  Designs the cocker    │
                                    │  spaniel image concept │
                                    └─────────────┬──────────┘
                                                  │
                                    ┌─────────────▼──────────┐
                                    │      image_maker       │
                                    │                        │
                                    │  Writes the final      │
                                    │  image generation      │
                                    │  prompt                │
                                    └─────────────┬──────────┘
                                                  │
                                    ┌─────────────▼──────────┐
                                    │   Telegram Delivery    │
                                    │                        │
                                    │  Sends to Yash &       │
                                    │  Pooja's phone         │
                                    └────────────────────────┘
```

---

## 5. The Six Agents

### Agent 1 — news_scout
**Role:** Searches the internet for today's best stories

- Uses Claude's live web search tool to scan the internet in real time
- Looks across Economics, STEM, and India Current Affairs
- Finds 4–6 candidate stories from credible sources
- Scores each story on: credibility, novelty, inspiration, educational value, India relevance, child suitability, memorability, and lesson potential
- Prefers sources like MIT News, MIT Outreach, India Today Education, Economic Times, Times of India, Bloomberg, Reuters, BBC, The Hindu, Mint, Nature, Financial Times

**Avoids:** Celebrity gossip, crime, graphic content, partisan politics, clickbait

---

### Agent 2 — family_fit_editor
**Role:** Picks the best stories for this specific family

- Reviews all candidate stories from news_scout
- Evaluates each one for age-appropriateness, emotional safety, educational value, and lesson potential
- Selects the best **1 story** (or at most **2** if two are exceptional)
- Rejects anything too dark, too political, or too trivial
- Adds family-specific notes explaining why each story was chosen

---

### Agent 3 — whatsapp_copywriter
**Role:** Writes the message Yash and Pooja send to their daughters

- Writes in the voice of both parents together — warm, intelligent, modern Indian family
- Keeps it short enough to read in 30 seconds
- Includes a catchy opening, the story in simple language, and a memorable lesson line
- Adds an optional thought-prompt question to spark conversation
- Signs off: *Love, Mama & Papa*
- Works for both an 11-year-old and an 18-year-old at the same time

**Style rules:** No babyish tone. No preaching. No excessive emojis. No fake facts. No motivational clichés.

---

### Agent 4 — memory_cue_designer
**Role:** Designs an image concept to help the daughters remember the story

- Always features the family's **cocker spaniel** doing something connected to the story
- Creates a charming, whimsical visual mnemonic
- Examples:
  - Space story → cocker spaniel in a mini astronaut helmet pointing at a rocket
  - Economics story → cocker spaniel arranging coins into a rising bar graph
  - Indian science breakthrough → cocker spaniel in a lab coat next to a glowing invention

---

### Agent 5 — image_maker
**Role:** Turns the image concept into a ready-to-use image generation prompt

- Writes a detailed prompt for DALL-E, Midjourney, or Stable Diffusion
- Square format (WhatsApp-friendly)
- Bright, warm, digital illustration style
- Cocker spaniel is always the visual centre

---

### Agent 6 — newswala (Supervisor)
**Role:** Orchestrates all agents and validates the final output

- Runs the full pipeline in sequence
- Handles errors and retries at each step
- Validates the output against quality checks
- Delivers the final package to Telegram

---

## 6. Daily Output

Every morning the system produces:

### WhatsApp Message
```
Hey Manishka & Divyana! 🌟

[Story in 3-4 simple sentences]

[Why it's interesting / what's cool]

[One memorable lesson line]

[Optional: a short question to think about]

Love, Mama & Papa
```

### Short Variant
A 3-4 line version for quick sharing.

### Image Prompt
A ready-to-paste prompt for DALL-E or Midjourney featuring the cocker spaniel.

### Quality Checks
Every output is automatically validated for:
- Age appropriateness
- Comes from both parents
- Contains cocker spaniel
- WhatsApp length (under 800 characters)
- Lesson line present
- Factual confidence (high / medium)

---

## 7. News Categories & Sources

| Category | Examples |
|---|---|
| Economics | RBI policy, India GDP, global markets with an educational angle, startup ecosystem |
| STEM | Space (ISRO), AI breakthroughs, medical discoveries, climate science, Indian innovation |
| Current Affairs | India on the world stage, geopolitics with context, social progress stories |

**Preferred sources:** Reuters, BBC, The Hindu, Indian Express, Mint, LiveMint, Business Standard, Financial Times, The Economist, ISRO/PIB, Nature, Science

---

## 8. Technology Stack

| Component | Technology |
|---|---|
| AI / LLM | Claude Opus 4.6 (Anthropic) |
| Web Search | Claude's built-in web_search tool |
| Language | Python 3 |
| Delivery | Telegram Bot API |
| Scheduling | PythonAnywhere scheduled tasks |
| Code hosting | GitHub (github.com/yashrajerande/NewsWala) |

---

## 9. Setup Requirements

| Credential | Where to get it |
|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com |
| `TELEGRAM_BOT_TOKEN` | @BotFather on Telegram |
| `TELEGRAM_CHAT_ID` | api.telegram.org/bot{token}/getUpdates |

These are stored in a `.env` file on PythonAnywhere (never shared publicly).

---

## 10. How to Run

```bash
# One-time test
python newswala.py --telegram

# Daily scheduled run (automated via PythonAnywhere)
python newswala_daily.py
```

---

## 11. File Structure

```
NewsWala/
├── newswala.py              ← Main runner (you run this)
├── newswala_daily.py        ← Scheduled runner (PythonAnywhere runs this)
├── .env                     ← Your secret keys (never share this)
├── .env.example             ← Template showing what keys are needed
├── api/
│   └── newswala/
│       ├── config.py        ← Family names, sources, constraints
│       ├── agents.py        ← All 5 sub-agents
│       ├── supervisor.py    ← Orchestrator + quality checker
│       ├── run.py           ← CLI entry point
│       ├── telegram_sender.py ← Telegram delivery
│       └── flask_api.py     ← Web API (optional)
└── NEWSWALA_DESIGN.md       ← This document
```

---

## 12. What Yash & Pooja Do Each Morning

1. Open **Telegram** on phone
2. See the digest waiting
3. Long-press the WhatsApp message → **Copy**
4. Open **WhatsApp** → paste into family group
5. Optionally generate the image using the prompt in DALL-E or Midjourney
6. Done — takes under 60 seconds

---

## 13. Future Ideas

- [ ] Generate the image automatically and send it directly to Telegram
- [ ] Add a weekly "best of the week" digest
- [ ] Let Manishka and Divyana reply with reactions that personalise future stories
- [ ] Add a Hindi/Hinglish mode for the message
- [ ] Track which stories got the best family engagement
- [ ] Birthday edition — special digest on Manishka's and Divyana's birthdays

---

*Built with Claude Opus 4.6 · Delivered via Telegram · Made with love by Yash & Pooja*
