"""
debug_senales.py — Diagnostic: shows raw messages from SENALES channel
Run: python debug_senales.py
"""
import asyncio
import os
import re
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

API_ID   = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
CH_SIGNALS  = int(os.getenv("CH_SIGNALS", "2164511324"))
CH_ANALYSIS = int(os.getenv("CH_ANALYSIS", "2186011027"))

# ── Signal regex (same as signal_parser.py) ─────────────────────────────────
SIGNAL_PATTERNS = [
    r"\b(Buy|Sell)\s+(\d{3,5}(?:[.,]\d+)?)\s+XAUUSD\b",
    r"\b(BUY|SELL)\s+XAUUSD\s+(\d{3,5}(?:[.,]\d+)?)\b",
]
NOISE_PATTERNS = [
    r"\+\d+\s*pips?", r"cerramos?\s+rango", r"resumen\s+del\s+d[íi]a",
    r"movemos?\s+sl", r"asegurad", r"seguimos?\s+en\s+rango",
    r"ya\s+hemos?\s+llegado", r"objetivo\s+alcanzado", r"cerrad", r"break\s*even",
]
_NOISE_RE = re.compile("|".join(NOISE_PATTERNS), re.IGNORECASE)

def check_signal(text):
    if not text:
        return "EMPTY"
    clean = " ".join(text.replace("\n", " ").split())
    if _NOISE_RE.search(clean):
        return "NOISE"
    for p in SIGNAL_PATTERNS:
        m = re.search(p, clean, re.IGNORECASE)
        if m:
            return f"✅ SIGNAL DETECTED: {m.group(1).upper()} @ {m.group(2)}"
    return "❌ NO MATCH (texto no reconocido como señal)"

async def main():
    client = TelegramClient("session", API_ID, API_HASH)
    await client.start()
    print("\n" + "="*60)
    print("DIAGNÓSTICO — ÚLTIMOS MENSAJES DE SENALES")
    print("="*60)
    try:
        entity = await client.get_entity(CH_SIGNALS)
        i = 0
        async for msg in client.iter_messages(entity, limit=15):
            if not msg.text:
                continue
            i += 1
            result = check_signal(msg.text)
            print(f"\n[MSG #{i} | ID:{msg.id} | {msg.date.strftime('%d/%m %H:%M')}]")
            print(f"  TEXTO: {msg.text[:150].replace(chr(10),' ')}")
            print(f"  PARSE: {result}")
    except Exception as e:
        print(f"ERROR leyendo SENALES: {e}")

    print("\n" + "="*60)
    print("DIAGNÓSTICO — ÚLTIMOS MENSAJES DE ANALISIS")
    print("="*60)
    try:
        entity = await client.get_entity(CH_ANALYSIS)
        i = 0
        async for msg in client.iter_messages(entity, limit=10):
            if not msg.text:
                continue
            i += 1
            print(f"\n[MSG #{i} | ID:{msg.id} | {msg.date.strftime('%d/%m %H:%M')}]")
            print(f"  TEXTO: {msg.text[:200].replace(chr(10),' ')}")
    except Exception as e:
        print(f"ERROR leyendo ANALISIS: {e}")

    await client.disconnect()
    print("\n" + "="*60)
    print("FIN DEL DIAGNÓSTICO")
    print("="*60)

asyncio.run(main())
