"""
NewsWala — Telegram delivery module.

Sends the daily family digest to a Telegram chat using the Telegram Bot API.
No external libraries needed — uses only the standard `urllib` module.

Setup (one-time, takes ~3 minutes):
  1. Open Telegram → search for @BotFather → send /newbot → follow prompts
     → copy the bot token (looks like: 7123456789:AAHdqTcvCH1vGBJ...)
  2. Start a chat with your new bot (tap the link BotFather gives you)
  3. Visit https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates in your browser
     → find "chat":{"id": XXXXXXX} → that's your CHAT_ID
  4. Set environment variables:
       export TELEGRAM_BOT_TOKEN=7123456789:AAHdqTcvCH1vGBJ...
       export TELEGRAM_CHAT_ID=123456789

  Optional: To send to a group instead, add the bot to the group,
  send any message in the group, then call getUpdates to find the group's
  negative chat ID (e.g., -1001234567890).
"""

import json
import os
import urllib.request
import urllib.error
import urllib.parse
from typing import Optional


TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


def _post(token: str, method: str, payload: dict) -> dict:
    """Make a POST request to the Telegram Bot API."""
    url = TELEGRAM_API.format(token=token, method=method)
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram API error {e.code}: {body}") from e


def send_digest(package: dict, token: Optional[str] = None, chat_id: Optional[str] = None) -> bool:
    """
    Send the full NewsWala digest to a Telegram chat.

    Args:
        package: The structured output dict from the newswala supervisor.
        token: Telegram bot token. Defaults to TELEGRAM_BOT_TOKEN env var.
        chat_id: Telegram chat ID. Defaults to TELEGRAM_CHAT_ID env var.

    Returns:
        True if all messages sent successfully, False otherwise.
    """
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")

    if not token:
        raise ValueError(
            "Telegram bot token not set. "
            "Set TELEGRAM_BOT_TOKEN environment variable or pass token= argument.\n"
            "Create a bot via @BotFather on Telegram."
        )
    if not chat_id:
        raise ValueError(
            "Telegram chat ID not set. "
            "Set TELEGRAM_CHAT_ID environment variable or pass chat_id= argument.\n"
            "Find it by visiting: https://api.telegram.org/bot<TOKEN>/getUpdates"
        )

    wa = package.get("whatsapp_output", {})
    img = package.get("image_output", {})
    stories = package.get("selected_stories", [])
    run_date = package.get("run_date", "")
    qc = package.get("quality_checks", {})

    success = True

    # ── Message 1: Header + WhatsApp message ────────────────────────────────
    story_titles = "\n".join(
        f"  {'📊' if s.get('category') == 'Economics' else '🔬' if s.get('category') == 'STEM' else '🌏'} "
        f"*{_esc(s.get('title', ''))}* \\({_esc(s.get('category', ''))}\\)"
        for s in stories
    )

    main_msg = wa.get("main_message", "")
    lesson = wa.get("lesson_line", "")

    header = (
        f"🐾 *NewsWala* \\| {_esc(run_date)}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*Today's stories:*\n{story_titles}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    try:
        _post(token, "sendMessage", {
            "chat_id": chat_id,
            "text": header,
            "parse_mode": "MarkdownV2",
        })
    except Exception as e:
        print(f"  [telegram] Header send failed: {e}")
        success = False

    # ── Message 2: The WhatsApp-ready message (copy-paste ready) ────────────
    # Send as plain text so it's easy to select and copy on mobile
    whatsapp_block = (
        f"📱 *WHATSAPP MESSAGE* \\(copy & paste\\)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{_esc(main_msg)}"
    )

    try:
        _post(token, "sendMessage", {
            "chat_id": chat_id,
            "text": whatsapp_block,
            "parse_mode": "MarkdownV2",
        })
    except Exception as e:
        # Fallback: send without markdown formatting
        try:
            _post(token, "sendMessage", {
                "chat_id": chat_id,
                "text": f"📱 WHATSAPP MESSAGE (copy & paste)\n{'─'*30}\n\n{main_msg}",
            })
        except Exception as e2:
            print(f"  [telegram] WhatsApp message send failed: {e2}")
            success = False

    # ── Message 3: Short variant ─────────────────────────────────────────────
    short = wa.get("shorter_variant", "")
    if short:
        try:
            _post(token, "sendMessage", {
                "chat_id": chat_id,
                "text": f"✂️ SHORT VERSION\n{'─'*20}\n\n{short}",
            })
        except Exception as e:
            print(f"  [telegram] Short variant send failed: {e}")

    # ── Message 4: Lesson line (memorable) ──────────────────────────────────
    if lesson:
        try:
            _post(token, "sendMessage", {
                "chat_id": chat_id,
                "text": f"💡 Today's lesson:\n\n\"{lesson}\"",
            })
        except Exception as e:
            print(f"  [telegram] Lesson line send failed: {e}")

    # ── Message 5: Image — send actual photo if generated, else send prompt ──
    image_url = img.get("generated_image_url", "")
    image_prompt = img.get("image_prompt", "")
    concept = img.get("concept", "")

    if image_url:
        # Send the actual DALL-E 3 generated image
        caption = f"🐾 {concept[:180]}" if concept else "🐾 Today's memory image"
        try:
            _post(token, "sendPhoto", {
                "chat_id": chat_id,
                "photo": image_url,
                "caption": caption,
            })
        except Exception as e:
            print(f"  [telegram] Photo send failed: {e} — falling back to text prompt")
            # Fallback: send the text prompt
            if image_prompt:
                try:
                    _post(token, "sendMessage", {
                        "chat_id": chat_id,
                        "text": f"🎨 Image prompt (Hergé/Tintin style):\n{'─'*30}\n\n{concept}\n\nPROMPT:\n{image_prompt}",
                    })
                except Exception as e2:
                    print(f"  [telegram] Image prompt fallback also failed: {e2}")
    elif image_prompt:
        # No DALL-E key — just send the text prompt
        img_msg = (
            f"🎨 Image prompt (Hergé/Tintin style)\n"
            f"Add OPENAI_API_KEY to .env to auto-generate\n"
            f"{'─'*30}\n\n"
            f"{concept}\n\n"
            f"PROMPT:\n{image_prompt}"
        )
        try:
            _post(token, "sendMessage", {
                "chat_id": chat_id,
                "text": img_msg,
            })
        except Exception as e:
            print(f"  [telegram] Image prompt send failed: {e}")

    # ── Message 6: Quality + cost summary ────────────────────────────────────
    confidence    = qc.get("factual_confidence", "medium")
    run_cost      = package.get("run_cost", 0.0)
    monthly       = package.get("monthly_spend", {})
    month_total   = monthly.get("total_usd", run_cost)
    month_runs    = monthly.get("runs", 1)
    budget        = monthly.get("budget_usd", 5.0)
    month_pct     = (month_total / budget * 100) if budget else 0

    # Cost alert thresholds (per run)
    if run_cost > 0.50:
        run_icon = "🚨 HIGH"
    elif run_cost > 0.15:
        run_icon = "⚠️  WATCH"
    else:
        run_icon = "✅"

    # Monthly budget alert
    if month_pct >= 90:
        budget_icon = "🚨"
    elif month_pct >= 60:
        budget_icon = "⚠️"
    else:
        budget_icon = "✅"

    summary = (
        f"{'─'*30}\n"
        f"{'✅' if confidence == 'high' else '⚠️'} Factual confidence: {confidence}\n"
        f"{'✅' if qc.get('age_appropriate') else '❌'} Age appropriate\n"
        f"{'✅' if qc.get('whatsapp_length_ok') else '⚠️'} WhatsApp length OK\n"
        f"{'─'*30}\n"
        f"{run_icon} This run: ${run_cost:.4f}\n"
        f"{budget_icon} This month: ${month_total:.4f} / ${budget:.2f} "
        f"({month_pct:.0f}%)  —  {month_runs} run{'s' if month_runs != 1 else ''}\n"
    )
    if run_cost > 0.15:
        summary += "⚠️  Run cost above target — check GitHub Actions log\n"
    if month_pct >= 90:
        summary += f"🚨 Monthly budget nearly exhausted!\n"

    try:
        _post(token, "sendMessage", {
            "chat_id": chat_id,
            "text": summary,
        })
    except Exception as e:
        print(f"  [telegram] Quality summary send failed: {e}")

    return success


def _esc(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    special = r"_*[]()~`>#+-=|{}.!"
    for ch in special:
        text = text.replace(ch, f"\\{ch}")
    return text


def send_setup_instructions(token: str, chat_id: str) -> None:
    """Send a test message to verify the bot is configured correctly."""
    _post(token, "sendMessage", {
        "chat_id": chat_id,
        "text": (
            "🐾 NewsWala bot is connected!\n\n"
            "You'll receive your daily family digest here each morning.\n\n"
            "Each digest includes:\n"
            "📱 A ready-to-paste WhatsApp message from Yash & Pooja\n"
            "✂️ A shorter variant for quick sharing\n"
            "💡 A memorable lesson line\n"
            "🎨 An image prompt featuring your cocker spaniel\n\n"
            "Run `python newswala.py` to get today's digest!"
        ),
    })
    print("✅ Test message sent to Telegram successfully.")
