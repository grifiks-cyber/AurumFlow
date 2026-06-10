import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional
from telethon import TelegramClient
from config.settings import SOURCE_CHANNELS, VT_MARKETS_LINK, SL_BUFFER_PIPS, TP1_PIPS, TP2_PIPS
from bot.signal_parser import extract_signal, extract_levels, extract_bias, extract_analysis_zones, extract_close_signal
from bot.format_signal import build_trade_message, build_trade_message_es, build_analysis_brief, build_analysis_brief_es
from bot.ai_rewriter import rewrite_signal, translate_analysis
from bot.publisher import publish_signal
from bot.telegram_client import get_recent_messages
from data.state import is_published, mark_published, register_active_signal, close_all_active_signals
from bot.result_tracker import run_result_tracker, get_xauusd_price
from tiktok.content_formatter import get_signal_copy
from tiktok.video_generator import generate_signal_video

# ── Entry-warning threshold (pips past zone before we flag as advanced) ───────
_ENTRY_WARNING_PIPS = int(os.getenv("ENTRY_WARNING_PIPS", "10"))

logger = logging.getLogger(__name__)

# ── AI status (logged once at startup) ───────────────────────────────────────
_AI_ENABLED = bool(os.getenv("OPENROUTER_API_KEY", "").strip())
if _AI_ENABLED:
    logger.info("AI rewriter: ENABLED (OpenRouter / Claude Haiku)")
else:
    logger.info("AI rewriter: DISABLED — no OPENROUTER_API_KEY set. Using standard formatter.")

# ── Global state ──────────────────────────────────────────────────────────────
current_bias: str = None

# ── Session-level counters (reset on restart) ─────────────────────────────────
_stats = {
    "cycles":    0,
    "detected":  0,
    "published": 0,
    "skipped_noise": 0,
    "skipped_bias":  0,
    "errors":    0,
}


def get_stats() -> dict:
    return dict(_stats)


def _log_stats():
    logger.info(
        f"📊 Session stats — "
        f"cycles: {_stats['cycles']} | "
        f"detected: {_stats['detected']} | "
        f"published: {_stats['published']} | "
        f"bias-blocked: {_stats['skipped_bias']} | "
        f"noise-skipped: {_stats['skipped_noise']} | "
        f"errors: {_stats['errors']}"
    )


def _compute_levels(signal: dict, levels: list) -> tuple:
    """
    Compute trade levels for a signal.

    SL is placed SL_BUFFER_PIPS beyond the zone edge — wide enough for
    intraday volatility without being triggered by normal noise.
    TrueTrading averages positions, so their implicit SL is much wider;
    we adapt for retail traders who need a defined risk level.

    All pip values are configurable via .env:
      SL_BUFFER_PIPS (default 25) — buffer above zone_high for SELL
      TP1_PIPS       (default 20) — pips from entry to first target
      TP2_PIPS       (default 45) — pips from entry to second target
    """
    side  = signal["type"]
    entry = signal["price"]

    if levels and len(levels) >= 2:
        zone_low  = min(levels[:2])
        zone_high = max(levels[:2])
    else:
        zone_low  = entry
        zone_high = entry + 3 if side == "SELL" else entry - 3

    sl  = zone_high + SL_BUFFER_PIPS if side == "SELL" else zone_low - SL_BUFFER_PIPS
    tp1 = entry - TP1_PIPS           if side == "SELL" else entry + TP1_PIPS
    tp2 = entry - TP2_PIPS           if side == "SELL" else entry + TP2_PIPS

    return zone_low, zone_high, sl, tp1, tp2


async def _update_bias(client: TelegramClient) -> None:
    global current_bias

    channel_id = SOURCE_CHANNELS.get("ANALISIS")
    if not channel_id:
        return

    messages = await get_recent_messages(client, channel_id, limit=30)

    for msg in messages:
        bias = extract_bias(msg.text)
        if bias:
            if bias != current_bias:
                logger.info(f"⚡ BIAS changed: {current_bias} → {bias}")
            current_bias = bias
            return

    logger.info(f"ANALISIS: no bias keyword found — keeping current bias: {current_bias}")


