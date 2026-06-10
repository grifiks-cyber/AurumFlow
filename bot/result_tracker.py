"""
result_tracker.py — Monitors open signals and publishes updates when
TP1, TP2, or SL is hit.

Fetches live XAUUSD price from Yahoo Finance (no API key needed).
Runs as a background task called every cycle from main pipeline.

On each event:
  - Publishes Telegram text update
  - Generates result video (TP1/TP2/SL card) and sends to review chat
"""
import asyncio
import logging
import httpx
from typing import Optional

from data.state import (
    get_open_signals, mark_tp1_hit, mark_tp2_hit, mark_sl_hit
)
from bot.publisher import publish_signal

logger = logging.getLogger(__name__)

_PRICE_CACHE: Optional[float] = None

# Multiple price sources — tried in order until one works
_PRICE_SOURCES = [
    # Yahoo Finance v8 (query2 more stable than query1)
    {
        "url": "https://query2.finance.yahoo.com/v8/finance/chart/XAUUSD=X",
        "params": {"interval": "1m", "range": "1d"},
        "parse": lambda d: float(d["chart"]["result"][0]["meta"]["regularMarketPrice"]),
    },
    # Yahoo Finance v7
    {
        "url": "https://query2.finance.yahoo.com/v7/finance/quote",
        "params": {"symbols": "XAUUSD=X"},
        "parse": lambda d: float(
            d["quoteResponse"]["result"][0]["regularMarketPrice"]
        ),
    },
    # Metals.live — free, no key
    {
        "url": "https://api.metals.live/v1/spot/gold",
        "params": {},
        "parse": lambda d: float(d[0]["price"]) if isinstance(d, list) else float(d["price"]),
    },
]


async def get_xauusd_price() -> Optional[float]:
    """Fetch current XAUUSD price. Tries multiple sources, returns cached on total failure."""
    global _PRICE_CACHE
    headers = {"User-Agent": "Mozilla/5.0"}

    for source in _PRICE_SOURCES:
        try:
            async with httpx.AsyncClient(timeout=6) as client:
                r = await client.get(source["url"], params=source["params"],
                                     headers=headers)
                r.raise_for_status()
                price = source["parse"](r.json())
                if price and 500 < price < 20000:  # sanity check for gold range
                    _PRICE_CACHE = price
                    return price
        except Exception:
            continue  # try next source silently

    # All sources failed — silent fallback to cache (no log spam)
    return _PRICE_CACHE


def _pips(signal: dict, current_price: float) -> int:
    """Return signed pip difference from entry (positive = in profit for the direction)."""
    diff = signal["entry"] - current_price
    return int(diff) if signal["type"] == "SELL" else int(-diff)


