"""
TikTok Content Formatter
Converts a trading signal into short, punchy TikTok copy.
Uses AI if available, falls back to templates.
"""
import os
import random
import httpx
import logging
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_URL     = "https://openrouter.ai/api/v1/chat/completions"
MODEL              = "anthropic/claude-3-haiku"

# ── Fallback templates per video type ─────────────────────────────────────────

SIGNAL_TEMPLATES = [
    ("{direction} XAUUSD\nSL {sl} | TP {tp1}\nBias: {bias}\n\nMore signals → Link in bio", ),
    ("{direction} GOLD NOW\nEntry {entry}\nStop {sl} | Target {tp1}\n\nFree signals in Telegram", ),
    ("XAUUSD {direction}\nSmart money is {bias_verb}\n\nEntry {entry} | SL {sl}\n\nLink in bio ↓", ),
]

RESULT_TEMPLATES = [
    ("TP HIT ✓\n+{pips} pips secured\n\nXAUUSD {direction}\n\nFree channel → Link in bio", ),
    ("+{pips} PIPS\nXAUUSD {direction}\nAnother clean trade\n\nSignals in bio", ),
    ("XAUUSD {direction}\n+{pips} pips\nTP reached\n\nJoin free → Link in bio", ),
]

NARRATIVE_TEMPLATES = [
    ("Retail is {retail_action}.\nWe are {our_action}.\n\nXAUUSD → {bias}\n\nLink in bio", ),
    ("Smart money was {direction_past}\nXAUUSD\n\nWere you in?\n\nFree signals → bio", ),
    ("Market structure: {bias}\nXAUUSD is telling you something\n\nFree signals in bio", ),
]

CTAS = [
    "More signals → Link in bio",
    "Free Telegram → Link in bio",
    "Join free → Link in bio",
    "XAUUSD sniper setup → bio",
    "Smart money feed → bio",
]


def _bias_verb(bias: str, direction: str) -> str:
    if bias == "BEARISH" or direction == "SELL":
        return "selling"
    return "buying"


def _retail_action(direction: str) -> str:
    return "buying" if direction == "SELL" else "selling"


def _our_action(direction: str) -> str:
    return "selling" if direction == "SELL" else "buying"


def _direction_past(direction: str) -> str:
    return "selling" if direction == "SELL" else "buying"


def _estimate_pips() -> int:
    return random.choice([70, 80, 90, 100, 110, 120])


def build_signal_copy_fallback(direction: str, entry: float, sl: float,
                                tp1: float, bias: str) -> str:
    template = random.choice(SIGNAL_TEMPLATES)[0]
    return template.format(
        direction=direction,
        entry=f"{entry:.0f}",
        sl=f"{sl:.0f}",
        tp1=f"{tp1:.0f}",
        bias=bias,
        bias_verb=_bias_verb(bias, direction),
    )


def build_result_copy_fallback(direction: str, pips: int = None) -> str:
    if not pips:
        pips = _estimate_pips()
    template = random.choice(RESULT_TEMPLATES)[0]
    return template.format(direction=direction, pips=pips)


def build_narrative_copy_fallback(direction: str, bias: str) -> str:
    template = random.choice(NARRATIVE_TEMPLATES)[0]
    return template.format(
        bias=bias,
        direction=direction,
        direction_past=_direction_past(direction),
        retail_action=_retail_action(direction),
        our_action=_our_action(direction),
    )


async def _ai_copy(prompt: str) -> Optional[str]:
    """Call OpenRouter for TikTok copy. Returns None on any failure."""
    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "your_key_here":
        return None
    try:
        async with httpx.AsyncClient(timeout=8) as http:
            resp = await http.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://aurumflow.com",
                    "X-Title": "Aurum Flow TikTok",
                },
                json={
                    "model": MODEL,
                    "messages": [
                        {"role": "system", "content": (
                            "You write ultra-short TikTok captions for a premium XAUUSD trading channel. "
                            "Rules: max 6 lines, no hashtags yet, punchy and institutional tone, "
                            "no hype or guarantees, end with exactly: 'Link in bio'"
                        )},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 120,
                    "temperature": 0.6,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning(f"TikTok AI copy failed: {e}")
        return None


async def get_signal_copy(direction: str, entry: float, sl: float,
                           tp1: float, bias: str) -> str:
    prompt = (
        f"Write a TikTok caption for this XAUUSD signal: "
        f"{direction} at {entry:.0f}, SL {sl:.0f}, TP {tp1:.0f}, bias {bias}."
    )
    ai = await _ai_copy(prompt)
    if ai:
        logger.info("TikTok copy: AI generated")
        return ai
    copy = build_signal_copy_fallback(direction, entry, sl, tp1, bias)
    logger.info("TikTok copy: template used")
    return copy


async def get_result_copy(direction: str, pips: int = None) -> str:
    pips = pips or _estimate_pips()
    prompt = f"Write a TikTok caption celebrating +{pips} pips on XAUUSD {direction} trade."
    ai = await _ai_copy(prompt)
    return ai or build_result_copy_fallback(direction, pips)


async def get_narrative_copy(direction: str, bias: str) -> str:
    prompt = (
        f"Write a mysterious/authoritative TikTok caption about smart money {_direction_past(direction)} "
        f"XAUUSD with {bias} structure."
    )
    ai = await _ai_copy(prompt)
    return ai or build_narrative_copy_fallback(direction, bias)