async def _process_close_signals(client: TelegramClient) -> bool:
    """
    Scans ANALISIS channel for manual close messages from TrueTrading.
    e.g. "Cerrad posiciones", "Salimos del rango", "Close trade"

    If detected:
      - Marks all open signals as closed in DB
      - Publishes a close update to the channel
      - Triggers CLOSE result video

    Returns True if a close was detected and handled.
    """
    channel_id = SOURCE_CHANNELS.get("ANALISIS")
    if not channel_id:
        return False

    messages = await get_recent_messages(client, channel_id, limit=10)

    for msg in messages:
        if is_published(msg.id, channel_id):
            continue

        if not extract_close_signal(msg.text):
            continue

        # Close message detected
        mark_published(msg.id, channel_id)
        logger.info(f"⚠️  CLOSE SIGNAL detected in ANALISIS | msg_id={msg.id}")

        closed_signals = close_all_active_signals()

        if not closed_signals:
            logger.info("Close signal: no open signals to close.")
            return True

        # Build close update message
        for sig in closed_signals:
            direction = sig["type"]
            entry     = sig["entry"]
            emoji     = "🔴" if direction == "SELL" else "🟢"

            close_msg = (
                f"⚠️ *Trade Closed — Manual Exit*\n\n"
                f"{emoji} {direction} XAUUSD\n"
                f"Entry Zone: `{entry:.0f}`\n\n"
                f"📉 _Position closed by source before TP/SL_\n\n"
                f"⚡ @AurumFlowXau"
            )
            await publish_signal(close_msg)
            logger.info(f"⚠️  CLOSE published | {direction} @ {entry:.0f}")

            # Generate CLOSE result video in background
            asyncio.create_task(
                _generate_result_video("CLOSE", direction, entry, sig["sl"],
                                       sig["tp1"], sig["tp2"], pips=None)
            )

        return True

    return False


async def _generate_result_video(event: str, direction: str, entry: float,
                                  sl: float, tp1: float, tp2: float,
                                  pips: Optional[int] = None):
    """
    Generate and send a result announcement video (TP1/TP2/SL/CLOSE).
    Runs as background task — never blocks pipeline.
    """
    try:
        from tiktok.result_video_generator import generate_result_video
        path = await generate_result_video(
            event=event,
            direction=direction,
            entry=entry,
            sl=sl,
            tp1=tp1,
            tp2=tp2,
            pips=pips,
        )
        if path:
            await _send_review_video(path, f"{event} {direction}")
        else:
            logger.warning(f"Result video generation failed for {event}")
    except Exception as e:
        logger.warning(f"Result video error ({event}): {e}")


async def _process_analysis_content(client: TelegramClient) -> bool:
    """
    Reads ANALISIS channel for the main daily analysis text (long message).
    Translates + summarises it to English using AI and posts to the channel.

    Detects messages that:
      - Are long (>200 chars)
      - Contain 'XAUUSD' or 'análisis'
      - Are NOT zone messages ('Posibles precios de')
      - Are NOT already published

    Returns True if an analysis post was published.
    """
    channel_id = SOURCE_CHANNELS.get("ANALISIS")
    if not channel_id:
        return False

    # Only post analysis if AI is available — no fallback for this feature
    from bot.ai_rewriter import translate_analysis as _translate
    if not _AI_ENABLED:
        return False

    messages = await get_recent_messages(client, channel_id, limit=10)

    for msg in messages:
        if is_published(msg.id, channel_id):
            continue

        text = msg.text or ""

        # Skip short messages, zone messages, and close signals
        if len(text) < 200:
            continue
        if "posibles precios de" in text.lower():
            continue
        if not any(kw in text.lower() for kw in ["xauusd", "análisis", "analisis", "tesis"]):
            continue

        # Found a main analysis message — translate it
        logger.info(f"📰 ANALYSIS CONTENT | msg_id={msg.id} | {len(text)} chars — translating...")
        translated = await _translate(text)

        if not translated:
            logger.warning("Analysis translation failed — skipping post.")
            mark_published(msg.id, channel_id)
            return False

        # Format as channel post — brief 2-line summary header
        post = (
            f"📰 *XAUUSD Daily Bias — Aurum Flow*\n\n"
            f"{translated}\n\n"
            f"⚡ @AurumFlowXau"
        )

        sent = await publish_signal(post)
        mark_published(msg.id, channel_id)

        if sent:
            logger.info(f"✅ ANALYSIS POSTED | msg_id={msg.id}")
            return True
        else:
            logger.warning("Analysis post: publish failed.")
            return False

    return False


