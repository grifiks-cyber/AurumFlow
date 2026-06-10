"""
Aurum Flow — TikTok LIVE Overlay Server
Serves the overlay page and pushes real-time signal updates via WebSocket.

Run: python live/overlay_server.py
Then add in OBS: Browser Source → http://localhost:8765/overlay

The overlay auto-updates whenever the bot publishes a new signal.
"""
import asyncio
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.parent
DB_PATH    = BASE_DIR / "data" / "aurumflow.db"
STATIC_DIR = Path(__file__).parent / "static"

sys.path.insert(0, str(BASE_DIR))

app = FastAPI(title="Aurum Flow Overlay")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ── Connected WebSocket clients ───────────────────────────────────────────────
_clients: list[WebSocket] = []


# ── DB helpers ────────────────────────────────────────────────────────────────
def get_latest_signal() -> dict:
    """Read the most recent published signal from SQLite."""
    if not DB_PATH.exists():
        return {}
    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            row = conn.execute("""
                SELECT signal_type, price, published_at
                FROM published_signals
                WHERE signal_type IS NOT NULL
                ORDER BY published_at DESC
                LIMIT 1
            """).fetchone()
        if row:
            return {
                "type":  row[0],
                "price": row[1],
                "time":  row[2],
            }
    except Exception:
        pass
    return {}


def get_current_bias() -> str:
    """
    Read bias from the live pipeline module if available,
    otherwise derive it from the latest signal direction.
    """
    try:
        from bot.full_pipeline import current_bias
        if current_bias:
            return current_bias
    except Exception:
        pass
    signal = get_latest_signal()
    if signal.get("type") == "SELL":
        return "BEARISH"
    if signal.get("type") == "BUY":
        return "BULLISH"
    return "NEUTRAL"


def build_state() -> dict:
    signal = get_latest_signal()
    bias   = get_current_bias()
    return {
        "bias":        bias,
        "signal_type": signal.get("type",  "—"),
        "signal_price": signal.get("price", "—"),
        "signal_time":  signal.get("time",  "—"),
        "timestamp":    datetime.utcnow().strftime("%H:%M:%S UTC"),
    }


# ── WebSocket broadcast ───────────────────────────────────────────────────────
async def broadcast(data: dict):
    dead = []
    for ws in _clients:
        try:
            await ws.send_json(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _clients.remove(ws)


# ── Background poller — checks DB every 10s for new signals ──────────────────
_last_signal_time = None

async def _poll_db():
    global _last_signal_time
    while True:
        await asyncio.sleep(10)
        signal = get_latest_signal()
        t = signal.get("time")
        if t and t != _last_signal_time:
            _last_signal_time = t
            state = build_state()
            await broadcast(state)


@app.on_event("startup")
async def startup():
    asyncio.create_task(_poll_db())


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/overlay", response_class=HTMLResponse)
async def overlay():
    html_path = STATIC_DIR / "overlay.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/state")
async def state():
    return build_state()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _clients.append(ws)
    # Send current state immediately on connect
    await ws.send_json(build_state())
    try:
        while True:
            await ws.receive_text()  # keep alive
    except WebSocketDisconnect:
        if ws in _clients:
            _clients.remove(ws)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  Aurum Flow — Overlay Server")
    print("  OBS Browser Source URL:")
    print("  → http://localhost:8765/overlay")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8765, log_level="warning")