async def check_and_update(signal: dict, price: float) -> bool:
    """
    Check a single open signal against the current price.
    Publishes update and updates DB if a level is hit.
    Returns True if an update was published.
    """
    sid       = signal["id"]
    direction = signal["type"]
    entry     = signal["entry"]
    sl        = signal["sl"]
    tp1       = signal["tp1"]
    tp2       = signal["tp2"]

    pip_diff = _pips(signal, price)

    # ── TP2 (full target) ────────────────────────────────────────────────────
    if not signal["tp2_hit"]:
        tp2_reached = (price <= tp2 if direction == "SELL" else price >= tp2)
        if tp2_reached:
            mark_tp2_hit(sid)
            pips = abs(pip_diff)
            msg = (
                f"🏆 *TP2 Hit — {direction} XAUUSD*\n\n"
                f"Full target reached `+{pips} pips`\n"
                f"Entry `{entry:.0f}` → TP2 `{tp2:.0f}`\n\n"
                f"_Clean execution. That's how it's done._\n\n"
                f"⚡ @AurumFlowXau"
            )
            await publish_signal(msg)
            logger.info(f"✅ Signal #{sid} TP2 hit @ {price:.2f}")
            asyncio.create_task(_send_result_video("TP2", signal, pips))
            return True

    # ── TP1 (first target) ───────────────────────────────────────────────────
    if not signal["tp1_hit"] and not signal["tp2_hit"]:
        tp1_reached = (price <= tp1 if direction == "SELL" else price >= tp1)
        if tp1_reached:
            mark_tp1_hit(sid)
            pips = abs(pip_diff)
            msg = (
                f"✅ *TP1 Hit — {direction} XAUUSD*\n\n"
                f"First target reached `+{pips} pips`\n"
                f"Entry `{entry:.0f}` → TP1 `{tp1:.0f}`\n\n"
                f"_Consider moving SL to break-even._\n\n"
                f"⚡ @AurumFlowXau"
            )
            await publish_signal(msg)
            logger.info(f"✅ Signal #{sid} TP1 hit @ {price:.2f}")
            asyncio.create_task(_send_result_video("TP1", signal, pips))
            return True

    # ── SL ───────────────────────────────────────────────────────────────────
    if not signal["sl_hit"]:
        sl_reached = (price >= sl if direction == "SELL" else price <= sl)
        if sl_reached:
            mark_sl_hit(sid)
            pips = abs(pip_diff)
            msg = (
                f"❌ *SL Hit — {direction} XAUUSD*\n\n"
                f"Signal invalidated `−{pips} pips`\n"
                f"Entry `{entry:.0f}` → SL `{sl:.0f}`\n\n"
                f"_Risk was managed. Next setup loading._\n\n"
                f"⚡ @AurumFlowXau"
            )
            await publish_signal(msg)
            logger.info(f"❌ Signal #{sid} SL hit @ {price:.2f}")
            asyncio.create_task(_send_result_video("SL", signal, pips))
            return True

    return False


async def _send_result_video(event: str, signal: dict, pips: Optional[int]):
    """Generate result video and deliver to review chat. Background task."""
    try:
        import os
        from telegram import Bot
        from tiktok.result_video_generator import generate_result_video

        path = await generate_result_video(
            event=event,
            direction=signal["type"],
            entry=signal["entry"],
            sl=signal["sl"],
            tp1=signal["tp1"],
            tp2=signal["tp2"],
            pips=pips,
        )
        if not path:
            return

        review_chat = os.getenv("TIKTOK_REVIEW_CHAT", "").strip()
        bot_token   = os.getenv("BOT_TOKEN", "").strip()
        if not review_chat or not bot_token:
            return

        event_labels = {
            "TP1":   "✅ TP1 Hit",
            "TP2":   "🏆 Full Target Hit",
            "SL":    "❌ SL Hit",
            "CLOSE": "⚠️ Manual Exit",
        }
        caption = (
            f"📱 *{event_labels.get(event, event)}* — {signal['type']} XAUUSD\n"
            f"`+{pips} pips` → Ready for TikTok/Instagram ↓"
            if pips and event != "SL" else
            f"📱 *{event_labels.get(event, event)}* — {signal['type']} XAUUSD\n"
            f"Ready for TikTok/Instagram ↓"
        )

        bot = Bot(token=bot_token)
        with open(path, "rb") as f:
            await bot.send_video(
                chat_id=review_chat,
                video=f,
                caption=caption,
                parse_mode="Markdown",
                supports_streaming=True,
            )
        logger.info(f"Result video delivered: {event} {signal['type']}")

    except Exception as e:
        logger.warning(f"Result video delivery failed ({event}): {e}")


async def run_result_tracker():
    """
    Main entry point — called once per pipeline cycle.
    Fetches price, checks all open signals, publishes any updates.
    Silent if no open signals or market is closed.
    """
    open_signals = get_open_signals()
    if not open_signals:
        return  # nothing to track

    price = await get_xauusd_price()
    if price is None:
        logger.debug("Result tracker: no price available this cycle.")
        return

    logger.debug(f"Result tracker: XAUUSD @ {price:.2f} | open signals: {len(open_signals)}")

    for signal in open_signals:
        try:
            await check_and_update(signal, price)
        except Exception as e:
            logger.warning(f"Result tracker error for signal #{signal['id']}: {e}")