async def _process_analysis_zones(client: TelegramClient) -> bool:
    """
    Reads ANALISIS channel for 'Posibles precios de venta / retrocesos' messages.
    Publishes a compact summary of ALL zones (SELL + BUY) from TrueTrading.
    Does NOT create a trade signal — just shows the price levels TrueTrading posted.
    Returns True if a zones post was published.
    """
    channel_id = SOURCE_CHANNELS.get("ANALISIS")
    if not channel_id:
        return False

    messages = await get_recent_messages(client, channel_id, limit=20)
    today_utc = datetime.now(timezone.utc).date()

    for msg in messages:
        if is_published(msg.id, channel_id):
            continue

        if msg.date and msg.date.date() < today_utc:
            logger.debug(f"ANALISIS zone: skipping old msg_id={msg.id} from {msg.date.date()}")
            mark_published(msg.id, channel_id)
            continue

        zones = extract_analysis_zones(msg.text)

        if not zones["SELL"] and not zones["BUY"]:
            continue

        logger.info(
            f"📐 ANALISIS ZONES | SELL:{len(zones['SELL'])} BUY:{len(zones['BUY'])} "
            f"| msg_id={msg.id} | BIAS={current_bias}"
        )

        formatted    = build_analysis_brief(zones, current_bias)
        formatted_es = build_analysis_brief_es(zones, current_bias)

        if not formatted:
            mark_published(msg.id, channel_id)
            _stats["errors"] += 1
            return False

        sent = await publish_signal(formatted, message_es=formatted_es)
        mark_published(msg.id, channel_id)

        if sent:
            _stats["published"] += 1
            _stats["detected"]  += 1
            logger.info(f"✅ ANALISIS ZONES PUBLISHED | msg_id={msg.id}")
            return True
        else:
            _stats["errors"] += 1
            logger.warning("ANALISIS zones: publish failed")
            return False

    return False


async def _check_entry_warning(signal: dict, levels: list) -> bool:
    """
    Returns True if the current XAUUSD price has already moved significantly
    past the entry zone, meaning subscribers would be chasing a late entry.

    SELL: price has already dropped more than ENTRY_WARNING_PIPS below zone_low
    BUY:  price has already risen more than ENTRY_WARNING_PIPS above zone_high
    """
    try:
        price = await get_xauusd_price()
        if price is None:
            return False

        side = signal["type"]
        zone_low, zone_high, _, _, _ = _compute_levels(signal, levels)

        if side == "SELL":
            # Price already dropped well below the sell zone
            if price < zone_low - _ENTRY_WARNING_PIPS:
                logger.info(
                    f"⚠️  ENTRY WARNING | SELL zone {zone_low:.0f}, price {price:.2f} "
                    f"({zone_low - price:.1f} pips past zone)"
                )
                return True
        else:
            # Price already rallied well above the buy zone
            if price > zone_high + _ENTRY_WARNING_PIPS:
                logger.info(
                    f"⚠️  ENTRY WARNING | BUY zone {zone_high:.0f}, price {price:.2f} "
                    f"({price - zone_high:.1f} pips past zone)"
                )
                return True
    except Exception as e:
        logger.debug(f"Entry warning check failed: {e}")

    return False


async def _format_message(signal: dict, levels: list, bias: str,
                           entry_warning: bool = False) -> str:
    """AI rewrite → fallback to standard formatter. Never raises."""
    side = signal["type"]
    zone_low, zone_high, sl, tp1, tp2 = _compute_levels(signal, levels)

    if _AI_ENABLED:
        logger.info("AI rewriter: ENABLED → attempting rewrite...")
        ai_message = await rewrite_signal(
            direction=side,
            zone_low=zone_low,
            zone_high=zone_high,
            sl=sl,
            tp1=tp1,
            tp2=tp2,
            bias=bias,
            vt_link=VT_MARKETS_LINK,
        )
        if ai_message:
            logger.info("AI rewriter: SUCCESS — using AI-rewritten message.")
            return ai_message
        else:
            logger.warning("AI rewriter: FAILED — falling back to standard formatter.")
    else:
        logger.info("AI rewriter: DISABLED → using standard formatter.")

    return build_trade_message(signal, levels, bias, entry_warning=entry_warning)


