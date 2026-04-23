"""
NewsWala — Gmail delivery module.

Sends the daily family digest as a personalised HTML email via Gmail SMTP.
Uses only the Python standard library (smtplib + email).

Setup (one-time, takes ~5 minutes):
  1. Go to myaccount.google.com → Security → 2-Step Verification → enable it
  2. Still in Security → Search "App passwords" → create one called "NewsWala"
     → Google gives you a 16-character password (e.g. abcd efgh ijkl mnop)
  3. Set environment variables:
       export GMAIL_ADDRESS=your.name@gmail.com
       export GMAIL_APP_PASSWORD=abcdefghijklmnop    ← no spaces

  In GitHub Actions, add GMAIL_ADDRESS and GMAIL_APP_PASSWORD as repository secrets.
"""

import os
import smtplib
import ssl
import urllib.request
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from .config import EMAIL_RECIPIENTS


_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 587

# Category emoji map
_CAT_ICON = {
    "Economics": "📊",
    "STEM": "🔬",
    "Current Affairs": "🌏",
}


def send_digest(
    package: dict,
    gmail_address: Optional[str] = None,
    gmail_app_password: Optional[str] = None,
) -> bool:
    """
    Send the daily digest as a personalised HTML email to every recipient
    listed in config.EMAIL_RECIPIENTS.

    Args:
        package:           Structured output dict from the newswala supervisor.
        gmail_address:     Sender Gmail address. Defaults to GMAIL_ADDRESS env var.
        gmail_app_password: Gmail App Password. Defaults to GMAIL_APP_PASSWORD env var.

    Returns:
        True if every email was sent successfully, False if any failed.
    """
    gmail_address    = gmail_address    or os.environ.get("GMAIL_ADDRESS", "")
    gmail_app_password = gmail_app_password or os.environ.get("GMAIL_APP_PASSWORD", "")

    if not gmail_address:
        raise ValueError(
            "Gmail address not set. "
            "Set GMAIL_ADDRESS env var or pass gmail_address= argument."
        )
    if not gmail_app_password:
        raise ValueError(
            "Gmail App Password not set. "
            "Set GMAIL_APP_PASSWORD env var or pass gmail_app_password= argument.\n"
            "Create one at: myaccount.google.com → Security → App passwords"
        )

    # Strip all whitespace including non-breaking spaces (\xa0) that sneak in
    # when copy-pasting Google's app password from the browser.
    gmail_address      = gmail_address.strip()
    gmail_app_password = "".join(c for c in gmail_app_password if c.isascii() and not c.isspace())

    wa       = package.get("whatsapp_output", {})
    img      = package.get("image_output", {})
    stories  = package.get("selected_stories", [])
    run_date = package.get("run_date", "")

    main_msg  = wa.get("main_message", "")
    lesson    = wa.get("lesson_line", "")
    short_ver = wa.get("shorter_variant", "")
    image_url = img.get("generated_image_url", "")
    concept   = img.get("concept", "")

    # Download image once while the DALL-E URL is still fresh.
    # Embed as bytes so it works regardless of URL expiry or email client blocking.
    image_bytes = None
    if image_url:
        try:
            with urllib.request.urlopen(image_url, timeout=20) as resp:
                image_bytes = resp.read()
            print(f"  [email] Image downloaded ({len(image_bytes) // 1024} KB) — will embed inline")
        except Exception as e:
            print(f"  [email] Could not download image ({e}) — email will send without it")

    success = True

    # Open one SMTP connection and send all emails through it
    context = ssl.create_default_context()
    try:
        with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
            smtp.login(gmail_address, gmail_app_password)

            for recipient in EMAIL_RECIPIENTS:
                try:
                    _send_one(
                        smtp=smtp,
                        sender=gmail_address,
                        recipient=recipient,
                        run_date=run_date,
                        stories=stories,
                        main_msg=main_msg,
                        lesson=lesson,
                        short_ver=short_ver,
                        image_bytes=image_bytes,
                        concept=concept,
                    )
                    print(f"  [email] ✅ Sent to {recipient['name']} <{recipient['email']}>")
                except Exception as e:
                    print(f"  [email] ❌ Failed for {recipient['name']}: {e}")
                    success = False

    except smtplib.SMTPAuthenticationError:
        raise RuntimeError(
            "Gmail authentication failed. "
            "Check GMAIL_ADDRESS and GMAIL_APP_PASSWORD. "
            "Make sure you're using an App Password, not your regular Gmail password."
        )
    except Exception as e:
        raise RuntimeError(f"SMTP connection failed: {e}") from e

    return success


