import sqlite3
import os
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "aurumflow.db")


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS published_signals (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id   INTEGER NOT NULL,
                channel_id   INTEGER NOT NULL,
                signal_type  TEXT,
                price        REAL,
                published_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(message_id, channel_id)
            )
        """)
        # ── Active signals table for result tracking ──────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS active_signals (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_type  TEXT    NOT NULL,
                entry        REAL    NOT NULL,
                sl           REAL    NOT NULL,
                tp1          REAL    NOT NULL,
                tp2          REAL    NOT NULL,
                tp1_hit      INTEGER DEFAULT 0,
                tp2_hit      INTEGER DEFAULT 0,
                sl_hit       INTEGER DEFAULT 0,
                closed       INTEGER DEFAULT 0,
                published_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def is_published(message_id: int, channel_id: int) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT 1 FROM published_signals WHERE message_id=? AND channel_id=?",
            (message_id, channel_id),
        ).fetchone()
    return row is not None


def mark_published(message_id: int, channel_id: int, signal_type: str = None, price: float = None):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO published_signals (message_id, channel_id, signal_type, price) VALUES (?,?,?,?)",
                (message_id, channel_id, signal_type, price),
            )
            conn.commit()
    except Exception as e:
        logger.error(f"DB error: {e}")


# ── Active signal tracking ────────────────────────────────────────────────────

def register_active_signal(signal_type: str, entry: float,
                            sl: float, tp1: float, tp2: float) -> int:
    """Save a newly published signal. Returns its DB row id."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            """INSERT INTO active_signals (signal_type, entry, sl, tp1, tp2)
               VALUES (?, ?, ?, ?, ?)""",
            (signal_type, entry, sl, tp1, tp2),
        )
        conn.commit()
        return cur.lastrowid


def get_open_signals() -> List[dict]:
    """Return all signals not yet fully closed."""
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """SELECT id, signal_type, entry, sl, tp1, tp2, tp1_hit, tp2_hit, sl_hit
               FROM active_signals WHERE closed = 0
               ORDER BY published_at ASC"""
        ).fetchall()
    return [
        {
            "id": r[0], "type": r[1], "entry": r[2],
            "sl": r[3], "tp1": r[4], "tp2": r[5],
            "tp1_hit": bool(r[6]), "tp2_hit": bool(r[7]), "sl_hit": bool(r[8]),
        }
        for r in rows
    ]


def mark_tp1_hit(signal_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE active_signals SET tp1_hit=1 WHERE id=?", (signal_id,))
        conn.commit()


def mark_tp2_hit(signal_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE active_signals SET tp2_hit=1, closed=1 WHERE id=?", (signal_id,)
        )
        conn.commit()


def mark_sl_hit(signal_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE active_signals SET sl_hit=1, closed=1 WHERE id=?", (signal_id,)
        )
        conn.commit()


def close_all_active_signals() -> List[dict]:
    """
    Mark all open signals as manually closed.
    Returns the list of signals that were closed (for notification).
    """
    open_sigs = get_open_signals()
    if not open_sigs:
        return []
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE active_signals SET closed=1 WHERE closed=0")
        conn.commit()
    return open_sigs
