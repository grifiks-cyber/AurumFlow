"""
END-TO-END AI REWRITER TEST
Run this ONCE after adding OPENROUTER_API_KEY to .env

What it tests:
  1. API key is present and loaded
  2. OpenRouter connection works
  3. Claude Haiku responds correctly
  4. Output follows expected format
  5. Fallback works when key is missing

Run: python bot/test_ai_rewriter.py
"""
import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from bot.ai_rewriter import rewrite_signal
from config.settings import VT_MARKETS_LINK

PASS = "✅ PASS"
FAIL = "❌ FAIL"
SKIP = "⏭  SKIP"

results = []

def check(condition, description):
    status = PASS if condition else FAIL
    results.append((status, description))
    print(f"  {status}  {description}")

def skip(description):
    results.append((SKIP, description))
    print(f"  {SKIP}  {description}")


async def run_tests():
    print("=" * 60)
    print("  AURUM FLOW — AI REWRITER TEST")
    print("=" * 60)

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()

    # ── Test 1: API key check ─────────────────────────────────
    print("\n[1] API Key Check")
    has_key = bool(api_key) and api_key != "your_key_here"
    check(has_key, "OPENROUTER_API_KEY is set in .env")

    if not has_key:
        print("\n  ⚠️  No API key found.")
        print("  Add your key to .env: OPENROUTER_API_KEY=sk-or-...")
        print("  Then re-run this test.\n")
        print("  Continuing with fallback test only...\n")

    # ── Test 2: Fallback (no key) ─────────────────────────────
    print("\n[2] Fallback Test (AI disabled path)")
    original_key = os.environ.get("OPENROUTER_API_KEY", "")
    os.environ["OPENROUTER_API_KEY"] = ""  # Temporarily disable

    # Re-import to pick up the empty key
    import importlib, bot.ai_rewriter as rw
    rw.OPENROUTER_API_KEY = ""

    result = await rewrite_signal(
        direction="SELL",
        zone_low=3318.0,
        zone_high=3321.0,
        sl=3326.0,
        tp1=3308.0,
        tp2=3298.0,
        bias="BEARISH",
        vt_link=VT_MARKETS_LINK,
    )
    check(result is None, "Returns None when key is missing (fallback triggers correctly)")

    os.environ["OPENROUTER_API_KEY"] = original_key
    rw.OPENROUTER_API_KEY = original_key

    # ── Test 3: Live AI call ──────────────────────────────────
    print("\n[3] Live AI Call (OpenRouter / Claude Haiku)")
    if not has_key:
        skip("Skipped — no API key (add key and re-run to test)")
    else:
        print("  Calling OpenRouter... (may take a few seconds)")
        ai_output = await rewrite_signal(
            direction="SELL",
            zone_low=3318.0,
            zone_high=3321.0,
            sl=3326.0,
            tp1=3308.0,
            tp2=3298.0,
            bias="BEARISH",
            vt_link=VT_MARKETS_LINK,
        )

        check(ai_output is not None,          "AI returned a response (not None)")

        if ai_output:
            check("SELL" in ai_output,        "Response contains direction (SELL)")
            check("XAUUSD" in ai_output,      "Response contains pair (XAUUSD)")
            check("3318" in ai_output or "3321" in ai_output, "Response contains entry levels")
            check("3326" in ai_output,        "Response contains stop loss")
            check("VT Markets" in ai_output or "vtmarkets" in ai_output.lower(), "Response contains affiliate link")
            check(len(ai_output) > 100,       "Response has sufficient length (>100 chars)")
            check(len(ai_output) < 1500,      "Response is not too long (<1500 chars)")

            print("\n  ── AI OUTPUT PREVIEW ─────────────────────────────")
            print(ai_output)
            print("  ──────────────────────────────────────────────────")

    # ── Summary ───────────────────────────────────────────────
    print("\n" + "=" * 60)
    passed = sum(1 for s, _ in results if s == PASS)
    failed = sum(1 for s, _ in results if s == FAIL)
    skipped = sum(1 for s, _ in results if s == SKIP)
    print(f"  RESULTS: {passed} passed / {failed} failed / {skipped} skipped")
    print("=" * 60)

    if failed > 0:
        print("\n⚠️  Some tests failed. Check output above.")
        sys.exit(1)
    elif skipped > 0:
        print("\n⏭  Add OPENROUTER_API_KEY to .env and re-run to complete all tests.")
    else:
        print("\n🎉  All tests passed. AI layer is ready.")



if __name__ == "__main__":
    asyncio.run(run_tests())