def _send_one(
    smtp: smtplib.SMTP,
    sender: str,
    recipient: dict,
    run_date: str,
    stories: list,
    main_msg: str,
    lesson: str,
    short_ver: str,
    image_bytes: Optional[bytes],
    concept: str,
) -> None:
    """Build and send one personalised email with the image embedded inline."""
    name     = recipient["name"]
    nickname = recipient["nickname"]
    subject  = f"🐾 Good morning, {nickname}! — NewsWala {run_date}"

    # Use cid:newsimage when we have bytes — no external URL, no blocking.
    img_src = "cid:newsimage" if image_bytes else ""

    html = _build_html(
        nickname=nickname,
        run_date=run_date,
        stories=stories,
        main_msg=main_msg,
        lesson=lesson,
        short_ver=short_ver,
        img_src=img_src,
        concept=concept,
    )
    plain = _build_plain(
        nickname=nickname,
        run_date=run_date,
        main_msg=main_msg,
        lesson=lesson,
    )

    # MIME structure:
    #   multipart/mixed
    #     multipart/related
    #       multipart/alternative
    #         text/plain
    #         text/html          ← references cid:newsimage
    #       image/png            ← inline, Content-ID: newsimage
    outer = MIMEMultipart("mixed")
    outer["Subject"] = subject
    outer["From"]    = f"NewsWala 🐾 <{sender}>"
    outer["To"]      = f"{name} <{recipient['email']}>"

    related = MIMEMultipart("related")
    outer.attach(related)

    alt = MIMEMultipart("alternative")
    related.attach(alt)

    alt.attach(MIMEText(plain, "plain", "utf-8"))
    alt.attach(MIMEText(html,  "html",  "utf-8"))

    if image_bytes:
        img_part = MIMEImage(image_bytes)
        img_part.add_header("Content-ID", "<newsimage>")
        img_part.add_header("Content-Disposition", "inline", filename="newsimage.png")
        related.attach(img_part)

    smtp.sendmail(sender, recipient["email"], outer.as_string())


def _build_html(
    nickname: str,
    run_date: str,
    stories: list,
    main_msg: str,
    lesson: str,
    short_ver: str,
    img_src: str,
    concept: str,
) -> str:
    """Return a full HTML email as a string."""

    # Stories table rows
    story_rows = ""
    for s in stories:
        icon  = _CAT_ICON.get(s.get("category", ""), "📰")
        title = _esc_html(s.get("title", ""))
        cat   = _esc_html(s.get("category", ""))
        src   = _esc_html(s.get("source", ""))
        url   = s.get("url", "")
        morsl = _esc_html(s.get("lesson_or_moral", ""))

        link  = f'<a href="{url}" style="color:#5b8dd9;text-decoration:none;">{title}</a>' if url else title

        story_rows += f"""
        <tr>
          <td style="padding:12px 0;border-bottom:1px solid #f0ede8;">
            <span style="font-size:22px;">{icon}</span>&nbsp;
            <strong>{link}</strong><br>
            <span style="color:#999;font-size:13px;">{cat} · {src}</span><br>
            <span style="color:#666;font-size:13px;font-style:italic;">"{morsl}"</span>
          </td>
        </tr>"""

    # Image block — uses cid: reference so it's embedded, not blocked
    image_block = ""
    if img_src:
        cap = _esc_html(concept[:200]) if concept else "Today's memory image"
        image_block = f"""
        <tr><td style="padding:20px 0 0;">
          <img src="{img_src}" alt="Today's image"
               style="max-width:100%;border-radius:10px;box-shadow:0 2px 12px rgba(0,0,0,.12);">
          <p style="margin:8px 0 0;color:#888;font-size:13px;font-style:italic;">{cap}</p>
        </td></tr>"""

    # Main message — convert newlines to <br>
    msg_html = _esc_html(main_msg).replace("\n", "<br>")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NewsWala — {run_date}</title>
