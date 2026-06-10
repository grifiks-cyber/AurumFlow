"""
TEST 2 — Historical replay mode (reads real Telegram messages)
Run: python bot/replay.py

Reads the last N messages from SENALES and ANALISIS channels
and simulates what the bot would do — WITHOUT actually publishing.

Output shows:
  ✅ WOULD PUBLISH — signal matches bias
  🚫 BIAS BLOCK   — signal blocked by bias
  ⏭  NOISE        — filtered as noise/management message
  ➖ NO SIGNAL    — no tradeable signal detected
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.telegram_client import build_client
from bot.signal_parser import extract_signal, extract_levels, extract_bias, is_noise
from bot.format_signal import build_trade_message
from config.settings import SOURCE_CHANNELS

LIMIT = 50  # How many messages to replay per channel


def apply_bias_filter(signal_type: str, bias: str) -> bool:
    if bias == "BEARISH" and signal_type != "SELL":
        return False
    if bias == "BULLISH" and signal_type != "BUY":
        return False
    return True


async def replay():
    client = build_client()
    await client.start()

    # ── Step 1: Get bias from ANALISIS ────────────────────
    print("=" * 60)
    print("  AURUM FLOW — HISTORICAL REPLAY")
    print("=" * 60)
    print(f"\n📡 Reading ANALISIS channel (last {LIMIT} messages)...\n")

    current_bias = None
    analisis_id = SOURCE_CHANNELS.get("ANALISIS")

    entity = await client.get_entity(analisis_id)
    async for msg in client.iter_messages(entity, limit=LIMIT):
        if not msg.text:
            continue
        bias = extract_bias(msg.text)
        if bias and not current_bias:
            current_bias = bias
            print(f"  🎯 Latest bias found: {current_bias}")
            print(f"     → {msg.text[:80].strip()}...")
            break

    if not current_bias:
        print("  ⚠️  No bias found in ANALISIS — will show signals without filter")
    print()

    # ── Step 2: Replay SENALES ────────────────────────────
    print(f"📡 Replaying SENALES channel (last {LIMIT} messages)...")
    print(f"   Active BIAS: {current_bias}")
    print("-" * 60)

    senales_id = SOURCE_CHANNELS.get("SENALES")
    entity = await client.get_entity(senales_id)

    counts = {"publish": 0, "blocked": 0, "noise": 0, "no_signal": 0}

    messages = []
    async for msg in client.iter_messages(entity, limit=LIMIT):
        if msg.text:
            messages.append(msg)

    # Process oldest first so order makes sense
    for msg in reversed(messages):
        text = msg.text
        preview = text[:60].replace("\n", " ").strip()

        if is_noise(text):
            print(f"⏭  NOISE      | {msg.date.strftime('%d/%m %H:%M')} | {preview}...")
            counts["noise"] += 1
            continue

        signal = extract_signal(text)

        if not signal:
            print(f"➖ NO SIGNAL  | {msg.date.strftime('%d/%m %H:%M')} | {preview}...")
            counts["no_signal"] += 1
            continue

        direction = signal["type"]
        price     = signal["price"]

        if current_bias and not apply_bias_filter(direction, current_bias):
            print(f"🚫 BIAS BLOCK | {msg.date.strftime('%d/%m %H:%M')} | {direction} @ {price} — blocked by {current_bias}")
            counts["blocked"] += 1
            continue

        levels    = extract_levels(text)
        formatted = build_trade_message(signal, levels, current_bias)

        if formatted:
            print(f"✅ WOULD PUB  | {msg.date.strftime('%d/%m %H:%M')} | {direction} @ {price} | BIAS={current_bias}")
            counts["publish"] += 1

            # Uncomment below to see full formatted message:
            # print("\n" + formatted + "\n")
        else:
            print(f"⚠️ INVALID LVL| {msg.date.strftime('%d/%m %H:%M')} | {direction} @ {price} — levels failed validation")
            counts["blocked"] += 1

    # ── Summary ───────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  REPLAY SUMMARY")
    print("=" * 60)
    print(f"  ✅ Would publish : {counts['publish']}")
    print(f"  🚫 Bias blocked  : {counts['blocked']}")
    print(f"  ⏭  Noise filtered: {counts['noise']}")
    print(f"  ➖ No signal     : {counts['no_signal']}")
    print(f"  📊 Total messages: {sum(counts.values())}")
    print("=" * 60)

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(replay())