async def _send_review_video(path: str, direction: str) -> bool:
    """
    Send video to TIKTOK_REVIEW_CHAT using Bot API (python-telegram-bot).
    NO Telethon session used here — pure HTTP, no SQLite lock, safe to run
    while main.py is active.
    Accepts both @username and numeric chat_id.
    Retries once on transient failure.
    """
    from telegram import Bot
    from telegram.error import TelegramError

    review_chat = os.getenv("TIKTOK_REVIEW_CHAT", "").strip()
    bot_token   = os.getenv("BOT_TOKEN", "").strip()

    if not review_chat:
        logger.info("TikTok delivery: TIKTOK_REVIEW_CHAT not set — video saved locally only.")
        return False
    if not bot_token:
        logger.warning("TikTok delivery: BOT_TOKEN not set.")
        return False

    caption = (
        f"📱 *TikTok Ready* — {direction} XAUUSD\n"
        f"Review and post to TikTok ↓"
    )

    logger.info(f"TikTok: sending review video to {review_chat}...")

    for attempt in range(1, 3):  # 2 attempts max
        try:
            bot = Bot(token=bot_token)
            with open(path, "rb") as f:
                await bot.send_video(
                    chat_id=review_chat,
                    video=f,
                    caption=caption,
                    parse_mode="Markdown",
                    supports_streaming=True,
                )
            logger.info(f"TikTok review delivery success → {review_chat}")
            return True
        except TelegramError as e:
            logger.warning(f"TikTok delivery attempt {attempt} failed: {e}")
            if attempt < 2:
                await asyncio.sleep(3)
        except Exception as e:
            logger.warning(f"TikTok delivery failed: {e}")
            return False

    logger.error("TikTok delivery: all attempts failed — video saved locally.")
    return False


async def _generate_tiktok(client: TelegramClient, signal: dict,
                           levels: list, bias: str,
                           ai_context: str = ""):
    """
    PRODUCTION MODE — uses real signal data from the pipeline.
    Generates V2 premium video and delivers via Bot API.
    Runs as background task — never blocks main pipeline.

    Inputs (all real, from live pipeline):
      signal     : {"type": "SELL"/"BUY", "price": float, "raw_text": str}
      levels     : list of extracted price levels
      bias       : "BEARISH" / "BULLISH" / "RANGE"
      ai_context : AI-rewritten signal text (used as video context lines)
    """
    direction = signal["type"]
    entry     = signal["price"]
    zone_low, zone_high, sl, tp1, tp2 = _compute_levels(signal, levels)

    try:
        logger.info("TikTok job started")
        logger.info(
            f"TikTok payload — {direction} @ {entry:.0f} | "
            f"SL {sl:.0f} | TP {tp1:.0f} | BIAS={bias}"
        )

        # Get TikTok copy (AI or template)
        copy = await get_signal_copy(direction, entry, sl, tp1, bias)

        # Build context for video: prefer AI rewritten text, fall back to copy
        context = ai_context if ai_context else copy

        # Generate V2 video with real data
        path = await generate_signal_video(
            direction=direction,
            entry=entry,
            sl=sl,
            tp1=tp1,
            tp2=tp2,
            bias=bias,
            copy_text=copy,
            context=context,
        )

        if not path:
            logger.warning("TikTok generation failed: video render returned None")
            return

        logger.info(f"TikTok output saved: {path}")
        await _send_review_video(path, direction)

    except Exception as e:
        logger.warning(f"TikTok generation failed: {e}")


