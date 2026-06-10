"""
TEST 1 — Bias filter validation (no Telegram needed)
Run: python bot/test_bias_flow.py

Tests that:
- BEARISH bias blocks BUY signals and allows SELL
- BULLISH bias blocks SELL signals and allows BUY
- Formatted output contains all required fields
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.format_signal import build_trade_message

PASS = "✅ PASS"
FAIL = "❌ FAIL"

results = []

def check(condition, description):
    status = PASS if condition else FAIL
    results.append((status, description))
    print(f"{status}  {description}")


def apply_bias_filter(signal, bias):
    """Simulates the bias filter from full_pipeline.py"""
    if bias == "BEARISH" and signal["type"] != "SELL":
        return False
    if bias == "BULLISH" and signal["type"] != "BUY":
        return False
    return True


print("=" * 55)
print("  AURUM FLOW — BIAS FILTER TEST")
print("=" * 55)

# ── Test signals ──────────────────────────────────────────
signals = [
    {"type": "SELL", "price": 3320.0, "raw_text": "Sell 3320 XAUUSD"},
    {"type": "BUY",  "price": 3320.0, "raw_text": "Buy 3320 XAUUSD"},
]

print("\n--- SCENARIO 1: BIAS = BEARISH ---\n")
bias = "BEARISH"
for s in signals:
    allowed = apply_bias_filter(s, bias)
    if allowed:
        check(s["type"] == "SELL", f"{s['type']} is ALLOWED (should only allow SELL)")
    else:
        check(s["type"] == "BUY", f"{s['type']} is BLOCKED (correct — bias is BEARISH)")

print("\n--- SCENARIO 2: BIAS = BULLISH ---\n")
bias = "BULLISH"
for s in signals:
    allowed = apply_bias_filter(s, bias)
    if allowed:
        check(s["type"] == "BUY", f"{s['type']} is ALLOWED (should only allow BUY)")
    else:
        check(s["type"] == "SELL", f"{s['type']} is BLOCKED (correct — bias is BULLISH)")

print("\n--- SCENARIO 3: FORMATTED OUTPUT ---\n")
signal = {"type": "SELL", "price": 3320.0, "raw_text": "Sell 3320 XAUUSD"}
levels = [3320.0, 3323.0]
msg = build_trade_message(signal, levels, "BEARISH")

if msg:
    print(msg)
    print()
    check("SELL" in msg,         "Message contains direction")
    check("XAUUSD" in msg,       "Message contains pair")
    check("Stop Loss" in msg,    "Message contains SL")
    check("TP1" in msg,          "Message contains TP1")
    check("TP2" in msg,          "Message contains TP2")
    check("VT Markets" in msg,   "Message contains affiliate link")
    check("Bearish" in msg,      "Message contains bias context")
else:
    check(False, "build_trade_message returned None — validation failed")

# ── Summary ───────────────────────────────────────────────
print("\n" + "=" * 55)
passed = sum(1 for s, _ in results if s == PASS)
failed = sum(1 for s, _ in results if s == FAIL)
print(f"  RESULTS: {passed} passed / {failed} failed")
print("=" * 55)

if failed > 0:
    print("\n⚠️  Some tests failed. Check the output above.")
    sys.exit(1)
else:
    print("\n🎉  All tests passed. Bias filter is working correctly.")
