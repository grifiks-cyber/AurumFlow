import os
from dotenv import load_dotenv

load_dotenv()

# === Telegram User API (Telethon) ===
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")

# === Telegram Bot (publisher) ===
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OUTPUT_CHANNEL    = os.getenv("CHANNEL_USERNAME",    "@AurumFlowXau")
OUTPUT_CHANNEL_ES = os.getenv("CHANNEL_USERNAME_ES", "")  # Spanish channel (optional)

# === Source channels (private, by numeric ID — NO negative sign) ===
SOURCE_CHANNELS = {
    "SENALES":  int(os.getenv("CH_SIGNALS",  "2164511324")),
    "ANALISIS": int(os.getenv("CH_ANALYSIS", "2186011027")),
}

# === Loop ===
LOOP_INTERVAL = int(os.getenv("LOOP_INTERVAL", "60"))

# === Affiliate link ===
VT_MARKETS_LINK = "https://www.vtmarkets.com/?r=aurumflow"

# === Session file (reuses old system session) ===
SESSION_NAME = "session"

# === Risk levels (pips) ===
# SL_BUFFER_PIPS : pips added above zone_high (SELL) or below zone_low (BUY)
# TP1_PIPS       : pips from entry to TP1
# TP2_PIPS       : pips from entry to TP2
# Defaults are set for intraday retail traders.
# TrueTrading averages positions — their SL can be 50-100 pips away.
# Keep SL_BUFFER_PIPS wide enough that normal volatility doesn't hit it.
SL_BUFFER_PIPS = int(os.getenv("SL_BUFFER_PIPS", "25"))
TP1_PIPS       = int(os.getenv("TP1_PIPS",       "20"))
TP2_PIPS       = int(os.getenv("TP2_PIPS",       "45"))