async def run_pipeline(client: TelegramClient):
    global current_bias
    _stats["cycles"] += 1

    logger.info(f"─── Cycle #{_stats['cycles']} start ───────────────────────────")

    # Step 1: Update bias
    await _update_bias(client)
    logger.info(f"Active BIAS: {current_bias}")

    # Step 2: No bias = skip
    if current_bias is None:
        logger.warning("⚠️  No market bias detected yet — skipping publish this cycle.")
        _log_stats()
        return

    # Step 2b: Check ANALISIS for manual close messages
    await _process_close_signals(client)

    # Step 2c: Post daily analysis translation (English summary for channel)
    await _process_analysis_content(client)

    # Step 2d: Check ANALISIS for zone messages (Posibles precios de venta/retrocesos)
    await _process_analysis_zones(client)

    # Step 3: Read SENALES
    channel_id = SOURCE_CHANNELS.get("SENALES")
    if not channel_id:
        logger.error("SENALES channel ID not configured.")
        return

    logger.info(f"Reading SENALES (ID: {channel_id})...")
    messages = await get_recent_messages(client, channel_id, limit=20)

    if not messages:
        logger.info("SENALES: no messages retrieved this cycle.")
        _log_stats()
        return

    signal_found = False

    for msg in messages:
        if is_published(msg.id, channel_id):
            continue

        signal = extract_signal(msg.text)
        levels = extract_levels(msg.text)

        if signal and not signal_found:
            direction = signal["type"]
            price     = signal["price"]
            _stats["detected"] += 1

            logger.info(f"🔍 SIGNAL DETECTED | {direction} @ {price} | msg_id={msg.id}")

            # Step 4: Bias context (advisory only for SENALES — never block)
            # TrueTrading publishes explicit BUY/SELL in SENALES — we always follow.
            # Bias filter only applies to ANALISIS zones where WE choose direction.
            bias_match = (
                (current_bias == "BEARISH" and direction == "SELL") or
                (current_bias == "BULLISH" and direction == "BUY") or
                current_bias == "RANGE" or
                current_bias is None
            )
            if bias_match:
                logger.info(f"✔️  BIAS MATCH | {direction} aligns with {current_bias}")
            else:
                logger.info(
                    f"⚡ BIAS COUNTER | {direction} vs {current_bias} "
                    f"— TrueTrading explicit signal, publishing anyway"
                )

            # Step 5: Entry-warning check (is price already past zone?)
            entry_warning = await _check_entry_warning(signal, levels)

            # Step 5b: Format English (AI or fallback) + Spanish
            formatted    = await _format_message(signal, levels, current_bias,
                                                  entry_warning=entry_warning)
            formatted_es = build_trade_message_es(signal, levels, current_bias,
                                                   entry_warning=entry_warning)

            if not formatted:
                logger.warning(f"⚠️  FORMAT FAILED | msg_id={msg.id} — levels invalid, skipping")
                _stats["errors"] += 1
                mark_published(msg.id, channel_id)
                continue

            # Step 6: Publish to Telegram (EN + ES)
            logger.info(f"📤 PUBLISHING | {direction} @ {price}...")
            sent = await publish_signal(formatted, message_es=formatted_es)

            if sent:
                mark_published(msg.id, channel_id, direction, price)
                signal_found = True
                _stats["published"] += 1
                logger.info(f"✅ PUBLISHED | {direction} @ {price} | BIAS={current_bias}")

                # Register in result tracker
                zone_low, zone_high, sl, tp1, tp2 = _compute_levels(signal, levels)
                register_active_signal(direction, price, sl, tp1, tp2)

                # Step 7: Generate TikTok video (async, non-blocking)
                asyncio.create_task(
                    _generate_tiktok(client, signal, levels, current_bias,
                                     ai_context=formatted or "")
                )
            else:
                _stats["errors"] += 1
                logger.warning(f"❌ PUBLISH FAILED | msg_id={msg.id}")

        else:
            # Noise or already processed
            if not signal:
                _stats["skipped_noise"] += 1
                # Log so we can see what TrueTrading is publishing that we miss
                preview = (msg.text or "")[:120].replace("\n", " ")
                logger.info(f"⏭️  NOISE/NO-MATCH | msg_id={msg.id} | \"{preview}\"")
            mark_published(msg.id, channel_id)

    if not signal_found:
        logger.info("No new signals published this cycle.")

    # Step 8: Check open signals for TP/SL hits
    await run_result_tracker()

    _log_stats()
    logger.info(f"─── Cycle #{_stats['cycles']} end ─────────────────────────────")