</head>
<body style="margin:0;padding:0;background:#faf8f5;font-family:'Helvetica Neue',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#faf8f5;padding:24px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0"
             style="max-width:600px;width:100%;background:#fff;border-radius:14px;
                    box-shadow:0 2px 16px rgba(0,0,0,.07);overflow:hidden;">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#2c3e50,#3d5a80);
                     padding:32px 36px;text-align:center;">
            <div style="font-size:36px;margin-bottom:8px;">🐾</div>
            <div style="color:#fff;font-size:24px;font-weight:700;letter-spacing:.5px;">NewsWala</div>
            <div style="color:#adc6e8;font-size:14px;margin-top:4px;">{run_date}</div>
          </td>
        </tr>

        <!-- Greeting -->
        <tr>
          <td style="padding:28px 36px 0;">
            <p style="margin:0;font-size:20px;font-weight:600;color:#2c3e50;">
              Good morning, {_esc_html(nickname)}! ☀️
            </p>
            <p style="margin:8px 0 0;color:#666;font-size:15px;">
              Here's your daily dose of interesting news from Mama & Papa.
            </p>
          </td>
        </tr>

        <!-- Stories -->
        <tr>
          <td style="padding:20px 36px 0;">
            <div style="font-size:11px;font-weight:700;letter-spacing:1.5px;
                        color:#999;text-transform:uppercase;margin-bottom:4px;">
              Today's Stories
            </div>
            <table width="100%" cellpadding="0" cellspacing="0">
              {story_rows}
            </table>
          </td>
        </tr>

        <!-- Main message -->
        <tr>
          <td style="padding:24px 36px 0;">
            <div style="font-size:11px;font-weight:700;letter-spacing:1.5px;
                        color:#999;text-transform:uppercase;margin-bottom:12px;">
              Today's Digest
            </div>
            <div style="background:#f7f5f1;border-radius:10px;padding:20px 22px;
                        color:#3a3530;font-size:15px;line-height:1.7;">
              {msg_html}
            </div>
          </td>
        </tr>

        <!-- Image -->
        <tr>
          <td style="padding:0 36px;">
            <table width="100%" cellpadding="0" cellspacing="0">
              {image_block}
            </table>
          </td>
        </tr>

        <!-- Lesson line -->
        <tr>
          <td style="padding:20px 36px 0;">
            <div style="border-left:4px solid #f0b429;background:#fffbef;
                        border-radius:0 8px 8px 0;padding:14px 18px;">
              <span style="font-size:13px;font-weight:700;color:#b7791f;
                           text-transform:uppercase;letter-spacing:1px;">
                💡 Today's Lesson
              </span><br>
              <span style="font-size:15px;color:#744210;font-style:italic;
                           line-height:1.6;margin-top:6px;display:block;">
                &ldquo;{_esc_html(lesson)}&rdquo;
              </span>
            </div>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:28px 36px 32px;text-align:center;">
            <p style="margin:0;color:#999;font-size:13px;">
              Sent with ❤️ from Mama &amp; Papa
            </p>
            <p style="margin:6px 0 0;color:#ccc;font-size:12px;">
              NewsWala · Daily family digest
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _build_plain(nickname: str, run_date: str, main_msg: str, lesson: str) -> str:
    """Plain-text fallback for email clients that don't render HTML."""
    return (
        f"Good morning, {nickname}! ☀️\n\n"
        f"NewsWala — {run_date}\n"
        f"{'─' * 40}\n\n"
        f"{main_msg}\n\n"
        f"{'─' * 40}\n"
        f"Today's lesson:\n\"{lesson}\"\n\n"
        f"Sent with love from Mama & Papa 🐾"
    )


def _esc_html(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
    )
