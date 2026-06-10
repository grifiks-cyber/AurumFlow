"""
AI Rewriter — uses OpenRouter (Claude Haiku) to produce professional,
institutional-style signal messages.

Failsafe: if the API call fails for ANY reason, returns None and the
pipeline falls back to the standard formatter. System never stops.
"""
import httpx
import logging
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL     = "https://openrouter.ai/api/v1/chat/completions"
MODEL              = "anthropic/claude-3-haiku"
TIMEOUT_SECONDS    = 10

# ── Style rules injected into every prompt ────────────────────────────────────
STYLE_RULES = """
You write trading signal messages for a professional XAUUSD signal channel.

TONE RULES (follow strictly):
- Professional trader tone, short and precise
- Slight institutional feel — like a desk trader, not a retail influencer
- No hype, no guarantees, no "100% win" language
- No excessive emojis (max 3 total in the message)
- Context must feel realistic, not mechanical

LANGUAGE EXAMPLES (use this style):
- "selling pressure remains active"
- "structure still bearish"
- "price reacting near key resistance"
- "setup remains valid under current conditions"
- "market structure supports further downside"
- "bulls defending this level — caution advised"

OUTPUT FORMAT (exact structure, no deviations):
Line 1: [emoji] *[BUY/SELL] XAUUSD — Aurum Flow Signal*
Line 2: (blank)
Line 3: 📍 Entry Zone: `[zone_low] – [zone_high]`
Line 4: 🛑 Stop Loss: `[sl]`
Line 5: (blank)
Line 6: 🎯 *Take Profit Targets:*
Line 7:   • TP1: `[tp1]`
Line 8:   • TP2: `[tp2]`
Line 9: (blank)
Line 10: 📊 Market Context: _[1-2 line context — use the style above]_
Line 11: (blank)
Line 12: ⚠️ Trade with discipline and proper risk management.
Line 13: (blank)
Line 14: Broker: [VT Markets]([vt_link])

Use 🔴 for SELL, 🟢 for BUY.
The broker line must be the LAST line — one line, no bold, no emoji, no extra text.
Do NOT add extra sections, do NOT expand the broker block.
"""


def _build_prompt(
    direction: str,
    zone_low: float,
    zone_high: float,
    sl: float,
    tp1: float,
    tp2: float,
    bias: Optional[str],
    vt_link: str,
) -> str:
    bias_context = f"Current market bias: {bias}." if bias else "No confirmed bias."

    return f"""Write a professional trading signal message using the exact format specified.

Signal data:
- Direction: {direction}
- Entry Zone: {zone_low:.0f} – {zone_high:.0f}
- Stop Loss: {sl:.0f}
- TP1: {tp1:.0f}
- TP2: {tp2:.0f}
- {bias_context}
- VT Markets link: {vt_link}

Follow the tone rules and output format exactly. Write the context line(s) based on the direction and bias — keep it to 1-2 lines maximum."""


async def rewrite_signal(
    direction: str,
    zone_low: float,
    zone_high: float,
    sl: float,
    tp1: float,
    tp2: float,
    bias: Optional[str],
    vt_link: str,
) -> Optional[str]:
    """
    Call OpenRouter to produce a professional signal message.
    Returns the AI-written message string, or None on failure.
    Caller must handle None by falling back to standard formatter.
    """
    if not OPENROUTER_API_KEY:
        logger.warning("OPENROUTER_API_KEY not set — skipping AI rewrite.")
        return None

    prompt = _build_prompt(direction, zone_low, zone_high, sl, tp1, tp2, bias, vt_link)

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": STYLE_RULES},
            {"role": "user",   "content": prompt},
        ],
        "max_tokens": 300,
        "temperature": 0.4,  # Low temp = consistent, not creative
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://aurumflow.com",
        "X-Title": "Aurum Flow Signal Bot",
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as http:
            response = await http.post(OPENROUTER_URL, json=payload, headers=headers)
            response.raise_for_status()
            data    = response.json()
            message = data["choices"][0]["message"]["content"].strip()
            logger.info("AI rewrite successful.")
            return message

    except httpx.TimeoutException:
        logger.warning("OpenRouter timeout — falling back to standard formatter.")
        return None

    except httpx.HTTPStatusError as e:
        logger.warning(f"OpenRouter HTTP error {e.response.status_code} — falling back.")
        return None

    except Exception as e:
        logger.warning(f"AI rewrite failed ({e}) — falling back to standard formatter.")
        return None


# ── Analysis translator ───────────────────────────────────────────────────────

_ANALYSIS_SYSTEM = """
You are a financial content editor for a XAUUSD Telegram trading channel.

TASK: Summarize a Spanish-language XAUUSD market analysis into exactly 2 lines of English.

RULES (no exceptions):
- English only
- Exactly 2 lines — nothing more
- Be specific: state bias direction + key reason in plain words
- No hype, no emojis, no filler phrases, no asterisks
- Write as if YOU are the analyst

OUTPUT FORMAT (exactly this, no deviations):
[BEARISH/BULLISH/RANGE] — [main reason, max 10 words]
Watch: [key level or zone] | [one structural note, max 8 words]
"""


async def translate_analysis(raw_text: str) -> Optional[str]:
    """
    Translate + summarise a Spanish XAUUSD analysis into a short English
    Telegram post. Returns formatted string or None on failure.
    """
    if not OPENROUTER_API_KEY:
        logger.info("Analysis translator: no API key — skipping.")
        return None

    if not raw_text or len(raw_text) < 100:
        return None

    # Trim to first 1200 chars to stay within token budget
    excerpt = raw_text[:1200]

    prompt = (
        f"Here is today's Spanish XAUUSD market analysis:\n\n"
        f"{excerpt}\n\n"
        f"Produce the English channel post following the format exactly."
    )

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": _ANALYSIS_SYSTEM},
            {"role": "user",   "content": prompt},
        ],
        "max_tokens": 80,
        "temperature": 0.2,
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://aurumflow.com",
        "X-Title": "Aurum Flow Signal Bot",
    }

    try:
        async with httpx.AsyncClient(timeout=15) as http:
            r = await http.post(OPENROUTER_URL, json=payload, headers=headers)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"].strip()
            logger.info("Analysis translation successful.")
            return content

    except Exception as e:
        logger.warning(f"Analysis translation failed: {e}")
        return None
